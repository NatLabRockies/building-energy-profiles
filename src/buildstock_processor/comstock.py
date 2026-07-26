"""
ComStock Processor - A tool to download and process ComStock data.

This package provides utilities for downloading metadata and time series data
from NREL's ComStock dataset hosted on AWS S3.

@author: nllong
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from ._base import BuildStockProcessor, BuildStockRelease, MetadataPartition, validate_release

# The last three published releases of the ComStock AMY2018 dataset. All three are hosted, as of
# this writing, under the 2025 directory of the OEDI data lake using the same
# metadata_and_annual_results/by_state_and_county partitioned layout, and the same
# timeseries_individual_buildings/by_state layout used for time series files.
#
# When NREL publishes a new release, add it here (bumping DEFAULT_RELEASE if it should become the
# default) and drop the oldest entry to keep this rolling window at three supported releases.
SUPPORTED_RELEASES: dict[str, BuildStockRelease] = {
    "release_1": BuildStockRelease(year="2025", folder="comstock_amy2018_release_1", label="ComStock AMY2018 Release 1"),
    "release_2": BuildStockRelease(year="2025", folder="comstock_amy2018_release_2", label="ComStock AMY2018 Release 2"),
    "release_3": BuildStockRelease(year="2025", folder="comstock_amy2018_release_3", label="ComStock AMY2018 Release 3"),
}

DEFAULT_RELEASE = "release_3"


class ComStockProcessor(BuildStockProcessor):
    product_name = "ComStock"

    def __init__(
        self,
        state: str,
        county_name: str | list[str],
        building_type: str,
        upgrade: str,
        base_dir: Path,
        release: str = DEFAULT_RELEASE,
        min_sqft: float | None = None,
        max_sqft: float | None = None,
    ) -> None:
        """ComStockProcess class helps users download metadata and time series data from the ComStock dataset.

        Args:
            state (str): 2-letter state abbreviation
            county_name (str | list[str]): name of the county, "All", or a list of county names (e.g. to
                query a metro area spanning several counties, like the Denver area's Denver, Arapahoe,
                Jefferson, Adams, Douglas, and Broomfield counties) without over-fetching an entire state
            building_type (str): type of building
            upgrade (str): upgrade identifier from ComStock, e.g., 0 = baseline
            base_dir (Path): directory to save the downloaded ComStock files
            release (str): which ComStock release to use. Must be one of SUPPORTED_RELEASES.
                Defaults to DEFAULT_RELEASE (the most recent supported release).
            min_sqft (float | None): if set, only include buildings with at least this square footage
            max_sqft (float | None): if set, only include buildings with at most this square footage
        """
        validate_release(release, SUPPORTED_RELEASES, "ComStock")

        self.state = state
        self.county_name = county_name
        self.building_type = building_type
        self.upgrade = upgrade
        self.base_dir = base_dir
        self.release = release
        self.min_sqft = min_sqft
        self.max_sqft = max_sqft

        if not self.base_dir.exists():
            self.base_dir.mkdir()

        release_info = SUPPORTED_RELEASES[release]

        # Data lake explorer link: https://data.openei.org/s3_viewer?bucket=oedi-data-lake&prefix=nrel-pds-building-stock%2Fend-use-load-profiles-for-us-building-stock%2F2025%2Fcomstock_amy2018_release_3%2F

        self.base_url = (
            f"https://{self.BUCKET}.s3.amazonaws.com/nrel-pds-building-stock/"
            f"end-use-load-profiles-for-us-building-stock/{release_info.year}/{release_info.folder}/"
        )

        # The S3 key (bucket-relative path, no domain) of the partitioned metadata root. Metadata is
        # published per state/county/upgrade, e.g.:
        #   .../metadata_and_annual_results/by_state_and_county/full/parquet/state=DE/county=G1000010/DE_G1000010_upgrade0.parquet
        self._metadata_key_prefix = (
            f"nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/{release_info.year}/{release_info.folder}/"
            "metadata_and_annual_results/by_state_and_county/full/parquet/"
        )
        self.metadata_url = f"https://{self.BUCKET}.s3.amazonaws.com/{self._metadata_key_prefix.rstrip('/')}"
        self.time_series_url = self.base_url + "timeseries_individual_buildings"

    def _available_counties(self, state: str) -> list[str]:
        """Return the county FIPS-style codes (e.g. "G1000010") published for a given state."""
        state_key_prefix = f"{self._metadata_key_prefix}state={state}/"
        prefixes = self._list_common_prefixes(state_key_prefix)
        return [name.split("=", 1)[1] for name in prefixes if name.startswith("county=")]

    def _metadata_partitions(self) -> list[MetadataPartition]:
        if self.county_name != "All" and self.state == "All":
            print("County is specified, but State is not. Ignoring County...")

        states = self._available_states() if self.state == "All" else [self.state]
        with ThreadPoolExecutor(max_workers=self.IO_WORKERS) as executor:
            counties_by_state = list(executor.map(self._available_counties, states))
        return [MetadataPartition(state=state, county=county) for state, counties in zip(states, counties_by_state) for county in counties]

    def _metadata_partition_cache_name(self, partition: MetadataPartition, upgrade: str) -> str:
        county = self._require_county(partition)
        return f"{partition.state}-{county}-upgrade{upgrade}.parquet"

    def _metadata_partition_url(self, partition: MetadataPartition, upgrade: str) -> str:
        county = self._require_county(partition)
        return f"{self.metadata_url}/state={partition.state}/county={county}/{partition.state}_{county}_upgrade{upgrade}.parquet"

    @staticmethod
    def _require_county(partition: MetadataPartition) -> str:
        if partition.county is None:
            raise ValueError("ComStock metadata partitions require a county.")
        return partition.county

    def _filter_metadata(self, meta_df: pd.DataFrame) -> pd.DataFrame:
        if self.county_name != "All" and self.state != "All":
            counties = [self.county_name] if isinstance(self.county_name, str) else self.county_name
            wanted_county_names = {f"{self.state}, {county}" for county in counties}
            meta_df = meta_df[meta_df["in.county_name"].isin(wanted_county_names)]

        if self.building_type != "All":
            meta_df = meta_df[meta_df["in.comstock_building_type"] == self.building_type]
        return meta_df

    def get_measure_crosswalk(self, save_dir: Path) -> pd.DataFrame:
        """Download (if needed) and return the measure name crosswalk for this release.

        The crosswalk maps a stable `measure_id` (e.g. "hvac_0005") to the upgrade id/name used for that
        measure in this release and in earlier releases (columns named like
        "{year}_{release_folder}_upgrade_id"/"_upgrade_name"). Since upgrade ids are *not* stable across
        releases, this is the mechanism for finding the "same" measure package across releases -- see
        `find_upgrade_id()`. Note that a given release's crosswalk only covers itself and earlier releases,
        not later ones, so the newest supported release (DEFAULT_RELEASE) has the most complete crosswalk
        covering all three currently-supported releases.

        Args:
            save_dir (Path): path to save the crosswalk file

        Returns:
            DataFrame: the measure name crosswalk table for this release.
        """
        save_path = save_dir / f"{self.release}-measure_name_crosswalk.csv"
        if not save_path.exists():
            self.download_file(f"{self.base_url}measure_name_crosswalk.csv", save_path)

        return pd.read_csv(save_path)

    def find_upgrade_id(self, save_dir: Path, measure_id: str, target_release: str | None = None) -> str | None:
        """Look up the upgrade id used for a stable `measure_id` in a specific release.

        Args:
            save_dir (Path): path to save the crosswalk file
            measure_id (str): the stable measure id from `get_measure_crosswalk()`, e.g. "hvac_0005"
            target_release (str | None): which release's upgrade id to look up. Defaults to `self.release`.
                Must be one of SUPPORTED_RELEASES, and must be covered by the currently loaded release's
                crosswalk (a release's crosswalk only covers itself and earlier releases -- use
                release="release_3" for a crosswalk covering all three currently-supported releases).

        Returns:
            str | None: the upgrade id for that measure in the target release, or None if the measure
                wasn't included in that release.
        """
        target_release = target_release or self.release
        validate_release(target_release, SUPPORTED_RELEASES, "ComStock")

        target_info = SUPPORTED_RELEASES[target_release]
        id_column = f"{target_info.year}_{target_info.folder}_upgrade_id"

        crosswalk = self.get_measure_crosswalk(save_dir)
        if id_column not in crosswalk.columns:
            raise ValueError(
                f"The '{self.release}' crosswalk does not include a '{id_column}' column (it only covers "
                f"itself and earlier releases). Try find_upgrade_id() on a processor configured with a "
                f"newer release, e.g. release='release_3', which covers all supported releases."
            )

        matches = crosswalk.loc[crosswalk["measure_id"] == measure_id, id_column]
        if matches.empty or pd.isna(matches.iloc[0]):
            return None

        return str(int(matches.iloc[0]))


def main() -> None:
    # Settings for modification
    state = "CA"
    county_name = "All"
    building_type = "All"
    upgrade = "0"
    release = DEFAULT_RELEASE

    base_dir = Path().resolve() / "datasets" / "comstock"
    timeseries_save_dir = base_dir / "timeseries"
    for d in [base_dir, timeseries_save_dir]:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)

    processor = ComStockProcessor(state, county_name, building_type, upgrade, base_dir, release=release)
    meta_df = processor.process_metadata(save_dir=base_dir)

    processor.process_building_time_series(meta_df, save_dir=timeseries_save_dir)


if __name__ == "__main__":
    main()
