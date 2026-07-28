"""Unit tests for the packaged ENERGY STAR Portfolio Manager -> BuildStock crosswalk."""

import pytest

from buildstock_processor import (
    ComStockProcessor,
    EnergyStarMapping,
    ResStockProcessor,
    energy_star_crosswalk,
    energy_star_property_types_for_buildstock_type,
    list_energy_star_property_types,
    map_energy_star_property_type,
)


class TestEnergyStarCrosswalk:
    """Test the static ENERGY STAR <-> BuildStock crosswalk API."""

    @pytest.mark.unit
    def test_crosswalk_is_non_empty_and_cached(self):
        crosswalk = energy_star_crosswalk()

        assert len(crosswalk) > 0
        assert crosswalk is energy_star_crosswalk()
        assert all(isinstance(entry, EnergyStarMapping) for entry in crosswalk)

    @pytest.mark.unit
    def test_list_energy_star_property_types_includes_known_types(self):
        types = list_energy_star_property_types()

        assert "Office" in types
        assert "Single Family Home" in types
        assert len(types) == len(energy_star_crosswalk())

    @pytest.mark.unit
    def test_map_energy_star_property_type_is_case_insensitive(self):
        exact = map_energy_star_property_type("Fast Food Restaurant")
        lower = map_energy_star_property_type("fast food restaurant")
        padded = map_energy_star_property_type("  Fast Food Restaurant  ")

        assert exact == lower == padded
        assert exact is not None
        assert exact.buildstock_product == "comstock"
        assert exact.buildstock_building_type == "QuickServiceRestaurant"
        assert exact.match_quality == "exact"

    @pytest.mark.unit
    def test_map_energy_star_property_type_returns_none_for_unknown_type(self):
        assert map_energy_star_property_type("Not A Real Property Type") is None

    @pytest.mark.unit
    def test_unmapped_entries_have_no_buildstock_type(self):
        zoo = map_energy_star_property_type("Zoo")

        assert zoo is not None
        assert zoo.match_quality == "unmapped"
        assert zoo.buildstock_product is None
        assert zoo.buildstock_building_type is None

    @pytest.mark.unit
    def test_residential_property_type_maps_to_resstock(self):
        single_family = map_energy_star_property_type("Single Family Home")

        assert single_family is not None
        assert single_family.buildstock_product == "resstock"
        assert single_family.buildstock_building_type == "Single-Family Detached"

    @pytest.mark.unit
    def test_every_mapped_building_type_is_a_real_buildstock_type(self):
        comstock_types = set(ComStockProcessor.building_types)
        resstock_types = set(ResStockProcessor.building_types)

        for entry in energy_star_crosswalk():
            if entry.match_quality == "unmapped":
                assert entry.buildstock_product is None
                assert entry.buildstock_building_type is None
                continue

            assert entry.buildstock_product in {"comstock", "resstock"}
            if entry.buildstock_product == "comstock":
                assert entry.buildstock_building_type in comstock_types
            else:
                assert entry.buildstock_building_type in resstock_types

    @pytest.mark.unit
    def test_energy_star_property_types_for_buildstock_type_reverse_lookup(self):
        office_types = energy_star_property_types_for_buildstock_type("comstock", "SmallOffice")

        assert "Bank Branch" in office_types
        assert "Financial Office" in office_types

        multifamily_types = energy_star_property_types_for_buildstock_type("resstock", "Multi-Family with 5+ Units")
        assert "Multifamily Housing" in multifamily_types

    @pytest.mark.unit
    def test_energy_star_property_types_for_buildstock_type_is_case_insensitive(self):
        assert energy_star_property_types_for_buildstock_type("ComStock", "smalloffice") == energy_star_property_types_for_buildstock_type(
            "comstock", "SmallOffice"
        )

    @pytest.mark.unit
    def test_energy_star_property_types_for_buildstock_type_returns_empty_for_unknown_type(self):
        assert energy_star_property_types_for_buildstock_type("comstock", "NotARealBuildingType") == ()
