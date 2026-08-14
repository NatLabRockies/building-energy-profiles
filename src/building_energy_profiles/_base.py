"""
Building Energy Profiles - shared infrastructure for downloading and processing
NLR building stock datasets (ComStock, ResStock) hosted on the OEDI data lake.

ComStockProcessor and ResStockProcessor both build on this module: the two datasets share the same S3
bucket, the same time series file layout, and the same upgrades_lookup.json convention, but differ in how
metadata is partitioned (ComStock: state+county, ResStock: state-only) and in their measure crosswalk file
format (ComStock: csv, ResStock: xlsx), so that logic lives in each product's own module.

Metadata is published on S3 as a Hive-partitioned Parquet dataset (`state=XX/county=YYYY/...`), so partition
discovery and reads here go through PyArrow's `pyarrow.fs`/`pyarrow.dataset` (anonymous S3 access, no
credentials needed for this public bucket) instead of hand-rolled S3 XML listing + plain HTTP downloads.
This gets us PyArrow's own retrying/multi-threaded S3 reader, and lets square-footage filtering be pushed
down to the Parquet reader (skipping row groups outside the requested range) rather than always
materializing every row into pandas before filtering.
"""

import json
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds
import pyarrow.fs as pafs
import pyarrow.parquet as pq
import requests
from tqdm import tqdm

# Region hosting the public, unauthenticated oedi-data-lake bucket. Passing this explicitly avoids an
# extra HEAD request PyArrow would otherwise make to auto-detect it.
_S3_REGION = "us-west-2"


