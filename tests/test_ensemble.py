"""Unit tests for EnsembleBuildingType/EnsembleComponent and combine_ensemble_time_series().

These exercise the pure-python validation and combining logic with synthetic time series data -- no
network calls. `pull_ensemble_time_series()` (which downloads real data end-to-end) is covered by an
integration test instead.
"""

from pathlib import Path

import pandas as pd
import pytest

from buildstock_processor import EnsembleBuildingType, EnsembleComponent, combine_ensemble_time_series, pull_ensemble_time_series


def _make_time_series(timestamps: pd.DatetimeIndex, value: float, column: str = "out.electricity.total.energy_consumption") -> pd.DataFrame:
    return pd.DataFrame({"bldg_id": 1, "timestamp": timestamps, column: value})


class TestEnsembleComponent:
    """Test cases for EnsembleComponent validation."""

    @pytest.mark.unit
    def test_valid_component(self):
        component = EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=0.7)

        assert component.key == ("comstock", "MediumOffice")

    @pytest.mark.unit
    def test_product_is_normalized_in_key(self):
        component = EnsembleComponent(product="ComStock", building_type="MediumOffice", fraction=0.7)

        assert component.key == ("comstock", "MediumOffice")

    @pytest.mark.unit
    @pytest.mark.parametrize("fraction", [0, -0.1, 1.1])
    def test_fraction_out_of_range_raises(self, fraction):
        with pytest.raises(ValueError, match="fraction must be in"):
            EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=fraction)

    @pytest.mark.unit
    def test_unsupported_product_raises(self):
        with pytest.raises(ValueError, match="product must be"):
            EnsembleComponent(product="notaproduct", building_type="MediumOffice", fraction=0.5)


class TestEnsembleBuildingType:
    """Test cases for EnsembleBuildingType validation and construction helpers."""

    @pytest.mark.unit
    def test_valid_ensemble(self):
        ensemble = EnsembleBuildingType(
            name="Mixed-Use Office/Retail",
            components=(
                EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=0.7),
                EnsembleComponent(product="comstock", building_type="RetailStripmall", fraction=0.3),
            ),
        )

        assert len(ensemble.components) == 2
        assert ensemble.component_map()[("comstock", "RetailStripmall")].fraction == 0.3

    @pytest.mark.unit
    def test_requires_at_least_two_components(self):
        with pytest.raises(ValueError, match="at least 2 components"):
            EnsembleBuildingType(
                name="Solo",
                components=(EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=1.0),),
            )

    @pytest.mark.unit
    def test_construction_allows_imperfect_fraction_sums(self):
        """Construction itself doesn't enforce fractions summing to 1.0, so `.normalized()` can fix up an
        already-constructed ensemble -- see `assert_normalized()`/`combine_ensemble_time_series()` for where
        the sum is actually enforced."""
        ensemble = EnsembleBuildingType(
            name="Bad Mix",
            components=(
                EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=0.7),
                EnsembleComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
            ),
        )

        assert ensemble.total_fraction == pytest.approx(1.2)

    @pytest.mark.unit
    def test_assert_normalized_raises_when_fractions_do_not_sum_to_one(self):
        ensemble = EnsembleBuildingType(
            name="Bad Mix",
            components=(
                EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=0.7),
                EnsembleComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
            ),
        )

        with pytest.raises(ValueError, match=r"must sum to 1\.0"):
            ensemble.assert_normalized()

    @pytest.mark.unit
    def test_assert_normalized_passes_for_valid_ensemble(self):
        ensemble = EnsembleBuildingType(
            name="Good Mix",
            components=(
                EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=0.7),
                EnsembleComponent(product="comstock", building_type="RetailStripmall", fraction=0.3),
            ),
        )

        ensemble.assert_normalized()  # should not raise

    @pytest.mark.unit
    def test_duplicate_components_rejected(self):
        with pytest.raises(ValueError, match="unique"):
            EnsembleBuildingType(
                name="Duplicate",
                components=(
                    EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=0.5),
                    EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=0.5),
                ),
            )

    @pytest.mark.unit
    def test_from_fractions_convenience_constructor(self):
        ensemble = EnsembleBuildingType.from_fractions(
            "Mixed-Use",
            {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3},
        )

        assert {c.key for c in ensemble.components} == {("comstock", "MediumOffice"), ("comstock", "RetailStripmall")}

    @pytest.mark.unit
    def test_normalized_rescales_imperfect_percentages(self):
        ensemble = EnsembleBuildingType(
            name="Rounded Thirds",
            components=(
                EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=0.333),
                EnsembleComponent(product="comstock", building_type="RetailStripmall", fraction=0.333),
                EnsembleComponent(product="comstock", building_type="SmallOffice", fraction=0.333),
            ),
        )

        normalized = ensemble.normalized()

        assert sum(c.fraction for c in normalized.components) == pytest.approx(1.0)


