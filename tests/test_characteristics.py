"""Unit tests for building-characteristic constraints (no network)."""

from pathlib import Path

import pandas as pd
import pytest

from building_energy_profiles import BuildingCharacteristics, ComStockProcessor, ResStockProcessor
from building_energy_profiles.composite import CompositeBuildingType, CompositeComponent
from building_energy_profiles.portfolio import PortfolioComponent


def _comstock_meta() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "bldg_id": [1, 2, 3, 4, 5],
            "in.heating_fuel": ["NaturalGas", "Electricity", "DistrictHeating", "Electricity", "Propane"],
            "in.service_water_heating_fuel": ["NaturalGas", "NaturalGas", "DistrictHeating", "Electricity", "Propane"],
            "in.hvac_category": ["A", "B", "A", "B", "A"],
            "out.natural_gas.total.energy_consumption..kwh": [100.0, 5.0, 0.0, 0.0, 0.0],
            "out.district_heating.total.energy_consumption..kwh": [0.0, 0.0, 50.0, 0.0, 0.0],
            "in.hvac_cool_type": ["DX", "ASHP", "District", "WCC", "DX"],
            "out.district_cooling.total.energy_consumption..kwh": [0.0, 0.0, 80.0, 0.0, 0.0],
        }
    )


def _resstock_meta() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "bldg_id": [10, 11, 12],
            "in.heating_fuel": ["Natural Gas", "Electricity", "Fuel Oil"],
            "in.water_heater_fuel": ["Natural Gas", "Electricity", "Electricity"],
            "out.natural_gas.total.energy_consumption..kwh": [10.0, 0.0, 0.0],
            "in.hvac_cooling_type": ["Central AC", "Ducted Heat Pump", "Room AC"],
        }
    )


class TestBuildingCharacteristics:
    def test_heating_fuel_maps_product_vocabulary(self):
        c = BuildingCharacteristics(heating_fuel="natural_gas")
        assert c.apply(_comstock_meta(), "ComStock")["bldg_id"].tolist() == [1]
        assert c.apply(_resstock_meta(), "ResStock")["bldg_id"].tolist() == [10]

    def test_fuel_names_are_normalized_and_validated(self):
        assert BuildingCharacteristics(heating_fuel=["Natural Gas", "fuel-oil"]).heating_fuel == ("natural_gas", "fuel_oil")
        with pytest.raises(ValueError, match="Unknown heating_fuel"):
            BuildingCharacteristics(heating_fuel="coal")

    def test_has_natural_gas_uses_consumption_not_heating_fuel(self):
        # bldg 2 is electrically heated but still burns gas (e.g. water heating) -> it "has natural gas"
        kept = BuildingCharacteristics(has_natural_gas=True).apply(_comstock_meta(), "comstock")
        assert kept["bldg_id"].tolist() == [1, 2]
        all_electric_or_other = BuildingCharacteristics(has_natural_gas=False).apply(_comstock_meta(), "comstock")
        assert all_electric_or_other["bldg_id"].tolist() == [3, 4, 5]

    def test_has_district_heating(self):
        assert BuildingCharacteristics(has_district_heating=True).apply(_comstock_meta(), "comstock")["bldg_id"].tolist() == [3]
        assert BuildingCharacteristics(has_district_heating=False).apply(_comstock_meta(), "comstock")["bldg_id"].tolist() == [1, 2, 4, 5]

    def test_district_heating_absent_column_resstock(self):
        # ResStock models no district heating: requiring it gives nothing, excluding it keeps everything
        assert BuildingCharacteristics(has_district_heating=True).apply(_resstock_meta(), "resstock").empty
        assert len(BuildingCharacteristics(has_district_heating=False).apply(_resstock_meta(), "resstock")) == 3

    def test_presence_flags_use_baseline_ids(self):
        upgrade = _comstock_meta().assign(**{"out.natural_gas.total.energy_consumption..kwh": 0.0})  # electrified
        baseline = _comstock_meta()
        kept = BuildingCharacteristics(has_natural_gas=True).apply(upgrade, "comstock", baseline_df=baseline)
        assert kept["bldg_id"].tolist() == [1, 2]

    def test_water_heating_and_attributes_combine(self):
        c = BuildingCharacteristics(water_heating_fuel="natural_gas", attributes={"in.hvac_category": ["B"]})
        assert c.apply(_comstock_meta(), "comstock")["bldg_id"].tolist() == [2]

    def test_missing_attribute_column_raises(self):
        with pytest.raises(KeyError, match=r"in\.nope"):
            BuildingCharacteristics(attributes={"in.nope": 1}).apply(_comstock_meta(), "comstock")

    def test_coerce_and_label(self):
        assert BuildingCharacteristics.coerce(None) is None
        assert BuildingCharacteristics.coerce({}) is None
        c = BuildingCharacteristics.coerce({"heating_fuel": "natural_gas", "has_district_heating": False})
        assert c is not None
        assert c.label() == "hf_natural_gas-dh0"
        assert c.to_dict() == {"heating_fuel": ["natural_gas"], "has_district_heating": False}
        with pytest.raises(ValueError, match="Unknown building characteristics"):
            BuildingCharacteristics.coerce({"heating": "gas"})
        with_attributes = BuildingCharacteristics(attributes={"in.hvac_category": "A"})
        assert with_attributes.label().startswith("attr_")
        assert with_attributes.label() == BuildingCharacteristics(attributes={"in.hvac_category": ["A"]}).label()


