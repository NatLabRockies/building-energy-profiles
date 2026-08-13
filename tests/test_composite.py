"""Unit tests for CompositeBuildingType/CompositeComponent and combine_composite_time_series().

These exercise the pure-python validation and combining logic with synthetic time series data -- no
network calls. `pull_composite_time_series()` (which downloads real data end-to-end) is covered by an
integration test instead.
"""

from pathlib import Path

import pandas as pd
import pytest

from building_energy_profiles import (
    CompositeBuildingType,
    CompositeComponent,
    combine_composite_time_series,
    find_nearest_sqft_bldg_id,
    pull_composite_time_series,
    resolve_fraction_weights,
)
from building_energy_profiles._base import BuildStockProcessor
from building_energy_profiles.comstock import ComStockProcessor


def _make_time_series(timestamps: pd.DatetimeIndex, value: float, column: str = "out.electricity.total.energy_consumption") -> pd.DataFrame:
    return pd.DataFrame({"bldg_id": 1, "timestamp": timestamps, column: value})


class TestFindNearestSqftBldgId:
    def test_picks_closest_row(self):
        metadata = pd.DataFrame({"bldg_id": [1, 2, 3], "in.sqft": [10_000.0, 25_000.0, 50_000.0]})

        assert find_nearest_sqft_bldg_id(metadata, target_sqft=27_000.0) == 2

    def test_exact_match_wins(self):
        metadata = pd.DataFrame({"bldg_id": [1, 2, 3], "in.sqft": [10_000.0, 25_000.0, 50_000.0]})

        assert find_nearest_sqft_bldg_id(metadata, target_sqft=50_000.0) == 3

    def test_tolerates_unit_suffixed_sqft_column(self):
        metadata = pd.DataFrame({"bldg_id": [1, 2], "in.sqft..ft2": [10_000.0, 50_000.0]})

        assert find_nearest_sqft_bldg_id(metadata, target_sqft=45_000.0) == 2

    def test_explicit_sqft_column_overrides_autodetect(self):
        metadata = pd.DataFrame({"bldg_id": [1, 2], "in.sqft": [10_000.0, 50_000.0], "custom_sqft": [48_000.0, 1_000.0]})

        assert find_nearest_sqft_bldg_id(metadata, target_sqft=45_000.0, sqft_column="custom_sqft") == 1

    def test_ignores_rows_with_nan_sqft(self):
        metadata = pd.DataFrame({"bldg_id": [1, 2, 3], "in.sqft": [10_000.0, None, 50_000.0]})

        assert find_nearest_sqft_bldg_id(metadata, target_sqft=20_000.0) == 1

    def test_empty_metadata_raises(self):
        with pytest.raises(ValueError, match="empty metadata"):
            find_nearest_sqft_bldg_id(pd.DataFrame(), target_sqft=10_000.0)

    def test_missing_sqft_column_raises(self):
        metadata = pd.DataFrame({"bldg_id": [1, 2]})

        with pytest.raises(ValueError, match="Could not find a floor-area column"):
            find_nearest_sqft_bldg_id(metadata, target_sqft=10_000.0)

    def test_all_nan_sqft_raises(self):
        metadata = pd.DataFrame({"bldg_id": [1, 2], "in.sqft": [None, None]})

        with pytest.raises(ValueError, match="No rows with a valid"):
            find_nearest_sqft_bldg_id(metadata, target_sqft=10_000.0)


class TestCompositeComponent:
    """Test cases for CompositeComponent validation."""

    @pytest.mark.unit
    def test_valid_component(self):
        component = CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.7)

        assert component.key == ("comstock", "MediumOffice")

    @pytest.mark.unit
    def test_product_is_normalized_in_key(self):
        component = CompositeComponent(product="ComStock", building_type="MediumOffice", fraction=0.7)

        assert component.key == ("comstock", "MediumOffice")

    @pytest.mark.unit
    @pytest.mark.parametrize("fraction", [0, -0.1, 1.1])
    def test_fraction_out_of_range_raises(self, fraction):
        with pytest.raises(ValueError, match="fraction must be in"):
            CompositeComponent(product="comstock", building_type="MediumOffice", fraction=fraction)

    @pytest.mark.unit
    def test_unsupported_product_raises(self):
        with pytest.raises(ValueError, match="product must be"):
            CompositeComponent(product="notaproduct", building_type="MediumOffice", fraction=0.5)