class TestCombineEnsembleTimeSeries:
    """Test cases for combine_ensemble_time_series()."""

    @pytest.mark.unit
    def test_combines_two_comstock_components_with_matching_columns(self):
        ensemble = EnsembleBuildingType(
            name="Mixed-Use Office/Retail",
            components=(
                EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=0.7),
                EnsembleComponent(product="comstock", building_type="RetailStripmall", fraction=0.3),
            ),
        )
        timestamps = pd.date_range("2018-01-01", periods=4, freq="15min")
        component_series = {
            ("comstock", "MediumOffice"): _make_time_series(timestamps, value=100.0),
            ("comstock", "RetailStripmall"): _make_time_series(timestamps, value=10.0),
        }

        combined = combine_ensemble_time_series(ensemble, component_series)

        assert list(combined.columns) == ["timestamp", "out.electricity.total.energy_consumption"]
        assert (combined["out.electricity.total.energy_consumption"] == 0.7 * 100.0 + 0.3 * 10.0).all()

    @pytest.mark.unit
    def test_normalizes_resstock_unit_suffixed_columns_before_combining(self):
        """ResStock time series carry a '..kwh'-style unit suffix that ComStock's don't; combining should
        still work by normalizing both to the bare out.* column name."""
        ensemble = EnsembleBuildingType(
            name="Mixed-Use Office/Apartments",
            components=(
                EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=0.6),
                EnsembleComponent(product="resstock", building_type="Multi-Family with 5+ Units", fraction=0.4),
            ),
        )
        timestamps = pd.date_range("2018-01-01", periods=4, freq="15min")
        comstock_series = _make_time_series(timestamps, value=100.0, column="out.electricity.total.energy_consumption")
        resstock_series = _make_time_series(timestamps, value=10.0, column="out.electricity.total.energy_consumption..kwh")
        component_series = {
            ("comstock", "MediumOffice"): comstock_series,
            ("resstock", "Multi-Family with 5+ Units"): resstock_series,
        }

        combined = combine_ensemble_time_series(ensemble, component_series)

        assert "out.electricity.total.energy_consumption" in combined.columns
        assert (combined["out.electricity.total.energy_consumption"] == 0.6 * 100.0 + 0.4 * 10.0).all()

    @pytest.mark.unit
    def test_only_combines_requested_value_columns(self):
        ensemble = EnsembleBuildingType(
            name="Mixed-Use",
            components=(
                EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=0.5),
                EnsembleComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
            ),
        )
        timestamps = pd.date_range("2018-01-01", periods=4, freq="15min")
        office = _make_time_series(timestamps, value=100.0)
        office["out.natural_gas.total.energy_consumption"] = 50.0
        retail = _make_time_series(timestamps, value=10.0)
        retail["out.natural_gas.total.energy_consumption"] = 5.0
        component_series = {
            ("comstock", "MediumOffice"): office,
            ("comstock", "RetailStripmall"): retail,
        }

        combined = combine_ensemble_time_series(ensemble, component_series, value_columns=["out.electricity.total.energy_consumption"])

        assert list(combined.columns) == ["timestamp", "out.electricity.total.energy_consumption"]

    @pytest.mark.unit
    def test_requested_column_missing_from_one_component_is_silently_dropped(self):
        """ComStock and ResStock don't publish identical end-use categories (e.g. ComStock has district
        cooling/heating outputs ResStock's residential schema doesn't) -- requesting a column present in
        only some components should narrow the result rather than raising."""
        ensemble = EnsembleBuildingType(
            name="Mixed-Use",
            components=(
                EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=0.5),
                EnsembleComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
            ),
        )
        timestamps = pd.date_range("2018-01-01", periods=4, freq="15min")
        office = _make_time_series(timestamps, value=100.0)
        office["out.district_cooling.total.energy_consumption"] = 20.0
        retail = _make_time_series(timestamps, value=10.0)  # no district_cooling column at all
        component_series = {
            ("comstock", "MediumOffice"): office,
            ("comstock", "RetailStripmall"): retail,
        }

        combined = combine_ensemble_time_series(
            ensemble,
            component_series,
            value_columns=["out.electricity.total.energy_consumption", "out.district_cooling.total.energy_consumption"],
        )

        assert list(combined.columns) == ["timestamp", "out.electricity.total.energy_consumption"]

    @pytest.mark.unit
    def test_aligns_on_overlapping_timestamps_only(self):
        ensemble = EnsembleBuildingType(
            name="Mixed-Use",
            components=(
                EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=0.5),
                EnsembleComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
            ),
        )
        office_timestamps = pd.date_range("2018-01-01", periods=5, freq="15min")
        retail_timestamps = pd.date_range("2018-01-01 00:30:00", periods=5, freq="15min")
        component_series = {
            ("comstock", "MediumOffice"): _make_time_series(office_timestamps, value=100.0),
            ("comstock", "RetailStripmall"): _make_time_series(retail_timestamps, value=10.0),
        }

        combined = combine_ensemble_time_series(ensemble, component_series)

        # Only timestamps 00:30, 00:45, 01:00 are shared between the two 5-row, 15-minute series.
        assert len(combined) == 3

    @pytest.mark.unit
    def test_missing_component_series_raises(self):
        ensemble = EnsembleBuildingType(
            name="Mixed-Use",
            components=(
                EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=0.5),
                EnsembleComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
            ),
        )
        timestamps = pd.date_range("2018-01-01", periods=4, freq="15min")
        component_series = {("comstock", "MediumOffice"): _make_time_series(timestamps, value=100.0)}

        with pytest.raises(ValueError, match="Missing component time series"):
            combine_ensemble_time_series(ensemble, component_series)

    @pytest.mark.unit
    def test_rejects_ensemble_with_non_normalized_fractions(self):
        ensemble = EnsembleBuildingType(
            name="Bad Mix",
            components=(
                EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=0.7),
                EnsembleComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
            ),
        )
        timestamps = pd.date_range("2018-01-01", periods=4, freq="15min")
        component_series = {
            ("comstock", "MediumOffice"): _make_time_series(timestamps, value=100.0),
            ("comstock", "RetailStripmall"): _make_time_series(timestamps, value=10.0),
        }

        with pytest.raises(ValueError, match=r"must sum to 1\.0"):
            combine_ensemble_time_series(ensemble, component_series)

    @pytest.mark.unit
    def test_no_overlapping_timestamps_raises(self):
        ensemble = EnsembleBuildingType(
            name="Mixed-Use",
            components=(
                EnsembleComponent(product="comstock", building_type="MediumOffice", fraction=0.5),
                EnsembleComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
            ),
        )
        office_timestamps = pd.date_range("2018-01-01", periods=2, freq="15min")
        retail_timestamps = pd.date_range("2019-01-01", periods=2, freq="15min")
        component_series = {
            ("comstock", "MediumOffice"): _make_time_series(office_timestamps, value=100.0),
            ("comstock", "RetailStripmall"): _make_time_series(retail_timestamps, value=10.0),
        }

        with pytest.raises(ValueError, match="share no common timestamps"):
            combine_ensemble_time_series(ensemble, component_series)