class TestProcessorIntegration:
    def test_processor_cache_name_includes_label(self, tmp_path: Path):
        plain = ComStockProcessor("DC", "All", "MediumOffice", "0", tmp_path)
        gas = ComStockProcessor("DC", "All", "MediumOffice", "0", tmp_path, characteristics={"heating_fuel": "natural_gas"})
        assert plain.characteristics is None
        assert "hf_natural_gas" not in plain._selected_metadata_path(tmp_path, "0").name
        assert "-hf_natural_gas-0-selected_metadata.csv" in gas._selected_metadata_path(tmp_path, "0").name

    def test_processor_applies_characteristics(self, tmp_path: Path):
        processor = ComStockProcessor("DC", "All", "All", "0", tmp_path, characteristics={"has_natural_gas": True})
        assert processor._apply_characteristics(_comstock_meta(), tmp_path, "0")["bldg_id"].tolist() == [1, 2]

    def test_non_baseline_upgrade_uses_baseline_presence(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        processor = ComStockProcessor("DC", "All", "All", "5", tmp_path, characteristics={"has_natural_gas": True})
        calls = []

        def fake_baseline(save_dir, upgrade):
            calls.append(upgrade)
            return _comstock_meta().iloc[:2]

        monkeypatch.setattr(processor, "_download_metadata_for_upgrade", fake_baseline)
        electrified = _comstock_meta().assign(**{"out.natural_gas.total.energy_consumption..kwh": 0.0})
        assert processor._apply_characteristics(electrified, tmp_path, "5")["bldg_id"].tolist() == [1, 2]
        assert calls == ["0"]

    def test_resstock_processor_accepts_characteristics(self, tmp_path: Path):
        processor = ResStockProcessor(
            "DC", "All", "Multi-Family with 5+ Units", "0", tmp_path, characteristics={"heating_fuel": "electricity"}
        )
        assert processor._apply_characteristics(_resstock_meta(), tmp_path, "0")["bldg_id"].tolist() == [11]

    def test_composite_and_portfolio_components_carry_characteristics(self):
        component = CompositeComponent("comstock", "MediumOffice", 0.6, characteristics={"heating_fuel": "natural_gas"})
        assert isinstance(component.characteristics, BuildingCharacteristics)
        composite = CompositeBuildingType("x", (component, CompositeComponent("comstock", "RetailStripmall", 0.6))).normalized()
        assert composite.components[0].characteristics == component.characteristics
        assert composite.components[1].characteristics is None
        portfolio = PortfolioComponent("comstock", "MediumOffice", target_sqft=1000, characteristics={"has_district_heating": False})
        assert portfolio.characteristics is not None
        assert portfolio.characteristics.has_district_heating is False


class TestDistrictCooling:
    """District cooling is handled like district heating: by results (`has_district_cooling`) and inputs (`cooling_type`)."""

    def test_has_district_cooling(self):
        meta = _comstock_meta()
        assert BuildingCharacteristics(has_district_cooling=True).apply(meta, "comstock")["bldg_id"].tolist() == [3]
        assert BuildingCharacteristics(has_district_cooling=False).apply(meta, "comstock")["bldg_id"].tolist() == [1, 2, 4, 5]

    def test_cooling_type_matches_presence_flag(self):
        meta = _comstock_meta()
        by_input = BuildingCharacteristics(cooling_type="district").apply(meta, "comstock")["bldg_id"].tolist()
        by_result = BuildingCharacteristics(has_district_cooling=True).apply(meta, "comstock")["bldg_id"].tolist()
        assert by_input == by_result == [3]

    def test_cooling_type_vocabulary(self):
        meta = _comstock_meta()
        assert BuildingCharacteristics(cooling_type=["chiller", "heat_pump"]).apply(meta, "comstock")["bldg_id"].tolist() == [2, 4]
        assert BuildingCharacteristics(cooling_type="dx").apply(_resstock_meta(), "resstock")["bldg_id"].tolist() == [10, 12]

    def test_resstock_has_no_district_cooling(self):
        res = _resstock_meta()
        assert BuildingCharacteristics(has_district_cooling=True).apply(res, "resstock").empty
        assert len(BuildingCharacteristics(has_district_cooling=False).apply(res, "resstock")) == 3
        assert BuildingCharacteristics(cooling_type="district").apply(res, "resstock").empty

    def test_district_heating_and_cooling_together(self):
        c = BuildingCharacteristics(has_district_heating=True, has_district_cooling=True)
        assert c.apply(_comstock_meta(), "comstock")["bldg_id"].tolist() == [3]
        assert c.label() == "dh1-dc1"

    def test_cooling_type_label_dict_and_errors(self):
        c = BuildingCharacteristics.coerce({"cooling_type": "District", "has_district_cooling": True})
        assert c.label() == "ct_district-dc1"
        assert c.to_dict() == {"cooling_type": ["district"], "has_district_cooling": True}
        with pytest.raises(ValueError, match="cooling_type"):
            BuildingCharacteristics(cooling_type="evaporative")


class TestRelaxation:
    def _meta(self):
        # 3 district-heated buildings, only 1 of them without district cooling
        return pd.DataFrame(
            {
                "bldg_id": [1, 2, 3, 4, 5],
                "in.heating_fuel": ["DistrictHeating", "DistrictHeating", "DistrictHeating", "NaturalGas", "Electricity"],
                "in.service_water_heating_fuel": ["NaturalGas"] * 5,
                "in.hvac_cool_type": ["DX", "District", "District", "DX", "DX"],
                "out.natural_gas.total.energy_consumption..kwh": [5.0, 5.0, 5.0, 100.0, 0.0],
                "out.district_heating.total.energy_consumption..kwh": [50.0, 50.0, 50.0, 0.0, 0.0],
                "out.district_cooling.total.energy_consumption..kwh": [0.0, 80.0, 80.0, 0.0, 0.0],
            }
        )

    def test_drops_one_constraint_at_a_time(self):
        c = BuildingCharacteristics(has_district_heating=True, has_district_cooling=False, has_natural_gas=True)
        out, used, dropped = c.apply_with_relaxation(self._meta(), "comstock", min_count=3)
        # has_natural_gas goes first (still 1), then has_district_cooling -> the 3 district-heated buildings remain
        assert dropped == ["has_natural_gas", "has_district_cooling"]
        assert out["bldg_id"].tolist() == [1, 2, 3]
        assert used.to_dict() == {"has_district_heating": True}

    def test_no_relaxation_needed(self):
        c = BuildingCharacteristics(has_district_heating=True)
        out, used, dropped = c.apply_with_relaxation(self._meta(), "comstock", min_count=2)
        assert dropped == []
        assert used is c
        assert len(out) == 3

    def test_falls_back_to_unconstrained(self):
        c = BuildingCharacteristics(has_district_heating=True)
        out, used, dropped = c.apply_with_relaxation(self._meta(), "comstock", min_count=5)
        assert used is None
        assert dropped == ["has_district_heating"]
        assert len(out) == 5
