"""Unit tests for select_building_condition_sample()."""

from __future__ import annotations

import pandas as pd
import pytest

from buildstock_processor.building_condition import (
    KWH_TO_KBTU,
    select_building_condition_sample,
)

ENERGY_COLUMN = "out.site_energy.total.energy_consumption"


def _uniform_eui_frame(n: int = 100, sqft: float = 1000.0) -> pd.DataFrame:
    """`n` rows with site energy 1..n and constant sqft, so EUI increases monotonically with bldg_id --
    makes expected percentile bands/medians easy to reason about in tests."""
    return pd.DataFrame(
        {
            "bldg_id": range(n),
            "in.sqft": sqft,
            ENERGY_COLUMN: [float(i) for i in range(1, n + 1)],
        }
    )


class TestSelectBuildingConditionSample:
    def test_selects_band_around_target_percentile(self):
        frame = _uniform_eui_frame(n=100)

        result = select_building_condition_sample(frame, percentile=50, band=5)

        assert result.lower_percentile == pytest.approx(45.0)
        assert result.upper_percentile == pytest.approx(55.0)
        assert result.sample_size == 10
        # bldg_id increases monotonically with EUI, so the band should be roughly bldg_ids 44-53.
        assert min(result.bldg_ids) == 44
        assert max(result.bldg_ids) == 53

    def test_median_bldg_id_is_near_the_middle_of_the_band(self):
        frame = _uniform_eui_frame(n=100)

        result = select_building_condition_sample(frame, percentile=50, band=5)

        assert 44 <= result.median_bldg_id <= 53

    def test_eui_median_uses_kwh_to_kbtu_conversion(self):
        frame = _uniform_eui_frame(n=100, sqft=1000.0)

        result = select_building_condition_sample(frame, percentile=50, band=5)

        # Median energy in the band (rows 45..54, 1-indexed bldg_id+1 energy) times conversion / sqft.
        expected_energy_median = pd.Series(range(45, 55)).median()  # energy values are bldg_id+1
        assert result.eui_kbtu_per_ft2_median == pytest.approx(expected_energy_median * KWH_TO_KBTU / 1000.0)

    def test_metric_medians_and_ranges_match_manual_band_selection(self):
        frame = _uniform_eui_frame(n=100)

        result = select_building_condition_sample(frame, percentile=50, band=5)

        assert result.metric_medians[ENERGY_COLUMN] == pytest.approx(49.5)
        assert result.metric_ranges[ENERGY_COLUMN] == pytest.approx((45.0, 54.0))

    def test_high_percentile_selects_high_eui_buildings(self):
        frame = _uniform_eui_frame(n=100)

        result = select_building_condition_sample(frame, percentile=90, band=5)

        assert min(result.bldg_ids) >= 80
        assert max(result.bldg_ids) <= 99

    def test_low_percentile_selects_low_eui_buildings(self):
        frame = _uniform_eui_frame(n=100)

        result = select_building_condition_sample(frame, percentile=10, band=5)

        assert min(result.bldg_ids) >= 0
        assert max(result.bldg_ids) <= 19

    def test_percentile_out_of_range_is_clamped(self):
        frame = _uniform_eui_frame(n=100)

        low = select_building_condition_sample(frame, percentile=-20, band=5)
        high = select_building_condition_sample(frame, percentile=150, band=5)

        assert low.lower_percentile == 0.0
        assert high.upper_percentile == 100.0

    def test_extreme_percentile_with_small_sample_widens_band_instead_of_raising(self):
        frame = _uniform_eui_frame(n=5)

        # A 5-row sample's rank(pct=True) values are 20/40/60/80/100 -- a target of 100 with a band of only
        # 1 would otherwise select nothing (99 < 100 - 1... no wait it should hit 100 itself). Use a target
        # that clearly falls in a gap to force widening.
        result = select_building_condition_sample(frame, percentile=1, band=1)

        assert result.sample_size >= 1

    def test_metric_columns_are_included_alongside_energy_column(self):
        frame = _uniform_eui_frame(n=100)
        frame["out.electricity.total.energy_consumption"] = frame[ENERGY_COLUMN] * 0.8

        result = select_building_condition_sample(frame, percentile=50, band=5, metric_columns=["out.electricity.total.energy_consumption"])

        assert "out.electricity.total.energy_consumption" in result.metric_medians
        assert result.metric_medians["out.electricity.total.energy_consumption"] == pytest.approx(
            result.metric_medians[ENERGY_COLUMN] * 0.8
        )

    def test_missing_metric_column_is_silently_skipped(self):
        frame = _uniform_eui_frame(n=100)

        result = select_building_condition_sample(frame, percentile=50, band=5, metric_columns=["out.does_not_exist"])

        assert "out.does_not_exist" not in result.metric_medians
        assert "out.does_not_exist" not in result.metric_ranges

    def test_tolerates_annual_metadata_unit_suffix(self):
        frame = _uniform_eui_frame(n=100)
        frame = frame.rename(columns={ENERGY_COLUMN: ENERGY_COLUMN + "..kwh", "in.sqft": "in.sqft..ft2"})

        result = select_building_condition_sample(frame, percentile=50, band=5)

        assert result.sample_size == 10
        assert ENERGY_COLUMN in result.metric_medians

    def test_empty_metadata_raises(self):
        with pytest.raises(ValueError, match="empty metadata"):
            select_building_condition_sample(pd.DataFrame(), percentile=50)

    def test_missing_sqft_or_energy_column_raises(self):
        frame = pd.DataFrame({"bldg_id": [1, 2], "in.sqft": [1000.0, 2000.0]})

        with pytest.raises(ValueError, match="Could not find both"):
            select_building_condition_sample(frame, percentile=50)

    def test_zero_sqft_rows_are_excluded(self):
        frame = _uniform_eui_frame(n=10)
        frame.loc[0, "in.sqft"] = 0.0

        result = select_building_condition_sample(frame, percentile=50, band=50)

        assert 0 not in result.bldg_ids
