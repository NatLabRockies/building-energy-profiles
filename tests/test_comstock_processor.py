"""
Unit tests for ComStockProcessor class.

These tests make actual calls to the ComStock API and download real data
to test the functionality end-to-end without mocks.
"""

from pathlib import Path

import pandas as pd
import pytest

from building_energy_profiles._base import scope_label, sqft_label
from building_energy_profiles.comstock import DEFAULT_RELEASE, SUPPORTED_RELEASES, ComStockProcessor


@pytest.fixture
def test_data_dir():
    """Create a test data directory in the project's datasets folder."""
    # Use the project's datasets directory for test data
    project_root = Path(__file__).parent.parent
    test_dir = project_root / "datasets" / "comstock"

    # Create the directory if it doesn't exist
    test_dir.mkdir(parents=True, exist_ok=True)

    return test_dir


@pytest.fixture
def sample_processor(test_data_dir):
    """Create a ComStockProcessor instance with small dataset for testing."""

    return ComStockProcessor(
        state="DE",  # Delaware is a small state with fewer buildings
        county_name="All",
        building_type="SmallOffice",  # Small building type for faster testing
        upgrade="0",
        base_dir=test_data_dir,
    )


@pytest.fixture
def california_processor(test_data_dir):
    """Create a ComStockProcessor instance for California testing."""

    return ComStockProcessor(state="CA", county_name="All", building_type="All", upgrade="0", base_dir=test_data_dir)