class TestCompositeBuildingType:
    """Test cases for CompositeBuildingType validation and construction helpers."""

    @pytest.mark.unit
    def test_valid_composite(self):
        composite = CompositeBuildingType(
            name="Mixed-Use Office/Retail",
            components=(
                CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.7),
                CompositeComponent(product="comstock", building_type="RetailStripmall", fraction=0.3),
            ),
        )

        assert len(composite.components) == 2
        assert composite.component_map()[("comstock", "RetailStripmall")].fraction == 0.3

    @pytest.mark.unit
    def test_requires_at_least_two_components(self):
        with pytest.raises(ValueError, match="at least 2 components"):
            CompositeBuildingType(
                name="Solo",
                components=(CompositeComponent(product="comstock", building_type="MediumOffice", fraction=1.0),),
            )

    @pytest.mark.unit
    def test_construction_allows_imperfect_fraction_sums(self):
        """Construction itself doesn't enforce fractions summing to 1.0, so `.normalized()` can fix up an
        already-constructed composite -- see `assert_normalized()`/`combine_composite_time_series()` for where
        the sum is actually enforced."""
        composite = CompositeBuildingType(
            name="Bad Mix",
            components=(
                CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.7),
                CompositeComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
            ),
        )

        assert composite.total_fraction == pytest.approx(1.2)

    @pytest.mark.unit
    def test_assert_normalized_raises_when_fractions_do_not_sum_to_one(self):
        composite = CompositeBuildingType(
            name="Bad Mix",
            components=(
                CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.7),
                CompositeComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
            ),
        )

        with pytest.raises(ValueError, match=r"must sum to 1\.0"):
            composite.assert_normalized()

    @pytest.mark.unit
    def test_assert_normalized_passes_for_valid_composite(self):
        composite = CompositeBuildingType(
            name="Good Mix",
            components=(
                CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.7),
                CompositeComponent(product="comstock", building_type="RetailStripmall", fraction=0.3),
            ),
        )

        composite.assert_normalized()  # should not raise

    @pytest.mark.unit
    def test_duplicate_components_rejected(self):
        with pytest.raises(ValueError, match="unique"):
            CompositeBuildingType(
                name="Duplicate",
                components=(
                    CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.5),
                    CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.5),
                ),
            )

    @pytest.mark.unit
    def test_from_fractions_convenience_constructor(self):
        composite = CompositeBuildingType.from_fractions(
            "Mixed-Use",
            {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3},
        )

        assert {c.key for c in composite.components} == {("comstock", "MediumOffice"), ("comstock", "RetailStripmall")}

    @pytest.mark.unit
    def test_normalized_rescales_imperfect_percentages(self):
        composite = CompositeBuildingType(
            name="Rounded Thirds",
            components=(
                CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.333),
                CompositeComponent(product="comstock", building_type="RetailStripmall", fraction=0.333),
                CompositeComponent(product="comstock", building_type="SmallOffice", fraction=0.333),
            ),
        )

        normalized = composite.normalized()

        assert sum(c.fraction for c in normalized.components) == pytest.approx(1.0)


