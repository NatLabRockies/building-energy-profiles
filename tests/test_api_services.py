"""Unit tests for the pure-python parts of api/services.py (composite resolution, column matching, record
conversion, resampling). No network calls -- these use the packaged, offline ENERGY STAR crosswalk and
synthetic time series data. Endpoints that need real ComStock/ResStock data are covered by
tests/test_api_main.py's integration tests instead.
"""

from pathlib import Path

import pandas as pd
import pytest

import building_energy_profiles.location as location_module
from api.config import Settings
from api.schemas import CompositeComponentSpec, CompositeResolveRequest, EnergyStarComponentIn
from api.services import (
    ServiceError,
    _apply_component_filters,
    _component_scales,
    _find_column,
    _frame_to_records,
    _resample_hourly,
    _sqft_bounds_warning,
    list_available_counties,
    list_available_states,
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


class TestApplyComponentFilters:
    """Test cases for _apply_component_filters() -- narrowing a component's metadata population by
    curated categorical columns (e.g. vintage, HVAC system type) before computing a distribution/summary.
    """

    def _frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "bldg_id": [1, 2, 3, 4],
                "in.vintage": ["1980 to 1989", "1980 to 1989", "2000 to 2012", "2000 to 2012"],
                "in.heating_fuel": ["Electricity", "NaturalGas", "Electricity", "NaturalGas"],
            }
        )

    @pytest.mark.unit
    def test_no_filters_returns_frame_unchanged(self):
        frame = self._frame()
        result = _apply_component_filters(frame, None)
        assert len(result) == len(frame)

    @pytest.mark.unit
    def test_single_column_filter_keeps_matching_rows_only(self):
        result = _apply_component_filters(self._frame(), {"in.vintage": ["1980 to 1989"]})
        assert sorted(result["bldg_id"].tolist()) == [1, 2]

    @pytest.mark.unit
    def test_multiple_values_in_one_column_are_ored(self):
        result = _apply_component_filters(self._frame(), {"in.vintage": ["1980 to 1989", "2000 to 2012"]})
        assert len(result) == 4

    @pytest.mark.unit
    def test_multiple_columns_are_anded(self):
        result = _apply_component_filters(self._frame(), {"in.vintage": ["1980 to 1989"], "in.heating_fuel": ["Electricity"]})
        assert result["bldg_id"].tolist() == [1]

    @pytest.mark.unit
    def test_unknown_column_is_silently_ignored(self):
        result = _apply_component_filters(self._frame(), {"in.does_not_exist": ["whatever"]})
        assert len(result) == 4

    @pytest.mark.unit
    def test_empty_allowed_values_list_is_ignored(self):
        result = _apply_component_filters(self._frame(), {"in.vintage": []})
        assert len(result) == 4

    @pytest.mark.unit
    def test_tolerates_unit_suffixed_column_name(self):
        frame = self._frame().rename(columns={"in.vintage": "in.vintage..yr"})
        result = _apply_component_filters(frame, {"in.vintage": ["1980 to 1989"]})
        assert sorted(result["bldg_id"].tolist()) == [1, 2]

    @pytest.mark.unit
    def test_filter_excluding_everyone_returns_empty_frame(self):
        result = _apply_component_filters(self._frame(), {"in.vintage": ["Before 1946"]})
        assert result.empty


class TestComponentScales:
    """A ResStock row is one dwelling unit, so mixing products has to size components by floor area and
    turn the residential share into a unit count -- see composite.resolve_fraction_weights_for().
    """

    OFFICE = ("comstock", "MediumOffice")
    MULTIFAMILY = ("resstock", "Multi-Family with 5+ Units")

    def _mixed_components(self) -> list[CompositeComponentSpec]:
        return [
            CompositeComponentSpec(product="comstock", building_type="MediumOffice", fraction=0.5),
            CompositeComponentSpec(product="resstock", building_type="Multi-Family with 5+ Units", fraction=0.5),
        ]

    @pytest.mark.unit
    def test_mixed_products_scale_multifamily_by_unit_count(self):
        scales, area_scaled = _component_scales(self._mixed_components(), {self.OFFICE: 50_000.0, self.MULTIFAMILY: 900.0}, None)

        assert area_scaled
        assert scales[self.OFFICE] == pytest.approx(0.5)
        assert scales[self.MULTIFAMILY] == pytest.approx(25_000 / 900)

    @pytest.mark.unit
    def test_all_comstock_keeps_bare_fractions(self):
        components = [
            CompositeComponentSpec(product="comstock", building_type="MediumOffice", fraction=0.7),
            CompositeComponentSpec(product="comstock", building_type="RetailStripmall", fraction=0.3),
        ]

        scales, area_scaled = _component_scales(components, {self.OFFICE: 50_000.0, ("comstock", "RetailStripmall"): 20_000.0}, None)

        assert not area_scaled
        assert scales == {self.OFFICE: 0.7, ("comstock", "RetailStripmall"): 0.3}

    @pytest.mark.unit
    def test_sqft_mode_scales_to_entered_square_footage(self):
        target = {self.OFFICE: 100_000.0, self.MULTIFAMILY: 45_000.0}

        scales, area_scaled = _component_scales(self._mixed_components(), {self.OFFICE: 50_000.0, self.MULTIFAMILY: 900.0}, target)

        assert area_scaled
        assert scales[self.OFFICE] == pytest.approx(2.0)
        assert scales[self.MULTIFAMILY] == pytest.approx(50.0)

    @pytest.mark.unit
    def test_sqft_mode_without_a_known_floor_area_raises(self):
        with pytest.raises(ServiceError, match="Could not determine floor area"):
            _component_scales(self._mixed_components(), {self.OFFICE: 50_000.0}, {self.OFFICE: 100_000.0, self.MULTIFAMILY: 45_000.0})


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
