"""
BuildStock Processor - shared infrastructure for downloading and processing
NLR building stock datasets (ComStock, ResStock) hosted on the OEDI data lake.

ComStockProcessor and ResStockProcessor both build on this module: the two datasets share the same S3
bucket, the same time series file layout, and the same upgrades_lookup.json convention, but differ in how
metadata is partitioned (ComStock: state+county, ResStock: state-only) and in their measure crosswalk file
format (ComStock: csv, ResStock: xlsx), so that logic lives in each product's own module.
"""

import json
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

# XML namespace used in the S3 "list bucket" (list-type=2) XML responses.
_S3_LIST_XML_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}


@dataclass(frozen=True)
class BuildStockRelease:
    """Describes where a single published release of a building stock dataset (ComStock or ResStock) lives
    on the OEDI data lake.

    NLR periodically republishes older releases under the most recent year's directory using a
    consistent, harmonized layout, so `year` below is the directory that currently hosts this release, not
    necessarily the year it was first published.
    """

    year: str
    folder: str
    label: str


@dataclass(frozen=True)
class MetadataPartition:
    """A published metadata partition for one state and, where applicable, one county."""

    state: str
    county: str | None = None


def validate_release(release: str, supported_releases: dict[str, BuildStockRelease], product: str) -> None:
    """Raise a clear ValueError if `release` isn't one of `supported_releases`."""
    if release not in supported_releases:
        supported = ", ".join(supported_releases)
        raise ValueError(f"Unsupported {product} release '{release}'. Supported releases are: {supported}.")


def scope_label(value: str | list[str]) -> str:
    """Build a filesystem-safe label describing a "county_name"-style filter, for use in cache filenames.

    Returns the "All" sentinel or a single county name as-is, or a sorted, "+"-joined list of names when
    multiple counties are requested (e.g. to query a metro area spanning several counties).
    """
    if value == "All" or isinstance(value, str):
        return value
    return "+".join(sorted(value))


def sqft_label(min_sqft: float | None, max_sqft: float | None) -> str:
    """Build a filesystem-safe label describing an optional square footage range, for use in cache
    filenames. Returns "All" if neither bound is set.
    """
    if min_sqft is None and max_sqft is None:
        return "All"
    lo = "0" if min_sqft is None else str(min_sqft)
    hi = "max" if max_sqft is None else str(max_sqft)
    return f"{lo}-{hi}sqft"