class TestCombineCompositeTimeSeries:
    """Test cases for combine_composite_time_series()."""

    @pytest.mark.unit
    def test_combines_two_comstock_components_with_matching_columns(self):
        composite = CompositeBuildingType(
            name="Mixed-Use Office/Retail",
            components=(
                CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.7),
                CompositeComponent(product="comstock", building_type="RetailStripmall", fraction=0.3),
            ),
        )
        timestamps = pd.date_range("2018-01-01", periods=4, freq="15min")
        component_series = {
            ("comstock", "MediumOffice"): _make_time_series(timestamps, value=100.0),
            ("comstock", "RetailStripmall"): _make_time_series(timestamps, value=10.0),
        }

        combined = combine_composite_time_series(composite, component_series)

        assert list(combined.columns) == ["timestamp", "out.electricity.total.energy_consumption"]
        assert (combined["out.electricity.total.energy_consumption"] == 0.7 * 100.0 + 0.3 * 10.0).all()

    @pytest.mark.unit
    def test_normalizes_resstock_unit_suffixed_columns_before_combining(self):
        """ResStock time series carry a '..kwh'-style unit suffix that ComStock's don't; combining should
        still work by normalizing both to the bare out.* column name."""
        composite = CompositeBuildingType(
            name="Mixed-Use Office/Apartments",
            components=(
                CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.6),
                CompositeComponent(product="resstock", building_type="Multi-Family with 5+ Units", fraction=0.4),
            ),
        )
        timestamps = pd.date_range("2018-01-01", periods=4, freq="15min")
        comstock_series = _make_time_series(timestamps, value=100.0, column="out.electricity.total.energy_consumption")
        resstock_series = _make_time_series(timestamps, value=10.0, column="out.electricity.total.energy_consumption..kwh")
        component_series = {
            ("comstock", "MediumOffice"): comstock_series,
            ("resstock", "Multi-Family with 5+ Units"): resstock_series,
        }

        combined = combine_composite_time_series(composite, component_series)

        assert "out.electricity.total.energy_consumption" in combined.columns
        assert (combined["out.electricity.total.energy_consumption"] == 0.6 * 100.0 + 0.4 * 10.0).all()

    @pytest.mark.unit
    def test_only_combines_requested_value_columns(self):
        composite = CompositeBuildingType(
            name="Mixed-Use",
            components=(
                CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.5),
                CompositeComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
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

        combined = combine_composite_time_series(composite, component_series, value_columns=["out.electricity.total.energy_consumption"])

        assert list(combined.columns) == ["timestamp", "out.electricity.total.energy_consumption"]

    @pytest.mark.unit
    def test_requested_column_missing_from_one_component_is_silently_dropped(self):
        """ComStock and ResStock don't publish identical end-use categories (e.g. ComStock has district
        cooling/heating outputs ResStock's residential schema doesn't) -- requesting a column present in
        only some components should narrow the result rather than raising."""
        composite = CompositeBuildingType(
            name="Mixed-Use",
            components=(
                CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.5),
                CompositeComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
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

        combined = combine_composite_time_series(
            composite,
            component_series,
            value_columns=["out.electricity.total.energy_consumption", "out.district_cooling.total.energy_consumption"],
        )

        assert list(combined.columns) == ["timestamp", "out.electricity.total.energy_consumption"]

    @pytest.mark.unit
    def test_aligns_on_overlapping_timestamps_only(self):
        composite = CompositeBuildingType(
            name="Mixed-Use",
            components=(
                CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.5),
                CompositeComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
            ),
        )
        office_timestamps = pd.date_range("2018-01-01", periods=5, freq="15min")
        retail_timestamps = pd.date_range("2018-01-01 00:30:00", periods=5, freq="15min")
        component_series = {
            ("comstock", "MediumOffice"): _make_time_series(office_timestamps, value=100.0),
            ("comstock", "RetailStripmall"): _make_time_series(retail_timestamps, value=10.0),
        }

        combined = combine_composite_time_series(composite, component_series)

        # Only timestamps 00:30, 00:45, 01:00 are shared between the two 5-row, 15-minute series.
        assert len(combined) == 3

    @pytest.mark.unit
    def test_missing_component_series_raises(self):
        composite = CompositeBuildingType(
            name="Mixed-Use",
            components=(
                CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.5),
                CompositeComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
            ),
        )
        timestamps = pd.date_range("2018-01-01", periods=4, freq="15min")
        component_series = {("comstock", "MediumOffice"): _make_time_series(timestamps, value=100.0)}

        with pytest.raises(ValueError, match="Missing component time series"):
            combine_composite_time_series(composite, component_series)

    @pytest.mark.unit
    def test_rejects_composite_with_non_normalized_fractions(self):
        composite = CompositeBuildingType(
            name="Bad Mix",
            components=(
                CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.7),
                CompositeComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
            ),
        )
        timestamps = pd.date_range("2018-01-01", periods=4, freq="15min")
        component_series = {
            ("comstock", "MediumOffice"): _make_time_series(timestamps, value=100.0),
            ("comstock", "RetailStripmall"): _make_time_series(timestamps, value=10.0),
        }

        with pytest.raises(ValueError, match=r"must sum to 1\.0"):
            combine_composite_time_series(composite, component_series)

    @pytest.mark.unit
    def test_no_overlapping_timestamps_raises(self):
        composite = CompositeBuildingType(
            name="Mixed-Use",
            components=(
                CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.5),
                CompositeComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
            ),
        )
        office_timestamps = pd.date_range("2018-01-01", periods=2, freq="15min")
        retail_timestamps = pd.date_range("2019-01-01", periods=2, freq="15min")
        component_series = {
            ("comstock", "MediumOffice"): _make_time_series(office_timestamps, value=100.0),
            ("comstock", "RetailStripmall"): _make_time_series(retail_timestamps, value=10.0),
        }

        with pytest.raises(ValueError, match="share no common timestamps"):
            combine_composite_time_series(composite, component_series)

    @pytest.mark.unit
    def test_weights_override_fraction_and_neednt_sum_to_one(self):
        """`weights` scales each component to an absolute target (e.g. square footage) rather than a
        floor-area *share* -- unlike `fraction`, it isn't required to sum to 1.0."""
        composite = CompositeBuildingType(
            name="Mixed-Use",
            components=(
                # Fractions deliberately don't sum to 1.0 -- would fail assert_normalized() if used, but
                # weights bypasses that check entirely.
                CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.7),
                CompositeComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
            ),
        )
        timestamps = pd.date_range("2018-01-01", periods=4, freq="15min")
        component_series = {
            ("comstock", "MediumOffice"): _make_time_series(timestamps, value=100.0),
            ("comstock", "RetailStripmall"): _make_time_series(timestamps, value=10.0),
        }

        combined = combine_composite_time_series(
            composite,
            component_series,
            weights={("comstock", "MediumOffice"): 2.0, ("comstock", "RetailStripmall"): 3.0},
        )

        assert (combined["out.electricity.total.energy_consumption"] == 2.0 * 100.0 + 3.0 * 10.0).all()

    @pytest.mark.unit
    def test_weights_missing_a_component_raises(self):
        composite = CompositeBuildingType(
            name="Mixed-Use",
            components=(
                CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.5),
                CompositeComponent(product="comstock", building_type="RetailStripmall", fraction=0.5),
            ),
        )
        timestamps = pd.date_range("2018-01-01", periods=4, freq="15min")
        component_series = {
            ("comstock", "MediumOffice"): _make_time_series(timestamps, value=100.0),
            ("comstock", "RetailStripmall"): _make_time_series(timestamps, value=10.0),
        }

        with pytest.raises(ValueError, match="Missing weight"):
            combine_composite_time_series(
                composite,
                component_series,
                weights={("comstock", "MediumOffice"): 2.0},
            )

    def test_records_the_applied_weights_on_the_result(self):
        composite = CompositeBuildingType.from_fractions("Mixed", {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3})
        timestamps = pd.date_range("2018-01-01", periods=4, freq="15min")
        component_series = {
            ("comstock", "MediumOffice"): _make_time_series(timestamps, value=100.0),
            ("comstock", "RetailStripmall"): _make_time_series(timestamps, value=10.0),
        }

        by_fraction = combine_composite_time_series(composite, component_series)
        by_weight = combine_composite_time_series(
            composite, component_series, weights={("comstock", "MediumOffice"): 2.0, ("comstock", "RetailStripmall"): 3.0}
        )

        assert by_fraction.attrs["component_weights"] == {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3}
        assert by_weight.attrs["component_weights"] == {("comstock", "MediumOffice"): 2.0, ("comstock", "RetailStripmall"): 3.0}