class TestPullEnsembleTimeSeries:
    """Integration test for the end-to-end download + combine workflow. Makes real network calls."""

    @pytest.mark.integration
    def test_pulls_and_combines_real_comstock_components(self):
        """A same-product (ComStock-only) ensemble: 70% MediumOffice + 30% RetailStripmall in Delaware."""
        project_root = Path(__file__).parent.parent
        save_dir = project_root / "datasets" / "ensemble"
        save_dir.mkdir(parents=True, exist_ok=True)

        ensemble = EnsembleBuildingType.from_fractions(
            "70% MediumOffice / 30% RetailStripmall",
            {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3},
        )

        combined, component_series = pull_ensemble_time_series(
            ensemble,
            save_dir=save_dir,
            state="DE",
            value_columns=["out.electricity.total.energy_consumption", "out.site_energy.total.energy_consumption"],
        )

        assert set(component_series) == {("comstock", "MediumOffice"), ("comstock", "RetailStripmall")}
        for series in component_series.values():
            assert isinstance(series, pd.DataFrame)
            assert len(series) > 0

        assert "timestamp" in combined.columns
        assert "out.electricity.total.energy_consumption" in combined.columns
        assert len(combined) > 0

        # The combined value at every timestamp should be the fraction-weighted sum of the two components.
        office = component_series[("comstock", "MediumOffice")].set_index("timestamp")
        retail = component_series[("comstock", "RetailStripmall")].set_index("timestamp")
        expected_first = (
            0.7 * office["out.electricity.total.energy_consumption"].iloc[0]
            + 0.3 * retail["out.electricity.total.energy_consumption"].iloc[0]
        )
        assert combined["out.electricity.total.energy_consumption"].iloc[0] == pytest.approx(expected_first)