class BuildStockProcessor(ABC):
    """Abstract base class for ComStockProcessor and ResStockProcessor.

    Owns the shared metadata workflow, S3 listing/downloading, cache naming, upgrade package lookup, and
    time-series downloading. Subclasses provide dataset-specific hooks for partition discovery, partition
    paths, metadata filtering, and measure crosswalks.
    """

    # Public, unauthenticated S3 bucket hosting both datasets.
    BUCKET = "oedi-data-lake"

    # Number of concurrent workers used for network-bound work (S3 listing/downloads). This is
    # intentionally higher than the CPU count used elsewhere for CPU-bound parallelism, since these
    # tasks mostly wait on network I/O rather than compute.
    IO_WORKERS = 16

    # Number of upgrade packages downloaded concurrently in process_metadata_for_upgrades() (e.g. when
    # comparing several measures at once). Each upgrade's own partitions already fan out to IO_WORKERS
    # concurrent downloads (see _download_metadata_for_upgrade()), so this is kept modest to bound total
    # concurrent connections at UPGRADE_WORKERS * IO_WORKERS rather than growing unbounded with however
    # many upgrades are requested (e.g. "every upgrade in the release").
    UPGRADE_WORKERS = 4

    # Set by subclasses in __init__.
    product_name: str
    base_url: str
    metadata_url: str
    time_series_url: str
    state: str
    release: str
    upgrade: str
    building_type: str
    base_dir: Path
    county_name: str | list[str]
    min_sqft: float | None
    max_sqft: float | None
    _metadata_key_prefix: str

    def download_file(self, url: str, save_path: Path) -> None:
        response = requests.get(url, timeout=300)
        if response.status_code == 200:
            with open(save_path, "wb") as file:
                file.write(response.content)
            # TODO: need to create valid logger so that we don't always show these messages
            # tqdm.write(f"File downloaded successfully: {save_path}")
        else:
            tqdm.write(f"Failed to download file: {url}")

    def _list_common_prefixes(self, key_prefix: str) -> list[str]:
        """List the immediate child "folder" names directly under an S3 key prefix.

        Uses the public, unauthenticated S3 list-objects-v2 REST API against the oedi-data-lake
        bucket, e.g. to discover which state=XX or county=YYYYYYY partitions exist.
        """
        names: list[str] = []
        continuation_token = None

        while True:
            params = {"list-type": "2", "prefix": key_prefix, "delimiter": "/"}
            if continuation_token:
                params["continuation-token"] = continuation_token

            response = requests.get(f"https://{self.BUCKET}.s3.amazonaws.com/", params=params, timeout=60)
            response.raise_for_status()
            # The XML here comes from AWS S3's own list-objects-v2 API against a hardcoded, trusted
            # bucket (not user-supplied data), so the usual XXE concerns with `xml.etree` don't apply.
            root = ET.fromstring(response.content)  # noqa: S314

            for common_prefix in root.findall("s3:CommonPrefixes", _S3_LIST_XML_NS):
                prefix_el = common_prefix.find("s3:Prefix", _S3_LIST_XML_NS)
                if prefix_el is None or prefix_el.text is None:
                    continue
                names.append(prefix_el.text[len(key_prefix) :].rstrip("/"))

            is_truncated_el = root.find("s3:IsTruncated", _S3_LIST_XML_NS)
            if is_truncated_el is None or is_truncated_el.text != "true":
                break

            token_el = root.find("s3:NextContinuationToken", _S3_LIST_XML_NS)
            if token_el is None or not token_el.text:
                break
            continuation_token = token_el.text

        return names

    def available_states(self) -> list[str]:
        """Return the state abbreviations that have published metadata for this release."""
        prefixes = self._list_common_prefixes(self._metadata_key_prefix)
        return [name.split("=", 1)[1] for name in prefixes if name.startswith("state=")]

    def _apply_sqft_filter(self, meta_df: pd.DataFrame) -> pd.DataFrame:
        """Filter a metadata DataFrame by `self.min_sqft`/`self.max_sqft` (either or both may be None),
        using the `in.sqft..ft2` column shared by ComStock and ResStock metadata.
        """
        if self.min_sqft is not None:
            meta_df = meta_df[meta_df["in.sqft..ft2"] >= self.min_sqft]
        if self.max_sqft is not None:
            meta_df = meta_df[meta_df["in.sqft..ft2"] <= self.max_sqft]
        return meta_df

    @abstractmethod
    def _metadata_partitions(self) -> list[MetadataPartition]:
        """Return the published metadata partitions required for this processor's state scope."""

    @abstractmethod
    def _metadata_partition_cache_name(self, partition: MetadataPartition, upgrade: str) -> str:
        """Return the local parquet filename for one metadata partition."""

    @abstractmethod
    def _metadata_partition_url(self, partition: MetadataPartition, upgrade: str) -> str:
        """Return the public URL for one metadata partition."""

    @abstractmethod
    def _filter_metadata(self, meta_df: pd.DataFrame) -> pd.DataFrame:
        """Apply dataset-specific geography and building-type filters."""

    @abstractmethod
    def get_measure_crosswalk(self, save_dir: Path) -> pd.DataFrame:
        """Download and return the dataset-specific measure crosswalk."""

    @abstractmethod
    def _building_energy_model_key(self, bldg_id: int, upgrade: str) -> str:
        """Return the S3 key (bucket-relative path) of one building's energy model file for `upgrade`.

        Both ComStock and ResStock publish these under a `building_energy_models/upgrade=<upgrade>/`
        prefix using a `bldg{7-digit bldg_id}-up{2-digit upgrade}.<ext>` filename, but differ in whether
        `<upgrade>` is zero-padded in the *folder* name (ComStock: "upgrade=00", ResStock: "upgrade=0") and
        in the model file's extension/format (ComStock: an OpenStudio ".osm.gz"; ResStock: a ".zip" bundle
        of the OpenStudio model + its schedule files) -- so this is dataset-specific, unlike the (identical
        between both) time series file layout in `process_building_time_series()`.
        """

    @abstractmethod
    def find_upgrade_id(self, save_dir: Path, measure_id: str, target_release: str | None = None) -> str | None:
        """Resolve a stable measure ID to a dataset- and release-specific upgrade ID."""

    def _cache_release_label(self) -> str:
        """Return the release-like label to use in local cache paths."""
        return self.release

    def _selected_metadata_path(self, save_dir: Path, upgrade_label: str) -> Path:
        return (
            save_dir / f"{self._cache_release_label()}-{self.state}-{scope_label(self.county_name)}-{self.building_type}-"
            f"{sqft_label(self.min_sqft, self.max_sqft)}-{upgrade_label}-selected_metadata.parquet"
        )

    @staticmethod
    def _read_cached_metadata(path: Path) -> pd.DataFrame:
        return pd.read_parquet(path)

    def _read_cached_metadata_if_exists(self, save_dir: Path, upgrade_label: str) -> pd.DataFrame | None:
        """Read a filtered Parquet cache when present; legacy CSV caches are intentionally ignored."""
        parquet_path = self._selected_metadata_path(save_dir, upgrade_label)
        if not parquet_path.exists():
            return None
        print(f"Metadata Parquet already exists. Skipping creation. Delete {parquet_path} if you want to save again.")
        return self._read_cached_metadata(parquet_path)

    def _write_metadata_cache(self, metadata: pd.DataFrame, save_dir: Path, upgrade_label: str) -> None:
        """Write the filtered metadata Parquet cache."""
        metadata.to_parquet(self._selected_metadata_path(save_dir, upgrade_label), index=False)

    def process_metadata(self, save_dir: Path) -> pd.DataFrame:
        """Download, cache, combine, and filter metadata for the configured upgrade."""
        return self._download_metadata_for_upgrade(save_dir, self.upgrade)

    def process_metadata_for_upgrades(self, save_dir: Path, upgrades: list[str] | None = None) -> pd.DataFrame:
        """Download and combine metadata for multiple upgrade packages, in parallel across upgrades when
        there's more than one (e.g. comparing several measures at once) -- each upgrade's own partitions
        are already downloaded in parallel too (see `_download_metadata_for_upgrade()`), so a multi-upgrade
        request no longer downloads one upgrade fully before starting the next.
        """
        all_upgrades = list(self.list_upgrades(save_dir))
        selected_upgrades = all_upgrades if upgrades is None else upgrades
        combo_label = "all" if set(selected_upgrades) == set(all_upgrades) else "-".join(sorted(selected_upgrades))
        upgrade_label = f"upgrades_{combo_label}"
        cached = self._read_cached_metadata_if_exists(save_dir, upgrade_label)
        if cached is not None:
            return cached

        if len(selected_upgrades) > 1:
            # `position` staggers each upgrade's own progress bar onto its own terminal line -- without it,
            # concurrent tqdm bars overwrite the same line and garble each other's output.
            with ThreadPoolExecutor(max_workers=min(len(selected_upgrades), self.UPGRADE_WORKERS)) as executor:
                frames = list(
                    executor.map(
                        lambda pair: self._download_metadata_for_upgrade(save_dir, pair[1], progress_position=pair[0]),
                        enumerate(selected_upgrades),
                    )
                )
        else:
            frames = [self._download_metadata_for_upgrade(save_dir, upgrade) for upgrade in selected_upgrades]

        combined_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        self._write_metadata_cache(combined_df, save_dir, upgrade_label)
        return combined_df

    def _download_metadata_for_upgrade(self, save_dir: Path, upgrade: str, progress_position: int | None = None) -> pd.DataFrame:
        """Download and filter all required metadata partitions for one upgrade.

        `progress_position` pins this upgrade's tqdm progress bar to a fixed terminal line (see `tqdm`'s
        `position` argument) -- passed by `process_metadata_for_upgrades()` when downloading several
        upgrades concurrently, so their progress bars stack cleanly instead of overwriting one another.
        """
        cached = self._read_cached_metadata_if_exists(save_dir, upgrade)
        if cached is not None:
            return cached

        partitions = self._metadata_partitions()
        raw_dir = save_dir / "raw_metadata" / self._cache_release_label()
        raw_dir.mkdir(parents=True, exist_ok=True)

        def download_partition(partition: MetadataPartition) -> Path | None:
            save_path = raw_dir / self._metadata_partition_cache_name(partition, upgrade)
            if not save_path.exists():
                partition_url = self._metadata_partition_url(partition, upgrade)
                try:
                    self.download_file(partition_url, save_path)
                except requests.RequestException:
                    tqdm.write(f"Failed to download metadata partition: {partition_url}")
                    return None
            return save_path if save_path.exists() else None

        with ThreadPoolExecutor(max_workers=self.IO_WORKERS) as executor:
            downloaded = list(
                tqdm(
                    executor.map(download_partition, partitions),
                    total=len(partitions),
                    desc=f"Downloading {self.product_name} metadata partitions (upgrade {upgrade})",
                    position=progress_position,
                    leave=True,
                )
            )

        partition_files = [path for path in downloaded if path is not None]
        if not partition_files:
            meta_df = pd.DataFrame()
        else:
            meta_df = pd.concat((pd.read_parquet(path) for path in partition_files), ignore_index=True)
            meta_df = self._filter_metadata(meta_df)
            meta_df = self._apply_sqft_filter(meta_df).reset_index(drop=True)

        self._write_metadata_cache(meta_df, save_dir, upgrade)
        return meta_df

    def list_upgrades(self, save_dir: Path) -> dict[str, str]:
        """Download (if needed) and return the upgrade package lookup for this release.

        Each release publishes an `upgrades_lookup.json` mapping upgrade id -> a human-readable measure
        package name (e.g. "0" -> "Baseline"). Which upgrade ids exist, and what they mean, differs release
        to release -- see `get_measure_crosswalk()` for a stable way to find the "same" measure package
        across releases.

        Args:
            save_dir (Path): path to save the upgrade lookup file

        Returns:
            dict[str, str]: upgrade id -> measure package name, for this release.
        """
        save_path = save_dir / f"{self._cache_release_label()}-upgrades_lookup.json"
        if not save_path.exists():
            self.download_file(f"{self.base_url}upgrades_lookup.json", save_path)

        with open(save_path) as file:
            upgrades: dict[str, str] = json.load(file)
        return upgrades

    def process_building_time_series(self, data_frame: pd.DataFrame, save_dir: Path) -> tuple[list[Path], list[str]]:
        """Pull the latest time series data from the BuildStock data files online using parallel execution.

        This layout (by_state/upgrade={upgrade}/state={state}/{bldg_id}-{upgrade}.parquet) is identical
        between ComStock and ResStock, so this method is shared by both.
        """
        print(f"Number of workers: {self.IO_WORKERS}")

        def download_task(row: pd.Series) -> tuple[Path, str]:
            building_id = str(row["bldg_id"])

            # Check if file already exists
            save_path = save_dir / f"bldg_id-{building_id}-upgrade-{self.upgrade}.parquet"
            if save_path.exists():
                return save_path, building_id

            building_time_series_file = (
                f"{self.time_series_url}/by_state/upgrade={self.upgrade}/state={row['in.state']}/{building_id}-{self.upgrade}.parquet"
            )
            self.download_file(building_time_series_file, save_path)
            return save_path, building_id

        data_rows = [row for _, row in data_frame.iterrows()]
        with ThreadPoolExecutor(max_workers=self.IO_WORKERS) as executor:
            results = list(tqdm(executor.map(download_task, data_rows), total=len(data_rows)))

        # break out the paths and building_ids
        paths, building_ids = zip(*results) if results else ([], [])
        return list(paths), list(building_ids)

    def building_energy_model_url(self, bldg_id: int, upgrade: str | None = None) -> str:
        """Return the public URL for one building's energy model file (an OpenStudio ".osm.gz" for
        ComStock, or a ".zip" bundle of the OpenStudio model + its schedule files for ResStock) at
        `upgrade` (defaults to `self.upgrade`, the processor's configured upgrade).
        """
        resolved_upgrade = self.upgrade if upgrade is None else upgrade
        return f"{self.base_url}{self._building_energy_model_key(bldg_id, resolved_upgrade)}"

    def building_energy_model_filename(self, bldg_id: int, upgrade: str | None = None) -> str:
        """Return the local filename `download_building_energy_model()` would save this building's model
        under (e.g. "comstock-bldg0000123-up00.osm.gz") -- exposed publicly so callers can determine the
        filename a model download will use without downloading it first (e.g. to list what a batch
        download will produce, or to name a file inside a `.zip` bundle of several components' models).
        """
        resolved_upgrade = self.upgrade if upgrade is None else upgrade
        key = self._building_energy_model_key(bldg_id, resolved_upgrade)
        return f"{self.product_name.lower()}-{key.rsplit('/', 1)[-1]}"

    def download_building_energy_model(self, bldg_id: int, save_dir: Path, upgrade: str | None = None) -> Path:
        """Download one building's energy model file to `save_dir`, skipping the download if it's already
        cached there. Returns the local path.

        Args:
            bldg_id: the sampled building/dwelling-unit's `bldg_id` (from metadata).
            save_dir: directory to save the downloaded model file in.
            upgrade: which upgrade's model to download (defaults to `self.upgrade`, the processor's
                configured upgrade) -- each upgrade has its own model file, since applying a measure can
                change the building's geometry/systems, not just its simulated results.
        """
        resolved_upgrade = self.upgrade if upgrade is None else upgrade
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / self.building_energy_model_filename(bldg_id, resolved_upgrade)
        if not save_path.exists():
            self.download_file(self.building_energy_model_url(bldg_id, resolved_upgrade), save_path)
        return save_path

    def download_building_energy_models(self, bldg_ids: list[int], save_dir: Path, upgrade: str | None = None) -> list[Path]:
        """Download several buildings' energy model files concurrently -- e.g. one per composite
        component. Returns the local paths in the same order as `bldg_ids`.
        """
        if len(bldg_ids) <= 1:
            return [self.download_building_energy_model(bldg_id, save_dir, upgrade) for bldg_id in bldg_ids]
        with ThreadPoolExecutor(max_workers=min(len(bldg_ids), self.IO_WORKERS)) as executor:
            return list(executor.map(lambda bldg_id: self.download_building_energy_model(bldg_id, save_dir, upgrade), bldg_ids))