class TestResolveFractionWeights:
    """Floor-area fractions -> per-component multipliers of each component's own representative building
    (i.e. a dwelling-unit count for a ResStock component)."""

    def _mixed_composite(self, office_fraction: float = 0.5) -> CompositeBuildingType:
        return CompositeBuildingType.from_fractions(
            "Mixed",
            {
                ("comstock", "MediumOffice"): office_fraction,
                ("resstock", "Multi-Family with 5+ Units"): 1 - office_fraction,
            },
        )

    def test_anchors_total_floor_area_on_the_whole_building_component(self):
        composite = self._mixed_composite()
        component_sqft = {("comstock", "MediumOffice"): 50_000.0, ("resstock", "Multi-Family with 5+ Units"): 900.0}

        weights = resolve_fraction_weights(composite, component_sqft)

        # 50% of the office-anchored 50,000 sqft total = 25,000 sqft of apartments / 900 sqft per unit.
        assert weights[("comstock", "MediumOffice")] == pytest.approx(0.5)
        assert weights[("resstock", "Multi-Family with 5+ Units")] == pytest.approx(25_000 / 900)

    def test_explicit_total_sqft_sizes_every_component(self):
        composite = self._mixed_composite(office_fraction=0.6)
        component_sqft = {("comstock", "MediumOffice"): 50_000.0, ("resstock", "Multi-Family with 5+ Units"): 900.0}

        weights = resolve_fraction_weights(composite, component_sqft, total_sqft=200_000.0)

        assert weights[("comstock", "MediumOffice")] == pytest.approx(0.6 * 200_000 / 50_000)
        assert weights[("resstock", "Multi-Family with 5+ Units")] == pytest.approx(0.4 * 200_000 / 900)

    def test_all_comstock_composite_keeps_bare_fractions(self):
        composite = CompositeBuildingType.from_fractions("Mixed", {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3})
        component_sqft = {("comstock", "MediumOffice"): 50_000.0, ("comstock", "RetailStripmall"): 20_000.0}

        assert resolve_fraction_weights(composite, component_sqft) is None

    def test_all_resstock_composite_keeps_bare_fractions(self):
        """Every component is already a dwelling unit, so a per-unit blend is self-consistent and there's
        no whole-building component to anchor a total floor area on."""
        composite = CompositeBuildingType.from_fractions(
            "Mixed",
            {("resstock", "Multi-Family with 5+ Units"): 0.5, ("resstock", "Single-Family Detached"): 0.5},
        )
        component_sqft = {("resstock", "Multi-Family with 5+ Units"): 900.0, ("resstock", "Single-Family Detached"): 2_000.0}

        assert resolve_fraction_weights(composite, component_sqft) is None

    def test_unknown_component_floor_area_raises(self):
        composite = self._mixed_composite()

        with pytest.raises(ValueError, match="Could not determine floor area"):
            resolve_fraction_weights(composite, {("comstock", "MediumOffice"): 50_000.0})

    def test_non_normalized_fractions_raise(self):
        composite = CompositeBuildingType(
            name="Bad",
            components=(
                CompositeComponent(product="comstock", building_type="MediumOffice", fraction=0.5),
                CompositeComponent(product="resstock", building_type="Multi-Family with 5+ Units", fraction=0.6),
            ),
        )

        with pytest.raises(ValueError, match="must sum to 1"):
            resolve_fraction_weights(composite, {("comstock", "MediumOffice"): 50_000.0, ("resstock", "Multi-Family with 5+ Units"): 900.0})


