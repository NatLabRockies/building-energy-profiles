"""
ResStock Processor - A tool to download and process ResStock data.

This module provides utilities for downloading metadata and time series data from NLR's ResStock
dataset hosted on AWS S3, building on the shared `BuildStockProcessor` infrastructure also used by
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

from pathlib import Path

import pandas as pd

from ._base import BuildStockProcessor, BuildStockRelease, MetadataPartition, validate_release
from .data_dictionary import data_dictionary

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

# Currently-supported ResStock 2025 Release 1 weather datasets. ResStock release numbers are scoped to
# publication year and weather dataset; 2024 release_2 is an older published dataset, not the newest release.
SUPPORTED_RELEASES: dict[str, BuildStockRelease] = {
    "release_1": BuildStockRelease(
        year="2025",
        folder="resstock_amy2018_release_1",
        label="ResStock 2025 Release 1",
    ),
}

DEFAULT_RELEASE = "release_1"
DEFAULT_WEATHER_YEAR = "amy2018"
SUPPORTED_WEATHER_YEARS = ("amy2018", "amy2012")

RESSTOCK_MEASURE_CROSSWALK_FILENAMES = {
    ("release_1", "amy2018"): "measure_name_crosswalk_res_2025_1.xlsx",
}

RESSTOCK_DATA_DICTIONARY = data_dictionary("resstock")
RESSTOCK_RESULT_VARIABLES = RESSTOCK_DATA_DICTIONARY.result_variables
RESSTOCK_MEASURE_UPGRADE_PACKAGES = RESSTOCK_DATA_DICTIONARY.measure_upgrade_packages


class ResStockProcessor(BuildStockProcessor):
    product_name = "ResStock"
    data_dictionary = RESSTOCK_DATA_DICTIONARY
    building_types = RESSTOCK_BUILDING_TYPES
    result_variables = RESSTOCK_RESULT_VARIABLES
    measure_upgrade_packages = RESSTOCK_MEASURE_UPGRADE_PACKAGES

    def __init__(
        self,
        state: str,
        county_name: str | list[str],
        building_type: str,
        upgrade: str,
        base_dir: Path,
        release: str = DEFAULT_RELEASE,
        weather_year: str = DEFAULT_WEATHER_YEAR,
        min_sqft: float | None = None,
        max_sqft: float | None = None,
    ) -> None:
        """ResStockProcessor helps users download metadata and time series data from the ResStock dataset.

        Args:
            state (str): 2-letter state abbreviation, or "All"
            county_name (str | list[str]): county name *without* the state prefix (e.g. "Kent County", not
                "DE, Kent County" like ComStock), "All", or a list of county names (e.g. to query a metro
                area spanning several counties without over-fetching an entire state). Note that ResStock
                metadata is only partitioned by state, so specifying a county doesn't reduce how much is
                downloaded -- it's filtered locally after downloading the state's file(s).
            building_type (str): one of RESSTOCK_BUILDING_TYPES (e.g. "Multi-Family with 5+ Units" for
                multifamily buildings), or "All"
            upgrade (str): upgrade identifier from ResStock, e.g., "0" = baseline
            base_dir (Path): directory to save the downloaded ResStock files
            release (str): which ResStock release to use. Must be one of SUPPORTED_RELEASES.
                Defaults to DEFAULT_RELEASE (the most recent supported release).
            weather_year (str): which weather dataset to use for the release. Must be one of
                SUPPORTED_WEATHER_YEARS. Defaults to DEFAULT_WEATHER_YEAR.
            min_sqft (float | None): if set, only include dwelling units with at least this square footage
            max_sqft (float | None): if set, only include dwelling units with at most this square footage
        """
        validate_release(release, SUPPORTED_RELEASES, "ResStock")
        if weather_year not in SUPPORTED_WEATHER_YEARS:
            supported_weather_years = ", ".join(SUPPORTED_WEATHER_YEARS)
            raise ValueError(f"Unsupported ResStock weather year '{weather_year}'. Supported weather years are: {supported_weather_years}.")
        if building_type != "All" and building_type not in RESSTOCK_BUILDING_TYPES:
            supported = ", ".join(RESSTOCK_BUILDING_TYPES)
            raise ValueError(f"Unsupported ResStock building type '{building_type}'. Supported building types are: {supported}, or 'All'.")

        self.state = state
        self.county_name = county_name
        self.building_type = building_type
        self.upgrade = upgrade
        self.base_dir = base_dir
        self.release = release
        self.weather_year = weather_year
        self.min_sqft = min_sqft
        self.max_sqft = max_sqft

        # `parents=True, exist_ok=True` makes this safe to call concurrently -- e.g. two composite
        # components sharing this same product both construct a processor with the same base_dir in
        # parallel (see composite.pull_composite_time_series()), so a plain exists()-check-then-mkdir()
        # would otherwise race.
        self.base_dir.mkdir(parents=True, exist_ok=True)

        release_info = self._release_info(release, weather_year)

        # Data lake explorer link: https://data.openei.org/s3_viewer?bucket=oedi-data-lake&prefix=nrel-pds-building-stock%2Fend-use-load-profiles-for-us-building-stock%2F2025%2Fresstock_amy2018_release_1%2F

        self.base_url = (
            f"https://{self.BUCKET}.s3.amazonaws.com/nrel-pds-building-stock/"
            f"end-use-load-profiles-for-us-building-stock/{release_info.year}/{release_info.folder}/"
        )

        self._metadata_key_prefix = self._metadata_root_key_prefix(release_info)
        self.metadata_url = f"https://{self.BUCKET}.s3.amazonaws.com/{self._metadata_key_prefix.rstrip('/')}"
        self.time_series_url = self.base_url + "timeseries_individual_buildings"

    def _cache_release_label(self) -> str:
        return f"{self.weather_year}_{self.release}"

    @staticmethod
    def _release_info(release: str, weather_year: str) -> BuildStockRelease:
        base_release = SUPPORTED_RELEASES[release]
        return BuildStockRelease(
            year=base_release.year,
            folder=f"resstock_{weather_year}_{release}",
            label=f"{base_release.label} {weather_year.upper()}",
        )

    def _metadata_root_key_prefix(self, release_info: BuildStockRelease) -> str:
        root = f"nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/{release_info.year}/{release_info.folder}/"
        # 2025 release_1: .../by_state/full/parquet/state=DE/DE_upgrade0.parquet
        return f"{root}metadata_and_annual_results/by_state/full/parquet/"

    def _metadata_partitions(self) -> list[MetadataPartition]:
        states = self.available_states() if self.state == "All" else [self.state]
        return [MetadataPartition(state=state) for state in states]

    def _metadata_partition_cache_name(self, partition: MetadataPartition, upgrade: str) -> str:
        return f"{partition.state}-{self._metadata_upgrade_file_label(upgrade)}.parquet"

    def _metadata_partition_url(self, partition: MetadataPartition, upgrade: str) -> str:
        upgrade_file_label = self._metadata_upgrade_file_label(upgrade)
        return f"{self.metadata_url}/state={partition.state}/{partition.state}_{upgrade_file_label}.parquet"

    def _metadata_upgrade_file_label(self, upgrade: str) -> str:
        return f"upgrade{upgrade}"

    def _filter_metadata(self, meta_df: pd.DataFrame) -> pd.DataFrame:
        if self.county_name != "All":
            counties = [self.county_name] if isinstance(self.county_name, str) else self.county_name
            meta_df = meta_df[meta_df["in.county_name"].isin(counties)]

        if self.building_type != "All":
            meta_df = meta_df[meta_df["in.geometry_building_type_recs"] == self.building_type]
        return meta_df

    def _building_energy_model_key(self, bldg_id: int, upgrade: str) -> str:
        # e.g. building_energy_models/upgrade=0/bldg0000001-up00.zip -- unlike ComStock, ResStock does NOT
        # zero-pad the "upgrade=" folder name (upgrade=0, not upgrade=00), and publishes each dwelling
        # unit's model as a ".zip" bundle (the OpenStudio model + its schedule files) rather than a bare
        # ".osm.gz" -- see comstock.py's own `_building_energy_model_key`.
        upgrade_int = int(upgrade)
        return f"building_energy_models/upgrade={upgrade_int}/bldg{bldg_id:07d}-up{upgrade_int:02d}.zip"

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
        try:
            crosswalk_filename = RESSTOCK_MEASURE_CROSSWALK_FILENAMES[(self.release, self.weather_year)]
        except KeyError as exc:
            raise ValueError(
                f"ResStock dataset '{self._cache_release_label()}' does not publish a measure name crosswalk "
                "in the OEDI dataset. Use list_upgrades() to inspect release-specific upgrade package ids."
            ) from exc

        save_path = save_dir / f"{self._cache_release_label()}-{crosswalk_filename}"
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