class TestComStockProcessor:
    """Test cases for ComStockProcessor class."""

    @pytest.mark.unit
    def test_initialization(self, test_data_dir):
        """Test that ComStockProcessor initializes correctly."""

        processor = ComStockProcessor(
            state="CA", county_name="Los Angeles", building_type="MediumOffice", upgrade="0", base_dir=test_data_dir
        )

        assert processor.state == "CA"
        assert processor.county_name == "Los Angeles"
        assert processor.building_type == "MediumOffice"
        assert processor.upgrade == "0"
        assert processor.base_dir == test_data_dir
        assert test_data_dir.exists()  # Directory should be created

        # Defaults to the most recent supported release
        assert processor.release == DEFAULT_RELEASE

        # Check URLs are constructed correctly
        expected_base = "https://oedi-data-lake.s3.amazonaws.com/nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/2025/comstock_amy2018_release_3/"
        assert processor.base_url == expected_base
        assert processor.metadata_url == expected_base + "metadata_and_annual_results/by_state_and_county/full/parquet"
        assert processor.time_series_url == expected_base + "timeseries_individual_buildings"

    @pytest.mark.unit
    @pytest.mark.parametrize("release", list(SUPPORTED_RELEASES))
    def test_initialization_for_each_supported_release(self, test_data_dir, release):
        """Test that every supported release builds distinct, well-formed URLs."""

        processor = ComStockProcessor(
            state="DE", county_name="All", building_type="All", upgrade="0", base_dir=test_data_dir, release=release
        )

        release_info = SUPPORTED_RELEASES[release]
        assert processor.release == release
        assert release_info.folder in processor.base_url
        assert processor.metadata_url.startswith(processor.base_url)
        assert processor.time_series_url == processor.base_url + "timeseries_individual_buildings"

    @pytest.mark.unit
    def test_invalid_release_raises(self, test_data_dir):
        """Test that an unsupported release identifier raises a clear error."""

        with pytest.raises(ValueError, match="Unsupported ComStock release"):
            ComStockProcessor(state="DE", county_name="All", building_type="All", upgrade="0", base_dir=test_data_dir, release="release_99")

    @pytest.mark.integration
    def test_process_metadata_download_and_filter(self, sample_processor):
        """Test metadata downloading and filtering functionality."""
        # Run the process_metadata method
        metadata_df = sample_processor.process_metadata(save_dir=sample_processor.base_dir)

        # Check that the per-state/county partition files were downloaded
        raw_dir = sample_processor.base_dir / "raw_metadata" / sample_processor.release
        assert raw_dir.exists()
        assert any(raw_dir.glob("DE-*-upgrade0.parquet"))

        expected_csv = (
            sample_processor.base_dir / f"{sample_processor.release}-{sample_processor.state}-{scope_label(sample_processor.county_name)}-"
            f"{sample_processor.building_type}-{sqft_label(sample_processor.min_sqft, sample_processor.max_sqft)}-"
            f"{sample_processor.upgrade}-selected_metadata.csv"
        )
        assert expected_csv.exists()

        # Check that DataFrame is returned and has expected properties
        assert isinstance(metadata_df, pd.DataFrame)
        assert len(metadata_df) > 0

        # Check that filtering worked correctly for Delaware SmallOffice buildings
        assert all(metadata_df["in.state"] == "DE")
        assert all(metadata_df["in.comstock_building_type"] == "SmallOffice")

        # Check that required columns exist
        required_columns = ["bldg_id", "in.state", "in.comstock_building_type"]
        for col in required_columns:
            assert col in metadata_df.columns

    @pytest.mark.integration
    @pytest.mark.parametrize("release", list(SUPPORTED_RELEASES))
    def test_process_metadata_across_supported_releases(self, test_data_dir, release):
        """Test that metadata can be downloaded and filtered for every supported release."""

        processor = ComStockProcessor(
            state="DE",
            county_name="All",
            building_type="SmallOffice",
            upgrade="0",
            base_dir=test_data_dir,
            release=release,
        )

        metadata_df = processor.process_metadata(save_dir=test_data_dir)

        assert isinstance(metadata_df, pd.DataFrame)
        assert len(metadata_df) > 0
        assert all(metadata_df["in.state"] == "DE")
        assert all(metadata_df["in.comstock_building_type"] == "SmallOffice")

    @pytest.mark.integration
    def test_process_metadata_caching(self, sample_processor):
        """Test that metadata caching works correctly."""
        # First call should download
        metadata_df1 = sample_processor.process_metadata(save_dir=sample_processor.base_dir)

        raw_dir = sample_processor.base_dir / "raw_metadata" / sample_processor.release
        partition_files = list(raw_dir.glob("DE-*-upgrade0.parquet"))
        csv_file = (
            sample_processor.base_dir / f"{sample_processor.release}-{sample_processor.state}-{scope_label(sample_processor.county_name)}-"
            f"{sample_processor.building_type}-{sqft_label(sample_processor.min_sqft, sample_processor.max_sqft)}-"
            f"{sample_processor.upgrade}-selected_metadata.csv"
        )

        assert partition_files
        assert csv_file.exists()

        # Get modification times
        partition_mtimes = {path: path.stat().st_mtime for path in partition_files}
        csv_mtime = csv_file.stat().st_mtime

        # Second call should use cached files
        metadata_df2 = sample_processor.process_metadata(save_dir=sample_processor.base_dir)

        # Files should not have been re-downloaded (same modification time)
        for path, mtime in partition_mtimes.items():
            assert path.stat().st_mtime == mtime
        assert csv_file.stat().st_mtime == csv_mtime

        # DataFrames should be identical
        pd.testing.assert_frame_equal(metadata_df1, metadata_df2)

    @pytest.mark.integration
    def test_process_building_time_series_small_sample(self, sample_processor):
        """Test time series downloading with a small sample of buildings."""
        # First get metadata
        metadata_df = sample_processor.process_metadata(save_dir=sample_processor.base_dir)

        # Take only first 2 buildings for testing to keep it fast
        small_sample = metadata_df.head(2)

        # Create time_series_data directory
        timeseries_dir = sample_processor.base_dir / "time_series_data"
        timeseries_dir.mkdir(exist_ok=True)

        # Test the time series download
        paths, building_ids = sample_processor.process_building_time_series(small_sample, save_dir=timeseries_dir)

        # Check that results are returned
        assert isinstance(paths, list)
        assert isinstance(building_ids, list)
        assert len(paths) == len(small_sample)
        assert len(building_ids) == len(small_sample)

        # Check that files were actually downloaded
        for path, building_id in zip(paths, building_ids):
            assert Path(path).exists()
            expected_filename = f"bldg_id-{building_id}-upgrade-{sample_processor.upgrade}.parquet"
            assert Path(path).name == expected_filename

            # Check that the file has some content
            assert Path(path).stat().st_size > 0

    @pytest.mark.integration
    def test_process_building_time_series_caching(self, sample_processor):
        """Test that time series file caching works correctly."""
        # Get metadata and take one building
        metadata_df = sample_processor.process_metadata(save_dir=sample_processor.base_dir)
        one_building = metadata_df.head(1)

        timeseries_dir = sample_processor.base_dir / "timeseries"
        timeseries_dir.mkdir(exist_ok=True)

        # First download
        paths1, building_ids1 = sample_processor.process_building_time_series(one_building, save_dir=timeseries_dir)

        # Check file exists and get modification time
        file_path = Path(paths1[0])
        assert file_path.exists()
        original_mtime = file_path.stat().st_mtime

        # Second download should use cached file
        paths2, building_ids2 = sample_processor.process_building_time_series(one_building, save_dir=timeseries_dir)

        # Should return same results
        assert paths1 == paths2
        assert building_ids1 == building_ids2

        # File should not have been re-downloaded
        assert file_path.stat().st_mtime == original_mtime

    @pytest.mark.integration
    def test_different_state_filters(self, test_data_dir):
        """Test that different state filters work correctly."""
        # Test with a different, small state (Rhode Island has only 5 counties, keeping the download small)

        processor_ri = ComStockProcessor(state="RI", county_name="All", building_type="All", upgrade="0", base_dir=test_data_dir)

        metadata_df = processor_ri.process_metadata(save_dir=test_data_dir)

        # Should only contain RI buildings
        assert all(metadata_df["in.state"] == "RI")
        assert len(metadata_df) > 0

    @pytest.mark.integration
    def test_building_type_filter(self, test_data_dir):
        """Test that building type filtering works correctly."""

        processor = ComStockProcessor(
            state="DE",  # Small state for faster testing
            county_name="All",
            building_type="MediumOffice",
            upgrade="0",
            base_dir=test_data_dir,
        )

        metadata_df = processor.process_metadata(save_dir=test_data_dir)

        # Should only contain MediumOffice buildings
        assert all(metadata_df["in.comstock_building_type"] == "MediumOffice")

    @pytest.mark.integration
    def test_error_handling_invalid_state(self, test_data_dir):
        """Test handling of invalid state codes."""

        processor = ComStockProcessor(
            state="XX",  # Invalid state code
            county_name="All",
            building_type="All",
            upgrade="0",
            base_dir=test_data_dir,
        )

        # Should still work but return empty DataFrame
        metadata_df = processor.process_metadata(save_dir=test_data_dir)

        # Should return empty DataFrame for invalid state
        assert len(metadata_df) == 0

    @pytest.mark.integration
    def test_all_state_filter(self, test_data_dir, mocker):
        """Test that 'All' state filter works and aggregates data across multiple states.

        Real ComStock metadata is partitioned per state/county, so a genuine state="All" run would
        discover and download every state's partitions (thousands of files). To keep this test fast and
        deterministic, we patch state discovery down to a couple of small states while still exercising
        the real "All" code path (discovery -> per-state download -> concatenation -> filtering).
        """
        mocker.patch.object(ComStockProcessor, "available_states", return_value=["DE", "RI"])

        processor = ComStockProcessor(
            state="All",
            county_name="All",
            building_type="SmallOffice",  # Limit building type for faster test
            upgrade="0",
            base_dir=test_data_dir,
        )

        metadata_df = processor.process_metadata(save_dir=test_data_dir)

        # Should contain buildings from multiple states
        unique_states = metadata_df["in.state"].unique()
        assert len(unique_states) > 1
        assert len(metadata_df) > 0

    @pytest.mark.unit
    def test_empty_dataframe_time_series(self, sample_processor):
        """Test time series processing with empty DataFrame."""
        timeseries_dir = sample_processor.base_dir / "time_series_data"
        timeseries_dir.mkdir(exist_ok=True)

        # Create empty DataFrame with required columns
        empty_df = pd.DataFrame(columns=["bldg_id"])

        # Should handle empty DataFrame gracefully
        paths, building_ids = sample_processor.process_building_time_series(empty_df, save_dir=timeseries_dir)

        assert isinstance(paths, list)
        assert isinstance(building_ids, list)
        assert len(paths) == 0
        assert len(building_ids) == 0

    @pytest.mark.integration
    def test_list_upgrades(self, sample_processor):
        """Test that the upgrade package lookup can be downloaded and parsed."""
        upgrades = sample_processor.list_upgrades(save_dir=sample_processor.base_dir)

        assert isinstance(upgrades, dict)
        assert upgrades["0"] == "Baseline"
        assert len(upgrades) > 1

        cache_path = sample_processor.base_dir / f"{sample_processor.release}-upgrades_lookup.json"
        assert cache_path.exists()

    @pytest.mark.integration
    def test_get_measure_crosswalk(self, sample_processor):
        """Test that the measure name crosswalk can be downloaded and parsed."""
        crosswalk = sample_processor.get_measure_crosswalk(save_dir=sample_processor.base_dir)

        assert isinstance(crosswalk, pd.DataFrame)
        assert "measure_id" in crosswalk.columns
        assert any(col.endswith("_upgrade_id") for col in crosswalk.columns)

    @pytest.mark.integration
    def test_find_upgrade_id_across_releases(self, test_data_dir):
        """Test that a stable measure_id resolves to the correct upgrade id in different releases."""
        processor = ComStockProcessor(
            state="DE", county_name="All", building_type="All", upgrade="0", base_dir=test_data_dir, release="release_3"
        )

        # "hvac_0005" (Heat Pump RTU) happens to be upgrade "1" in every currently-supported release
        upgrade_id_r3 = processor.find_upgrade_id(save_dir=test_data_dir, measure_id="hvac_0005")
        upgrade_id_r1 = processor.find_upgrade_id(save_dir=test_data_dir, measure_id="hvac_0005", target_release="release_1")

        assert upgrade_id_r3 == "1"
        assert upgrade_id_r1 == "1"

    @pytest.mark.integration
    def test_find_upgrade_id_missing_measure_returns_none(self, test_data_dir):
        """Test that an unknown measure_id returns None instead of raising."""
        processor = ComStockProcessor(state="DE", county_name="All", building_type="All", upgrade="0", base_dir=test_data_dir)

        assert processor.find_upgrade_id(save_dir=test_data_dir, measure_id="does_not_exist") is None

    @pytest.mark.integration
    def test_find_upgrade_id_release_not_covered_raises(self, test_data_dir):
        """Test that requesting a release not covered by the currently loaded crosswalk raises a clear error."""
        processor = ComStockProcessor(
            state="DE", county_name="All", building_type="All", upgrade="0", base_dir=test_data_dir, release="release_1"
        )

        # release_1's crosswalk only covers itself and earlier releases, not release_3
        with pytest.raises(ValueError, match="does not include"):
            processor.find_upgrade_id(save_dir=test_data_dir, measure_id="hvac_0005", target_release="release_3")

    @pytest.mark.unit
    def test_find_upgrade_id_invalid_target_release_raises(self, test_data_dir):
        """Test that an invalid target_release raises before attempting any download."""
        processor = ComStockProcessor(state="DE", county_name="All", building_type="All", upgrade="0", base_dir=test_data_dir)

        with pytest.raises(ValueError, match="Unsupported ComStock release"):
            processor.find_upgrade_id(save_dir=test_data_dir, measure_id="hvac_0005", target_release="release_99")

    @pytest.mark.integration
    def test_process_metadata_for_upgrades_explicit_list(self, test_data_dir):
        """Test that metadata for multiple explicit upgrades can be downloaded and combined for comparison."""
        processor = ComStockProcessor(state="DE", county_name="All", building_type="SmallOffice", upgrade="0", base_dir=test_data_dir)

        combined_df = processor.process_metadata_for_upgrades(save_dir=test_data_dir, upgrades=["0", "1"])

        assert isinstance(combined_df, pd.DataFrame)
        assert len(combined_df) > 0
        assert set(combined_df["upgrade"].unique()) == {0, 1}
        assert set(combined_df["in.upgrade_name"].unique()) == {"Baseline", "Variable Speed HP RTU, Electric Backup"}

        # the same buildings should be simulated under both packages, enabling a building-level comparison
        buildings_per_upgrade = combined_df.groupby("upgrade")["bldg_id"].apply(set)
        assert buildings_per_upgrade[0] == buildings_per_upgrade[1]

    @pytest.mark.unit
    def test_process_metadata_for_upgrades_defaults_to_every_upgrade(self, tmp_path, mocker):
        """Test that process_metadata_for_upgrades() defaults to every upgrade from list_upgrades()."""
        processor = ComStockProcessor(state="DE", county_name="All", building_type="SmallOffice", upgrade="0", base_dir=tmp_path)

        mocker.patch.object(ComStockProcessor, "list_upgrades", return_value={"0": "Baseline", "1": "Some Package"})

        def fake_download_for_upgrade(save_dir, upgrade):
            return pd.DataFrame({"bldg_id": [1], "upgrade": [int(upgrade)], "in.upgrade_name": [f"pkg-{upgrade}"]})

        mock_download = mocker.patch.object(ComStockProcessor, "_download_metadata_for_upgrade", side_effect=fake_download_for_upgrade)

        combined_df = processor.process_metadata_for_upgrades(save_dir=tmp_path)

        assert mock_download.call_count == 2
        called_upgrades = {call.args[1] for call in mock_download.call_args_list}
        assert called_upgrades == {"0", "1"}
        assert sorted(combined_df["upgrade"].tolist()) == [0, 1]

    @pytest.mark.integration
    def test_multi_county_filter(self, test_data_dir):
        """Test that a list of counties selects buildings from all of them (e.g. a metro area query)."""
        processor = ComStockProcessor(
            state="DE",
            county_name=["Kent County", "Sussex County"],
            building_type="SmallOffice",
            upgrade="0",
            base_dir=test_data_dir,
        )

        metadata_df = processor.process_metadata(save_dir=test_data_dir)

        assert len(metadata_df) > 0
        assert set(metadata_df["in.county_name"].unique()) == {"DE, Kent County", "DE, Sussex County"}

    @pytest.mark.integration
    def test_sqft_filter(self, test_data_dir):
        """Test that min_sqft/max_sqft narrow results to the requested building size range."""
        processor = ComStockProcessor(
            state="DE",
            county_name="All",
            building_type="SmallOffice",
            upgrade="0",
            base_dir=test_data_dir,
            min_sqft=1000,
            max_sqft=10000,
        )

        metadata_df = processor.process_metadata(save_dir=test_data_dir)

        assert len(metadata_df) > 0
        assert metadata_df["in.sqft..ft2"].min() >= 1000
        assert metadata_df["in.sqft..ft2"].max() <= 10000

    @pytest.mark.integration
    def test_search_then_download_time_series(self, test_data_dir):
        """Test the "find a set of buildings, then download their time series" workflow end to end."""
        processor = ComStockProcessor(
            state="DE",
            county_name=["Kent County", "Sussex County"],
            building_type="SmallOffice",
            upgrade="0",
            base_dir=test_data_dir,
            max_sqft=10000,
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
        base_processor = ComStockProcessor(state="DE", county_name="All", building_type="SmallOffice", upgrade="0", base_dir=tmp_path)
        multi_county_processor = ComStockProcessor(
            state="DE", county_name=["Kent County", "Sussex County"], building_type="SmallOffice", upgrade="0", base_dir=tmp_path
        )
        sqft_processor = ComStockProcessor(
            state="DE", county_name="All", building_type="SmallOffice", upgrade="0", base_dir=tmp_path, max_sqft=10000
        )

        def cache_filename(processor: ComStockProcessor) -> str:
            return (
                f"{processor.release}-{processor.state}-{scope_label(processor.county_name)}-{processor.building_type}-"
                f"{sqft_label(processor.min_sqft, processor.max_sqft)}-{processor.upgrade}-selected_metadata.csv"
            )

        filenames = {cache_filename(base_processor), cache_filename(multi_county_processor), cache_filename(sqft_processor)}
        assert len(filenames) == 3