class TestPullCompositeTimeSeriesMixedProducts:
    """Monkeypatched (no network) coverage of the ComStock + ResStock unit-multiplier weighting."""

    @staticmethod
    def _patch(monkeypatch: pytest.MonkeyPatch, office_sqft: float, unit_sqft: float) -> None:
        office_metadata = pd.DataFrame({"bldg_id": [1], "in.state": "DE", "in.sqft": [office_sqft]})
        multifamily_metadata = pd.DataFrame({"bldg_id": [7, 8], "in.state": "DE", "in.sqft": [unit_sqft, unit_sqft]})

        def fake_process_metadata(self: BuildStockProcessor, save_dir: Path) -> pd.DataFrame:
            return office_metadata if self.building_type == "MediumOffice" else multifamily_metadata

        def fake_process_building_time_series(
            self: BuildStockProcessor, data_frame: pd.DataFrame, save_dir: Path
        ) -> tuple[list[Path], list[str]]:
            bldg_id = int(data_frame["bldg_id"].iloc[0])
            save_dir.mkdir(parents=True, exist_ok=True)
            path = save_dir / f"bldg_{bldg_id}.parquet"
            value = 100.0 if self.building_type == "MediumOffice" else 10.0
            pd.DataFrame(
                {
                    "bldg_id": bldg_id,
                    "timestamp": pd.date_range("2018-01-01", periods=4, freq="6h"),
                    "out.electricity.total.energy_consumption": [value] * 4,
                }
            ).to_parquet(path)
            return [path], [str(bldg_id)]

        monkeypatch.setattr(BuildStockProcessor, "process_metadata", fake_process_metadata)
        monkeypatch.setattr(BuildStockProcessor, "process_building_time_series", fake_process_building_time_series)

    def test_multifamily_component_is_weighted_by_dwelling_unit_count(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._patch(monkeypatch, office_sqft=50_000.0, unit_sqft=900.0)
        composite = CompositeBuildingType.from_fractions(
            "Mixed", {("comstock", "MediumOffice"): 0.5, ("resstock", "Multi-Family with 5+ Units"): 0.5}
        )

        combined, _series = pull_composite_time_series(
            composite, save_dir=tmp_path, state="DE", value_columns=["out.electricity.total.energy_consumption"]
        )

        expected_units = (0.5 * 50_000) / 900
        assert combined["out.electricity.total.energy_consumption"].iloc[0] == pytest.approx(0.5 * 100.0 + expected_units * 10.0)

    def test_total_sqft_overrides_the_inferred_gross_floor_area(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self._patch(monkeypatch, office_sqft=50_000.0, unit_sqft=900.0)
        composite = CompositeBuildingType.from_fractions(
            "Mixed", {("comstock", "MediumOffice"): 0.5, ("resstock", "Multi-Family with 5+ Units"): 0.5}
        )

        combined, _series = pull_composite_time_series(
            composite,
            save_dir=tmp_path,
            state="DE",
            value_columns=["out.electricity.total.energy_consumption"],
            total_sqft=200_000.0,
        )

        expected_office = 0.5 * 200_000 / 50_000
        expected_units = 0.5 * 200_000 / 900
        assert combined["out.electricity.total.energy_consumption"].iloc[0] == pytest.approx(
            expected_office * 100.0 + expected_units * 10.0
        )


class TestPullCompositeTimeSeries:
    """Integration test for the end-to-end download + combine workflow. Makes real network calls."""

    @pytest.mark.integration
    def test_pulls_and_combines_real_comstock_components(self):
        """A same-product (ComStock-only) composite: 70% MediumOffice + 30% RetailStripmall in Delaware."""
        project_root = Path(__file__).parent.parent
        save_dir = project_root / "datasets" / "composite"
        save_dir.mkdir(parents=True, exist_ok=True)

        composite = CompositeBuildingType.from_fractions(
            "70% MediumOffice / 30% RetailStripmall",
            {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3},
        )

        combined, component_series = pull_composite_time_series(
            composite,
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

    @pytest.mark.integration
    def test_target_sqft_scales_result_linearly_with_square_footage_for_a_fixed_building(self):
        """`target_sqft` should scale each component by target_sqft / representative_building_sqft, so
        doubling every target_sqft value should exactly double the combined result -- pinning `bldg_ids`
        isolates this scaling-math invariant from `find_nearest_sqft_bldg_id()`'s own building selection,
        which intentionally picks a *different* (better-matching) building for a different target_sqft
        (see test_target_sqft_picks_a_real_building_close_in_size_to_the_target below)."""
        project_root = Path(__file__).parent.parent
        save_dir = project_root / "datasets" / "composite"
        save_dir.mkdir(parents=True, exist_ok=True)

        composite = CompositeBuildingType.from_fractions(
            "70% MediumOffice / 30% RetailStripmall",
            {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3},
        )
        value_columns = ["out.electricity.total.energy_consumption"]
        target_sqft = {("comstock", "MediumOffice"): 40_000.0, ("comstock", "RetailStripmall"): 20_000.0}

        _combined, component_series = pull_composite_time_series(
            composite, save_dir=save_dir, state="DE", value_columns=value_columns, target_sqft=target_sqft
        )
        # Pin the buildings picked above so both calls below scale the *same* representative building.
        bldg_ids = {key: int(series["bldg_id"].iloc[0]) for key, series in component_series.items()}

        combined, _ = pull_composite_time_series(
            composite, save_dir=save_dir, state="DE", value_columns=value_columns, target_sqft=target_sqft, bldg_ids=bldg_ids
        )
        combined_doubled, _ = pull_composite_time_series(
            composite,
            save_dir=save_dir,
            state="DE",
            value_columns=value_columns,
            target_sqft={key: sqft * 2 for key, sqft in target_sqft.items()},
            bldg_ids=bldg_ids,
        )

        assert combined_doubled["out.electricity.total.energy_consumption"].iloc[0] == pytest.approx(
            2 * combined["out.electricity.total.energy_consumption"].iloc[0]
        )

    @pytest.mark.integration
    def test_target_sqft_picks_a_real_building_close_in_size_to_the_target(self):
        """Without an explicit `bldg_ids` override, target_sqft mode should pick the real sampled building
        whose own floor area is closest to the target (find_nearest_sqft_bldg_id()), not an arbitrary
        "first found" one scaled by a potentially large factor."""
        project_root = Path(__file__).parent.parent
        save_dir = project_root / "datasets" / "composite"
        save_dir.mkdir(parents=True, exist_ok=True)
        office_key = ("comstock", "MediumOffice")

        composite = CompositeBuildingType.from_fractions(
            "70% MediumOffice / 30% RetailStripmall", {office_key: 0.7, ("comstock", "RetailStripmall"): 0.3}
        )
        target_sqft = {office_key: 40_000.0, ("comstock", "RetailStripmall"): 20_000.0}

        processor = ComStockProcessor(
            state="DE", county_name="All", building_type="MediumOffice", upgrade="0", base_dir=save_dir / "comstock"
        )
        metadata = processor.process_metadata(save_dir=processor.base_dir)
        sqft_column = next(c for c in metadata.columns if c.startswith("in.sqft"))
        observed_sqft = pd.to_numeric(metadata[sqft_column], errors="coerce")
        best_possible_distance = (observed_sqft - target_sqft[office_key]).abs().min()

        _combined, component_series = pull_composite_time_series(
            composite, save_dir=save_dir, state="DE", value_columns=["out.electricity.total.energy_consumption"], target_sqft=target_sqft
        )
        chosen_bldg_id = int(component_series[office_key]["bldg_id"].iloc[0])
        chosen_sqft = float(metadata.loc[metadata["bldg_id"] == chosen_bldg_id, sqft_column].iloc[0])

        assert abs(chosen_sqft - target_sqft[office_key]) == pytest.approx(best_possible_distance)

    @pytest.mark.integration
    def test_target_sqft_missing_component_raises(self):
        project_root = Path(__file__).parent.parent
        save_dir = project_root / "datasets" / "composite"
        save_dir.mkdir(parents=True, exist_ok=True)

        composite = CompositeBuildingType.from_fractions(
            "70% MediumOffice / 30% RetailStripmall",
            {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3},
        )

        with pytest.raises(ValueError, match="Missing target_sqft"):
            pull_composite_time_series(
                composite,
                save_dir=save_dir,
                state="DE",
                value_columns=["out.electricity.total.energy_consumption"],
                target_sqft={("comstock", "MediumOffice"): 40_000.0},
            )

    @pytest.mark.integration
    def test_upgrade_by_component_isolates_override_to_matching_component(self):
        """upgrade_by_component should only change the overridden component's own time series -- any
        component NOT in the mapping must stay at the shared `upgrade` (identical to a plain baseline
        pull), so a single component's upgrade can't accidentally bleed into an unrelated one."""
        project_root = Path(__file__).parent.parent
        save_dir = project_root / "datasets" / "composite"
        save_dir.mkdir(parents=True, exist_ok=True)

        composite = CompositeBuildingType.from_fractions(
            "70% MediumOffice / 30% RetailStripmall",
            {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3},
        )
        value_columns = ["out.electricity.total.energy_consumption"]
        office_key = ("comstock", "MediumOffice")
        retail_key = ("comstock", "RetailStripmall")

        _combined_baseline, component_series_baseline = pull_composite_time_series(
            composite, save_dir=save_dir, state="DE", value_columns=value_columns
        )
        _combined_override, component_series_override = pull_composite_time_series(
            composite,
            save_dir=save_dir,
            state="DE",
            value_columns=value_columns,
            upgrade_by_component={office_key: "1"},
        )

        # RetailStripmall wasn't overridden -- it must stay at the shared baseline upgrade, unaffected.
        pd.testing.assert_frame_equal(
            component_series_override[retail_key].reset_index(drop=True),
            component_series_baseline[retail_key].reset_index(drop=True),
        )
        # MediumOffice *was* overridden to upgrade "1" -- its profile should differ from the baseline pull.
        office_baseline = component_series_baseline[office_key]["out.electricity.total.energy_consumption"]
        office_override = component_series_override[office_key]["out.electricity.total.energy_consumption"]
        assert not office_baseline.equals(office_override)


class TestPullCompositeTimeSeriesBuildingCondition:
    """Unit test (monkeypatched, no network calls) for `pull_composite_time_series`'s `building_condition`
    parameter -- see `TestPullCompositeTimeSeries` above for the real, network-calling integration tests.
    """

    def test_selects_percentile_band_median_building_instead_of_first_found(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        # Site energy increases monotonically with bldg_id (1,000..100,000), so EUI-based percentile
        # selection is easy to reason about -- p50 +/-5 is already known (from test_building_condition.py)
        # to select bldg_ids 44-53, not bldg_id 0 (which "first building found" would pick instead).
        office_metadata = pd.DataFrame(
            {
                "bldg_id": range(100),
                "in.state": "DE",
                "in.sqft": 50_000.0,
                "out.electricity.total.energy_consumption": [float(i + 1) * 1_000.0 for i in range(100)],
                "out.site_energy.total.energy_consumption": [float(i + 1) * 1_000.0 for i in range(100)],
            }
        )
        retail_metadata = pd.DataFrame(
            {
                "bldg_id": range(20),
                "in.state": "DE",
                "in.sqft": 20_000.0,
                "out.electricity.total.energy_consumption": 35_000.0,
            }
        )
        requested_bldg_ids: list[int] = []

        def fake_process_metadata(self: BuildStockProcessor, save_dir: Path) -> pd.DataFrame:
            return office_metadata if self.building_type == "MediumOffice" else retail_metadata

        def fake_process_building_time_series(
            self: BuildStockProcessor, data_frame: pd.DataFrame, save_dir: Path
        ) -> tuple[list[Path], list[str]]:
            bldg_id = int(data_frame["bldg_id"].iloc[0])
            requested_bldg_ids.append(bldg_id)
            save_dir.mkdir(parents=True, exist_ok=True)
            path = save_dir / f"bldg_{bldg_id}.parquet"
            pd.DataFrame(
                {
                    "bldg_id": bldg_id,
                    "timestamp": pd.date_range("2018-01-01", periods=4, freq="6h"),
                    "out.electricity.total.energy_consumption": [float(bldg_id)] * 4,
                }
            ).to_parquet(path)
            return [path], [str(bldg_id)]

        monkeypatch.setattr(BuildStockProcessor, "process_metadata", fake_process_metadata)
        monkeypatch.setattr(BuildStockProcessor, "process_building_time_series", fake_process_building_time_series)

        composite = CompositeBuildingType.from_fractions("Mixed", {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3})

        pull_composite_time_series(
            composite,
            save_dir=tmp_path,
            state="DE",
            value_columns=["out.electricity.total.energy_consumption"],
            building_condition={("comstock", "MediumOffice"): 50},
        )

        office_bldg_id = requested_bldg_ids[0]
        assert 44 <= office_bldg_id <= 53
        assert office_bldg_id != 0

    def test_explicit_bldg_id_takes_precedence_over_building_condition(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        office_metadata = pd.DataFrame(
            {
                "bldg_id": range(100),
                "in.state": "DE",
                "in.sqft": 50_000.0,
                "out.electricity.total.energy_consumption": [float(i + 1) * 1_000.0 for i in range(100)],
                "out.site_energy.total.energy_consumption": [float(i + 1) * 1_000.0 for i in range(100)],
            }
        )
        retail_metadata = pd.DataFrame(
            {
                "bldg_id": range(20),
                "in.state": "DE",
                "in.sqft": 20_000.0,
                "out.electricity.total.energy_consumption": 35_000.0,
            }
        )
        requested_bldg_ids: list[int] = []

        def fake_process_metadata(self: BuildStockProcessor, save_dir: Path) -> pd.DataFrame:
            return office_metadata if self.building_type == "MediumOffice" else retail_metadata

        def fake_process_building_time_series(
            self: BuildStockProcessor, data_frame: pd.DataFrame, save_dir: Path
        ) -> tuple[list[Path], list[str]]:
            bldg_id = int(data_frame["bldg_id"].iloc[0])
            requested_bldg_ids.append(bldg_id)
            save_dir.mkdir(parents=True, exist_ok=True)
            path = save_dir / f"bldg_{bldg_id}.parquet"
            pd.DataFrame(
                {
                    "bldg_id": bldg_id,
                    "timestamp": pd.date_range("2018-01-01", periods=4, freq="6h"),
                    "out.electricity.total.energy_consumption": [float(bldg_id)] * 4,
                }
            ).to_parquet(path)
            return [path], [str(bldg_id)]

        monkeypatch.setattr(BuildStockProcessor, "process_metadata", fake_process_metadata)
        monkeypatch.setattr(BuildStockProcessor, "process_building_time_series", fake_process_building_time_series)

        composite = CompositeBuildingType.from_fractions("Mixed", {("comstock", "MediumOffice"): 0.7, ("comstock", "RetailStripmall"): 0.3})

        pull_composite_time_series(
            composite,
            save_dir=tmp_path,
            state="DE",
            value_columns=["out.electricity.total.energy_consumption"],
            bldg_ids={("comstock", "MediumOffice"): 7},
            building_condition={("comstock", "MediumOffice"): 50},
        )

        assert requested_bldg_ids[0] == 7
