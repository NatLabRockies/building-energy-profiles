"""Unit tests for compute_building_distribution()."""

from __future__ import annotations

import pandas as pd
import pytest

from building_energy_profiles.building_distribution import (
    PERCENTILE_TARGETS,
    compute_building_distribution,
)

ENERGY_COLUMN = "out.site_energy.total.energy_consumption"


def _uniform_eui_frame(n: int = 100, sqft: float = 1000.0) -> pd.DataFrame:
    """`n` rows with site energy 1..n and constant sqft, so EUI increases monotonically with bldg_id --
    makes expected percentile/mean selections easy to reason about in tests."""
    return pd.DataFrame(
        {
            "bldg_id": range(n),
            "in.sqft": sqft,
            ENERGY_COLUMN: [float(i) for i in range(1, n + 1)],
        }
    )


class TestComputeBuildingDistribution:
    @pytest.mark.unit
    def test_basic_shape(self):
        frame = _uniform_eui_frame(n=100)

        result = compute_building_distribution(frame)

        assert result.metric == "site_eui"
        assert result.sample_size == 100
        assert len(result.points) == 100
        # Points are sorted ascending by value.
        assert [p.value for p in result.points] == sorted(p.value for p in result.points)

    @pytest.mark.unit
    def test_histogram_density_integrates_to_one(self):
        frame = _uniform_eui_frame(n=200)

        result = compute_building_distribution(frame, bins=20)

        bin_widths = [b - a for a, b in zip(result.histogram_bin_edges, result.histogram_bin_edges[1:])]
        area = sum(d * w for d, w in zip(result.histogram_density, bin_widths))
        assert area == pytest.approx(1.0, rel=1e-6)
        assert sum(result.histogram_counts) == 200

    @pytest.mark.unit
    def test_kde_curve_is_computed_for_a_normal_sample(self):
        frame = _uniform_eui_frame(n=100)

        result = compute_building_distribution(frame, kde_points=50)

        assert len(result.kde_x) == 50
        assert len(result.kde_y) == 50
        assert all(y >= 0 for y in result.kde_y)

    @pytest.mark.unit
    def test_kde_curve_empty_for_degenerate_single_value_sample(self):
        frame = pd.DataFrame({"bldg_id": [1, 2, 3], "in.sqft": [1000.0, 1000.0, 1000.0], ENERGY_COLUMN: [10.0, 10.0, 10.0]})

        result = compute_building_distribution(frame)

        assert result.kde_x == []
        assert result.kde_y == []

    @pytest.mark.unit
    def test_percentile_buildings_have_expected_keys(self):
        frame = _uniform_eui_frame(n=100)

        result = compute_building_distribution(frame)

        assert set(result.percentile_buildings) == set(PERCENTILE_TARGETS) | {"mean"}

    @pytest.mark.unit
    def test_percentile_buildings_rank_in_expected_order(self):
        frame = _uniform_eui_frame(n=100)

        result = compute_building_distribution(frame)

        p5 = result.percentile_buildings["p5"]
        p25 = result.percentile_buildings["p25"]
        median = result.percentile_buildings["median"]
        p75 = result.percentile_buildings["p75"]
        p95 = result.percentile_buildings["p95"]
        assert p5.value < p25.value < median.value < p75.value < p95.value
        # EUI increases monotonically with bldg_id in this fixture -- the median building should land
        # near the middle of the sample.
        assert 40 <= median.bldg_id <= 59

    @pytest.mark.unit
    def test_mean_building_is_close_to_arithmetic_mean(self):
        frame = _uniform_eui_frame(n=100)

        result = compute_building_distribution(frame)

        expected_mean_energy = pd.Series(range(1, 101)).mean()
        expected_mean_eui = expected_mean_energy * 3.412141633 / 1000.0
        mean_point = result.percentile_buildings["mean"]
        assert mean_point.value == pytest.approx(expected_mean_eui, rel=0.05)
        assert result.mean_value == pytest.approx(expected_mean_eui, rel=1e-6)

    @pytest.mark.unit
    def test_points_capped_by_max_points(self):
        frame = _uniform_eui_frame(n=500)

        result = compute_building_distribution(frame, max_points=50)

        assert len(result.points) <= 50
        # Percentile selection still reflects the full 500-row population, not the downsampled points.
        assert result.sample_size == 500

    @pytest.mark.unit
    def test_points_include_sqft_and_energy(self):
        frame = _uniform_eui_frame(n=10, sqft=2000.0)

        result = compute_building_distribution(frame)

        first = result.points[0]
        assert first.sqft == pytest.approx(2000.0)
        assert first.annual_site_energy_kwh is not None

    @pytest.mark.unit
    def test_tolerates_annual_metadata_unit_suffix(self):
        frame = _uniform_eui_frame(n=50)
        frame = frame.rename(columns={ENERGY_COLUMN: ENERGY_COLUMN + "..kwh", "in.sqft": "in.sqft..ft2"})

        result = compute_building_distribution(frame)

        assert result.sample_size == 50

    @pytest.mark.unit
    def test_zero_sqft_rows_are_excluded(self):
        frame = _uniform_eui_frame(n=10)
        frame.loc[0, "in.sqft"] = 0.0

        result = compute_building_distribution(frame)

        assert result.sample_size == 9
        assert all(p.bldg_id != 0 for p in result.points)

    @pytest.mark.unit
    def test_empty_metadata_raises(self):
        with pytest.raises(ValueError, match="empty metadata"):
            compute_building_distribution(pd.DataFrame())

    @pytest.mark.unit
    def test_missing_sqft_or_energy_column_raises(self):
        frame = pd.DataFrame({"bldg_id": [1, 2], "in.sqft": [1000.0, 2000.0]})

        with pytest.raises(ValueError, match="Could not find both"):
            compute_building_distribution(frame)
