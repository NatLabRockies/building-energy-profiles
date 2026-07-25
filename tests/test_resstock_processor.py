"""
Unit tests for ResStockProcessor class.

These tests make actual calls to the ResStock API and download real data
to test the functionality end-to-end without mocks.
"""

from pathlib import Path

import pandas as pd
import pytest

from building_stock_processor import scope_label, sqft_label
from resstock_processor import DEFAULT_RELEASE, RESSTOCK_BUILDING_TYPES, ResStockProcessor


@pytest.fixture
def test_data_dir():
    """Create a test data directory in the project's datasets folder."""
    # Use the project's datasets directory for test data
    project_root = Path(__file__).parent.parent
    test_dir = project_root / "datasets" / "resstock"

    # Create the directory if it doesn't exist
    test_dir.mkdir(parents=True, exist_ok=True)

    return test_dir


@pytest.fixture
def sample_processor(test_data_dir):
    """Create a ResStockProcessor instance with a small dataset for testing."""

    return ResStockProcessor(
        state="DE",  # Delaware is a small state with fewer buildings
        county_name="All",
        building_type="Multi-Family with 2 - 4 Units",  # Small multifamily category for faster testing
        upgrade="0",
        base_dir=test_data_dir,
    )


class TestResStockProcessor:
    """Test cases for ResStockProcessor class."""

    @pytest.mark.unit
    def test_initialization(self, test_data_dir):
        """Test that ResStockProcessor initializes correctly."""

        processor = ResStockProcessor(
            state="CA", county_name="Los Angeles County", building_type="Single-Family Detached", upgrade="0", base_dir=test_data_dir
        )

        assert processor.state == "CA"
        assert processor.county_name == "Los Angeles County"
        assert processor.building_type == "Single-Family Detached"
        assert processor.upgrade == "0"
        assert processor.base_dir == test_data_dir
        assert test_data_dir.exists()

        # Defaults to the most recent supported release
        assert processor.release == DEFAULT_RELEASE

        expected_base = "https://oedi-data-lake.s3.amazonaws.com/nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/2025/resstock_amy2018_release_1/"
        assert processor.base_url == expected_base
        assert processor.metadata_url == expected_base + "metadata_and_annual_results/by_state/full/parquet"
        assert processor.time_series_url == expected_base + "timeseries_individual_buildings"

    @pytest.mark.unit
    def test_invalid_release_raises(self, test_data_dir):
        """Test that an unsupported release identifier raises a clear error."""

        with pytest.raises(ValueError, match="Unsupported ResStock release"):
            ResStockProcessor(state="DE", county_name="All", building_type="All", upgrade="0", base_dir=test_data_dir, release="release_99")

    @pytest.mark.unit
    def test_invalid_building_type_raises(self, test_data_dir):
        """Test that an unsupported building type raises a clear error."""

        with pytest.raises(ValueError, match="Unsupported ResStock building type"):
            ResStockProcessor(state="DE", county_name="All", building_type="Bogus Type", upgrade="0", base_dir=test_data_dir)

    @pytest.mark.unit
    def test_all_building_type_is_allowed(self, test_data_dir):
        """Test that building_type="All" is always allowed, not just the RESSTOCK_BUILDING_TYPES values."""

        processor = ResStockProcessor(state="DE", county_name="All", building_type="All", upgrade="0", base_dir=test_data_dir)
        assert processor.building_type == "All"

    @pytest.mark.unit
    def test_resstock_building_types_includes_multifamily(self):
        """Test that the multifamily categories used to identify multifamily buildings are present."""

        assert "Multi-Family with 2 - 4 Units" in RESSTOCK_BUILDING_TYPES
        assert "Multi-Family with 5+ Units" in RESSTOCK_BUILDING_TYPES

    @pytest.mark.unit
    def test_find_upgrade_id_invalid_target_release_raises(self, test_data_dir):
        """Test that an invalid target_release raises before attempting any download."""

        processor = ResStockProcessor(state="DE", county_name="All", building_type="All", upgrade="0", base_dir=test_data_dir)

        with pytest.raises(ValueError, match="Unsupported ResStock release"):
            processor.find_upgrade_id(save_dir=test_data_dir, measure_id="hvac_001", target_release="release_99")

    @pytest.mark.unit
    def test_empty_dataframe_time_series(self, sample_processor):
        """Test time series processing with an empty DataFrame."""
        timeseries_dir = sample_processor.base_dir / "time_series_data"
        timeseries_dir.mkdir(exist_ok=True)

        empty_df = pd.DataFrame(columns=["bldg_id"])

        paths, building_ids = sample_processor.process_building_time_series(empty_df, save_dir=timeseries_dir)

        assert isinstance(paths, list)
        assert isinstance(building_ids, list)
        assert len(paths) == 0
        assert len(building_ids) == 0

    @pytest.mark.unit
    def test_process_metadata_for_upgrades_defaults_to_every_upgrade(self, tmp_path, mocker):
        """Test that process_metadata_for_upgrades() defaults to every upgrade from list_upgrades()."""
        processor = ResStockProcessor(
            state="DE", county_name="All", building_type="Multi-Family with 2 - 4 Units", upgrade="0", base_dir=tmp_path
        )

        mocker.patch.object(ResStockProcessor, "list_upgrades", return_value={"0": "Baseline", "1": "Some Package"})

        def fake_download_for_upgrade(save_dir, upgrade):
            return pd.DataFrame({"bldg_id": [1], "upgrade": [int(upgrade)], "in.upgrade_name": [f"pkg-{upgrade}"]})

        mock_download = mocker.patch.object(ResStockProcessor, "_download_metadata_for_upgrade", side_effect=fake_download_for_upgrade)

        combined_df = processor.process_metadata_for_upgrades(save_dir=tmp_path)

        assert mock_download.call_count == 2
        called_upgrades = {call.args[1] for call in mock_download.call_args_list}
        assert called_upgrades == {"0", "1"}
        assert sorted(combined_df["upgrade"].tolist()) == [0, 1]

    @pytest.mark.integration
    def test_process_metadata_download_and_filter(self, sample_processor):
        """Test metadata downloading and filtering for a multifamily building type."""
        metadata_df = sample_processor.process_metadata(save_dir=sample_processor.base_dir)

        raw_dir = sample_processor.base_dir / "raw_metadata" / sample_processor.release
        assert raw_dir.exists()
        assert any(raw_dir.glob("DE-upgrade0.parquet"))

        expected_csv = (
            sample_processor.base_dir / f"{sample_processor.release}-{sample_processor.state}-{scope_label(sample_processor.county_name)}-"
            f"{sample_processor.building_type}-{sqft_label(sample_processor.min_sqft, sample_processor.max_sqft)}-"
            f"{sample_processor.upgrade}-selected_metadata.csv"
        )
        assert expected_csv.exists()

        assert isinstance(metadata_df, pd.DataFrame)
        assert len(metadata_df) > 0
        assert all(metadata_df["in.geometry_building_type_recs"] == "Multi-Family with 2 - 4 Units")

        required_columns = ["bldg_id", "in.state", "in.geometry_building_type_recs", "weight"]
        for col in required_columns:
            assert col in metadata_df.columns

    @pytest.mark.integration
    def test_process_metadata_caching(self, sample_processor):
        """Test that metadata caching works correctly."""
        metadata_df1 = sample_processor.process_metadata(save_dir=sample_processor.base_dir)

        raw_dir = sample_processor.base_dir / "raw_metadata" / sample_processor.release
        partition_files = list(raw_dir.glob("DE-upgrade0.parquet"))
        csv_file = (
            sample_processor.base_dir / f"{sample_processor.release}-{sample_processor.state}-{scope_label(sample_processor.county_name)}-"
            f"{sample_processor.building_type}-{sqft_label(sample_processor.min_sqft, sample_processor.max_sqft)}-"
            f"{sample_processor.upgrade}-selected_metadata.csv"
        )

        assert partition_files
        assert csv_file.exists()

        partition_mtimes = {path: path.stat().st_mtime for path in partition_files}
        csv_mtime = csv_file.stat().st_mtime

        metadata_df2 = sample_processor.process_metadata(save_dir=sample_processor.base_dir)

        for path, mtime in partition_mtimes.items():
            assert path.stat().st_mtime == mtime
        assert csv_file.stat().st_mtime == csv_mtime

        pd.testing.assert_frame_equal(metadata_df1, metadata_df2)

    @pytest.mark.integration
    def test_multifamily_5plus_building_type_filter(self, test_data_dir):
        """Test that the "Multi-Family with 5+ Units" category returns only that housing type, and that
        the per-unit context columns used to describe multifamily buildings are present."""
        processor = ResStockProcessor(
            state="DE", county_name="All", building_type="Multi-Family with 5+ Units", upgrade="0", base_dir=test_data_dir
        )

        metadata_df = processor.process_metadata(save_dir=test_data_dir)

        assert len(metadata_df) > 0
        assert all(metadata_df["in.geometry_building_type_recs"] == "Multi-Family with 5+ Units")

        # ResStock models individual dwelling units, so multifamily buildings have per-unit context columns
        for col in ["in.geometry_building_number_units_mf", "in.geometry_building_horizontal_location_mf", "in.geometry_building_level_mf"]:
            assert col in metadata_df.columns

    @pytest.mark.integration
    def test_county_name_filter(self, test_data_dir):
        """Test that county_name filtering works (ResStock's in.county_name has no state prefix)."""
        processor = ResStockProcessor(state="DE", county_name="Kent County", building_type="All", upgrade="0", base_dir=test_data_dir)

        metadata_df = processor.process_metadata(save_dir=test_data_dir)

        assert len(metadata_df) > 0
        assert all(metadata_df["in.county_name"] == "Kent County")

    @pytest.mark.integration
    def test_process_building_time_series_small_sample(self, sample_processor):
        """Test time series downloading with a small sample of dwelling units."""
        metadata_df = sample_processor.process_metadata(save_dir=sample_processor.base_dir)
        small_sample = metadata_df.head(2)

        timeseries_dir = sample_processor.base_dir / "time_series_data"
        timeseries_dir.mkdir(exist_ok=True)

        paths, building_ids = sample_processor.process_building_time_series(small_sample, save_dir=timeseries_dir)

        assert len(paths) == len(small_sample)
        assert len(building_ids) == len(small_sample)

        for path, building_id in zip(paths, building_ids):
            assert Path(path).exists()
            assert Path(path).name == f"bldg_id-{building_id}-upgrade-{sample_processor.upgrade}.parquet"
            assert Path(path).stat().st_size > 0

    @pytest.mark.integration
    def test_list_upgrades(self, sample_processor):
        """Test that the upgrade package lookup can be downloaded and parsed."""
        upgrades = sample_processor.list_upgrades(save_dir=sample_processor.base_dir)

        assert isinstance(upgrades, dict)
        assert upgrades["0"] == "Baseline"
        assert len(upgrades) > 1

    @pytest.mark.integration
    def test_get_measure_crosswalk(self, sample_processor):
        """Test that the (xlsx) measure crosswalk can be downloaded and parsed."""
        crosswalk = sample_processor.get_measure_crosswalk(save_dir=sample_processor.base_dir)

        assert isinstance(crosswalk, pd.DataFrame)
        assert "measure_id" in crosswalk.columns
        assert any(col.endswith("_upgrade_id") for col in crosswalk.columns)

    @pytest.mark.integration
    def test_find_upgrade_id_known_measure(self, sample_processor):
        """Test that a stable measure_id resolves to an upgrade id."""
        upgrade_id = sample_processor.find_upgrade_id(save_dir=sample_processor.base_dir, measure_id="hvac_005")

        assert upgrade_id == "5"

    @pytest.mark.integration
    def test_find_upgrade_id_missing_measure_returns_none(self, sample_processor):
        """Test that an unknown measure_id returns None instead of raising."""
        assert sample_processor.find_upgrade_id(save_dir=sample_processor.base_dir, measure_id="does_not_exist") is None

    @pytest.mark.integration
    def test_process_metadata_for_upgrades_explicit_list(self, test_data_dir):
        """Test that metadata for multiple explicit upgrades can be downloaded and combined for comparison."""
        processor = ResStockProcessor(
            state="DE", county_name="All", building_type="Multi-Family with 2 - 4 Units", upgrade="0", base_dir=test_data_dir
        )

        combined_df = processor.process_metadata_for_upgrades(save_dir=test_data_dir, upgrades=["0", "1"])

        assert isinstance(combined_df, pd.DataFrame)
        assert len(combined_df) > 0
        assert set(combined_df["upgrade"].unique()) == {0, 1}

        # the same dwelling units should be simulated under both packages, enabling a unit-level comparison
        buildings_per_upgrade = combined_df.groupby("upgrade")["bldg_id"].apply(set)
        assert buildings_per_upgrade[0] == buildings_per_upgrade[1]

    @pytest.mark.integration
    def test_multi_county_filter(self, test_data_dir):
        """Test that a list of counties selects dwelling units from all of them (e.g. a metro area query)."""
        processor = ResStockProcessor(
            state="DE",
            county_name=["Kent County", "Sussex County"],
            building_type="Single-Family Detached",
            upgrade="0",
            base_dir=test_data_dir,
        )

        metadata_df = processor.process_metadata(save_dir=test_data_dir)

        assert len(metadata_df) > 0
        assert set(metadata_df["in.county_name"].unique()) == {"Kent County", "Sussex County"}

    @pytest.mark.integration
    def test_sqft_filter(self, test_data_dir):
        """Test that min_sqft/max_sqft narrow results to the requested dwelling unit size range."""
        processor = ResStockProcessor(
            state="DE",
            county_name="All",
            building_type="Single-Family Detached",
            upgrade="0",
            base_dir=test_data_dir,
            min_sqft=2000,
            max_sqft=3000,
        )

        metadata_df = processor.process_metadata(save_dir=test_data_dir)

        assert len(metadata_df) > 0
        assert metadata_df["in.sqft..ft2"].min() >= 2000
        assert metadata_df["in.sqft..ft2"].max() <= 3000

    @pytest.mark.integration
    def test_search_then_download_time_series(self, test_data_dir):
        """Test the "find a set of dwelling units, then download their time series" workflow end to end."""
        processor = ResStockProcessor(
            state="DE",
            county_name=["Kent County", "Sussex County"],
            building_type="Single-Family Detached",
            upgrade="0",
            base_dir=test_data_dir,
            min_sqft=2000,
            max_sqft=3000,
        )

        matching_buildings = processor.process_metadata(save_dir=test_data_dir)
        assert len(matching_buildings) > 0

        small_sample = matching_buildings.head(2)
        timeseries_dir = test_data_dir / "search_time_series_data"
        timeseries_dir.mkdir(exist_ok=True)

        paths, building_ids = processor.process_building_time_series(small_sample, save_dir=timeseries_dir)

        assert len(paths) == len(small_sample)
        assert len(building_ids) == len(small_sample)
        for path in paths:
            assert Path(path).exists()
            assert Path(path).stat().st_size > 0

    @pytest.mark.unit
    def test_different_filter_scopes_use_different_cache_files(self, tmp_path):
        """Test that different county/sqft filter combos don't collide on the same cache filename."""
        base_processor = ResStockProcessor(
            state="DE", county_name="All", building_type="Single-Family Detached", upgrade="0", base_dir=tmp_path
        )
        multi_county_processor = ResStockProcessor(
            state="DE",
            county_name=["Kent County", "Sussex County"],
            building_type="Single-Family Detached",
            upgrade="0",
            base_dir=tmp_path,
        )
        sqft_processor = ResStockProcessor(
            state="DE", county_name="All", building_type="Single-Family Detached", upgrade="0", base_dir=tmp_path, max_sqft=3000
        )

        def cache_filename(processor: ResStockProcessor) -> str:
            return (
                f"{processor.release}-{processor.state}-{scope_label(processor.county_name)}-{processor.building_type}-"
                f"{sqft_label(processor.min_sqft, processor.max_sqft)}-{processor.upgrade}-selected_metadata.csv"
            )

        filenames = {cache_filename(base_processor), cache_filename(multi_county_processor), cache_filename(sqft_processor)}
        assert len(filenames) == 3
