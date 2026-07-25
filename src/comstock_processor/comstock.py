"""
ComStock Processor - A tool to download and process ComStock data.

This package provides utilities for downloading metadata and time series data
from NREL's ComStock dataset hosted on AWS S3.

@author: nllong
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

from ._base import BuildStockProcessor, BuildStockRelease, scope_label, sqft_label, validate_release

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

    def process_metadata(self, save_dir: Path) -> pd.DataFrame:
        """Download (if needed) and process the ComStock metadata for the configured release and upgrade.

        Unlike a single national metadata file, ComStock metadata is published per state/county/upgrade
        partition, e.g. state=DE/county=G1000010/DE_G1000010_upgrade0.parquet. This method discovers the
        relevant partitions for the class's state (or every available state, if state="All"), downloads
        them in parallel (skipping any partition files already cached on disk), concatenates them, and
        filters by county name, building type, and square footage (if `min_sqft`/`max_sqft` were set) to
        match the class's constraints -- e.g. to find "all office buildings under 10,000 sqft in the Denver
        area" pass county_name=["Denver County", "Arapahoe County", ...], building_type="SmallOffice" (or
        similar), and max_sqft=10000. Note that requesting a specific county_name does not reduce how many
        partitions are downloaded (there's no local mapping from county name to its FIPS-style folder), and
        state="All" downloads every state's/county's partition for the given upgrade, which can be a large
        number of files. The resulting DataFrame's `bldg_id`/`in.state` columns can be passed directly to
        `process_building_time_series()` to download time series only for the matching buildings.

        Args:
            save_dir (Path): path to save the metadata

        Returns:
            DataFrame: the resulting metadata filtered by the classes "constraints".
        """
        return self._download_metadata_for_upgrade(save_dir, self.upgrade)

    def process_metadata_for_upgrades(self, save_dir: Path, upgrades: list[str] | None = None) -> pd.DataFrame:
        """Download and combine metadata/annual-results for multiple upgrade packages, to compare buildings
        across packages.

        Each ComStock upgrade represents a different measure package applied to the same baseline building
        sample (e.g. "Baseline", "Heat Pump RTU", "VRF with DOAS" - see `list_upgrades()`). Every metadata
        partition already includes an `upgrade` id column and an `in.upgrade_name` column, so combining
        several upgrades' worth of metadata into one DataFrame lets you group by `bldg_id` and compare
        results (e.g. energy consumption, savings) for the same building across packages.

        Note: a single building can appear more than once per upgrade in the "full" metadata, since it can
        be reused to represent multiple census tracts (each with its own `weight` and demographic
        attributes). If you only care about a building's simulated performance (not tract-level
        weighting), group/filter by `bldg_id` and `upgrade` and take the first row of each group.

        Args:
            save_dir (Path): path to save the metadata
            upgrades (list[str] | None): the upgrade ids to download and combine. Defaults to every
                upgrade available for this release (from `list_upgrades()`) -- i.e. every package,
                including the baseline (upgrade "0").

        Returns:
            DataFrame: the combined, filtered metadata for all requested upgrades, with `upgrade` and
                `in.upgrade_name` columns identifying which package each row belongs to.
        """
        all_upgrades = list(self.list_upgrades(save_dir))
        if upgrades is None:
            upgrades = all_upgrades

        combo_label = "all" if set(upgrades) == set(all_upgrades) else "-".join(sorted(upgrades))
        output_csv = (
            save_dir / f"{self.release}-{self.state}-{scope_label(self.county_name)}-{self.building_type}-"
            f"{sqft_label(self.min_sqft, self.max_sqft)}-upgrades_{combo_label}-selected_metadata.csv"
        )
        if output_csv.exists():
            print(f"Metadata csv already exists. Skipping creation. Delete {output_csv} if you want to save again.")
            return pd.read_csv(output_csv)

        frames = [self._download_metadata_for_upgrade(save_dir, upgrade) for upgrade in upgrades]
        combined_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        combined_df.to_csv(output_csv, index=False)

        return combined_df

    def _download_metadata_for_upgrade(self, save_dir: Path, upgrade: str) -> pd.DataFrame:
        """Download (if needed) and filter the ComStock metadata for a single upgrade package.

        This is the shared implementation behind `process_metadata()` (which always uses `self.upgrade`)
        and `process_metadata_for_upgrades()` (which calls this once per requested upgrade).
        """
        # check if the csv already exists, don't create it again if so, but give a warning
        output_csv = (
            save_dir / f"{self.release}-{self.state}-{scope_label(self.county_name)}-{self.building_type}-"
            f"{sqft_label(self.min_sqft, self.max_sqft)}-{upgrade}-selected_metadata.csv"
        )
        if output_csv.exists():
            print(f"Metadata csv already exists. Skipping creation. Delete {output_csv} if you want to save again.")
            return pd.read_csv(output_csv)

        if self.county_name != "All" and self.state == "All":
            print("County is specified, but State is not. Ignoring County...")

        states = self._available_states() if self.state == "All" else [self.state]

        with ThreadPoolExecutor(max_workers=self.IO_WORKERS) as executor:
            counties_by_state = list(executor.map(self._available_counties, states))
        partitions = [(state, county) for state, counties in zip(states, counties_by_state) for county in counties]

        raw_dir = save_dir / "raw_metadata" / self.release
        raw_dir.mkdir(parents=True, exist_ok=True)

        def download_partition(partition: tuple[str, str]) -> Path | None:
            state, county = partition
            save_path = raw_dir / f"{state}-{county}-upgrade{upgrade}.parquet"
            if not save_path.exists():
                partition_url = f"{self.metadata_url}/state={state}/county={county}/{state}_{county}_upgrade{upgrade}.parquet"
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
                    desc=f"Downloading metadata partitions (upgrade {upgrade})",
                )
            )

        partition_files = [path for path in downloaded if path is not None]
        if not partition_files:
            meta_df = pd.DataFrame()
        else:
            meta_df = pd.concat((pd.read_parquet(path) for path in partition_files), ignore_index=True)

            if self.county_name != "All" and self.state != "All":
                counties = [self.county_name] if isinstance(self.county_name, str) else self.county_name
                wanted_county_names = {f"{self.state}, {county}" for county in counties}
                meta_df = meta_df[meta_df["in.county_name"].isin(wanted_county_names)]

            if self.building_type != "All":
                meta_df = meta_df[meta_df["in.comstock_building_type"] == self.building_type]

            meta_df = self._apply_sqft_filter(meta_df)

            meta_df = meta_df.reset_index(drop=True)

        # save to csv
        meta_df.to_csv(output_csv, index=False)

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
