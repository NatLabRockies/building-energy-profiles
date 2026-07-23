"""
Unit tests for ComStockProcessor class.

These tests make actual calls to the ComStock API and download real data
to test the functionality end-to-end without mocks.
"""

from pathlib import Path

import pandas as pd
import pytest

from comstock_processor import ComStockProcessor


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

        # Check URLs are constructed correctly
        expected_base = "https://oedi-data-lake.s3.amazonaws.com/nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/2024/comstock_amy2018_release_1/"
        assert processor.base_url == expected_base
        assert processor.metadata_url == expected_base + "metadata"
        assert processor.time_series_url == expected_base + "timeseries_individual_buildings"

    @pytest.mark.integration
    def test_process_metadata_download_and_filter(self, sample_processor):
        """Test metadata downloading and filtering functionality."""
        # Run the process_metadata method
        metadata_df = sample_processor.process_metadata(save_dir=sample_processor.base_dir)

        # Check that files were created
        assert (sample_processor.base_dir / "comstock_metadata.parquet").exists()
        expected_csv = (
            sample_processor.base_dir
            / f"{sample_processor.state}-{sample_processor.county_name}-{sample_processor.building_type}-{sample_processor.upgrade}-selected_metadata.csv"
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
    def test_process_metadata_caching(self, sample_processor):
        """Test that metadata caching works correctly."""
        # First call should download
        metadata_df1 = sample_processor.process_metadata(save_dir=sample_processor.base_dir)

        # Check files exist
        parquet_file = sample_processor.base_dir / "comstock_metadata.parquet"
        csv_file = (
            sample_processor.base_dir
            / f"{sample_processor.state}-{sample_processor.county_name}-{sample_processor.building_type}-{sample_processor.upgrade}-selected_metadata.csv"
        )

        assert parquet_file.exists()
        assert csv_file.exists()

        # Get modification times
        parquet_mtime = parquet_file.stat().st_mtime
        csv_mtime = csv_file.stat().st_mtime

        # Second call should use cached files
        metadata_df2 = sample_processor.process_metadata(save_dir=sample_processor.base_dir)

        # Files should not have been re-downloaded (same modification time)
        assert parquet_file.stat().st_mtime == parquet_mtime
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
        # Test with a different state

        processor_ny = ComStockProcessor(state="NY", county_name="All", building_type="All", upgrade="0", base_dir=test_data_dir)

        metadata_df = processor_ny.process_metadata(save_dir=test_data_dir)

        # Should only contain NY buildings
        assert all(metadata_df["in.state"] == "NY")
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
    def test_all_state_filter(self, test_data_dir):
        """Test that 'All' state filter works and returns multiple states."""

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
