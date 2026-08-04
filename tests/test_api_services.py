"""Unit tests for the pure-python parts of api/services.py (composite resolution, column matching, record
conversion, resampling). No network calls -- these use the packaged, offline ENERGY STAR crosswalk and
synthetic time series data. Endpoints that need real ComStock/ResStock data are covered by
tests/test_api_main.py's integration tests instead.
"""

import io
import zipfile
from pathlib import Path

import pandas as pd
import pytest

import buildstock_processor.location as location_module
from api.config import Settings
from api.schemas import (
    BuildingEnergyModelRequest,
    CompositeComponentSpec,
    CompositeResolveRequest,
    EnergyStarComponentIn,
    EuiDistributionRequest,
    EuiPercentileBuildingsRequest,
    MeasuresCompareRequest,
    MetadataSummaryRequest,
)
from api.services import (
    ServiceError,
    _find_column,
    _frame_to_records,
    _resample_hourly,
    _sqft_bounds_warning,
    _sqft_scaling_note,
    _weighted_percentile,
    build_building_energy_models,
    compare_measures,
    get_building_energy_model_manifest,
    get_eui_distribution,
    get_eui_percentile_buildings,
    get_metadata_summary,
    list_available_counties,
    list_available_states,
    list_building_types,
    resolve_composite,
)


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(cache_dir=tmp_path, default_state="DE", cors_origins=[])


