"""Unit tests for packaged BuildStock data dictionaries."""

import pytest

from building_energy_profiles import (
    BuildStock,
    ComStockProcessor,
    ResStockProcessor,
    data_dictionary,
    result_variables_from_columns,
)


class TestDataDictionary:
    """Test the static metadata dictionary API."""

    @pytest.mark.unit
    def test_buildstock_catalog_groups_products(self):
        assert BuildStock["comstock"] is ComStockProcessor.data_dictionary
        assert "SmallOffice" in BuildStock.building_types["comstock"]
        assert "Single-Family Detached" in BuildStock.building_types["resstock"]
        assert BuildStock.measure_upgrade_packages["resstock"]["release_1"]["0"] == "Baseline"

    @pytest.mark.unit
    def test_class_level_building_types(self):
        assert "SmallOffice" in ComStockProcessor.building_types
        assert "LargeOffice" in ComStockProcessor.building_types
        assert "Multi-Family with 5+ Units" in ResStockProcessor.building_types

    @pytest.mark.unit
    def test_class_level_data_dictionary_is_cached(self):
        assert ComStockProcessor.data_dictionary is data_dictionary("comstock")
        assert ResStockProcessor.data_dictionary is data_dictionary("resstock")

    @pytest.mark.unit
    def test_result_variables_include_units(self):
        variable = next(item for item in ComStockProcessor.result_variables if item.name == "out.site_energy.total.energy_consumption..kwh")

        assert variable.unit == "kwh"
        assert variable.source == "site_energy"
        assert variable.end_use == "total"
        assert variable.metric == "energy_consumption"
        assert variable in ComStockProcessor.data_dictionary.result_variables_by_unit("kwh")

    @pytest.mark.unit
    def test_upgrade_packages_are_release_specific(self):
        assert ComStockProcessor.data_dictionary.upgrade_packages()["0"] == "Baseline"
        assert ComStockProcessor.data_dictionary.upgrade_packages("release_2")["10"] == "Cold Climate Challenge HP RTU, Electric Backup"
        assert ResStockProcessor.data_dictionary.upgrade_packages()["0"] == "Baseline"

    @pytest.mark.unit
    def test_unknown_upgrade_release_raises(self):
        with pytest.raises(ValueError, match="Unsupported ComStock upgrade-package release"):
            ComStockProcessor.data_dictionary.upgrade_packages("release_99")

    @pytest.mark.unit
    def test_result_variables_from_columns(self):
        variables = result_variables_from_columns(
            [
                "bldg_id",
                "out.electricity.total.energy_consumption..kwh",
                "in.state",
            ]
        )

        assert len(variables) == 1
        assert variables[0].name == "out.electricity.total.energy_consumption..kwh"
        assert variables[0].unit == "kwh"