@lru_cache(maxsize=1)
def _s3_filesystem() -> pafs.S3FileSystem:
    """A shared, anonymous PyArrow S3 filesystem for the public oedi-data-lake bucket.

    Cached so repeated calls (partition listing, partition reads) reuse one client/connection pool
    instead of constructing a new one each time.
    """
    return pafs.S3FileSystem(anonymous=True, region=_S3_REGION)


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

    # Set by subclasses as a class attribute: the building energy model file extension published under
    # `building_energy_models/` -- a gzipped OpenStudio model (".osm.gz") for ComStock, or a zip archive
    # bundling the OSM with its supporting files (".zip") for ResStock.
    model_file_extension: str

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

        Uses PyArrow's S3 filesystem (anonymous access) against the public oedi-data-lake bucket to walk
        its Hive-style partition layout, e.g. to discover which state=XX or county=YYYYYYY partitions
        exist, without downloading any of the partition files themselves.
        """
        selector = pafs.FileSelector(f"{self.BUCKET}/{key_prefix}", recursive=False, allow_not_found=True)
        infos = _s3_filesystem().get_file_info(selector)
        return [info.path.rsplit("/", 1)[-1] for info in infos if info.type == pafs.FileType.Directory]

    def _s3_path_from_url(self, url: str) -> str:
        """Convert one of this processor's `https://{bucket}.s3.amazonaws.com/...` URLs into the bucket/key
        path PyArrow's S3 filesystem expects.
        """
        https_prefix = f"https://{self.BUCKET}.s3.amazonaws.com/"
        if not url.startswith(https_prefix):
            raise ValueError(f"Expected a {self.BUCKET!r} S3 URL, got: {url}")
        return f"{self.BUCKET}/{url[len(https_prefix) :]}"

    def _sqft_filter_expression(self) -> ds.Expression | None:
        """Build a PyArrow dataset filter expression for `self.min_sqft`/`self.max_sqft` (either or both
        may be None), to be pushed down into the Parquet reader rather than applied after the fact in
        pandas. Returns None if neither bound is set (i.e. no filtering).
        """
        expression: ds.Expression | None = None
        if self.min_sqft is not None:
            expression = ds.field("in.sqft..ft2") >= self.min_sqft
        if self.max_sqft is not None:
            upper_bound = ds.field("in.sqft..ft2") <= self.max_sqft
            expression = upper_bound if expression is None else expression & upper_bound
        return expression

    def available_states(self) -> list[str]:
        """Return the state abbreviations that have published metadata for this release."""
        prefixes = self._list_common_prefixes(self._metadata_key_prefix)
        return [name.split("=", 1)[1] for name in prefixes if name.startswith("state=")]

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
    def find_upgrade_id(self, save_dir: Path, measure_id: str, target_release: str | None = None) -> str | None:
        """Resolve a stable measure ID to a dataset- and release-specific upgrade ID."""

    @abstractmethod
    def _model_upgrade_folder(self, upgrade: str) -> str:
        """Return the `building_energy_models/upgrade=...` folder name published for `upgrade`.

        ComStock zero-pads this to two digits (e.g. "00"); ResStock does not (e.g. "0"). Either way, the
        *filename* inside that folder always uses a two-digit, zero-padded upgrade id -- see
        `model_file_name()`.
        """

    def _cache_release_label(self) -> str:
        """Return the release-like label to use in local cache paths."""
        return self.release

    def _selected_metadata_path(self, save_dir: Path, upgrade_label: str) -> Path:
        return (
            save_dir / f"{self._cache_release_label()}-{self.state}-{scope_label(self.county_name)}-{self.building_type}-"
            f"{sqft_label(self.min_sqft, self.max_sqft)}-{upgrade_label}-selected_metadata.csv"
        )

    @staticmethod
    def _read_cached_metadata(path: Path) -> pd.DataFrame:
        try:
            return pd.read_csv(path)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()

    def process_metadata(self, save_dir: Path) -> pd.DataFrame:
        """Download, cache, combine, and filter metadata for the configured upgrade."""
        return self._download_metadata_for_upgrade(save_dir, self.upgrade)

    def process_metadata_for_upgrades(self, save_dir: Path, upgrades: list[str] | None = None) -> pd.DataFrame:
        """Download and combine metadata for multiple upgrade packages."""
        all_upgrades = list(self.list_upgrades(save_dir))
        selected_upgrades = all_upgrades if upgrades is None else upgrades
        combo_label = "all" if set(selected_upgrades) == set(all_upgrades) else "-".join(sorted(selected_upgrades))
        output_csv = self._selected_metadata_path(save_dir, f"upgrades_{combo_label}")

        if output_csv.exists():
            print(f"Metadata csv already exists. Skipping creation. Delete {output_csv} if you want to save again.")
            return self._read_cached_metadata(output_csv)

        frames = [self._download_metadata_for_upgrade(save_dir, upgrade) for upgrade in selected_upgrades]
        combined_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        combined_df.to_csv(output_csv, index=False)
        return combined_df

    def _download_metadata_for_upgrade(self, save_dir: Path, upgrade: str) -> pd.DataFrame:
        """Download and filter all required metadata partitions for one upgrade."""
        output_csv = self._selected_metadata_path(save_dir, upgrade)
        if output_csv.exists():
            print(f"Metadata csv already exists. Skipping creation. Delete {output_csv} if you want to save again.")
            return self._read_cached_metadata(output_csv)

        partitions = self._metadata_partitions()
        raw_dir = save_dir / "raw_metadata" / self._cache_release_label()
        raw_dir.mkdir(parents=True, exist_ok=True)

        filesystem = _s3_filesystem()

        def download_partition(partition: MetadataPartition) -> Path | None:
            save_path = raw_dir / self._metadata_partition_cache_name(partition, upgrade)
            if not save_path.exists():
                s3_path = self._s3_path_from_url(self._metadata_partition_url(partition, upgrade))
                try:
                    # Read directly via PyArrow's S3 filesystem (parallel range reads, automatic
                    # retries) rather than a single-shot `requests.get`, then write the resulting table
                    # back out as our local partition cache file.
                    table = pq.read_table(s3_path, filesystem=filesystem)
                    pq.write_table(table, save_path)
                except OSError:
                    tqdm.write(f"Failed to download metadata partition: {s3_path}")
                    return None
            return save_path if save_path.exists() else None

        with ThreadPoolExecutor(max_workers=self.IO_WORKERS) as executor:
            downloaded = list(
                tqdm(
                    executor.map(download_partition, partitions),
                    total=len(partitions),
                    desc=f"Downloading {self.product_name} metadata partitions (upgrade {upgrade})",
                )
            )

        partition_files = [path for path in downloaded if path is not None]
        if not partition_files:
            meta_df = pd.DataFrame()
        else:
            # Read all cached partition files as a single Parquet dataset (instead of looping
            # pd.read_parquet + pd.concat) so the square-footage filter can be pushed down into the
            # Parquet reader -- skipping whole row groups outside the requested range where Parquet's own
            # statistics allow it -- rather than always materializing every row into pandas first.
            dataset = ds.dataset([str(path) for path in partition_files], format="parquet")
            meta_df = dataset.to_table(filter=self._sqft_filter_expression()).to_pandas()
            meta_df = self._filter_metadata(meta_df).reset_index(drop=True)

        meta_df.to_csv(output_csv, index=False)
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

    @staticmethod
    def _model_upgrade_label(upgrade: str) -> str:
        """The two-digit, zero-padded upgrade id used in every building energy model *filename*,
        regardless of how the containing `upgrade=...` folder itself is named (see
        `_model_upgrade_folder()`).
        """
        return f"{int(upgrade):02d}"

    def model_file_name(self, building_id: int | str, upgrade: str) -> str:
        """Return the published building energy model filename for one building/upgrade, e.g.
        "bldg0000001-up00.osm.gz" (ComStock) or "bldg0000001-up00.zip" (ResStock).
        """
        return f"bldg{int(building_id):07d}-up{self._model_upgrade_label(upgrade)}{self.model_file_extension}"

    def model_file_url(self, building_id: int | str, upgrade: str) -> str:
        """Return the public URL for one building's energy model file."""
        return f"{self.base_url}building_energy_models/upgrade={self._model_upgrade_folder(upgrade)}/{self.model_file_name(building_id, upgrade)}"

    def download_building_model(self, building_id: int | str, save_dir: Path, upgrade: str | None = None) -> Path:
        """Download (if needed) one building's energy model file.

        This is a gzipped OpenStudio ".osm.gz" model for ComStock, or a ".zip" archive (bundling the OSM
        with its supporting files, e.g. schedules) for ResStock -- see `model_file_extension`. Like
        `process_building_time_series()`, downloaded files are cached locally and reused on subsequent
        calls.

        Args:
            building_id: the `bldg_id` from this processor's metadata.
            save_dir (Path): directory to save the downloaded model file. Created if it doesn't exist.
            upgrade (str | None): which upgrade's model to download. Defaults to `self.upgrade`.

        Returns:
            Path: where the model file was (or already had been) saved.
        """
        save_dir.mkdir(parents=True, exist_ok=True)
        upgrade = self.upgrade if upgrade is None else upgrade
        save_path = save_dir / self.model_file_name(building_id, upgrade)
        if not save_path.exists():
            self.download_file(self.model_file_url(building_id, upgrade), save_path)
        return save_path

    def download_building_models(self, data_frame: pd.DataFrame, save_dir: Path) -> tuple[list[Path], list[str]]:
        """Download this processor's building energy model file for every building in `data_frame`
        (typically a `process_metadata()`/`process_building_time_series()` sample), in parallel.

        Mirrors `process_building_time_series()`'s shape and caching behavior, but for the ComStock
        ".osm.gz" / ResStock ".zip" building energy model files instead of time series data.

        Args:
            data_frame (pd.DataFrame): rows with at least a `bldg_id` column, e.g. from `process_metadata()`.
            save_dir (Path): directory to save the downloaded model files. Created if it doesn't exist.

        Returns:
            tuple[list[Path], list[str]]: the saved file paths and their corresponding building ids, in
                the same order as `data_frame`.
        """
        save_dir.mkdir(parents=True, exist_ok=True)

        def download_task(row: pd.Series) -> tuple[Path, str]:
            building_id = str(row["bldg_id"])
            return self.download_building_model(building_id, save_dir), building_id

        data_rows = [row for _, row in data_frame.iterrows()]
        with ThreadPoolExecutor(max_workers=self.IO_WORKERS) as executor:
            results = list(
                tqdm(
                    executor.map(download_task, data_rows),
                    total=len(data_rows),
                    desc=f"Downloading {self.product_name} building energy models",
                )
            )

        paths, building_ids = zip(*results) if results else ([], [])
        return list(paths), list(building_ids)
