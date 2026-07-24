"""
Building Stock Processor - shared infrastructure for downloading and processing
NREL building stock datasets (ComStock, ResStock) hosted on the OEDI data lake.

ComStockProcessor and ResStockProcessor both build on this module: the two datasets share the same S3
bucket, the same time series file layout, and the same upgrades_lookup.json convention, but differ in how
metadata is partitioned (ComStock: state+county, ResStock: state-only) and in their measure crosswalk file
format (ComStock: csv, ResStock: xlsx), so that logic lives in each product's own module.
"""

import json
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

# XML namespace used in the S3 "list bucket" (list-type=2) XML responses.
_S3_LIST_XML_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}


@dataclass(frozen=True)
class BuildingStockRelease:
    """Describes where a single published release of a building stock dataset (ComStock or ResStock) lives
    on the OEDI data lake.

    NREL periodically republishes older releases under the most recent year's directory using a
    consistent, harmonized layout, so `year` below is the directory that currently hosts this release, not
    necessarily the year it was first published.
    """

    year: str
    folder: str
    label: str


def validate_release(release: str, supported_releases: dict[str, BuildingStockRelease], product: str) -> None:
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


class BuildingStockProcessor:
    """Shared base class for ComStockProcessor and ResStockProcessor.

    Provides S3 listing/downloading, upgrade package lookup, and time series downloading, since those are
    identical between ComStock and ResStock. Subclasses set `self.base_url`, `self.time_series_url`,
    `self._metadata_key_prefix`, `self.release`, and `self.upgrade` in their own `__init__`, and implement
    their own `process_metadata()`/`get_measure_crosswalk()`/`find_upgrade_id()`, since metadata
    partitioning (state+county vs. state-only) and measure crosswalk file formats (csv vs. xlsx) differ
    between products.
    """

    # Public, unauthenticated S3 bucket hosting both datasets.
    BUCKET = "oedi-data-lake"

    # Number of concurrent workers used for network-bound work (S3 listing/downloads). This is
    # intentionally higher than the CPU count used elsewhere for CPU-bound parallelism, since these
    # tasks mostly wait on network I/O rather than compute.
    IO_WORKERS = 16

    # Set by subclasses in __init__.
    base_url: str
    time_series_url: str
    release: str
    upgrade: str
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

    def _available_states(self) -> list[str]:
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
        save_path = save_dir / f"{self.release}-upgrades_lookup.json"
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
