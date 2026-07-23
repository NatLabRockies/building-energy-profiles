"""
ResStock Processor - A tool to download and process ResStock data.

This module provides utilities for downloading metadata and time series data from NREL's ResStock
dataset hosted on AWS S3, building on the shared `BuildingStockProcessor` infrastructure also used by
`ComStockProcessor`.

Unlike ComStock, ResStock simulates individual dwelling units, not whole buildings: each metadata row is
one simulated housing unit, weighted (via `weight`/`in.units_represented`) to represent some number of real
housing units. Multifamily buildings are represented via `in.geometry_building_type_recs` (see
RESSTOCK_BUILDING_TYPES below), with additional columns describing the sampled unit's context within its
building:
    - `in.geometry_building_number_units_mf`: how many units are in that unit's (whole) building
    - `in.geometry_building_horizontal_location_mf` / `in.geometry_building_level_mf`: the unit's position
      within the building (corner/middle, top/bottom floor), which affects heat transfer through shared
      walls/ceilings/floors with neighboring units
There is no shared "building id" tying multiple sampled units back to one specific real building -- each
unit is an independently sampled and weighted record, not a sub-unit of an explicitly modeled whole
building.

@author: nllong
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

from building_stock_processor import BuildingStockProcessor, BuildingStockRelease, validate_release

# The ResStock housing-type categories used in `in.geometry_building_type_recs`. Filtering on one of the
# "Multi-Family" values selects dwelling units within multifamily buildings (not whole buildings -- see the
# module docstring).
RESSTOCK_BUILDING_TYPES = (
    "Mobile Home",
    "Single-Family Detached",
    "Single-Family Attached",
    "Multi-Family with 2 - 4 Units",
    "Multi-Family with 5+ Units",
)

# Currently-supported ResStock releases. Unlike ComStock, ResStock has not yet been fully remastered
# across multiple releases into one consistent layout on the OEDI data lake: release_1 (below) uses a
# consistent by-state-partitioned layout under the 2025 directory, but other releases (e.g. the 2024
# resstock_amy2018_release_2) use a different directory layout and aren't supported here yet. Add them
# following the same pattern once their layout is confirmed.
SUPPORTED_RELEASES: dict[str, BuildingStockRelease] = {
    "release_1": BuildingStockRelease(year="2025", folder="resstock_amy2018_release_1", label="ResStock AMY2018 Release 1"),
}

DEFAULT_RELEASE = "release_1"


class ResStockProcessor(BuildingStockProcessor):
    def __init__(
        self,
        state: str,
        county_name: str,
        building_type: str,
        upgrade: str,
        base_dir: Path,
        release: str = DEFAULT_RELEASE,
    ) -> None:
        """ResStockProcessor helps users download metadata and time series data from the ResStock dataset.

        Args:
            state (str): 2-letter state abbreviation, or "All"
            county_name (str): county name *without* the state prefix (e.g. "Kent County", not
                "DE, Kent County" like ComStock), or "All". Note that ResStock metadata is only
                partitioned by state, so specifying a county doesn't reduce how much is downloaded -- it's
                filtered locally after downloading the state's file(s).
            building_type (str): one of RESSTOCK_BUILDING_TYPES (e.g. "Multi-Family with 5+ Units" for
                multifamily buildings), or "All"
            upgrade (str): upgrade identifier from ResStock, e.g., "0" = baseline
            base_dir (Path): directory to save the downloaded ResStock files
            release (str): which ResStock release to use. Must be one of SUPPORTED_RELEASES.
                Defaults to DEFAULT_RELEASE (the most recent supported release).
        """
        validate_release(release, SUPPORTED_RELEASES, "ResStock")
        if building_type != "All" and building_type not in RESSTOCK_BUILDING_TYPES:
            supported = ", ".join(RESSTOCK_BUILDING_TYPES)
            raise ValueError(f"Unsupported ResStock building type '{building_type}'. Supported building types are: {supported}, or 'All'.")

        self.state = state
        self.county_name = county_name
        self.building_type = building_type
        self.upgrade = upgrade
        self.base_dir = base_dir
        self.release = release

        if not self.base_dir.exists():
            self.base_dir.mkdir()

        release_info = SUPPORTED_RELEASES[release]

        # Data lake explorer link: https://data.openei.org/s3_viewer?bucket=oedi-data-lake&prefix=nrel-pds-building-stock%2Fend-use-load-profiles-for-us-building-stock%2F2025%2Fresstock_amy2018_release_1%2F

        self.base_url = (
            f"https://{self.BUCKET}.s3.amazonaws.com/nrel-pds-building-stock/"
            f"end-use-load-profiles-for-us-building-stock/{release_info.year}/{release_info.folder}/"
        )

        # Unlike ComStock (partitioned by state+county), ResStock metadata is partitioned only by state,
        # e.g.: .../metadata_and_annual_results/by_state/full/parquet/state=DE/DE_upgrade0.parquet
        self._metadata_key_prefix = (
            f"nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/{release_info.year}/{release_info.folder}/"
            "metadata_and_annual_results/by_state/full/parquet/"
        )
        self.metadata_url = f"https://{self.BUCKET}.s3.amazonaws.com/{self._metadata_key_prefix.rstrip('/')}"
        self.time_series_url = self.base_url + "timeseries_individual_buildings"

    def process_metadata(self, save_dir: Path) -> pd.DataFrame:
        """Download (if needed) and process the ResStock metadata for the configured release and upgrade.

        ResStock metadata is published per state/upgrade partition (e.g. state=DE/DE_upgrade0.parquet).
        This method discovers the relevant partitions for the class's state (or every available state, if
        state="All"), downloads them in parallel (skipping any partition files already cached on disk),
        concatenates them, and filters by county name and building type (one of RESSTOCK_BUILDING_TYPES,
        e.g. "Multi-Family with 5+ Units" for multifamily buildings) to match the class's constraints.

        Args:
            save_dir (Path): path to save the metadata

        Returns:
            DataFrame: the resulting metadata filtered by the class's constraints.
        """
        return self._download_metadata_for_upgrade(save_dir, self.upgrade)

    def process_metadata_for_upgrades(self, save_dir: Path, upgrades: list[str] | None = None) -> pd.DataFrame:
        """Download and combine metadata/annual-results for multiple upgrade packages, to compare buildings
        (dwelling units) across packages.

        See `ComStockProcessor.process_metadata_for_upgrades()` for the general idea -- every partition
        already includes `upgrade` and `in.upgrade_name` columns, so grouping the combined result by
        `bldg_id` lets you compare a unit's simulated results across packages.

        Args:
            save_dir (Path): path to save the metadata
            upgrades (list[str] | None): the upgrade ids to download and combine. Defaults to every
                upgrade available for this release (from `list_upgrades()`).

        Returns:
            DataFrame: the combined, filtered metadata for all requested upgrades.
        """
        all_upgrades = list(self.list_upgrades(save_dir))
        if upgrades is None:
            upgrades = all_upgrades

        combo_label = "all" if set(upgrades) == set(all_upgrades) else "-".join(sorted(upgrades))
        output_csv = (
            save_dir / f"{self.release}-{self.state}-{self.county_name}-{self.building_type}-upgrades_{combo_label}-selected_metadata.csv"
        )
        if output_csv.exists():
            print(f"Metadata csv already exists. Skipping creation. Delete {output_csv} if you want to save again.")
            return pd.read_csv(output_csv)

        frames = [self._download_metadata_for_upgrade(save_dir, upgrade) for upgrade in upgrades]
        combined_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        combined_df.to_csv(output_csv, index=False)

        return combined_df

    def _download_metadata_for_upgrade(self, save_dir: Path, upgrade: str) -> pd.DataFrame:
        """Download (if needed) and filter the ResStock metadata for a single upgrade package.

        This is the shared implementation behind `process_metadata()` (which always uses `self.upgrade`)
        and `process_metadata_for_upgrades()` (which calls this once per requested upgrade).
        """
        output_csv = save_dir / f"{self.release}-{self.state}-{self.county_name}-{self.building_type}-{upgrade}-selected_metadata.csv"
        if output_csv.exists():
            print(f"Metadata csv already exists. Skipping creation. Delete {output_csv} if you want to save again.")
            return pd.read_csv(output_csv)

        states = self._available_states() if self.state == "All" else [self.state]

        raw_dir = save_dir / "raw_metadata" / self.release
        raw_dir.mkdir(parents=True, exist_ok=True)

        def download_partition(state: str) -> Path | None:
            save_path = raw_dir / f"{state}-upgrade{upgrade}.parquet"
            if not save_path.exists():
                partition_url = f"{self.metadata_url}/state={state}/{state}_upgrade{upgrade}.parquet"
                try:
                    self.download_file(partition_url, save_path)
                except requests.RequestException:
                    tqdm.write(f"Failed to download metadata partition: {partition_url}")
                    return None

            return save_path if save_path.exists() else None

        with ThreadPoolExecutor(max_workers=self.IO_WORKERS) as executor:
            downloaded = list(
                tqdm(
                    executor.map(download_partition, states),
                    total=len(states),
                    desc=f"Downloading metadata partitions (upgrade {upgrade})",
                )
            )

        partition_files = [path for path in downloaded if path is not None]
        if not partition_files:
            meta_df = pd.DataFrame()
        else:
            meta_df = pd.concat((pd.read_parquet(path) for path in partition_files), ignore_index=True)

            if self.county_name != "All":
                meta_df = meta_df[meta_df["in.county_name"] == self.county_name]

            if self.building_type != "All":
                meta_df = meta_df[meta_df["in.geometry_building_type_recs"] == self.building_type]

            meta_df = meta_df.reset_index(drop=True)

        meta_df.to_csv(output_csv, index=False)

        return meta_df

    def get_measure_crosswalk(self, save_dir: Path) -> pd.DataFrame:
        """Download (if needed) and return the measure name crosswalk for this release.

        Unlike ComStock's csv crosswalk, ResStock publishes this as an Excel file named
        `measure_name_crosswalk_res_{year}_{release number}.xlsx`. It maps a stable `measure_id` to the
        upgrade id used for that measure in this release (column named like
        "{year}_{release_folder}_upgrade_id") -- see `find_upgrade_id()`.

        Args:
            save_dir (Path): path to save the crosswalk file

        Returns:
            DataFrame: the measure name crosswalk table for this release.
        """
        release_number = self.release.rsplit("_", 1)[-1]
        release_info = SUPPORTED_RELEASES[self.release]
        crosswalk_filename = f"measure_name_crosswalk_res_{release_info.year}_{release_number}.xlsx"

        save_path = save_dir / f"{self.release}-{crosswalk_filename}"
        if not save_path.exists():
            self.download_file(f"{self.base_url}{crosswalk_filename}", save_path)

        return pd.read_excel(save_path)

    def find_upgrade_id(self, save_dir: Path, measure_id: str, target_release: str | None = None) -> str | None:
        """Look up the upgrade id used for a stable `measure_id` in a specific release.

        Args:
            save_dir (Path): path to save the crosswalk file
            measure_id (str): the stable measure id from `get_measure_crosswalk()`, e.g. "hvac_001"
            target_release (str | None): which release's upgrade id to look up. Defaults to `self.release`.
                Must be one of SUPPORTED_RELEASES and covered by the currently loaded release's crosswalk.

        Returns:
            str | None: the upgrade id for that measure in the target release, or None if the measure
                wasn't included in that release.
        """
        target_release = target_release or self.release
        validate_release(target_release, SUPPORTED_RELEASES, "ResStock")

        target_info = SUPPORTED_RELEASES[target_release]
        id_column = f"{target_info.year}_{target_info.folder}_upgrade_id"

        crosswalk = self.get_measure_crosswalk(save_dir)
        if id_column not in crosswalk.columns:
            raise ValueError(f"The '{self.release}' crosswalk does not include a '{id_column}' column.")

        matches = crosswalk.loc[crosswalk["measure_id"] == measure_id, id_column]
        if matches.empty or pd.isna(matches.iloc[0]):
            return None

        return str(int(matches.iloc[0]))


def main() -> None:
    # Settings for modification
    state = "CA"
    county_name = "All"
    building_type = "Multi-Family with 5+ Units"
    upgrade = "0"
    release = DEFAULT_RELEASE

    base_dir = Path().resolve() / "datasets" / "resstock"
    timeseries_save_dir = base_dir / "timeseries"
    for d in [base_dir, timeseries_save_dir]:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)

    processor = ResStockProcessor(state, county_name, building_type, upgrade, base_dir, release=release)
    meta_df = processor.process_metadata(save_dir=base_dir)

    processor.process_building_time_series(meta_df, save_dir=timeseries_save_dir)


if __name__ == "__main__":
    main()
