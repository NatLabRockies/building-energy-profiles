"""Unit tests for summarize_composite_metadata()/compare_composite_measures().

These exercise the pure-python aggregation/scaling logic against synthetic metadata DataFrames by
monkeypatching `BuildStockProcessor.process_metadata`/`process_metadata_for_upgrades` -- no network calls
are made.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from buildstock_processor import CompositeBuildingType
from buildstock_processor._base import BuildStockProcessor
from buildstock_processor.composite_metadata import (
    KWH_TO_KBTU,
    compare_composite_measures,
    summarize_composite_metadata,
)

ELECTRICITY_TOTAL = "out.electricity.total.energy_consumption"
ELECTRICITY_HEATING = "out.electricity.heating.energy_consumption"
GAS_TOTAL = "out.natural_gas.total.energy_consumption"
GAS_HEATING = "out.natural_gas.heating.energy_consumption"
SITE_ENERGY = "out.site_energy.total.energy_consumption"


def _office_frame(n: int = 20, sqft: float = 50_000.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "bldg_id": range(n),
            "in.sqft": sqft,
            ELECTRICITY_HEATING: 20_000.0,
            ELECTRICITY_TOTAL: 80_000.0,
            GAS_HEATING: 5_000.0,
            GAS_TOTAL: 5_000.0,
            SITE_ENERGY: 100_000.0,
        }
    )


def _retail_frame(n: int = 20, sqft: float = 20_000.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "bldg_id": range(n),
            "in.sqft": sqft,
            ELECTRICITY_HEATING: 4_000.0,
            ELECTRICITY_TOTAL: 30_000.0,
            GAS_HEATING: 1_000.0,
            GAS_TOTAL: 1_000.0,
            SITE_ENERGY: 35_000.0,
        }
    )


def _multifamily_frame(n: int = 20, sqft: float = 900.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "bldg_id": range(n),
            "in.sqft": sqft,
            ELECTRICITY_HEATING: 1_200.0,
            ELECTRICITY_TOTAL: 3_000.0,
            GAS_HEATING: 400.0,
            GAS_TOTAL: 400.0,
            SITE_ENERGY: 3_500.0,
        }
    )


@pytest.fixture
def patch_metadata(monkeypatch):
    """Register `{(product, building_type): DataFrame}` for `process_metadata()`, and
    `{(product, building_type): {upgrade_id: DataFrame}}` for `process_metadata_for_upgrades()`.
    """
    frames: dict[tuple[str, str], pd.DataFrame] = {}
    upgrade_frames: dict[tuple[str, str], dict[str, pd.DataFrame]] = {}
    upgrades_lookup: dict[tuple[str, str], dict[str, str]] = {}

    def fake_process_metadata(self: BuildStockProcessor, save_dir: Path) -> pd.DataFrame:
        key = (self.product_name.strip().lower(), self.building_type)
        if key not in frames:
            raise AssertionError(f"No synthetic metadata registered for {key}")
        return frames[key]

    def fake_process_metadata_for_upgrades(self: BuildStockProcessor, save_dir: Path, upgrades: list[str] | None = None) -> pd.DataFrame:
        key = (self.product_name.strip().lower(), self.building_type)
        by_upgrade = upgrade_frames.get(key, {})
        selected = upgrades if upgrades is not None else list(by_upgrade)
        combined = [frame.assign(upgrade=upgrade_id) for upgrade_id, frame in by_upgrade.items() if upgrade_id in selected]
        return pd.concat(combined, ignore_index=True) if combined else pd.DataFrame()

    def fake_list_upgrades(self: BuildStockProcessor, save_dir: Path) -> dict[str, str]:
        key = (self.product_name.strip().lower(), self.building_type)
        return upgrades_lookup.get(key, {})

    monkeypatch.setattr(BuildStockProcessor, "process_metadata", fake_process_metadata)
    monkeypatch.setattr(BuildStockProcessor, "process_metadata_for_upgrades", fake_process_metadata_for_upgrades)
    monkeypatch.setattr(BuildStockProcessor, "list_upgrades", fake_list_upgrades)
    return frames, upgrade_frames, upgrades_lookup


class TestSummarizeCompositeMetadata:
    def test_fraction_mode_weights_and_aggregates_by_fuel_and_end_use(self, patch_metadata, tmp_path):
        frames, _upgrade_frames, _upgrades_lookup = patch_metadata
        frames[("comstock", "MediumOffice")] = _office_frame()
        frames[("comstock", "RetailStripmall")] = _retail_frame()
        composite = CompositeBuildingType.from_fractions(
            "70% MediumOffice / 30% RetailStripmall",
            {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3},
        )

        result = summarize_composite_metadata(composite, save_dir=tmp_path, state="DE")

        assert result.weighted_building_count == 40
        assert result.weighted_avg_sqft == pytest.approx(0.7 * 50_000 + 0.3 * 20_000)
        assert result.weighted_annual_site_energy_kwh == pytest.approx(0.7 * 100_000 + 0.3 * 35_000)

        electricity = next(v for v in result.by_fuel if v.key == "electricity")
        assert electricity.annual_energy_kwh == pytest.approx(0.7 * 80_000 + 0.3 * 30_000)
        gas = next(v for v in result.by_fuel if v.key == "natural_gas")
        assert gas.annual_energy_kwh == pytest.approx(0.7 * 5_000 + 0.3 * 1_000)
        # site_energy is an aggregate source, not a real fuel -- excluded from by_fuel.
        assert not any(v.key == "site_energy" for v in result.by_fuel)

        heating = next(v for v in result.by_end_use if v.key == "heating")
        assert heating.annual_energy_kwh == pytest.approx(0.7 * (20_000 + 5_000) + 0.3 * (4_000 + 1_000))
        # "total" is a rollup label, not a real end use -- excluded from by_end_use.
        assert not any(v.key == "total" for v in result.by_end_use)

        office_summary = next(c for c in result.components if c.building_type == "MediumOffice")
        assert office_summary.building_count == 20
        assert office_summary.avg_sqft == pytest.approx(50_000)
        assert office_summary.site_eui_kbtu_per_ft2 == pytest.approx(100_000 * KWH_TO_KBTU / 50_000)

    def test_target_sqft_mode_scales_and_warns_outside_range(self, patch_metadata, tmp_path):
        frames, _upgrade_frames, _upgrades_lookup = patch_metadata
        frames[("comstock", "MediumOffice")] = _office_frame()
        frames[("comstock", "RetailStripmall")] = _retail_frame()
        composite = CompositeBuildingType.from_fractions("Mixed", {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3})

        result = summarize_composite_metadata(
            composite,
            save_dir=tmp_path,
            state="DE",
            target_sqft={("comstock", "MediumOffice"): 5_000_000.0, ("comstock", "RetailStripmall"): 20_000.0},
        )

        office_summary = next(c for c in result.components if c.building_type == "MediumOffice")
        assert office_summary.avg_sqft == pytest.approx(5_000_000.0)
        assert office_summary.annual_site_energy_kwh == pytest.approx(100_000 * (5_000_000 / 50_000))
        assert result.weighted_avg_sqft == pytest.approx(5_000_000.0 + 20_000.0)
        # Only the office component's resolved target (5,000,000 sqft) is outside its observed sample range.
        assert result.warnings
        assert "MediumOffice" in result.warnings[0]
        assert "outside" in result.warnings[0]

    def test_missing_target_sqft_for_component_raises(self, patch_metadata, tmp_path):
        frames, _upgrade_frames, _upgrades_lookup = patch_metadata
        frames[("comstock", "MediumOffice")] = _office_frame()
        frames[("comstock", "RetailStripmall")] = _retail_frame()
        composite = CompositeBuildingType.from_fractions("Mixed", {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3})

        with pytest.raises(ValueError, match="Missing target_sqft"):
            summarize_composite_metadata(composite, save_dir=tmp_path, state="DE", target_sqft={("comstock", "MediumOffice"): 100_000.0})

    def test_non_normalized_fractions_raise_in_fraction_mode(self, patch_metadata, tmp_path):
        frames, _upgrade_frames, _upgrades_lookup = patch_metadata
        frames[("comstock", "MediumOffice")] = _office_frame()
        frames[("comstock", "RetailStripmall")] = _retail_frame()
        composite = CompositeBuildingType.from_fractions(
            "Not normalized", {("comstock", "MediumOffice"): 0.5, ("comstock", "RetailStripmall"): 0.6}
        )

        with pytest.raises(ValueError, match="must sum to 1"):
            summarize_composite_metadata(composite, save_dir=tmp_path, state="DE")

    def test_empty_metadata_raises(self, patch_metadata, tmp_path):
        frames, _upgrade_frames, _upgrades_lookup = patch_metadata
        frames[("comstock", "MediumOffice")] = pd.DataFrame()
        frames[("comstock", "RetailStripmall")] = _retail_frame()
        composite = CompositeBuildingType.from_fractions("Mixed", {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3})

        with pytest.raises(ValueError, match="No buildings found"):
            summarize_composite_metadata(composite, save_dir=tmp_path, state="DE")


class TestCompareCompositeMeasures:
    def test_bare_selection_applies_to_every_component(self, patch_metadata, tmp_path):
        _frames, upgrade_frames, upgrades_lookup = patch_metadata
        office_baseline = _office_frame()
        office_upgrade = _office_frame().assign(**{ELECTRICITY_TOTAL: 60_000.0, SITE_ENERGY: 80_000.0})
        retail_baseline = _retail_frame()
        retail_upgrade = _retail_frame().assign(**{ELECTRICITY_TOTAL: 24_000.0, SITE_ENERGY: 29_000.0})
        upgrade_frames[("comstock", "MediumOffice")] = {"0": office_baseline, "5": office_upgrade}
        upgrade_frames[("comstock", "RetailStripmall")] = {"0": retail_baseline, "5": retail_upgrade}
        upgrades_lookup[("comstock", "MediumOffice")] = {"0": "Baseline", "5": "HVAC upgrade"}
        upgrades_lookup[("comstock", "RetailStripmall")] = {"0": "Baseline", "5": "HVAC upgrade"}

        composite = CompositeBuildingType.from_fractions("Mixed", {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3})

        result = compare_composite_measures(
            composite,
            save_dir=tmp_path,
            state="DE",
            baseline_upgrade="0",
            comparison_upgrades=["5"],
            metric_columns=[ELECTRICITY_TOTAL, SITE_ENERGY],
        )

        savings = result.results[ELECTRICITY_TOTAL][0]
        assert savings.name == "HVAC upgrade"
        assert savings.baseline_kwh == pytest.approx(0.7 * 80_000 + 0.3 * 30_000)
        assert savings.upgrade_kwh == pytest.approx(0.7 * 60_000 + 0.3 * 24_000)
        assert savings.absolute_savings_kwh == pytest.approx(savings.baseline_kwh - savings.upgrade_kwh)
        assert "5" in result.by_end_use

    def test_product_prefixed_selection_isolates_to_matching_component(self, patch_metadata, tmp_path):
        _frames, upgrade_frames, upgrades_lookup = patch_metadata
        office_baseline = _office_frame()
        office_upgrade = _office_frame().assign(**{ELECTRICITY_TOTAL: 60_000.0})
        multifamily_baseline = _multifamily_frame()
        upgrade_frames[("comstock", "MediumOffice")] = {"0": office_baseline, "5": office_upgrade}
        upgrade_frames[("resstock", "Multi-Family with 5+ Units")] = {"0": multifamily_baseline}
        upgrades_lookup[("comstock", "MediumOffice")] = {"0": "Baseline", "5": "Office-only upgrade"}
        upgrades_lookup[("resstock", "Multi-Family with 5+ Units")] = {"0": "Baseline"}

        composite = CompositeBuildingType.from_fractions(
            "Mixed", {("comstock", "MediumOffice"): 0.7, ("resstock", "Multi-Family with 5+ Units"): 0.3}
        )

        result = compare_composite_measures(
            composite,
            save_dir=tmp_path,
            state="DE",
            baseline_upgrade="0",
            comparison_upgrades=["comstock:5"],
            metric_columns=[ELECTRICITY_TOTAL],
        )

        savings = result.results[ELECTRICITY_TOTAL][0]
        # The residential component stays at baseline (3,000) since the selection is comstock-only; only
        # the office component's own value should have changed.
        assert savings.upgrade_kwh == pytest.approx(0.7 * 60_000 + 0.3 * 3_000)
        assert savings.product == "comstock"

    def test_empty_comparison_upgrades_raises(self, patch_metadata, tmp_path):
        frames, _upgrade_frames, _upgrades_lookup = patch_metadata
        frames[("comstock", "MediumOffice")] = _office_frame()
        frames[("comstock", "RetailStripmall")] = _retail_frame()
        composite = CompositeBuildingType.from_fractions("Mixed", {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3})

        with pytest.raises(ValueError, match="at least 1 entry"):
            compare_composite_measures(composite, save_dir=tmp_path, state="DE", comparison_upgrades=[])
