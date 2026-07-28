"""Unit tests for PortfolioComponent/estimate_portfolio_energy().

These exercise the pure-python validation, scaling, and combination logic against synthetic metadata
DataFrames by monkeypatching `BuildStockProcessor.process_metadata` -- no network calls are made.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from buildstock_processor import ComStockProcessor, ResStockProcessor
from buildstock_processor._base import BuildStockProcessor
from buildstock_processor.portfolio import (
    PortfolioComponent,
    estimate_portfolio_energy,
)

ELECTRICITY = "out.electricity.total.energy_consumption"
SITE_ENERGY = "out.site_energy.total.energy_consumption"


def _comstock_frame(n: int, sqft: float, electricity_mean: float, electricity_std: float, seed: int = 0) -> pd.DataFrame:
    """One row per whole building (ComStock-style): fixed `in.sqft`, normally-distributed energy."""
    rng = np.random.default_rng(seed)
    values = rng.normal(electricity_mean, electricity_std, size=n)
    return pd.DataFrame(
        {
            "bldg_id": range(n),
            "in.sqft": sqft,
            ELECTRICITY: values,
            SITE_ENERGY: values * 1.2,
        }
    )


def _resstock_frame(
    n: int, unit_sqft: float, electricity_mean: float, electricity_std: float, units_in_building: float = 50, seed: int = 1
) -> pd.DataFrame:
    """One row per dwelling unit (ResStock-style): fixed per-unit `in.sqft`, normally-distributed energy."""
    rng = np.random.default_rng(seed)
    values = rng.normal(electricity_mean, electricity_std, size=n)
    return pd.DataFrame(
        {
            "bldg_id": range(n),
            "in.sqft": unit_sqft,
            "in.geometry_building_number_units_mf": units_in_building,
            ELECTRICITY: values,
            SITE_ENERGY: values * 1.1,
        }
    )


@pytest.fixture
def patch_metadata(monkeypatch):
    """Register a `{(product, building_type): DataFrame}` mapping and monkeypatch
    `BuildStockProcessor.process_metadata` to return the matching frame based on `self.product_name`/
    `self.building_type`, regardless of scope/network.
    """
    frames: dict[tuple[str, str], pd.DataFrame] = {}

    def fake_process_metadata(self: BuildStockProcessor, save_dir: Path) -> pd.DataFrame:
        key = (self.product_name.strip().lower(), self.building_type)
        if key not in frames:
            raise AssertionError(f"No synthetic metadata registered for {key}")
        return frames[key]

    monkeypatch.setattr(BuildStockProcessor, "process_metadata", fake_process_metadata)
    return frames


class TestPortfolioComponent:
    def test_valid_sqft_component(self):
        component = PortfolioComponent(product="comstock", building_type="MediumOffice", target_sqft=40_000)
        assert component.key == ("comstock", "MediumOffice")
        assert component.sizing_mode == "sqft"

    def test_valid_units_component(self):
        component = PortfolioComponent(product="resstock", building_type="Multi-Family with 5+ Units", target_units=1000)
        assert component.sizing_mode == "units"

    def test_valid_fraction_component(self):
        component = PortfolioComponent(product="comstock", building_type="MediumOffice", fraction=0.2)
        assert component.sizing_mode == "fraction"

    def test_no_sizing_mode_raises(self):
        with pytest.raises(ValueError, match="exactly one of"):
            PortfolioComponent(product="comstock", building_type="MediumOffice")

    def test_two_sizing_modes_raises(self):
        with pytest.raises(ValueError, match="exactly one of"):
            PortfolioComponent(product="comstock", building_type="MediumOffice", target_sqft=1000, fraction=0.2)

    def test_invalid_product_raises(self):
        with pytest.raises(ValueError, match="product must be"):
            PortfolioComponent(product="bogus", building_type="MediumOffice", target_sqft=1000)

    @pytest.mark.parametrize("fraction", [0, 1, -0.1, 1.1])
    def test_fraction_out_of_range_raises(self, fraction):
        with pytest.raises(ValueError, match="fraction must be"):
            PortfolioComponent(product="comstock", building_type="MediumOffice", fraction=fraction)

    def test_non_positive_target_sqft_raises(self):
        with pytest.raises(ValueError, match="target_sqft must be"):
            PortfolioComponent(product="comstock", building_type="MediumOffice", target_sqft=0)

    def test_non_positive_target_units_raises(self):
        with pytest.raises(ValueError, match="target_units must be"):
            PortfolioComponent(product="resstock", building_type="Multi-Family with 5+ Units", target_units=-5)


class TestEstimatePortfolioEnergySingleComponent:
    def test_target_sqft_scales_mean_and_std_linearly(self, patch_metadata, tmp_path):
        patch_metadata[("comstock", "MediumOffice")] = _comstock_frame(n=200, sqft=50_000, electricity_mean=100_000, electricity_std=10_000)
        component = PortfolioComponent(product="comstock", building_type="MediumOffice", target_sqft=100_000)

        result = estimate_portfolio_energy([component], save_dir=tmp_path, state="CO", county_name="Denver", value_columns=[ELECTRICITY])

        estimate = result.components[0]
        assert estimate.sample_size == 200
        assert estimate.avg_sqft == pytest.approx(50_000)
        assert estimate.resolved_target_sqft == pytest.approx(100_000)
        metric = estimate.metrics[ELECTRICITY]
        scale = 100_000 / 50_000
        assert metric.scaled_mean == pytest.approx(metric.sample_mean * scale)
        assert metric.scaled_std == pytest.approx(metric.sample_std * scale)
        # Doubling target_sqft should exactly double both mean and std.
        component_doubled = PortfolioComponent(product="comstock", building_type="MediumOffice", target_sqft=200_000)
        result_doubled = estimate_portfolio_energy(
            [component_doubled], save_dir=tmp_path, state="CO", county_name="Denver", value_columns=[ELECTRICITY]
        )
        metric_doubled = result_doubled.components[0].metrics[ELECTRICITY]
        assert metric_doubled.scaled_mean == pytest.approx(2 * metric.scaled_mean)
        assert metric_doubled.scaled_std == pytest.approx(2 * metric.scaled_std)

    def test_target_units_scales_mean_linearly_and_std_by_sqrt_n(self, patch_metadata, tmp_path):
        patch_metadata[("resstock", "Multi-Family with 5+ Units")] = _resstock_frame(
            n=300, unit_sqft=900, electricity_mean=3_000, electricity_std=500
        )
        component = PortfolioComponent(product="resstock", building_type="Multi-Family with 5+ Units", target_units=1000)

        result = estimate_portfolio_energy([component], save_dir=tmp_path, state="CO", county_name="Denver", value_columns=[ELECTRICITY])

        estimate = result.components[0]
        assert estimate.resolved_target_units == pytest.approx(1000)
        assert estimate.resolved_target_sqft is None
        metric = estimate.metrics[ELECTRICITY]
        assert metric.scaled_mean == pytest.approx(metric.sample_mean * 1000)
        assert metric.scaled_std == pytest.approx(metric.sample_std * (1000**0.5))
        # Relative uncertainty (std / mean) should shrink versus the per-unit distribution.
        assert (metric.scaled_std / metric.scaled_mean) < (metric.sample_std / metric.sample_mean)

    def test_target_units_outside_observed_range_warns(self, patch_metadata, tmp_path):
        patch_metadata[("resstock", "Multi-Family with 5+ Units")] = _resstock_frame(
            n=50, unit_sqft=900, electricity_mean=3_000, electricity_std=500, units_in_building=20
        )
        component = PortfolioComponent(product="resstock", building_type="Multi-Family with 5+ Units", target_units=5000)

        result = estimate_portfolio_energy([component], save_dir=tmp_path, state="CO", value_columns=[ELECTRICITY])

        assert result.warnings
        assert "outside" in result.warnings[0]
        assert result.components[0].warnings

    def test_target_sqft_outside_observed_range_warns(self, patch_metadata, tmp_path):
        patch_metadata[("comstock", "MediumOffice")] = _comstock_frame(n=50, sqft=50_000, electricity_mean=100_000, electricity_std=10_000)
        component = PortfolioComponent(product="comstock", building_type="MediumOffice", target_sqft=5_000_000)

        result = estimate_portfolio_energy([component], save_dir=tmp_path, state="CO", value_columns=[ELECTRICITY])

        assert result.warnings
        assert "outside" in result.warnings[0]

    def test_missing_metric_column_is_skipped_with_warning(self, patch_metadata, tmp_path):
        patch_metadata[("comstock", "MediumOffice")] = _comstock_frame(n=10, sqft=50_000, electricity_mean=100_000, electricity_std=10_000)
        component = PortfolioComponent(product="comstock", building_type="MediumOffice", target_sqft=50_000)

        result = estimate_portfolio_energy(
            [component], save_dir=tmp_path, state="CO", value_columns=[ELECTRICITY, "out.natural_gas.total.energy_consumption"]
        )

        assert "out.natural_gas.total.energy_consumption" not in result.components[0].metrics
        assert any("natural_gas" in warning for warning in result.warnings)

    def test_empty_metadata_raises(self, patch_metadata, tmp_path):
        patch_metadata[("comstock", "MediumOffice")] = pd.DataFrame()
        component = PortfolioComponent(product="comstock", building_type="MediumOffice", target_sqft=50_000)

        with pytest.raises(ValueError, match="No buildings/units found"):
            estimate_portfolio_energy([component], save_dir=tmp_path, state="CO")


class TestEstimatePortfolioEnergyMultipleComponents:
    def test_combined_mean_and_variance_sum_across_components(self, patch_metadata, tmp_path):
        patch_metadata[("comstock", "MediumOffice")] = _comstock_frame(n=200, sqft=50_000, electricity_mean=100_000, electricity_std=10_000)
        patch_metadata[("resstock", "Multi-Family with 5+ Units")] = _resstock_frame(
            n=300, unit_sqft=900, electricity_mean=3_000, electricity_std=500
        )
        office = PortfolioComponent(product="comstock", building_type="MediumOffice", target_sqft=100_000)
        multifamily = PortfolioComponent(product="resstock", building_type="Multi-Family with 5+ Units", target_units=1000)

        result = estimate_portfolio_energy(
            [office, multifamily], save_dir=tmp_path, state="CO", county_name="Denver", value_columns=[ELECTRICITY]
        )

        office_metric = next(c for c in result.components if c.building_type == "MediumOffice").metrics[ELECTRICITY]
        mf_metric = next(c for c in result.components if "Multi-Family" in c.building_type).metrics[ELECTRICITY]
        combined = result.combined[ELECTRICITY]

        assert combined.mean == pytest.approx(office_metric.scaled_mean + mf_metric.scaled_mean)
        expected_std = (office_metric.scaled_std**2 + mf_metric.scaled_std**2) ** 0.5
        assert combined.std == pytest.approx(expected_std)
        assert combined.ci95_low == pytest.approx(combined.mean - 1.96 * combined.std)
        assert combined.ci95_high == pytest.approx(combined.mean + 1.96 * combined.std)

    def test_fraction_component_resolved_against_units_anchor(self, patch_metadata, tmp_path):
        patch_metadata[("resstock", "Multi-Family with 5+ Units")] = _resstock_frame(
            n=300, unit_sqft=900, electricity_mean=3_000, electricity_std=500
        )
        patch_metadata[("comstock", "MediumOffice")] = _comstock_frame(n=200, sqft=50_000, electricity_mean=100_000, electricity_std=10_000)

        multifamily = PortfolioComponent(product="resstock", building_type="Multi-Family with 5+ Units", target_units=1000)
        office = PortfolioComponent(product="comstock", building_type="MediumOffice", fraction=0.2)

        result = estimate_portfolio_energy(
            [multifamily, office], save_dir=tmp_path, state="CO", county_name="Denver", value_columns=[ELECTRICITY]
        )

        # Anchor sqft = 1000 units * 900 sqft/unit = 900,000. Total = anchor / (1 - 0.2) = 1,125,000.
        # Office resolved sqft = 0.2 * 1,125,000 = 225,000.
        office_estimate = next(c for c in result.components if c.building_type == "MediumOffice")
        assert office_estimate.resolved_target_sqft == pytest.approx(225_000)

    def test_fraction_without_anchor_raises(self, patch_metadata, tmp_path):
        patch_metadata[("comstock", "MediumOffice")] = _comstock_frame(n=50, sqft=50_000, electricity_mean=100_000, electricity_std=10_000)
        patch_metadata[("comstock", "RetailStripmall")] = _comstock_frame(n=50, sqft=20_000, electricity_mean=40_000, electricity_std=4_000)
        office = PortfolioComponent(product="comstock", building_type="MediumOffice", fraction=0.5)
        retail = PortfolioComponent(product="comstock", building_type="RetailStripmall", fraction=0.5)

        with pytest.raises(ValueError, match="anchor"):
            estimate_portfolio_energy([office, retail], save_dir=tmp_path, state="CO")

    def test_fractions_summing_to_one_or_more_raises(self, patch_metadata, tmp_path):
        patch_metadata[("comstock", "MediumOffice")] = _comstock_frame(n=50, sqft=50_000, electricity_mean=100_000, electricity_std=10_000)
        patch_metadata[("comstock", "RetailStripmall")] = _comstock_frame(n=50, sqft=20_000, electricity_mean=40_000, electricity_std=4_000)
        patch_metadata[("resstock", "Multi-Family with 5+ Units")] = _resstock_frame(
            n=50, unit_sqft=900, electricity_mean=3_000, electricity_std=500
        )
        anchor = PortfolioComponent(product="resstock", building_type="Multi-Family with 5+ Units", target_units=100)
        office = PortfolioComponent(product="comstock", building_type="MediumOffice", fraction=0.6)
        retail = PortfolioComponent(product="comstock", building_type="RetailStripmall", fraction=0.4)

        with pytest.raises(ValueError, match="sum to less than"):
            estimate_portfolio_energy([anchor, office, retail], save_dir=tmp_path, state="CO")

    def test_duplicate_component_keys_raise(self, patch_metadata, tmp_path):
        office_a = PortfolioComponent(product="comstock", building_type="MediumOffice", target_sqft=10_000)
        office_b = PortfolioComponent(product="comstock", building_type="MediumOffice", target_sqft=20_000)

        with pytest.raises(ValueError, match="unique"):
            estimate_portfolio_energy([office_a, office_b], save_dir=tmp_path, state="CO")

    def test_empty_components_raises(self, tmp_path):
        with pytest.raises(ValueError, match="at least 1 component"):
            estimate_portfolio_energy([], save_dir=tmp_path, state="CO")


class TestEstimatePortfolioEnergyProcessorSelection:
    def test_uses_comstock_and_resstock_processor_classes(self, monkeypatch, tmp_path):
        """Confirm the right processor class is built per component's product."""
        seen_classes: list[type] = []
        original_init_comstock = ComStockProcessor.__init__
        original_init_resstock = ResStockProcessor.__init__

        def spy_comstock_init(self, *args, **kwargs):
            seen_classes.append(ComStockProcessor)
            return original_init_comstock(self, *args, **kwargs)

        def spy_resstock_init(self, *args, **kwargs):
            seen_classes.append(ResStockProcessor)
            return original_init_resstock(self, *args, **kwargs)

        def fake_process_metadata(self: BuildStockProcessor, save_dir: Path) -> pd.DataFrame:
            if isinstance(self, ComStockProcessor):
                return _comstock_frame(n=10, sqft=50_000, electricity_mean=100_000, electricity_std=10_000)
            return _resstock_frame(n=10, unit_sqft=900, electricity_mean=3_000, electricity_std=500)

        monkeypatch.setattr(ComStockProcessor, "__init__", spy_comstock_init)
        monkeypatch.setattr(ResStockProcessor, "__init__", spy_resstock_init)
        monkeypatch.setattr(BuildStockProcessor, "process_metadata", fake_process_metadata)

        office = PortfolioComponent(product="comstock", building_type="MediumOffice", target_sqft=50_000)
        multifamily = PortfolioComponent(product="resstock", building_type="Multi-Family with 5+ Units", target_units=100)

        estimate_portfolio_energy([office, multifamily], save_dir=tmp_path, state="CO", value_columns=[ELECTRICITY])

        assert ComStockProcessor in seen_classes
        assert ResStockProcessor in seen_classes