class TestResolveComposite:
    @pytest.mark.unit
    def test_resolves_exact_and_approximate_matches(self, tmp_path: Path) -> None:
        request = CompositeResolveRequest(
            components=[
                EnergyStarComponentIn(energy_star_property_type="Supermarket/Grocery Store", fraction=0.7),
                EnergyStarComponentIn(energy_star_property_type="Bank Branch", fraction=0.3),
            ]
        )

        response = resolve_composite(request, _make_settings(tmp_path))

        assert response.ok is True
        assert response.unmapped == []
        assert len(response.resolvable) == 2
        by_type = {c.building_type: c for c in response.resolvable}
        assert by_type["Grocery"].fraction == pytest.approx(0.7)
        assert by_type["SmallOffice"].fraction == pytest.approx(0.3)

    @pytest.mark.unit
    def test_unmapped_type_excluded_from_resolvable_and_fractions_renormalized(self, tmp_path: Path) -> None:
        request = CompositeResolveRequest(
            components=[
                EnergyStarComponentIn(energy_star_property_type="Bank Branch", fraction=0.5),
                EnergyStarComponentIn(energy_star_property_type="Zoo", fraction=0.5),
            ]
        )

        response = resolve_composite(request, _make_settings(tmp_path))

        assert response.unmapped == ["Zoo"]
        assert len(response.resolvable) == 1
        # Only one resolvable component -- its fraction is renormalized to 1.0.
        assert response.resolvable[0].fraction == pytest.approx(1.0)
        assert response.total_fraction == pytest.approx(1.0)

    @pytest.mark.unit
    def test_unrecognized_property_type_name_is_unmapped(self, tmp_path: Path) -> None:
        request = CompositeResolveRequest(components=[EnergyStarComponentIn(energy_star_property_type="Not A Real Type", fraction=1.0)])

        response = resolve_composite(request, _make_settings(tmp_path))

        assert response.unmapped == ["Not A Real Type"]
        assert response.resolvable == []
        assert response.components[0].match_quality == "unmapped"

    @pytest.mark.unit
    def test_all_unmapped_gives_empty_resolvable_without_dividing_by_zero(self, tmp_path: Path) -> None:
        request = CompositeResolveRequest(
            components=[
                EnergyStarComponentIn(energy_star_property_type="Zoo", fraction=0.6),
                EnergyStarComponentIn(energy_star_property_type="Swimming Pool", fraction=0.4),
            ]
        )

        response = resolve_composite(request, _make_settings(tmp_path))

        assert response.resolvable == []
        assert response.unmapped == ["Zoo", "Swimming Pool"]

    @pytest.mark.unit
    def test_sqft_mode_derives_fractions_and_passes_through_absolute_sqft(self, tmp_path: Path) -> None:
        request = CompositeResolveRequest(
            components=[
                EnergyStarComponentIn(energy_star_property_type="Supermarket/Grocery Store", sqft=70_000),
                EnergyStarComponentIn(energy_star_property_type="Bank Branch", sqft=30_000),
            ]
        )

        response = resolve_composite(request, _make_settings(tmp_path))

        assert response.total_sqft == pytest.approx(100_000)
        by_type = {c.building_type: c for c in response.resolvable}
        assert by_type["Grocery"].fraction == pytest.approx(0.7)
        assert by_type["Grocery"].sqft == pytest.approx(70_000)
        assert by_type["SmallOffice"].fraction == pytest.approx(0.3)
        assert by_type["SmallOffice"].sqft == pytest.approx(30_000)

    @pytest.mark.unit
    def test_sqft_mode_unmapped_type_keeps_absolute_sqft_on_resolvable_subset(self, tmp_path: Path) -> None:
        """Unlike fraction, sqft isn't renormalized when an entry is dropped as unmapped -- it stays the
        literal square footage the user entered for the remaining resolvable components."""
        request = CompositeResolveRequest(
            components=[
                EnergyStarComponentIn(energy_star_property_type="Bank Branch", sqft=50_000),
                EnergyStarComponentIn(energy_star_property_type="Zoo", sqft=50_000),
            ]
        )

        response = resolve_composite(request, _make_settings(tmp_path))

        assert response.unmapped == ["Zoo"]
        assert len(response.resolvable) == 1
        assert response.resolvable[0].fraction == pytest.approx(1.0)
        assert response.resolvable[0].sqft == pytest.approx(50_000)
        assert response.total_sqft == pytest.approx(100_000)

    @pytest.mark.unit
    def test_sqft_mode_without_state_does_not_auto_select_bldg_id(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No `state` given -> stays a fast, offline crosswalk lookup; no metadata download attempted."""
        called = False

        def fake_build_processor(*args: object, **kwargs: object) -> object:
            nonlocal called
            called = True
            raise AssertionError("should not be called")

        monkeypatch.setattr("api.services._build_processor", fake_build_processor)
        request = CompositeResolveRequest(components=[EnergyStarComponentIn(energy_star_property_type="Bank Branch", sqft=50_000)])

        response = resolve_composite(request, _make_settings(tmp_path))

        assert called is False
        assert response.resolvable[0].bldg_id is None
        assert response.warnings == []

    @pytest.mark.unit
    def test_sqft_mode_with_state_auto_selects_bldg_id(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        metadata = pd.DataFrame({"bldg_id": [1, 2, 3], "in.sqft": [10_000.0, 50_000.0, 100_000.0]})

        class _FakeProcessor:
            base_dir = tmp_path

            def process_metadata(self, save_dir: Path) -> pd.DataFrame:
                return metadata

        def fake_build_processor(*args: object, **kwargs: object) -> _FakeProcessor:
            return _FakeProcessor()

        monkeypatch.setattr("api.services._build_processor", fake_build_processor)
        request = CompositeResolveRequest(
            components=[EnergyStarComponentIn(energy_star_property_type="Bank Branch", sqft=50_000)],
            state="DE",
        )

        response = resolve_composite(request, _make_settings(tmp_path))

        assert response.resolvable[0].bldg_id == 2
        assert response.components[0].bldg_id == 2
        assert response.warnings == []

    @pytest.mark.unit
    def test_sqft_mode_bldg_id_lookup_failure_warns_but_does_not_raise(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_build_processor(*args: object, **kwargs: object) -> object:
            raise RuntimeError("network down")

        monkeypatch.setattr("api.services._build_processor", fake_build_processor)
        request = CompositeResolveRequest(
            components=[EnergyStarComponentIn(energy_star_property_type="Bank Branch", sqft=50_000)],
            state="DE",
        )

        response = resolve_composite(request, _make_settings(tmp_path))

        assert response.ok is True
        assert response.resolvable[0].bldg_id is None
        assert response.warnings
        assert "network down" in response.warnings[0]

    @pytest.mark.unit
    def test_mixed_fraction_and_sqft_components_rejected(self):
        with pytest.raises(ValueError, match="same mode"):
            CompositeResolveRequest(
                components=[
                    EnergyStarComponentIn(energy_star_property_type="Bank Branch", fraction=0.5),
                    EnergyStarComponentIn(energy_star_property_type="Supermarket/Grocery Store", sqft=50_000),
                ]
            )

    @pytest.mark.unit
    def test_component_with_neither_fraction_nor_sqft_rejected(self):
        with pytest.raises(ValueError, match="exactly one"):
            EnergyStarComponentIn(energy_star_property_type="Bank Branch")

    @pytest.mark.unit
    def test_component_with_both_fraction_and_sqft_rejected(self):
        with pytest.raises(ValueError, match="exactly one"):
            EnergyStarComponentIn(energy_star_property_type="Bank Branch", fraction=0.5, sqft=50_000)


class TestResolveCompositeDirectBuildstockType:
    """Entering a ComStock/ResStock building type directly (skipping the ENERGY STAR crosswalk) -- see
    EnergyStarComponentIn.product/building_type."""

    @pytest.mark.unit
    def test_component_with_neither_energy_star_nor_buildstock_type_rejected(self):
        with pytest.raises(ValueError, match="exactly one"):
            EnergyStarComponentIn(fraction=1.0)

    @pytest.mark.unit
    def test_component_with_both_energy_star_and_buildstock_type_rejected(self):
        with pytest.raises(ValueError, match="exactly one"):
            EnergyStarComponentIn(energy_star_property_type="Bank Branch", product="comstock", building_type="SmallOffice", fraction=1.0)

    @pytest.mark.unit
    def test_component_with_only_product_and_not_building_type_rejected(self):
        with pytest.raises(ValueError, match="both must be set together"):
            EnergyStarComponentIn(product="comstock", fraction=1.0)

    @pytest.mark.unit
    def test_component_with_only_building_type_and_not_product_rejected(self):
        with pytest.raises(ValueError, match="both must be set together"):
            EnergyStarComponentIn(building_type="SmallOffice", fraction=1.0)

    @pytest.mark.unit
    def test_mixing_energy_star_and_direct_buildstock_components_rejected(self):
        with pytest.raises(ValueError, match="same type source"):
            CompositeResolveRequest(
                components=[
                    EnergyStarComponentIn(energy_star_property_type="Bank Branch", fraction=0.5),
                    EnergyStarComponentIn(product="comstock", building_type="MediumOffice", fraction=0.5),
                ]
            )

    @pytest.mark.unit
    def test_direct_buildstock_type_resolves_without_crosswalk(self, tmp_path: Path) -> None:
        request = CompositeResolveRequest(
            components=[
                EnergyStarComponentIn(product="comstock", building_type="MediumOffice", fraction=0.6),
                EnergyStarComponentIn(product="resstock", building_type="Multi-Family with 5+ Units", fraction=0.4),
            ]
        )

        response = resolve_composite(request, _make_settings(tmp_path))

        assert response.unmapped == []
        assert len(response.resolvable) == 2
        by_type = {c.building_type: c for c in response.resolvable}
        assert by_type["MediumOffice"].product == "comstock"
        assert by_type["MediumOffice"].fraction == pytest.approx(0.6)
        assert by_type["Multi-Family with 5+ Units"].product == "resstock"
        assert response.components[0].match_quality == "exact"
        assert "Directly-selected" in response.components[0].notes

    @pytest.mark.unit
    def test_invalid_building_type_for_product_is_unmapped(self, tmp_path: Path) -> None:
        request = CompositeResolveRequest(
            components=[EnergyStarComponentIn(product="comstock", building_type="NotARealType", fraction=1.0)]
        )

        response = resolve_composite(request, _make_settings(tmp_path))

        assert response.resolvable == []
        assert response.components[0].match_quality == "unmapped"
        assert response.unmapped == ["NotARealType (comstock)"]

    @pytest.mark.unit
    def test_direct_buildstock_type_sqft_mode_auto_selects_bldg_id(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        metadata = pd.DataFrame({"bldg_id": [1, 2, 3], "in.sqft": [10_000.0, 50_000.0, 100_000.0]})

        class _FakeProcessor:
            base_dir = tmp_path

            def process_metadata(self, save_dir: Path) -> pd.DataFrame:
                return metadata

        monkeypatch.setattr("api.services._build_processor", lambda *_args, **_kwargs: _FakeProcessor())
        request = CompositeResolveRequest(
            components=[EnergyStarComponentIn(product="comstock", building_type="MediumOffice", sqft=50_000)],
            state="DE",
        )

        response = resolve_composite(request, _make_settings(tmp_path))

        assert response.resolvable[0].bldg_id == 2


class TestListBuildingTypes:
    @pytest.mark.unit
    def test_lists_comstock_building_types(self) -> None:
        response = list_building_types("comstock")

        assert response.ok is True
        assert response.product == "comstock"
        assert "MediumOffice" in response.building_types
        assert "All" not in response.building_types

    @pytest.mark.unit
    def test_lists_resstock_building_types(self) -> None:
        response = list_building_types("resstock")

        assert response.product == "resstock"
        assert "Multi-Family with 5+ Units" in response.building_types
        assert "All" not in response.building_types


class TestFindColumn:
    @pytest.mark.unit
    def test_matches_bare_column_name(self):
        columns = pd.Index(["bldg_id", "out.electricity.total.energy_consumption"])
        assert _find_column(columns, "out.electricity.total.energy_consumption") == "out.electricity.total.energy_consumption"

    @pytest.mark.unit
    def test_matches_unit_suffixed_column_name(self):
        columns = pd.Index(["bldg_id", "out.electricity.total.energy_consumption..kwh"])
        assert _find_column(columns, "out.electricity.total.energy_consumption") == "out.electricity.total.energy_consumption..kwh"

    @pytest.mark.unit
    def test_returns_none_when_not_found(self):
        columns = pd.Index(["bldg_id"])
        assert _find_column(columns, "out.does_not_exist") is None


class TestSqftBoundsWarning:
    """Test cases for _sqft_bounds_warning() -- e.g. a user picking "LargeOffice" but entering a target
    square footage smaller than any sampled LargeOffice building should get a clear out-of-bounds warning.
    """

    @staticmethod
    def _component() -> CompositeComponentSpec:
        return CompositeComponentSpec(product="comstock", building_type="LargeOffice", fraction=1.0)

    @pytest.mark.unit
    def test_target_within_observed_range_gives_no_warning(self):
        metadata = pd.DataFrame({"in.sqft": [10_000, 20_000, 30_000]})

        warning = _sqft_bounds_warning(self._component(), metadata, "in.sqft", 15_000)

        assert warning is None

    @pytest.mark.unit
    def test_target_below_observed_minimum_warns(self):
        metadata = pd.DataFrame({"in.sqft": [10_000, 20_000, 30_000]})

        warning = _sqft_bounds_warning(self._component(), metadata, "in.sqft", 5_000)

        assert warning is not None
        assert "5,000" in warning
        assert "10,000-30,000" in warning
        assert "LargeOffice" in warning
        assert "comstock" in warning

    @pytest.mark.unit
    def test_target_above_observed_maximum_warns(self):
        metadata = pd.DataFrame({"in.sqft": [10_000, 20_000, 30_000]})

        warning = _sqft_bounds_warning(self._component(), metadata, "in.sqft", 100_000)

        assert warning is not None
        assert "100,000" in warning

    @pytest.mark.unit
    def test_target_exactly_at_bounds_gives_no_warning(self):
        metadata = pd.DataFrame({"in.sqft": [10_000, 20_000, 30_000]})

        assert _sqft_bounds_warning(self._component(), metadata, "in.sqft", 10_000) is None
        assert _sqft_bounds_warning(self._component(), metadata, "in.sqft", 30_000) is None

    @pytest.mark.unit
    def test_missing_sqft_column_gives_no_warning(self):
        metadata = pd.DataFrame({"bldg_id": [1, 2, 3]})

        assert _sqft_bounds_warning(self._component(), metadata, None, 5_000) is None

    @pytest.mark.unit
    def test_empty_sqft_values_gives_no_warning(self):
        metadata = pd.DataFrame({"in.sqft": [None, None]})

        assert _sqft_bounds_warning(self._component(), metadata, "in.sqft", 5_000) is None

    @pytest.mark.unit
    def test_uses_label_over_building_type_when_set(self):
        metadata = pd.DataFrame({"in.sqft": [10_000, 20_000, 30_000]})
        component = CompositeComponentSpec(product="comstock", building_type="LargeOffice", fraction=1.0, label="My Office")

        warning = _sqft_bounds_warning(component, metadata, "in.sqft", 5_000)

        assert warning is not None
        assert "My Office" in warning


class TestSqftBoundsWarningResStock:
    """A ResStock component's `in.sqft` metadata is one sampled *dwelling's* floor area -- either a
    multifamily unit or a whole standalone single-family/mobile home (every ResStock row is one dwelling
    either way, see `resstock.py`'s module docstring) -- not an arbitrary total. So an entered `target_sqft`
    representing many dwellings' worth of total floor area is expected to exceed a single dwelling's sqft,
    and shouldn't be flagged as "outside the range" the way an oversized ComStock building would be. Only a
    target too small to represent even one whole dwelling is a genuine extrapolation concern. This applies
    equally to multifamily units and single-family/mobile homes -- a "500,000 sqft subdivision" component
    is just as valid a multi-dwelling total as a "80,000 sqft apartment building" one.
    """

    @staticmethod
    def _multifamily_component() -> CompositeComponentSpec:
        return CompositeComponentSpec(product="resstock", building_type="Multi-Family with 5+ Units", fraction=1.0)

    @staticmethod
    def _single_family_component() -> CompositeComponentSpec:
        return CompositeComponentSpec(product="resstock", building_type="Single-Family Detached", fraction=1.0)

    @pytest.mark.unit
    def test_multifamily_target_far_above_observed_unit_range_gives_no_warning(self):
        metadata = pd.DataFrame({"in.sqft": [500, 850, 1_200]})

        # 80,000 sqft is way outside the per-unit range, but represents ~94 units -- a normal, valid entry.
        warning = _sqft_bounds_warning(self._multifamily_component(), metadata, "in.sqft", 80_000)

        assert warning is None

    @pytest.mark.unit
    def test_multifamily_target_below_smallest_sampled_unit_warns(self):
        metadata = pd.DataFrame({"in.sqft": [500, 850, 1_200]})

        warning = _sqft_bounds_warning(self._multifamily_component(), metadata, "in.sqft", 300)

        assert warning is not None
        assert "300" in warning
        assert "500" in warning
        assert "one whole" in warning

    @pytest.mark.unit
    def test_single_family_target_far_above_observed_home_range_gives_no_warning(self):
        metadata = pd.DataFrame({"in.sqft": [1_000, 2_000, 3_000]})

        # 500,000 sqft represents ~250 homes in a subdivision -- also a normal, valid entry, not "one
        # impossibly large house".
        warning = _sqft_bounds_warning(self._single_family_component(), metadata, "in.sqft", 500_000)

        assert warning is None

    @pytest.mark.unit
    def test_single_family_target_below_smallest_sampled_home_warns(self):
        metadata = pd.DataFrame({"in.sqft": [1_000, 2_000, 3_000]})

        warning = _sqft_bounds_warning(self._single_family_component(), metadata, "in.sqft", 500)

        assert warning is not None
        assert "500" in warning
        assert "one whole" in warning

    @pytest.mark.unit
    def test_comstock_component_still_uses_whole_building_bounds_check(self):
        """Unlike ResStock, ComStock's `in.sqft` IS the whole (single) building's floor area, so both
        bounds still apply -- unchanged from the original ComStock-only behavior."""
        component = CompositeComponentSpec(product="comstock", building_type="LargeOffice", fraction=1.0)
        metadata = pd.DataFrame({"in.sqft": [10_000, 20_000, 30_000]})

        warning = _sqft_bounds_warning(component, metadata, "in.sqft", 100_000)

        assert warning is not None
        assert "10,000-30,000" in warning


class TestSqftScalingNoteResStock:
    @pytest.mark.unit
    def test_multifamily_note_mentions_units_not_building(self):
        component = CompositeComponentSpec(product="resstock", building_type="Multi-Family with 5+ Units", fraction=1.0)

        note = _sqft_scaling_note(component, 850, 80_000)

        assert note is not None
        assert "unit" in note
        assert "building" not in note

    @pytest.mark.unit
    def test_single_family_note_mentions_homes_not_building(self):
        component = CompositeComponentSpec(product="resstock", building_type="Single-Family Detached", fraction=1.0)

        note = _sqft_scaling_note(component, 2_000, 500_000)

        assert note is not None
        assert "home" in note
        assert "building" not in note


class TestFrameToRecords:
    @pytest.mark.unit
    def test_preserves_dotted_column_names(self):
        """Regression test: pandas' itertuples()/namedtuple path silently mangles column names containing
        dots (like every BuildStock out.* column) into _1, _2, ... -- _frame_to_records() must not do that."""
        frame = pd.DataFrame(
            {
                "timestamp": pd.date_range("2018-01-01", periods=2, freq="h"),
                "out.electricity.total.energy_consumption": [1.5, 2.5],
            }
        )

        records = _frame_to_records(frame)

        assert records[0]["timestamp"] == "2018-01-01T00:00:00"
        assert records[0]["out.electricity.total.energy_consumption"] == 1.5
        assert records[1]["out.electricity.total.energy_consumption"] == 2.5
        assert "_1" not in records[0]

    @pytest.mark.unit
    def test_nan_values_become_none(self):
        frame = pd.DataFrame(
            {
                "timestamp": pd.date_range("2018-01-01", periods=1, freq="h"),
                "out.electricity.total.energy_consumption": [float("nan")],
            }
        )

        records = _frame_to_records(frame)

        assert records[0]["out.electricity.total.energy_consumption"] is None


class TestResampleHourly:
    @pytest.mark.unit
    def test_sums_15_minute_intervals_into_hours(self):
        timestamps = pd.date_range("2018-01-01", periods=4, freq="15min")
        frame = pd.DataFrame({"timestamp": timestamps, "out.electricity.total.energy_consumption": [1.0, 1.0, 1.0, 1.0]})

        resampled = _resample_hourly(frame, ["out.electricity.total.energy_consumption"])

        assert len(resampled) == 1
        assert resampled["out.electricity.total.energy_consumption"].iloc[0] == pytest.approx(4.0)

    @pytest.mark.unit
    def test_truncates_to_8760_rows(self):
        timestamps = pd.date_range("2018-01-01", periods=8761 * 4, freq="15min")
        frame = pd.DataFrame({"timestamp": timestamps, "out.electricity.total.energy_consumption": 1.0})

        resampled = _resample_hourly(frame, ["out.electricity.total.energy_consumption"])

        assert len(resampled) == 8760


class TestServiceErrorIsValueError:
    @pytest.mark.unit
    def test_service_error_is_a_value_error(self):
        assert issubclass(ServiceError, ValueError)


class TestListAvailableStates:
    @pytest.mark.unit
    def test_returns_states_from_location_module(self, monkeypatch, tmp_path):
        def fake_list_available_states(product, save_dir, release=None):
            return ["CA", "DE"]

        monkeypatch.setattr(location_module, "list_available_states", fake_list_available_states)
        settings = Settings(cache_dir=tmp_path, default_state="DE", cors_origins=[])

        result = list_available_states("comstock", settings)

        assert result.ok is True
        assert result.product == "comstock"
        assert result.states == ["CA", "DE"]

    @pytest.mark.unit
    def test_wraps_exceptions_in_service_error(self, monkeypatch, tmp_path):
        def _raise(product, save_dir, release=None):
            raise RuntimeError("boom")

        monkeypatch.setattr(location_module, "list_available_states", _raise)
        settings = Settings(cache_dir=tmp_path, default_state="DE", cors_origins=[])

        with pytest.raises(ServiceError):
            list_available_states("comstock", settings)


class TestListAvailableCounties:
    @pytest.mark.unit
    def test_returns_counties_and_note_from_location_module(self, monkeypatch, tmp_path):
        def fake_list_available_counties(product, state, save_dir, release=None):
            return ["Kent County", "New Castle County"]

        monkeypatch.setattr(location_module, "list_available_counties", fake_list_available_counties)
        settings = Settings(cache_dir=tmp_path, default_state="DE", cors_origins=[])

        result = list_available_counties("comstock", "DE", settings)

        assert result.ok is True
        assert result.state == "DE"
        assert result.counties == ["Kent County", "New Castle County"]
        assert "All" in result.note

    @pytest.mark.unit
    def test_wraps_exceptions_in_service_error(self, monkeypatch, tmp_path):
        def _raise(product, state, save_dir, release=None):
            raise RuntimeError("boom")

        monkeypatch.setattr(location_module, "list_available_counties", _raise)
        settings = Settings(cache_dir=tmp_path, default_state="DE", cors_origins=[])

        with pytest.raises(ServiceError):
            list_available_counties("comstock", "DE", settings)


class TestWeightedPercentile:
    @pytest.mark.unit
    def test_equal_weights_matches_simple_percentile_shape(self):
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        weights = [1.0, 1.0, 1.0, 1.0, 1.0]

        median = _weighted_percentile(values, weights, 50.0)

        assert median == pytest.approx(30.0, abs=1.0)

    @pytest.mark.unit
    def test_below_range_returns_minimum(self):
        assert _weighted_percentile([10.0, 20.0], [1.0, 1.0], 0.0) == 10.0

    @pytest.mark.unit
    def test_above_range_returns_maximum(self):
        assert _weighted_percentile([10.0, 20.0], [1.0, 1.0], 100.0) == 20.0

    @pytest.mark.unit
    def test_heavier_weight_pulls_percentile_toward_it(self):
        # A much heavier weight on the first value should pull the median down toward it.
        values = [10.0, 20.0, 30.0]
        weights = [10.0, 1.0, 1.0]

        median = _weighted_percentile(values, weights, 50.0)

        assert median < 20.0


class TestGetEuiDistribution:
    """Uses a fake `_build_processor` returning synthetic per-component metadata (bldg_id/in.sqft/site
    energy) so this exercises the pure aggregation/percentile-selection logic without any network access.
    """

    @staticmethod
    def _fake_metadata(bldg_ids: list[int], sqft: list[float], site_energy_kwh: list[float]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "bldg_id": bldg_ids,
                "in.sqft": sqft,
                "out.site_energy.total.energy_consumption": site_energy_kwh,
            }
        )

    @pytest.mark.unit
    def test_single_component_distribution_and_percentiles(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # site EUI (kBtu/ft2) = energy_kwh * 3.412141633 / sqft; sqft is held constant at 1000 so EUI ranks
        # follow energy directly: [10, 20, ..., 100] kWh -> EUI ~ [34.1, 68.2, ..., 341.2].
        metadata = self._fake_metadata(
            bldg_ids=list(range(1, 11)),
            sqft=[1_000.0] * 10,
            site_energy_kwh=[10.0 * i for i in range(1, 11)],
        )

        class _FakeProcessor:
            base_dir = tmp_path

            def process_metadata(self, save_dir: Path) -> pd.DataFrame:
                return metadata

        monkeypatch.setattr("api.services._build_processor", lambda *_args, **_kwargs: _FakeProcessor())

        request = EuiDistributionRequest(
            components=[CompositeComponentSpec(product="comstock", building_type="SmallOffice", fraction=1.0)],
            state="DE",
            curve_points=11,
        )
        settings = _make_settings(tmp_path)

        response = get_eui_distribution(request, settings)

        assert response.ok is True
        assert response.sample_size == 10
        assert len(response.curve) == 11
        # Now a density-shaped curve (x = site EUI, y = peak-normalized density 0-1), not a percentile-rank
        # line -- eui_kbtu_per_ft2 is monotonically increasing (evenly-spaced x-positions), and each point
        # still carries its own percentile rank so the frontend can map a click back to a percentile.
        assert all(response.curve[i].eui_kbtu_per_ft2 <= response.curve[i + 1].eui_kbtu_per_ft2 for i in range(len(response.curve) - 1))
        assert all(0.0 <= point.density <= 1.0 for point in response.curve)
        assert max(point.density for point in response.curve) == pytest.approx(1.0)
        assert all(0.0 <= point.percentile <= 100.0 for point in response.curve)
        assert response.mean_eui_kbtu_per_ft2 == pytest.approx(0.18767, rel=0.01)

        labels = {p.label for p in response.percentiles}
        assert labels == {"5th percentile", "25th percentile", "Median (50th)", "Average", "75th percentile", "95th percentile"}

        median = next(p for p in response.percentiles if p.label == "Median (50th)")
        assert median.bldg_ids == {"comstock:SmallOffice": pytest.approx(median.bldg_ids["comstock:SmallOffice"])}
        # Median building should be a real bldg_id from the sample.
        assert median.bldg_ids["comstock:SmallOffice"] in range(1, 11)

        low = next(p for p in response.percentiles if p.label == "5th percentile")
        high = next(p for p in response.percentiles if p.label == "95th percentile")
        assert low.eui_kbtu_per_ft2 < median.eui_kbtu_per_ft2 < high.eui_kbtu_per_ft2

    @pytest.mark.unit
    def test_multi_component_composite_weights_by_fraction(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        office_metadata = self._fake_metadata([1, 2, 3], [1_000.0, 1_000.0, 1_000.0], [10.0, 20.0, 30.0])
        retail_metadata = self._fake_metadata([101, 102, 103], [2_000.0, 2_000.0, 2_000.0], [40.0, 50.0, 60.0])

        class _FakeProcessor:
            def __init__(self, metadata: pd.DataFrame) -> None:
                self._metadata = metadata
                self.base_dir = tmp_path

            def process_metadata(self, save_dir: Path) -> pd.DataFrame:
                return self._metadata

        def fake_build_processor(base_cache_dir, product, state, county_name, building_type, *args, **kwargs):
            return _FakeProcessor(office_metadata if building_type == "SmallOffice" else retail_metadata)

        monkeypatch.setattr("api.services._build_processor", fake_build_processor)

        request = EuiDistributionRequest(
            components=[
                CompositeComponentSpec(product="comstock", building_type="SmallOffice", fraction=0.5),
                CompositeComponentSpec(product="comstock", building_type="RetailStandalone", fraction=0.5),
            ],
            state="DE",
        )
        settings = _make_settings(tmp_path)

        response = get_eui_distribution(request, settings)

        assert response.sample_size == 6
        average = next(p for p in response.percentiles if p.label == "Average")
        assert set(average.bldg_ids.keys()) == {"comstock:SmallOffice", "comstock:RetailStandalone"}
        assert average.bldg_ids["comstock:SmallOffice"] in {1, 2, 3}
        assert average.bldg_ids["comstock:RetailStandalone"] in {101, 102, 103}

    @pytest.mark.unit
    def test_missing_columns_component_excluded_with_warning(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        metadata = pd.DataFrame({"bldg_id": [1, 2], "some_other_column": [1, 2]})

        class _FakeProcessor:
            base_dir = tmp_path

            def process_metadata(self, save_dir: Path) -> pd.DataFrame:
                return metadata

        monkeypatch.setattr("api.services._build_processor", lambda *_args, **_kwargs: _FakeProcessor())

        request = EuiDistributionRequest(
            components=[CompositeComponentSpec(product="comstock", building_type="SmallOffice", fraction=1.0)],
            state="DE",
        )
        settings = _make_settings(tmp_path)

        with pytest.raises(ServiceError, match="No component had a usable site EUI"):
            get_eui_distribution(request, settings)


class TestGetEuiPercentileBuildings:
    """Uses the same fake `_build_processor`/metadata pattern as TestGetEuiDistribution."""

    @staticmethod
    def _fake_metadata(bldg_ids: list[int], sqft: list[float], site_energy_kwh: list[float]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "bldg_id": bldg_ids,
                "in.sqft": sqft,
                "out.site_energy.total.energy_consumption": site_energy_kwh,
            }
        )

    @pytest.mark.unit
    def test_returns_candidates_near_requested_percentile(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # EUI ranks follow energy directly since sqft is constant: bldg 1 (lowest EUI) -> bldg 10 (highest).
        metadata = self._fake_metadata(
            bldg_ids=list(range(1, 11)),
            sqft=[1_000.0] * 10,
            site_energy_kwh=[10.0 * i for i in range(1, 11)],
        )

        class _FakeProcessor:
            base_dir = tmp_path

            def process_metadata(self, save_dir: Path) -> pd.DataFrame:
                return metadata

        monkeypatch.setattr("api.services._build_processor", lambda *_args, **_kwargs: _FakeProcessor())

        request = EuiPercentileBuildingsRequest(
            components=[CompositeComponentSpec(product="comstock", building_type="SmallOffice", fraction=1.0)],
            state="DE",
            percentile=50.0,
            band=15.0,
        )
        settings = _make_settings(tmp_path)

        response = get_eui_percentile_buildings(request, settings)

        assert response.ok is True
        assert response.percentile == 50.0
        assert len(response.components) == 1
        component = response.components[0]
        assert component.product == "comstock"
        assert component.building_type == "SmallOffice"
        # The selected building should be the closest-ranked candidate (first in the sorted list).
        assert component.selected_bldg_id == component.candidates[0].bldg_id
        # A +/-15 percentile-point band around the median of 10 evenly-spaced buildings should catch
        # more than just one candidate.
        assert len(component.candidates) > 1
        # Candidates should be sorted by closeness to the target percentile.
        distances = [abs(c.percentile_rank - 50.0) for c in component.candidates]
        assert distances == sorted(distances)

    @pytest.mark.unit
    def test_narrow_band_with_no_matches_falls_back_to_closest_building(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        metadata = self._fake_metadata(bldg_ids=[1, 2, 3], sqft=[1_000.0] * 3, site_energy_kwh=[10.0, 50.0, 100.0])

        class _FakeProcessor:
            base_dir = tmp_path

            def process_metadata(self, save_dir: Path) -> pd.DataFrame:
                return metadata

        monkeypatch.setattr("api.services._build_processor", lambda *_args, **_kwargs: _FakeProcessor())

        request = EuiPercentileBuildingsRequest(
            components=[CompositeComponentSpec(product="comstock", building_type="SmallOffice", fraction=1.0)],
            state="DE",
            percentile=50.0,
            band=0.001,
        )
        settings = _make_settings(tmp_path)

        response = get_eui_percentile_buildings(request, settings)

        assert len(response.components[0].candidates) >= 1

    @pytest.mark.unit
    def test_max_candidates_per_component_caps_results(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        metadata = self._fake_metadata(
            bldg_ids=list(range(1, 21)),
            sqft=[1_000.0] * 20,
            site_energy_kwh=[10.0 * i for i in range(1, 21)],
        )

        class _FakeProcessor:
            base_dir = tmp_path

            def process_metadata(self, save_dir: Path) -> pd.DataFrame:
                return metadata

        monkeypatch.setattr("api.services._build_processor", lambda *_args, **_kwargs: _FakeProcessor())

        request = EuiPercentileBuildingsRequest(
            components=[CompositeComponentSpec(product="comstock", building_type="SmallOffice", fraction=1.0)],
            state="DE",
            percentile=50.0,
            band=50.0,
            max_candidates_per_component=3,
        )
        settings = _make_settings(tmp_path)

        response = get_eui_percentile_buildings(request, settings)

        assert len(response.components[0].candidates) == 3

    @pytest.mark.unit
    def test_multi_component_resolves_each_independently(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        office_metadata = self._fake_metadata([1, 2, 3], [1_000.0] * 3, [10.0, 20.0, 30.0])
        retail_metadata = self._fake_metadata([101, 102, 103], [2_000.0] * 3, [40.0, 50.0, 60.0])

        class _FakeProcessor:
            def __init__(self, metadata: pd.DataFrame) -> None:
                self._metadata = metadata
                self.base_dir = tmp_path

            def process_metadata(self, save_dir: Path) -> pd.DataFrame:
                return self._metadata

        def fake_build_processor(base_cache_dir, product, state, county_name, building_type, *args, **kwargs):
            return _FakeProcessor(office_metadata if building_type == "SmallOffice" else retail_metadata)

        monkeypatch.setattr("api.services._build_processor", fake_build_processor)

        request = EuiPercentileBuildingsRequest(
            components=[
                CompositeComponentSpec(product="comstock", building_type="SmallOffice", fraction=0.5),
                CompositeComponentSpec(product="comstock", building_type="RetailStandalone", fraction=0.5),
            ],
            state="DE",
            percentile=50.0,
        )
        settings = _make_settings(tmp_path)

        response = get_eui_percentile_buildings(request, settings)

        assert len(response.components) == 2
        building_types = {c.building_type for c in response.components}
        assert building_types == {"SmallOffice", "RetailStandalone"}
        office_component = next(c for c in response.components if c.building_type == "SmallOffice")
        retail_component = next(c for c in response.components if c.building_type == "RetailStandalone")
        assert office_component.selected_bldg_id in {1, 2, 3}
        assert retail_component.selected_bldg_id in {101, 102, 103}


class TestBuildingEnergyModelDownload:
    """Uses a fake `_build_processor` so these exercise the pure resolution/packaging logic in
    `get_building_energy_model_manifest()`/`build_building_energy_models()` without any network access.
    """

    @staticmethod
    def _fake_processor_factory(tmp_path: Path, bldg_ids: list[int] | None = None, product: str = "comstock"):
        bldg_ids = bldg_ids or [1, 2, 3]
        metadata = pd.DataFrame({"bldg_id": bldg_ids, "in.sqft": [1_000.0 * (i + 1) for i in range(len(bldg_ids))]})

        class _FakeProcessor:
            base_dir = tmp_path

            def process_metadata(self, save_dir: Path) -> pd.DataFrame:
                return metadata

            def building_energy_model_filename(self, bldg_id: int, upgrade: str | None = None) -> str:
                ext = "zip" if product == "resstock" else "osm.gz"
                return f"{product}-bldg{bldg_id:07d}-up{int(upgrade or '0'):02d}.{ext}"

            def download_building_energy_model(self, bldg_id: int, save_dir: Path, upgrade: str | None = None) -> Path:
                save_dir.mkdir(parents=True, exist_ok=True)
                path = save_dir / self.building_energy_model_filename(bldg_id, upgrade)
                path.write_bytes(f"fake-model-{bldg_id}".encode())
                return path

        return _FakeProcessor

    @pytest.mark.unit
    def test_manifest_resolves_first_bldg_id_when_nothing_pinned(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_cls = self._fake_processor_factory(tmp_path, bldg_ids=[42, 43])
        monkeypatch.setattr("api.services._build_processor", lambda *_args, **_kwargs: fake_cls())

        request = BuildingEnergyModelRequest(
            components=[CompositeComponentSpec(product="comstock", building_type="SmallOffice", fraction=1.0)],
            state="DE",
        )
        response = get_building_energy_model_manifest(request, _make_settings(tmp_path))

        assert response.ok is True
        assert response.components[0].bldg_id == 42
        assert response.components[0].filename == "comstock-bldg0000042-up00.osm.gz"

    @pytest.mark.unit
    def test_manifest_uses_pinned_component_bldg_id(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_cls = self._fake_processor_factory(tmp_path, bldg_ids=[42, 43])
        monkeypatch.setattr("api.services._build_processor", lambda *_args, **_kwargs: fake_cls())

        request = BuildingEnergyModelRequest(
            components=[CompositeComponentSpec(product="comstock", building_type="SmallOffice", fraction=1.0, bldg_id=99)],
            state="DE",
        )
        response = get_building_energy_model_manifest(request, _make_settings(tmp_path))

        # 99 wasn't in the fake sample, but a pinned bldg_id is trusted directly (no metadata lookup) --
        # mirrors _pull_timeseries()'s own precedence (see _resolve_component_bldg_ids's docstring).
        assert response.components[0].bldg_id == 99

    @pytest.mark.unit
    def test_manifest_explicit_override_takes_priority_over_pinned(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_cls = self._fake_processor_factory(tmp_path, bldg_ids=[42, 43])
        monkeypatch.setattr("api.services._build_processor", lambda *_args, **_kwargs: fake_cls())

        request = BuildingEnergyModelRequest(
            components=[CompositeComponentSpec(product="comstock", building_type="SmallOffice", fraction=1.0, bldg_id=99)],
            state="DE",
            bldg_ids={"comstock:SmallOffice": 7},
        )
        response = get_building_energy_model_manifest(request, _make_settings(tmp_path))

        assert response.components[0].bldg_id == 7

    @pytest.mark.unit
    def test_manifest_sqft_mode_picks_nearest_bldg_id(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_cls = self._fake_processor_factory(tmp_path, bldg_ids=[1, 2, 3])  # sqft: 1000, 2000, 3000
        monkeypatch.setattr("api.services._build_processor", lambda *_args, **_kwargs: fake_cls())

        request = BuildingEnergyModelRequest(
            components=[CompositeComponentSpec(product="comstock", building_type="SmallOffice", fraction=1.0, sqft=1_900.0)],
            state="DE",
        )
        response = get_building_energy_model_manifest(request, _make_settings(tmp_path))

        assert response.components[0].bldg_id == 2

    @pytest.mark.unit
    def test_build_single_component_returns_native_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_cls = self._fake_processor_factory(tmp_path, bldg_ids=[42])
        monkeypatch.setattr("api.services._build_processor", lambda *_args, **_kwargs: fake_cls())

        request = BuildingEnergyModelRequest(
            components=[CompositeComponentSpec(product="comstock", building_type="SmallOffice", fraction=1.0)],
            state="DE",
        )
        content, filename, media_type = build_building_energy_models(request, _make_settings(tmp_path))

        assert filename == "comstock-bldg0000042-up00.osm.gz"
        assert media_type == "application/gzip"
        assert content == b"fake-model-42"

    @pytest.mark.unit
    def test_build_multi_component_returns_zip_bundle(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        comstock_cls = self._fake_processor_factory(tmp_path, bldg_ids=[42], product="comstock")
        resstock_cls = self._fake_processor_factory(tmp_path, bldg_ids=[7], product="resstock")

        def fake_build_processor(cache_dir, product, *args, **kwargs):
            return comstock_cls() if product == "comstock" else resstock_cls()

        monkeypatch.setattr("api.services._build_processor", fake_build_processor)

        request = BuildingEnergyModelRequest(
            components=[
                CompositeComponentSpec(product="comstock", building_type="SmallOffice", fraction=0.6),
                CompositeComponentSpec(product="resstock", building_type="Single-Family Detached", fraction=0.4),
            ],
            state="DE",
        )
        content, filename, media_type = build_building_energy_models(request, _make_settings(tmp_path))

        assert filename.endswith(".zip")
        assert media_type == "application/zip"

        zf = zipfile.ZipFile(io.BytesIO(content))
        assert set(zf.namelist()) == {"comstock-bldg0000042-up00.osm.gz", "resstock-bldg0000007-up00.zip"}


class TestGetMetadataSummaryHonorsPinnedBldgId:
    """A pinned `CompositeComponentSpec.bldg_id` (e.g. from the builder's EUI-percentile picker) should
    restrict this summary to that one real building's own values, not the full building type's population
    mean -- otherwise the Dashboard silently shows a different EUI than the one the user explicitly picked.
    """

    @staticmethod
    def _fake_metadata() -> pd.DataFrame:
        return pd.DataFrame(
            {
                "bldg_id": [1, 2, 3],
                "in.sqft": [1_000.0, 2_000.0, 3_000.0],
                "out.site_energy.total.energy_consumption": [50.0, 100.0, 900.0],
            }
        )

    @pytest.mark.unit
    def test_pinned_bldg_id_restricts_to_that_building(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        metadata = self._fake_metadata()

        class _FakeProcessor:
            base_dir = tmp_path

            def process_metadata(self, save_dir: Path) -> pd.DataFrame:
                return metadata

        monkeypatch.setattr("api.services._build_processor", lambda *_args, **_kwargs: _FakeProcessor())

        request = MetadataSummaryRequest(
            components=[CompositeComponentSpec(product="comstock", building_type="SmallOffice", fraction=1.0, bldg_id=2)],
            state="DE",
            upgrade="0",
        )
        settings = _make_settings(tmp_path)

        response = get_metadata_summary(request, settings)

        component = response.components[0]
        assert component.building_count == 1
        assert component.avg_sqft == 2_000.0
        # EUI for bldg_id 2: 100 kWh * 3.412141633 / 2000 sqft.
        assert component.site_eui_kbtu_per_ft2 == pytest.approx(100.0 * 3.412141633 / 2000.0, rel=1e-6)

    @pytest.mark.unit
    def test_no_pinned_bldg_id_uses_population_mean(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        metadata = self._fake_metadata()

        class _FakeProcessor:
            base_dir = tmp_path

            def process_metadata(self, save_dir: Path) -> pd.DataFrame:
                return metadata

        monkeypatch.setattr("api.services._build_processor", lambda *_args, **_kwargs: _FakeProcessor())

        request = MetadataSummaryRequest(
            components=[CompositeComponentSpec(product="comstock", building_type="SmallOffice", fraction=1.0)],
            state="DE",
            upgrade="0",
        )
        settings = _make_settings(tmp_path)

        response = get_metadata_summary(request, settings)

        component = response.components[0]
        assert component.building_count == 3
        assert component.avg_sqft == pytest.approx(2_000.0)


class TestCompareMeasuresHonorsPinnedBldgId:
    """Mirrors TestGetMetadataSummaryHonorsPinnedBldgId, for compare_measures()."""

    @staticmethod
    def _fake_metadata_for_upgrades() -> pd.DataFrame:
        return pd.DataFrame(
            {
                "bldg_id": [1, 2, 1, 2],
                "upgrade": ["0", "0", "1", "1"],
                "in.sqft": [1_000.0, 2_000.0, 1_000.0, 2_000.0],
                "out.electricity.total.energy_consumption": [100.0, 200.0, 80.0, 150.0],
            }
        )

    @pytest.mark.unit
    def test_pinned_bldg_id_restricts_baseline_and_upgrade_to_that_building(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        metadata = self._fake_metadata_for_upgrades()

        class _FakeProcessor:
            base_dir = tmp_path

            def process_metadata_for_upgrades(self, save_dir: Path, upgrades: list[str]) -> pd.DataFrame:
                return metadata

            def list_upgrades(self, save_dir: Path) -> dict[str, str]:
                return {"0": "Baseline", "1": "Some Package"}

        monkeypatch.setattr("api.services._build_processor", lambda *_args, **_kwargs: _FakeProcessor())

        request = MeasuresCompareRequest(
            components=[CompositeComponentSpec(product="comstock", building_type="SmallOffice", fraction=1.0, bldg_id=2)],
            state="DE",
            baseline_upgrade="0",
            comparison_upgrades=["1"],
            columns=["out.electricity.total.energy_consumption"],
        )
        settings = _make_settings(tmp_path)

        response = compare_measures(request, settings)

        savings = response.results["out.electricity.total.energy_consumption"][0]
        # bldg_id 2: baseline 200 kWh, upgrade 150 kWh -- not the population-mean baseline (150) that
        # would result from averaging bldg_id 1 and 2 together.
        assert savings.baseline_kwh == pytest.approx(200.0)
        assert savings.upgrade_kwh == pytest.approx(150.0)
