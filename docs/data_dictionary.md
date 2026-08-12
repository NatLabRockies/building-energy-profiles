# BuildStock Data Dictionary

This file mirrors `src/building_energy_profiles/data_dictionary.json` in a Markdown format that is easy for people and simple tools to parse. The Python API exposes the same data through `BuildStock`, `ComStockProcessor.data_dictionary`, and `ResStockProcessor.data_dictionary`.

Result-variable lists are annual metadata output columns from the current default supported releases: ComStock
`release_3` at `2025/comstock_amy2018_release_3/` and ResStock `release_1` with `weather_year="amy2018"` at
`2025/resstock_amy2018_release_1/`. Upgrade package names are grouped by release because upgrade ids are not
stable across releases.

## ComStock

- Default release: `release_3`
- Record type: commercial whole-building record
- Building type column: `in.comstock_building_type`
- Result variables: 916

### Building Types

- `FullServiceRestaurant`
- `Grocery`
- `Hospital`
- `LargeHotel`
- `LargeOffice`
- `MediumOffice`
- `Outpatient`
- `PrimarySchool`
- `QuickServiceRestaurant`
- `RetailStandalone`
- `RetailStripmall`
- `SecondarySchool`
- `SmallHotel`
- `SmallOffice`
- `Warehouse`

### Result Variables

| Name | Unit | Source | End Use | Metric |
| --- | --- | --- | --- | --- |
| out.district_cooling.cooling.energy_consumption..kwh | kwh | district_cooling | cooling | energy_consumption |
| out.district_cooling.cooling.energy_savings..kwh | kwh | district_cooling | cooling | energy_savings |
| out.district_cooling.total.energy_consumption..kwh | kwh | district_cooling | total | energy_consumption |
| out.district_cooling.total.energy_savings..kwh | kwh | district_cooling | total | energy_savings |
| out.district_heating.cooling.energy_savings..kwh | kwh | district_heating | cooling | energy_savings |
| out.district_heating.heating.energy_consumption..kwh | kwh | district_heating | heating | energy_consumption |
| out.district_heating.heating.energy_savings..kwh | kwh | district_heating | heating | energy_savings |
| out.district_heating.interior_equipment.energy_savings..kwh | kwh | district_heating | interior_equipment | energy_savings |
| out.district_heating.total.energy_consumption..kwh | kwh | district_heating | total | energy_consumption |
| out.district_heating.total.energy_savings..kwh | kwh | district_heating | total | energy_savings |
| out.district_heating.water_systems.energy_consumption..kwh | kwh | district_heating | water_systems | energy_consumption |
| out.district_heating.water_systems.energy_savings..kwh | kwh | district_heating | water_systems | energy_savings |
| out.electricity.cooling.energy_consumption..kwh | kwh | electricity | cooling | energy_consumption |
| out.electricity.cooling.energy_savings..kwh | kwh | electricity | cooling | energy_savings |
| out.electricity.exterior_lighting.energy_consumption..kwh | kwh | electricity | exterior_lighting | energy_consumption |
| out.electricity.exterior_lighting.energy_savings..kwh | kwh | electricity | exterior_lighting | energy_savings |
| out.electricity.fans.energy_consumption..kwh | kwh | electricity | fans | energy_consumption |
| out.electricity.fans.energy_savings..kwh | kwh | electricity | fans | energy_savings |
| out.electricity.heat_recovery.energy_consumption..kwh | kwh | electricity | heat_recovery | energy_consumption |
| out.electricity.heat_recovery.energy_savings..kwh | kwh | electricity | heat_recovery | energy_savings |
| out.electricity.heat_rejection.energy_consumption..kwh | kwh | electricity | heat_rejection | energy_consumption |
| out.electricity.heat_rejection.energy_savings..kwh | kwh | electricity | heat_rejection | energy_savings |
| out.electricity.heating.energy_consumption..kwh | kwh | electricity | heating | energy_consumption |
| out.electricity.heating.energy_savings..kwh | kwh | electricity | heating | energy_savings |
| out.electricity.interior_equipment.energy_consumption..kwh | kwh | electricity | interior_equipment | energy_consumption |
| out.electricity.interior_equipment.energy_savings..kwh | kwh | electricity | interior_equipment | energy_savings |
| out.electricity.interior_lighting.energy_consumption..kwh | kwh | electricity | interior_lighting | energy_consumption |
| out.electricity.interior_lighting.energy_savings..kwh | kwh | electricity | interior_lighting | energy_savings |
| out.electricity.net.energy_consumption..kwh | kwh | electricity | net | energy_consumption |
| out.electricity.net.energy_savings..kwh | kwh | electricity | net | energy_savings |
| out.electricity.pumps.energy_consumption..kwh | kwh | electricity | pumps | energy_consumption |
| out.electricity.pumps.energy_savings..kwh | kwh | electricity | pumps | energy_savings |
| out.electricity.purchased.energy_consumption..kwh | kwh | electricity | purchased | energy_consumption |
| out.electricity.purchased.energy_savings..kwh | kwh | electricity | purchased | energy_savings |
| out.electricity.pv.energy_consumption..kwh | kwh | electricity | pv | energy_consumption |
| out.electricity.pv.energy_savings..kwh | kwh | electricity | pv | energy_savings |
| out.electricity.refrigeration.energy_consumption..kwh | kwh | electricity | refrigeration | energy_consumption |
| out.electricity.refrigeration.energy_savings..kwh | kwh | electricity | refrigeration | energy_savings |
| out.electricity.total.apr.energy_consumption..kwh | kwh | electricity | total | apr.energy_consumption |
| out.electricity.total.aug.energy_consumption..kwh | kwh | electricity | total | aug.energy_consumption |
| out.electricity.total.dec.energy_consumption..kwh | kwh | electricity | total | dec.energy_consumption |
| out.electricity.total.energy_consumption..kwh | kwh | electricity | total | energy_consumption |
| out.electricity.total.energy_savings..kwh | kwh | electricity | total | energy_savings |
| out.electricity.total.feb.energy_consumption..kwh | kwh | electricity | total | feb.energy_consumption |
| out.electricity.total.jan.energy_consumption..kwh | kwh | electricity | total | jan.energy_consumption |
| out.electricity.total.jul.energy_consumption..kwh | kwh | electricity | total | jul.energy_consumption |
| out.electricity.total.jun.energy_consumption..kwh | kwh | electricity | total | jun.energy_consumption |
| out.electricity.total.mar.energy_consumption..kwh | kwh | electricity | total | mar.energy_consumption |
| out.electricity.total.may.energy_consumption..kwh | kwh | electricity | total | may.energy_consumption |
| out.electricity.total.nov.energy_consumption..kwh | kwh | electricity | total | nov.energy_consumption |
| out.electricity.total.oct.energy_consumption..kwh | kwh | electricity | total | oct.energy_consumption |
| out.electricity.total.sep.energy_consumption..kwh | kwh | electricity | total | sep.energy_consumption |
| out.electricity.water_systems.energy_consumption..kwh | kwh | electricity | water_systems | energy_consumption |
| out.electricity.water_systems.energy_savings..kwh | kwh | electricity | water_systems | energy_savings |
| out.fuel_oil.generators.energy_consumption..kwh | kwh | fuel_oil | generators | energy_consumption |
| out.fuel_oil.heating.energy_consumption..kwh | kwh | fuel_oil | heating | energy_consumption |
| out.fuel_oil.heating.energy_savings..kwh | kwh | fuel_oil | heating | energy_savings |
| out.fuel_oil.interior_equipment.energy_savings..kwh | kwh | fuel_oil | interior_equipment | energy_savings |
| out.fuel_oil.total.energy_consumption..kwh | kwh | fuel_oil | total | energy_consumption |
| out.fuel_oil.total.energy_savings..kwh | kwh | fuel_oil | total | energy_savings |
| out.fuel_oil.water_systems.energy_consumption..kwh | kwh | fuel_oil | water_systems | energy_consumption |
| out.fuel_oil.water_systems.energy_savings..kwh | kwh | fuel_oil | water_systems | energy_savings |
| out.natural_gas.cooling.energy_savings..kwh | kwh | natural_gas | cooling | energy_savings |
| out.natural_gas.heating.energy_consumption..kwh | kwh | natural_gas | heating | energy_consumption |
| out.natural_gas.heating.energy_savings..kwh | kwh | natural_gas | heating | energy_savings |
| out.natural_gas.interior_equipment.energy_consumption..kwh | kwh | natural_gas | interior_equipment | energy_consumption |
| out.natural_gas.interior_equipment.energy_savings..kwh | kwh | natural_gas | interior_equipment | energy_savings |
| out.natural_gas.total.energy_consumption..kwh | kwh | natural_gas | total | energy_consumption |
| out.natural_gas.total.energy_savings..kwh | kwh | natural_gas | total | energy_savings |
| out.natural_gas.water_systems.energy_consumption..kwh | kwh | natural_gas | water_systems | energy_consumption |
| out.natural_gas.water_systems.energy_savings..kwh | kwh | natural_gas | water_systems | energy_savings |
| out.other_fuel.total.energy_consumption..kwh | kwh | other_fuel | total | energy_consumption |
| out.propane.generators.energy_consumption..kwh | kwh | propane | generators | energy_consumption |
| out.propane.heating.energy_consumption..kwh | kwh | propane | heating | energy_consumption |
| out.propane.heating.energy_savings..kwh | kwh | propane | heating | energy_savings |
| out.propane.interior_equipment.energy_savings..kwh | kwh | propane | interior_equipment | energy_savings |
| out.propane.total.energy_consumption..kwh | kwh | propane | total | energy_consumption |
| out.propane.total.energy_savings..kwh | kwh | propane | total | energy_savings |
| out.propane.water_systems.energy_consumption..kwh | kwh | propane | water_systems | energy_consumption |
| out.propane.water_systems.energy_savings..kwh | kwh | propane | water_systems | energy_savings |
| out.site_energy.net.energy_consumption..kwh | kwh | site_energy | net | energy_consumption |
| out.site_energy.net.energy_savings..kwh | kwh | site_energy | net | energy_savings |
| out.site_energy.total.energy_consumption..kwh | kwh | site_energy | total | energy_consumption |
| out.site_energy.total.energy_savings..kwh | kwh | site_energy | total | energy_savings |
| out.electricity.total.peak_demand..kw | kw | electricity | total | peak_demand |
| out.district_cooling.cooling.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | district_cooling | cooling | energy_consumption_intensity |
| out.district_cooling.cooling.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | district_cooling | cooling | energy_savings_intensity |
| out.district_cooling.total.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | district_cooling | total | energy_consumption_intensity |
| out.district_cooling.total.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | district_cooling | total | energy_savings_intensity |
| out.district_heating.cooling.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | district_heating | cooling | energy_consumption_intensity |
| out.district_heating.cooling.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | district_heating | cooling | energy_savings_intensity |
| out.district_heating.heating.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | district_heating | heating | energy_consumption_intensity |
| out.district_heating.heating.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | district_heating | heating | energy_savings_intensity |
| out.district_heating.interior_equipment.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | district_heating | interior_equipment | energy_consumption_intensity |
| out.district_heating.interior_equipment.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | district_heating | interior_equipment | energy_savings_intensity |
| out.district_heating.total.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | district_heating | total | energy_consumption_intensity |
| out.district_heating.total.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | district_heating | total | energy_savings_intensity |
| out.district_heating.water_systems.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | district_heating | water_systems | energy_consumption_intensity |
| out.district_heating.water_systems.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | district_heating | water_systems | energy_savings_intensity |
| out.electricity.cooling.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | cooling | energy_consumption_intensity |
| out.electricity.cooling.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | cooling | energy_savings_intensity |
| out.electricity.exterior_lighting.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | exterior_lighting | energy_consumption_intensity |
| out.electricity.exterior_lighting.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | exterior_lighting | energy_savings_intensity |
| out.electricity.fans.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | fans | energy_consumption_intensity |
| out.electricity.fans.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | fans | energy_savings_intensity |
| out.electricity.heat_recovery.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | heat_recovery | energy_consumption_intensity |
| out.electricity.heat_recovery.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | heat_recovery | energy_savings_intensity |
| out.electricity.heat_rejection.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | heat_rejection | energy_consumption_intensity |
| out.electricity.heat_rejection.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | heat_rejection | energy_savings_intensity |
| out.electricity.heating.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | heating | energy_consumption_intensity |
| out.electricity.heating.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | heating | energy_savings_intensity |
| out.electricity.interior_equipment.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | interior_equipment | energy_consumption_intensity |
| out.electricity.interior_equipment.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | interior_equipment | energy_savings_intensity |
| out.electricity.interior_lighting.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | interior_lighting | energy_consumption_intensity |
| out.electricity.interior_lighting.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | interior_lighting | energy_savings_intensity |
| out.electricity.net.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | net | energy_consumption_intensity |
| out.electricity.net.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | net | energy_savings_intensity |
| out.electricity.pumps.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | pumps | energy_consumption_intensity |
| out.electricity.pumps.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | pumps | energy_savings_intensity |
| out.electricity.purchased.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | purchased | energy_consumption_intensity |
| out.electricity.purchased.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | purchased | energy_savings_intensity |
| out.electricity.pv.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | pv | energy_consumption_intensity |
| out.electricity.pv.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | pv | energy_savings_intensity |
| out.electricity.refrigeration.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | refrigeration | energy_consumption_intensity |
| out.electricity.refrigeration.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | refrigeration | energy_savings_intensity |
| out.electricity.total.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | total | energy_consumption_intensity |
| out.electricity.total.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | total | energy_savings_intensity |
| out.electricity.water_systems.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | water_systems | energy_consumption_intensity |
| out.electricity.water_systems.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | water_systems | energy_savings_intensity |
| out.fuel_oil.heating.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | fuel_oil | heating | energy_consumption_intensity |
| out.fuel_oil.heating.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | fuel_oil | heating | energy_savings_intensity |
| out.fuel_oil.interior_equipment.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | fuel_oil | interior_equipment | energy_consumption_intensity |
| out.fuel_oil.interior_equipment.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | fuel_oil | interior_equipment | energy_savings_intensity |
| out.fuel_oil.total.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | fuel_oil | total | energy_consumption_intensity |
| out.fuel_oil.total.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | fuel_oil | total | energy_savings_intensity |
| out.fuel_oil.water_systems.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | fuel_oil | water_systems | energy_consumption_intensity |
| out.fuel_oil.water_systems.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | fuel_oil | water_systems | energy_savings_intensity |
| out.natural_gas.cooling.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | cooling | energy_consumption_intensity |
| out.natural_gas.cooling.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | cooling | energy_savings_intensity |
| out.natural_gas.heating.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | heating | energy_consumption_intensity |
| out.natural_gas.heating.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | heating | energy_savings_intensity |
| out.natural_gas.interior_equipment.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | interior_equipment | energy_consumption_intensity |
| out.natural_gas.interior_equipment.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | interior_equipment | energy_savings_intensity |
| out.natural_gas.total.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | total | energy_consumption_intensity |
| out.natural_gas.total.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | total | energy_savings_intensity |
| out.natural_gas.water_systems.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | water_systems | energy_consumption_intensity |
| out.natural_gas.water_systems.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | water_systems | energy_savings_intensity |
| out.propane.heating.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | heating | energy_consumption_intensity |
| out.propane.heating.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | heating | energy_savings_intensity |
| out.propane.interior_equipment.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | interior_equipment | energy_consumption_intensity |
| out.propane.interior_equipment.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | interior_equipment | energy_savings_intensity |
| out.propane.total.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | total | energy_consumption_intensity |
| out.propane.total.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | total | energy_savings_intensity |
| out.propane.water_systems.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | water_systems | energy_consumption_intensity |
| out.propane.water_systems.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | water_systems | energy_savings_intensity |
| out.site_energy.net.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | site_energy | net | energy_consumption_intensity |
| out.site_energy.net.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | site_energy | net | energy_savings_intensity |
| out.site_energy.total.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | site_energy | total | energy_consumption_intensity |
| out.site_energy.total.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | site_energy | total | energy_savings_intensity |
| out.qoi.maximum_daily_peak_apr..kw | kw | qoi | maximum_daily_peak_apr |  |
| out.qoi.maximum_daily_peak_aug..kw | kw | qoi | maximum_daily_peak_aug |  |
| out.qoi.maximum_daily_peak_dec..kw | kw | qoi | maximum_daily_peak_dec |  |
| out.qoi.maximum_daily_peak_feb..kw | kw | qoi | maximum_daily_peak_feb |  |
| out.qoi.maximum_daily_peak_jan..kw | kw | qoi | maximum_daily_peak_jan |  |
| out.qoi.maximum_daily_peak_jul..kw | kw | qoi | maximum_daily_peak_jul |  |
| out.qoi.maximum_daily_peak_jun..kw | kw | qoi | maximum_daily_peak_jun |  |
| out.qoi.maximum_daily_peak_mar..kw | kw | qoi | maximum_daily_peak_mar |  |
| out.qoi.maximum_daily_peak_may..kw | kw | qoi | maximum_daily_peak_may |  |
| out.qoi.maximum_daily_peak_nov..kw | kw | qoi | maximum_daily_peak_nov |  |
| out.qoi.maximum_daily_peak_oct..kw | kw | qoi | maximum_daily_peak_oct |  |
| out.qoi.maximum_daily_peak_sep..kw | kw | qoi | maximum_daily_peak_sep |  |
| out.qoi.maximum_daily_timing_shoulder_hour..hr | hr | qoi | maximum_daily_timing_shoulder_hour |  |
| out.qoi.maximum_daily_timing_summer_hour..hr | hr | qoi | maximum_daily_timing_summer_hour |  |
| out.qoi.maximum_daily_timing_winter_hour..hr | hr | qoi | maximum_daily_timing_winter_hour |  |
| out.qoi.maximum_daily_use_shoulder..kw | kw | qoi | maximum_daily_use_shoulder |  |
| out.qoi.maximum_daily_use_shoulder_intensity..w_per_ft2 | w_per_ft2 | qoi | maximum_daily_use_shoulder_intensity |  |
| out.qoi.maximum_daily_use_summer..kw | kw | qoi | maximum_daily_use_summer |  |
| out.qoi.maximum_daily_use_summer_intensity..w_per_ft2 | w_per_ft2 | qoi | maximum_daily_use_summer_intensity |  |
| out.qoi.maximum_daily_use_winter..kw | kw | qoi | maximum_daily_use_winter |  |
| out.qoi.maximum_daily_use_winter_intensity..w_per_ft2 | w_per_ft2 | qoi | maximum_daily_use_winter_intensity |  |
| out.qoi.mean_daily_peak_apr..kw | kw | qoi | mean_daily_peak_apr |  |
| out.qoi.mean_daily_peak_aug..kw | kw | qoi | mean_daily_peak_aug |  |
| out.qoi.mean_daily_peak_dec..kw | kw | qoi | mean_daily_peak_dec |  |
| out.qoi.mean_daily_peak_feb..kw | kw | qoi | mean_daily_peak_feb |  |
| out.qoi.mean_daily_peak_grid_peak_apr..kw | kw | qoi | mean_daily_peak_grid_peak_apr |  |
| out.qoi.mean_daily_peak_grid_peak_aug..kw | kw | qoi | mean_daily_peak_grid_peak_aug |  |
| out.qoi.mean_daily_peak_grid_peak_dec..kw | kw | qoi | mean_daily_peak_grid_peak_dec |  |
| out.qoi.mean_daily_peak_grid_peak_feb..kw | kw | qoi | mean_daily_peak_grid_peak_feb |  |
| out.qoi.mean_daily_peak_grid_peak_jan..kw | kw | qoi | mean_daily_peak_grid_peak_jan |  |
| out.qoi.mean_daily_peak_grid_peak_jul..kw | kw | qoi | mean_daily_peak_grid_peak_jul |  |
| out.qoi.mean_daily_peak_grid_peak_jun..kw | kw | qoi | mean_daily_peak_grid_peak_jun |  |
| out.qoi.mean_daily_peak_grid_peak_mar..kw | kw | qoi | mean_daily_peak_grid_peak_mar |  |
| out.qoi.mean_daily_peak_grid_peak_may..kw | kw | qoi | mean_daily_peak_grid_peak_may |  |
| out.qoi.mean_daily_peak_grid_peak_nov..kw | kw | qoi | mean_daily_peak_grid_peak_nov |  |
| out.qoi.mean_daily_peak_grid_peak_oct..kw | kw | qoi | mean_daily_peak_grid_peak_oct |  |
| out.qoi.mean_daily_peak_grid_peak_sep..kw | kw | qoi | mean_daily_peak_grid_peak_sep |  |
| out.qoi.mean_daily_peak_grid_window_apr..kw | kw | qoi | mean_daily_peak_grid_window_apr |  |
| out.qoi.mean_daily_peak_grid_window_aug..kw | kw | qoi | mean_daily_peak_grid_window_aug |  |
| out.qoi.mean_daily_peak_grid_window_dec..kw | kw | qoi | mean_daily_peak_grid_window_dec |  |
| out.qoi.mean_daily_peak_grid_window_feb..kw | kw | qoi | mean_daily_peak_grid_window_feb |  |
| out.qoi.mean_daily_peak_grid_window_jan..kw | kw | qoi | mean_daily_peak_grid_window_jan |  |
| out.qoi.mean_daily_peak_grid_window_jul..kw | kw | qoi | mean_daily_peak_grid_window_jul |  |
| out.qoi.mean_daily_peak_grid_window_jun..kw | kw | qoi | mean_daily_peak_grid_window_jun |  |
| out.qoi.mean_daily_peak_grid_window_mar..kw | kw | qoi | mean_daily_peak_grid_window_mar |  |
| out.qoi.mean_daily_peak_grid_window_may..kw | kw | qoi | mean_daily_peak_grid_window_may |  |
| out.qoi.mean_daily_peak_grid_window_nov..kw | kw | qoi | mean_daily_peak_grid_window_nov |  |
| out.qoi.mean_daily_peak_grid_window_oct..kw | kw | qoi | mean_daily_peak_grid_window_oct |  |
| out.qoi.mean_daily_peak_grid_window_sep..kw | kw | qoi | mean_daily_peak_grid_window_sep |  |
| out.qoi.mean_daily_peak_jan..kw | kw | qoi | mean_daily_peak_jan |  |
| out.qoi.mean_daily_peak_jul..kw | kw | qoi | mean_daily_peak_jul |  |
| out.qoi.mean_daily_peak_jun..kw | kw | qoi | mean_daily_peak_jun |  |
| out.qoi.mean_daily_peak_mar..kw | kw | qoi | mean_daily_peak_mar |  |
| out.qoi.mean_daily_peak_may..kw | kw | qoi | mean_daily_peak_may |  |
| out.qoi.mean_daily_peak_nov..kw | kw | qoi | mean_daily_peak_nov |  |
| out.qoi.mean_daily_peak_oct..kw | kw | qoi | mean_daily_peak_oct |  |
| out.qoi.mean_daily_peak_sep..kw | kw | qoi | mean_daily_peak_sep |  |
| out.qoi.median_daily_peak_apr..kw | kw | qoi | median_daily_peak_apr |  |
| out.qoi.median_daily_peak_aug..kw | kw | qoi | median_daily_peak_aug |  |
| out.qoi.median_daily_peak_dec..kw | kw | qoi | median_daily_peak_dec |  |
| out.qoi.median_daily_peak_feb..kw | kw | qoi | median_daily_peak_feb |  |
| out.qoi.median_daily_peak_jan..kw | kw | qoi | median_daily_peak_jan |  |
| out.qoi.median_daily_peak_jul..kw | kw | qoi | median_daily_peak_jul |  |
| out.qoi.median_daily_peak_jun..kw | kw | qoi | median_daily_peak_jun |  |
| out.qoi.median_daily_peak_mar..kw | kw | qoi | median_daily_peak_mar |  |
| out.qoi.median_daily_peak_may..kw | kw | qoi | median_daily_peak_may |  |
| out.qoi.median_daily_peak_nov..kw | kw | qoi | median_daily_peak_nov |  |
| out.qoi.median_daily_peak_oct..kw | kw | qoi | median_daily_peak_oct |  |
| out.qoi.median_daily_peak_sep..kw | kw | qoi | median_daily_peak_sep |  |
| out.qoi.minimum_daily_use_shoulder..kw | kw | qoi | minimum_daily_use_shoulder |  |
| out.qoi.minimum_daily_use_shoulder_intensity..w_per_ft2 | w_per_ft2 | qoi | minimum_daily_use_shoulder_intensity |  |
| out.qoi.minimum_daily_use_summer..kw | kw | qoi | minimum_daily_use_summer |  |
| out.qoi.minimum_daily_use_summer_intensity..w_per_ft2 | w_per_ft2 | qoi | minimum_daily_use_summer_intensity |  |
| out.qoi.minimum_daily_use_winter..kw | kw | qoi | minimum_daily_use_winter |  |
| out.qoi.minimum_daily_use_winter_intensity..w_per_ft2 | w_per_ft2 | qoi | minimum_daily_use_winter_intensity |  |
| out.emissions.district_cooling..co2e_kg | co2e_kg | emissions | district_cooling |  |
| out.emissions.district_cooling.cooling..co2e_kg | co2e_kg | emissions | district_cooling | cooling |
| out.emissions.district_cooling.enduse_group.hvac..co2e_kg | co2e_kg | emissions | district_cooling | enduse_group.hvac |
| out.emissions.district_cooling.interior_equipment..co2e_kg | co2e_kg | emissions | district_cooling | interior_equipment |
| out.emissions.district_cooling.water_systems..co2e_kg | co2e_kg | emissions | district_cooling | water_systems |
| out.emissions.district_heating..co2e_kg | co2e_kg | emissions | district_heating |  |
| out.emissions.district_heating.enduse_group.hvac..co2e_kg | co2e_kg | emissions | district_heating | enduse_group.hvac |
| out.emissions.district_heating.heating..co2e_kg | co2e_kg | emissions | district_heating | heating |
| out.emissions.district_heating.interior_equipment..co2e_kg | co2e_kg | emissions | district_heating | interior_equipment |
| out.emissions.district_heating.water_systems..co2e_kg | co2e_kg | emissions | district_heating | water_systems |
| out.emissions.electricity.aer_95_decarb_by_2035_from_2023..co2e_kg | co2e_kg | emissions | electricity | aer_95_decarb_by_2035_from_2023 |
| out.emissions.electricity.aer_95_decarb_by_2050_from_2023..co2e_kg | co2e_kg | emissions | electricity | aer_95_decarb_by_2050_from_2023 |
| out.emissions.electricity.aer_high_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | aer_high_re_cost_from_2023 |
| out.emissions.electricity.aer_low_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | aer_low_re_cost_from_2023 |
| out.emissions.electricity.aer_mid_case_from_2023..co2e_kg | co2e_kg | emissions | electricity | aer_mid_case_from_2023 |
| out.emissions.electricity.cooling.aer_95_decarb_by_2035_from_2023..co2e_kg | co2e_kg | emissions | electricity | cooling.aer_95_decarb_by_2035_from_2023 |
| out.emissions.electricity.cooling.aer_95_decarb_by_2050_from_2023..co2e_kg | co2e_kg | emissions | electricity | cooling.aer_95_decarb_by_2050_from_2023 |
| out.emissions.electricity.cooling.aer_high_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | cooling.aer_high_re_cost_from_2023 |
| out.emissions.electricity.cooling.aer_low_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | cooling.aer_low_re_cost_from_2023 |
| out.emissions.electricity.cooling.aer_mid_case_from_2023..co2e_kg | co2e_kg | emissions | electricity | cooling.aer_mid_case_from_2023 |
| out.emissions.electricity.cooling.egrid_2018_state..co2e_kg | co2e_kg | emissions | electricity | cooling.egrid_2018_state |
| out.emissions.electricity.cooling.egrid_2018_subregion..co2e_kg | co2e_kg | emissions | electricity | cooling.egrid_2018_subregion |
| out.emissions.electricity.cooling.egrid_2019_state..co2e_kg | co2e_kg | emissions | electricity | cooling.egrid_2019_state |
| out.emissions.electricity.cooling.egrid_2019_subregion..co2e_kg | co2e_kg | emissions | electricity | cooling.egrid_2019_subregion |
| out.emissions.electricity.cooling.egrid_2020_state..co2e_kg | co2e_kg | emissions | electricity | cooling.egrid_2020_state |
| out.emissions.electricity.cooling.egrid_2020_subregion..co2e_kg | co2e_kg | emissions | electricity | cooling.egrid_2020_subregion |
| out.emissions.electricity.cooling.egrid_2021_state..co2e_kg | co2e_kg | emissions | electricity | cooling.egrid_2021_state |
| out.emissions.electricity.cooling.egrid_2021_subregion..co2e_kg | co2e_kg | emissions | electricity | cooling.egrid_2021_subregion |
| out.emissions.electricity.cooling.lrmer_95_decarb_by_2035_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | cooling.lrmer_95_decarb_by_2035_15_2023_start |
| out.emissions.electricity.cooling.lrmer_95_decarb_by_2035_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | cooling.lrmer_95_decarb_by_2035_15_2025_start |
| out.emissions.electricity.cooling.lrmer_95_decarb_by_2035_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | cooling.lrmer_95_decarb_by_2035_25_2025_start |
| out.emissions.electricity.cooling.lrmer_95_decarb_by_2035_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | cooling.lrmer_95_decarb_by_2035_30_2023_start |
| out.emissions.electricity.cooling.lrmer_95_decarb_by_2050_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | cooling.lrmer_95_decarb_by_2050_15_2023_start |
| out.emissions.electricity.cooling.lrmer_95_decarb_by_2050_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | cooling.lrmer_95_decarb_by_2050_30_2023_start |
| out.emissions.electricity.cooling.lrmer_high_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | cooling.lrmer_high_re_cost_15_2023_start |
| out.emissions.electricity.cooling.lrmer_high_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | cooling.lrmer_high_re_cost_30_2023_start |
| out.emissions.electricity.cooling.lrmer_low_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | cooling.lrmer_low_re_cost_15_2023_start |
| out.emissions.electricity.cooling.lrmer_low_re_cost_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | cooling.lrmer_low_re_cost_15_2025_start |
| out.emissions.electricity.cooling.lrmer_low_re_cost_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | cooling.lrmer_low_re_cost_25_2025_start |
| out.emissions.electricity.cooling.lrmer_low_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | cooling.lrmer_low_re_cost_30_2023_start |
| out.emissions.electricity.cooling.lrmer_mid_case_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | cooling.lrmer_mid_case_15_2023_start |
| out.emissions.electricity.cooling.lrmer_mid_case_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | cooling.lrmer_mid_case_15_2025_start |
| out.emissions.electricity.cooling.lrmer_mid_case_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | cooling.lrmer_mid_case_25_2025_start |
| out.emissions.electricity.cooling.lrmer_mid_case_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | cooling.lrmer_mid_case_30_2023_start |
| out.emissions.electricity.egrid_2018_state..co2e_kg | co2e_kg | emissions | electricity | egrid_2018_state |
| out.emissions.electricity.egrid_2018_subregion..co2e_kg | co2e_kg | emissions | electricity | egrid_2018_subregion |
| out.emissions.electricity.egrid_2019_state..co2e_kg | co2e_kg | emissions | electricity | egrid_2019_state |
| out.emissions.electricity.egrid_2019_subregion..co2e_kg | co2e_kg | emissions | electricity | egrid_2019_subregion |
| out.emissions.electricity.egrid_2020_state..co2e_kg | co2e_kg | emissions | electricity | egrid_2020_state |
| out.emissions.electricity.egrid_2020_subregion..co2e_kg | co2e_kg | emissions | electricity | egrid_2020_subregion |
| out.emissions.electricity.egrid_2021_state..co2e_kg | co2e_kg | emissions | electricity | egrid_2021_state |
| out.emissions.electricity.egrid_2021_subregion..co2e_kg | co2e_kg | emissions | electricity | egrid_2021_subregion |
| out.emissions.electricity.enduse_group.hvac.aer_95_decarb_by_2035_from_2023..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.aer_95_decarb_by_2035_from_2023 |
| out.emissions.electricity.enduse_group.hvac.aer_95_decarb_by_2050_from_2023..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.aer_95_decarb_by_2050_from_2023 |
| out.emissions.electricity.enduse_group.hvac.aer_high_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.aer_high_re_cost_from_2023 |
| out.emissions.electricity.enduse_group.hvac.aer_low_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.aer_low_re_cost_from_2023 |
| out.emissions.electricity.enduse_group.hvac.aer_mid_case_from_2023..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.aer_mid_case_from_2023 |
| out.emissions.electricity.enduse_group.hvac.egrid_2018_state..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.egrid_2018_state |
| out.emissions.electricity.enduse_group.hvac.egrid_2018_subregion..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.egrid_2018_subregion |
| out.emissions.electricity.enduse_group.hvac.egrid_2019_state..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.egrid_2019_state |
| out.emissions.electricity.enduse_group.hvac.egrid_2019_subregion..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.egrid_2019_subregion |
| out.emissions.electricity.enduse_group.hvac.egrid_2020_state..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.egrid_2020_state |
| out.emissions.electricity.enduse_group.hvac.egrid_2020_subregion..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.egrid_2020_subregion |
| out.emissions.electricity.enduse_group.hvac.egrid_2021_state..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.egrid_2021_state |
| out.emissions.electricity.enduse_group.hvac.egrid_2021_subregion..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.egrid_2021_subregion |
| out.emissions.electricity.enduse_group.hvac.lrmer_95_decarb_by_2035_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.lrmer_95_decarb_by_2035_15_2023_start |
| out.emissions.electricity.enduse_group.hvac.lrmer_95_decarb_by_2035_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.lrmer_95_decarb_by_2035_15_2025_start |
| out.emissions.electricity.enduse_group.hvac.lrmer_95_decarb_by_2035_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.lrmer_95_decarb_by_2035_25_2025_start |
| out.emissions.electricity.enduse_group.hvac.lrmer_95_decarb_by_2035_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.lrmer_95_decarb_by_2035_30_2023_start |
| out.emissions.electricity.enduse_group.hvac.lrmer_95_decarb_by_2050_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.lrmer_95_decarb_by_2050_15_2023_start |
| out.emissions.electricity.enduse_group.hvac.lrmer_95_decarb_by_2050_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.lrmer_95_decarb_by_2050_30_2023_start |
| out.emissions.electricity.enduse_group.hvac.lrmer_high_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.lrmer_high_re_cost_15_2023_start |
| out.emissions.electricity.enduse_group.hvac.lrmer_high_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.lrmer_high_re_cost_30_2023_start |
| out.emissions.electricity.enduse_group.hvac.lrmer_low_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.lrmer_low_re_cost_15_2023_start |
| out.emissions.electricity.enduse_group.hvac.lrmer_low_re_cost_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.lrmer_low_re_cost_15_2025_start |
| out.emissions.electricity.enduse_group.hvac.lrmer_low_re_cost_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.lrmer_low_re_cost_25_2025_start |
| out.emissions.electricity.enduse_group.hvac.lrmer_low_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.lrmer_low_re_cost_30_2023_start |
| out.emissions.electricity.enduse_group.hvac.lrmer_mid_case_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.lrmer_mid_case_15_2023_start |
| out.emissions.electricity.enduse_group.hvac.lrmer_mid_case_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.lrmer_mid_case_15_2025_start |
| out.emissions.electricity.enduse_group.hvac.lrmer_mid_case_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.lrmer_mid_case_25_2025_start |
| out.emissions.electricity.enduse_group.hvac.lrmer_mid_case_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | enduse_group.hvac.lrmer_mid_case_30_2023_start |
| out.emissions.electricity.exterior_lights.aer_95_decarb_by_2035_from_2023..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.aer_95_decarb_by_2035_from_2023 |
| out.emissions.electricity.exterior_lights.aer_95_decarb_by_2050_from_2023..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.aer_95_decarb_by_2050_from_2023 |
| out.emissions.electricity.exterior_lights.aer_high_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.aer_high_re_cost_from_2023 |
| out.emissions.electricity.exterior_lights.aer_low_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.aer_low_re_cost_from_2023 |
| out.emissions.electricity.exterior_lights.aer_mid_case_from_2023..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.aer_mid_case_from_2023 |
| out.emissions.electricity.exterior_lights.egrid_2018_state..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.egrid_2018_state |
| out.emissions.electricity.exterior_lights.egrid_2018_subregion..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.egrid_2018_subregion |
| out.emissions.electricity.exterior_lights.egrid_2019_state..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.egrid_2019_state |
| out.emissions.electricity.exterior_lights.egrid_2019_subregion..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.egrid_2019_subregion |
| out.emissions.electricity.exterior_lights.egrid_2020_state..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.egrid_2020_state |
| out.emissions.electricity.exterior_lights.egrid_2020_subregion..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.egrid_2020_subregion |
| out.emissions.electricity.exterior_lights.egrid_2021_state..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.egrid_2021_state |
| out.emissions.electricity.exterior_lights.egrid_2021_subregion..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.egrid_2021_subregion |
| out.emissions.electricity.exterior_lights.lrmer_95_decarb_by_2035_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.lrmer_95_decarb_by_2035_15_2023_start |
| out.emissions.electricity.exterior_lights.lrmer_95_decarb_by_2035_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.lrmer_95_decarb_by_2035_15_2025_start |
| out.emissions.electricity.exterior_lights.lrmer_95_decarb_by_2035_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.lrmer_95_decarb_by_2035_25_2025_start |
| out.emissions.electricity.exterior_lights.lrmer_95_decarb_by_2035_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.lrmer_95_decarb_by_2035_30_2023_start |
| out.emissions.electricity.exterior_lights.lrmer_95_decarb_by_2050_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.lrmer_95_decarb_by_2050_15_2023_start |
| out.emissions.electricity.exterior_lights.lrmer_95_decarb_by_2050_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.lrmer_95_decarb_by_2050_30_2023_start |
| out.emissions.electricity.exterior_lights.lrmer_high_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.lrmer_high_re_cost_15_2023_start |
| out.emissions.electricity.exterior_lights.lrmer_high_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.lrmer_high_re_cost_30_2023_start |
| out.emissions.electricity.exterior_lights.lrmer_low_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.lrmer_low_re_cost_15_2023_start |
| out.emissions.electricity.exterior_lights.lrmer_low_re_cost_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.lrmer_low_re_cost_15_2025_start |
| out.emissions.electricity.exterior_lights.lrmer_low_re_cost_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.lrmer_low_re_cost_25_2025_start |
| out.emissions.electricity.exterior_lights.lrmer_low_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.lrmer_low_re_cost_30_2023_start |
| out.emissions.electricity.exterior_lights.lrmer_mid_case_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.lrmer_mid_case_15_2023_start |
| out.emissions.electricity.exterior_lights.lrmer_mid_case_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.lrmer_mid_case_15_2025_start |
| out.emissions.electricity.exterior_lights.lrmer_mid_case_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.lrmer_mid_case_25_2025_start |
| out.emissions.electricity.exterior_lights.lrmer_mid_case_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | exterior_lights.lrmer_mid_case_30_2023_start |
| out.emissions.electricity.heating.aer_95_decarb_by_2035_from_2023..co2e_kg | co2e_kg | emissions | electricity | heating.aer_95_decarb_by_2035_from_2023 |
| out.emissions.electricity.heating.aer_95_decarb_by_2050_from_2023..co2e_kg | co2e_kg | emissions | electricity | heating.aer_95_decarb_by_2050_from_2023 |
| out.emissions.electricity.heating.aer_high_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | heating.aer_high_re_cost_from_2023 |
| out.emissions.electricity.heating.aer_low_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | heating.aer_low_re_cost_from_2023 |
| out.emissions.electricity.heating.aer_mid_case_from_2023..co2e_kg | co2e_kg | emissions | electricity | heating.aer_mid_case_from_2023 |
| out.emissions.electricity.heating.egrid_2018_state..co2e_kg | co2e_kg | emissions | electricity | heating.egrid_2018_state |
| out.emissions.electricity.heating.egrid_2018_subregion..co2e_kg | co2e_kg | emissions | electricity | heating.egrid_2018_subregion |
| out.emissions.electricity.heating.egrid_2019_state..co2e_kg | co2e_kg | emissions | electricity | heating.egrid_2019_state |
| out.emissions.electricity.heating.egrid_2019_subregion..co2e_kg | co2e_kg | emissions | electricity | heating.egrid_2019_subregion |
| out.emissions.electricity.heating.egrid_2020_state..co2e_kg | co2e_kg | emissions | electricity | heating.egrid_2020_state |
| out.emissions.electricity.heating.egrid_2020_subregion..co2e_kg | co2e_kg | emissions | electricity | heating.egrid_2020_subregion |
| out.emissions.electricity.heating.egrid_2021_state..co2e_kg | co2e_kg | emissions | electricity | heating.egrid_2021_state |
| out.emissions.electricity.heating.egrid_2021_subregion..co2e_kg | co2e_kg | emissions | electricity | heating.egrid_2021_subregion |
| out.emissions.electricity.heating.lrmer_95_decarb_by_2035_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | heating.lrmer_95_decarb_by_2035_15_2023_start |
| out.emissions.electricity.heating.lrmer_95_decarb_by_2035_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | heating.lrmer_95_decarb_by_2035_15_2025_start |
| out.emissions.electricity.heating.lrmer_95_decarb_by_2035_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | heating.lrmer_95_decarb_by_2035_25_2025_start |
| out.emissions.electricity.heating.lrmer_95_decarb_by_2035_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | heating.lrmer_95_decarb_by_2035_30_2023_start |
| out.emissions.electricity.heating.lrmer_95_decarb_by_2050_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | heating.lrmer_95_decarb_by_2050_15_2023_start |
| out.emissions.electricity.heating.lrmer_95_decarb_by_2050_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | heating.lrmer_95_decarb_by_2050_30_2023_start |
| out.emissions.electricity.heating.lrmer_high_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | heating.lrmer_high_re_cost_15_2023_start |
| out.emissions.electricity.heating.lrmer_high_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | heating.lrmer_high_re_cost_30_2023_start |
| out.emissions.electricity.heating.lrmer_low_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | heating.lrmer_low_re_cost_15_2023_start |
| out.emissions.electricity.heating.lrmer_low_re_cost_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | heating.lrmer_low_re_cost_15_2025_start |
| out.emissions.electricity.heating.lrmer_low_re_cost_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | heating.lrmer_low_re_cost_25_2025_start |
| out.emissions.electricity.heating.lrmer_low_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | heating.lrmer_low_re_cost_30_2023_start |
| out.emissions.electricity.heating.lrmer_mid_case_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | heating.lrmer_mid_case_15_2023_start |
| out.emissions.electricity.heating.lrmer_mid_case_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | heating.lrmer_mid_case_15_2025_start |
| out.emissions.electricity.heating.lrmer_mid_case_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | heating.lrmer_mid_case_25_2025_start |
| out.emissions.electricity.heating.lrmer_mid_case_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | heating.lrmer_mid_case_30_2023_start |
| out.emissions.electricity.interior_equipment.aer_95_decarb_by_2035_from_2023..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.aer_95_decarb_by_2035_from_2023 |
| out.emissions.electricity.interior_equipment.aer_95_decarb_by_2050_from_2023..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.aer_95_decarb_by_2050_from_2023 |
| out.emissions.electricity.interior_equipment.aer_high_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.aer_high_re_cost_from_2023 |
| out.emissions.electricity.interior_equipment.aer_low_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.aer_low_re_cost_from_2023 |
| out.emissions.electricity.interior_equipment.aer_mid_case_from_2023..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.aer_mid_case_from_2023 |
| out.emissions.electricity.interior_equipment.egrid_2018_state..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.egrid_2018_state |
| out.emissions.electricity.interior_equipment.egrid_2018_subregion..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.egrid_2018_subregion |
| out.emissions.electricity.interior_equipment.egrid_2019_state..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.egrid_2019_state |
| out.emissions.electricity.interior_equipment.egrid_2019_subregion..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.egrid_2019_subregion |
| out.emissions.electricity.interior_equipment.egrid_2020_state..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.egrid_2020_state |
| out.emissions.electricity.interior_equipment.egrid_2020_subregion..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.egrid_2020_subregion |
| out.emissions.electricity.interior_equipment.egrid_2021_state..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.egrid_2021_state |
| out.emissions.electricity.interior_equipment.egrid_2021_subregion..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.egrid_2021_subregion |
| out.emissions.electricity.interior_equipment.lrmer_95_decarb_by_2035_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.lrmer_95_decarb_by_2035_15_2023_start |
| out.emissions.electricity.interior_equipment.lrmer_95_decarb_by_2035_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.lrmer_95_decarb_by_2035_15_2025_start |
| out.emissions.electricity.interior_equipment.lrmer_95_decarb_by_2035_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.lrmer_95_decarb_by_2035_25_2025_start |
| out.emissions.electricity.interior_equipment.lrmer_95_decarb_by_2035_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.lrmer_95_decarb_by_2035_30_2023_start |
| out.emissions.electricity.interior_equipment.lrmer_95_decarb_by_2050_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.lrmer_95_decarb_by_2050_15_2023_start |
| out.emissions.electricity.interior_equipment.lrmer_95_decarb_by_2050_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.lrmer_95_decarb_by_2050_30_2023_start |
| out.emissions.electricity.interior_equipment.lrmer_high_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.lrmer_high_re_cost_15_2023_start |
| out.emissions.electricity.interior_equipment.lrmer_high_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.lrmer_high_re_cost_30_2023_start |
| out.emissions.electricity.interior_equipment.lrmer_low_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.lrmer_low_re_cost_15_2023_start |
| out.emissions.electricity.interior_equipment.lrmer_low_re_cost_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.lrmer_low_re_cost_15_2025_start |
| out.emissions.electricity.interior_equipment.lrmer_low_re_cost_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.lrmer_low_re_cost_25_2025_start |
| out.emissions.electricity.interior_equipment.lrmer_low_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.lrmer_low_re_cost_30_2023_start |
| out.emissions.electricity.interior_equipment.lrmer_mid_case_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.lrmer_mid_case_15_2023_start |
| out.emissions.electricity.interior_equipment.lrmer_mid_case_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.lrmer_mid_case_15_2025_start |
| out.emissions.electricity.interior_equipment.lrmer_mid_case_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.lrmer_mid_case_25_2025_start |
| out.emissions.electricity.interior_equipment.lrmer_mid_case_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_equipment.lrmer_mid_case_30_2023_start |
| out.emissions.electricity.interior_lights.aer_95_decarb_by_2035_from_2023..co2e_kg | co2e_kg | emissions | electricity | interior_lights.aer_95_decarb_by_2035_from_2023 |
| out.emissions.electricity.interior_lights.aer_95_decarb_by_2050_from_2023..co2e_kg | co2e_kg | emissions | electricity | interior_lights.aer_95_decarb_by_2050_from_2023 |
| out.emissions.electricity.interior_lights.aer_high_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | interior_lights.aer_high_re_cost_from_2023 |
| out.emissions.electricity.interior_lights.aer_low_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | interior_lights.aer_low_re_cost_from_2023 |
| out.emissions.electricity.interior_lights.aer_mid_case_from_2023..co2e_kg | co2e_kg | emissions | electricity | interior_lights.aer_mid_case_from_2023 |
| out.emissions.electricity.interior_lights.egrid_2018_state..co2e_kg | co2e_kg | emissions | electricity | interior_lights.egrid_2018_state |
| out.emissions.electricity.interior_lights.egrid_2018_subregion..co2e_kg | co2e_kg | emissions | electricity | interior_lights.egrid_2018_subregion |
| out.emissions.electricity.interior_lights.egrid_2019_state..co2e_kg | co2e_kg | emissions | electricity | interior_lights.egrid_2019_state |
| out.emissions.electricity.interior_lights.egrid_2019_subregion..co2e_kg | co2e_kg | emissions | electricity | interior_lights.egrid_2019_subregion |
| out.emissions.electricity.interior_lights.egrid_2020_state..co2e_kg | co2e_kg | emissions | electricity | interior_lights.egrid_2020_state |
| out.emissions.electricity.interior_lights.egrid_2020_subregion..co2e_kg | co2e_kg | emissions | electricity | interior_lights.egrid_2020_subregion |
| out.emissions.electricity.interior_lights.egrid_2021_state..co2e_kg | co2e_kg | emissions | electricity | interior_lights.egrid_2021_state |
| out.emissions.electricity.interior_lights.egrid_2021_subregion..co2e_kg | co2e_kg | emissions | electricity | interior_lights.egrid_2021_subregion |
| out.emissions.electricity.interior_lights.lrmer_95_decarb_by_2035_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_lights.lrmer_95_decarb_by_2035_15_2023_start |
| out.emissions.electricity.interior_lights.lrmer_95_decarb_by_2035_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | interior_lights.lrmer_95_decarb_by_2035_15_2025_start |
| out.emissions.electricity.interior_lights.lrmer_95_decarb_by_2035_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | interior_lights.lrmer_95_decarb_by_2035_25_2025_start |
| out.emissions.electricity.interior_lights.lrmer_95_decarb_by_2035_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_lights.lrmer_95_decarb_by_2035_30_2023_start |
| out.emissions.electricity.interior_lights.lrmer_95_decarb_by_2050_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_lights.lrmer_95_decarb_by_2050_15_2023_start |
| out.emissions.electricity.interior_lights.lrmer_95_decarb_by_2050_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_lights.lrmer_95_decarb_by_2050_30_2023_start |
| out.emissions.electricity.interior_lights.lrmer_high_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_lights.lrmer_high_re_cost_15_2023_start |
| out.emissions.electricity.interior_lights.lrmer_high_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_lights.lrmer_high_re_cost_30_2023_start |
| out.emissions.electricity.interior_lights.lrmer_low_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_lights.lrmer_low_re_cost_15_2023_start |
| out.emissions.electricity.interior_lights.lrmer_low_re_cost_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | interior_lights.lrmer_low_re_cost_15_2025_start |
| out.emissions.electricity.interior_lights.lrmer_low_re_cost_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | interior_lights.lrmer_low_re_cost_25_2025_start |
| out.emissions.electricity.interior_lights.lrmer_low_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_lights.lrmer_low_re_cost_30_2023_start |
| out.emissions.electricity.interior_lights.lrmer_mid_case_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_lights.lrmer_mid_case_15_2023_start |
| out.emissions.electricity.interior_lights.lrmer_mid_case_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | interior_lights.lrmer_mid_case_15_2025_start |
| out.emissions.electricity.interior_lights.lrmer_mid_case_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | interior_lights.lrmer_mid_case_25_2025_start |
| out.emissions.electricity.interior_lights.lrmer_mid_case_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | interior_lights.lrmer_mid_case_30_2023_start |
| out.emissions.electricity.lrmer_95_decarb_by_2035_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | lrmer_95_decarb_by_2035_15_2023_start |
| out.emissions.electricity.lrmer_95_decarb_by_2035_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | lrmer_95_decarb_by_2035_15_2025_start |
| out.emissions.electricity.lrmer_95_decarb_by_2035_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | lrmer_95_decarb_by_2035_25_2025_start |
| out.emissions.electricity.lrmer_95_decarb_by_2035_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | lrmer_95_decarb_by_2035_30_2023_start |
| out.emissions.electricity.lrmer_95_decarb_by_2050_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | lrmer_95_decarb_by_2050_15_2023_start |
| out.emissions.electricity.lrmer_95_decarb_by_2050_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | lrmer_95_decarb_by_2050_30_2023_start |
| out.emissions.electricity.lrmer_high_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | lrmer_high_re_cost_15_2023_start |
| out.emissions.electricity.lrmer_high_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | lrmer_high_re_cost_30_2023_start |
| out.emissions.electricity.lrmer_low_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | lrmer_low_re_cost_15_2023_start |
| out.emissions.electricity.lrmer_low_re_cost_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | lrmer_low_re_cost_15_2025_start |
| out.emissions.electricity.lrmer_low_re_cost_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | lrmer_low_re_cost_25_2025_start |
| out.emissions.electricity.lrmer_low_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | lrmer_low_re_cost_30_2023_start |
| out.emissions.electricity.lrmer_mid_case_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | lrmer_mid_case_15_2023_start |
| out.emissions.electricity.lrmer_mid_case_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | lrmer_mid_case_15_2025_start |
| out.emissions.electricity.lrmer_mid_case_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | lrmer_mid_case_25_2025_start |
| out.emissions.electricity.lrmer_mid_case_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | lrmer_mid_case_30_2023_start |
| out.emissions.electricity.refrigeration.aer_95_decarb_by_2035_from_2023..co2e_kg | co2e_kg | emissions | electricity | refrigeration.aer_95_decarb_by_2035_from_2023 |
| out.emissions.electricity.refrigeration.aer_95_decarb_by_2050_from_2023..co2e_kg | co2e_kg | emissions | electricity | refrigeration.aer_95_decarb_by_2050_from_2023 |
| out.emissions.electricity.refrigeration.aer_high_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | refrigeration.aer_high_re_cost_from_2023 |
| out.emissions.electricity.refrigeration.aer_low_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | refrigeration.aer_low_re_cost_from_2023 |
| out.emissions.electricity.refrigeration.aer_mid_case_from_2023..co2e_kg | co2e_kg | emissions | electricity | refrigeration.aer_mid_case_from_2023 |
| out.emissions.electricity.refrigeration.egrid_2018_state..co2e_kg | co2e_kg | emissions | electricity | refrigeration.egrid_2018_state |
| out.emissions.electricity.refrigeration.egrid_2018_subregion..co2e_kg | co2e_kg | emissions | electricity | refrigeration.egrid_2018_subregion |
| out.emissions.electricity.refrigeration.egrid_2019_state..co2e_kg | co2e_kg | emissions | electricity | refrigeration.egrid_2019_state |
| out.emissions.electricity.refrigeration.egrid_2019_subregion..co2e_kg | co2e_kg | emissions | electricity | refrigeration.egrid_2019_subregion |
| out.emissions.electricity.refrigeration.egrid_2020_state..co2e_kg | co2e_kg | emissions | electricity | refrigeration.egrid_2020_state |
| out.emissions.electricity.refrigeration.egrid_2020_subregion..co2e_kg | co2e_kg | emissions | electricity | refrigeration.egrid_2020_subregion |
| out.emissions.electricity.refrigeration.egrid_2021_state..co2e_kg | co2e_kg | emissions | electricity | refrigeration.egrid_2021_state |
| out.emissions.electricity.refrigeration.egrid_2021_subregion..co2e_kg | co2e_kg | emissions | electricity | refrigeration.egrid_2021_subregion |
| out.emissions.electricity.refrigeration.lrmer_95_decarb_by_2035_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | refrigeration.lrmer_95_decarb_by_2035_15_2023_start |
| out.emissions.electricity.refrigeration.lrmer_95_decarb_by_2035_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | refrigeration.lrmer_95_decarb_by_2035_15_2025_start |
| out.emissions.electricity.refrigeration.lrmer_95_decarb_by_2035_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | refrigeration.lrmer_95_decarb_by_2035_25_2025_start |
| out.emissions.electricity.refrigeration.lrmer_95_decarb_by_2035_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | refrigeration.lrmer_95_decarb_by_2035_30_2023_start |
| out.emissions.electricity.refrigeration.lrmer_95_decarb_by_2050_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | refrigeration.lrmer_95_decarb_by_2050_15_2023_start |
| out.emissions.electricity.refrigeration.lrmer_95_decarb_by_2050_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | refrigeration.lrmer_95_decarb_by_2050_30_2023_start |
| out.emissions.electricity.refrigeration.lrmer_high_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | refrigeration.lrmer_high_re_cost_15_2023_start |
| out.emissions.electricity.refrigeration.lrmer_high_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | refrigeration.lrmer_high_re_cost_30_2023_start |
| out.emissions.electricity.refrigeration.lrmer_low_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | refrigeration.lrmer_low_re_cost_15_2023_start |
| out.emissions.electricity.refrigeration.lrmer_low_re_cost_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | refrigeration.lrmer_low_re_cost_15_2025_start |
| out.emissions.electricity.refrigeration.lrmer_low_re_cost_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | refrigeration.lrmer_low_re_cost_25_2025_start |
| out.emissions.electricity.refrigeration.lrmer_low_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | refrigeration.lrmer_low_re_cost_30_2023_start |
| out.emissions.electricity.refrigeration.lrmer_mid_case_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | refrigeration.lrmer_mid_case_15_2023_start |
| out.emissions.electricity.refrigeration.lrmer_mid_case_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | refrigeration.lrmer_mid_case_15_2025_start |
| out.emissions.electricity.refrigeration.lrmer_mid_case_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | refrigeration.lrmer_mid_case_25_2025_start |
| out.emissions.electricity.refrigeration.lrmer_mid_case_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | refrigeration.lrmer_mid_case_30_2023_start |
| out.emissions.electricity.shoulder_daily_average.egrid_2021_state..co2e_kg | co2e_kg | emissions | electricity | shoulder_daily_average.egrid_2021_state |
| out.emissions.electricity.shoulder_daily_average.egrid_2021_subregion..co2e_kg | co2e_kg | emissions | electricity | shoulder_daily_average.egrid_2021_subregion |
| out.emissions.electricity.shoulder_daily_average.lrmer_high_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | shoulder_daily_average.lrmer_high_re_cost_15_2023_start |
| out.emissions.electricity.shoulder_daily_average.lrmer_low_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | shoulder_daily_average.lrmer_low_re_cost_15_2023_start |
| out.emissions.electricity.shoulder_daily_average.lrmer_mid_case_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | shoulder_daily_average.lrmer_mid_case_15_2023_start |
| out.emissions.electricity.summer_daily_average.egrid_2021_state..co2e_kg | co2e_kg | emissions | electricity | summer_daily_average.egrid_2021_state |
| out.emissions.electricity.summer_daily_average.egrid_2021_subregion..co2e_kg | co2e_kg | emissions | electricity | summer_daily_average.egrid_2021_subregion |
| out.emissions.electricity.summer_daily_average.lrmer_high_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | summer_daily_average.lrmer_high_re_cost_15_2023_start |
| out.emissions.electricity.summer_daily_average.lrmer_low_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | summer_daily_average.lrmer_low_re_cost_15_2023_start |
| out.emissions.electricity.summer_daily_average.lrmer_mid_case_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | summer_daily_average.lrmer_mid_case_15_2023_start |
| out.emissions.electricity.water_systems.aer_95_decarb_by_2035_from_2023..co2e_kg | co2e_kg | emissions | electricity | water_systems.aer_95_decarb_by_2035_from_2023 |
| out.emissions.electricity.water_systems.aer_95_decarb_by_2050_from_2023..co2e_kg | co2e_kg | emissions | electricity | water_systems.aer_95_decarb_by_2050_from_2023 |
| out.emissions.electricity.water_systems.aer_high_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | water_systems.aer_high_re_cost_from_2023 |
| out.emissions.electricity.water_systems.aer_low_re_cost_from_2023..co2e_kg | co2e_kg | emissions | electricity | water_systems.aer_low_re_cost_from_2023 |
| out.emissions.electricity.water_systems.aer_mid_case_from_2023..co2e_kg | co2e_kg | emissions | electricity | water_systems.aer_mid_case_from_2023 |
| out.emissions.electricity.water_systems.egrid_2018_state..co2e_kg | co2e_kg | emissions | electricity | water_systems.egrid_2018_state |
| out.emissions.electricity.water_systems.egrid_2018_subregion..co2e_kg | co2e_kg | emissions | electricity | water_systems.egrid_2018_subregion |
| out.emissions.electricity.water_systems.egrid_2019_state..co2e_kg | co2e_kg | emissions | electricity | water_systems.egrid_2019_state |
| out.emissions.electricity.water_systems.egrid_2019_subregion..co2e_kg | co2e_kg | emissions | electricity | water_systems.egrid_2019_subregion |
| out.emissions.electricity.water_systems.egrid_2020_state..co2e_kg | co2e_kg | emissions | electricity | water_systems.egrid_2020_state |
| out.emissions.electricity.water_systems.egrid_2020_subregion..co2e_kg | co2e_kg | emissions | electricity | water_systems.egrid_2020_subregion |
| out.emissions.electricity.water_systems.egrid_2021_state..co2e_kg | co2e_kg | emissions | electricity | water_systems.egrid_2021_state |
| out.emissions.electricity.water_systems.egrid_2021_subregion..co2e_kg | co2e_kg | emissions | electricity | water_systems.egrid_2021_subregion |
| out.emissions.electricity.water_systems.lrmer_95_decarb_by_2035_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | water_systems.lrmer_95_decarb_by_2035_15_2023_start |
| out.emissions.electricity.water_systems.lrmer_95_decarb_by_2035_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | water_systems.lrmer_95_decarb_by_2035_15_2025_start |
| out.emissions.electricity.water_systems.lrmer_95_decarb_by_2035_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | water_systems.lrmer_95_decarb_by_2035_25_2025_start |
| out.emissions.electricity.water_systems.lrmer_95_decarb_by_2035_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | water_systems.lrmer_95_decarb_by_2035_30_2023_start |
| out.emissions.electricity.water_systems.lrmer_95_decarb_by_2050_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | water_systems.lrmer_95_decarb_by_2050_15_2023_start |
| out.emissions.electricity.water_systems.lrmer_95_decarb_by_2050_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | water_systems.lrmer_95_decarb_by_2050_30_2023_start |
| out.emissions.electricity.water_systems.lrmer_high_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | water_systems.lrmer_high_re_cost_15_2023_start |
| out.emissions.electricity.water_systems.lrmer_high_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | water_systems.lrmer_high_re_cost_30_2023_start |
| out.emissions.electricity.water_systems.lrmer_low_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | water_systems.lrmer_low_re_cost_15_2023_start |
| out.emissions.electricity.water_systems.lrmer_low_re_cost_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | water_systems.lrmer_low_re_cost_15_2025_start |
| out.emissions.electricity.water_systems.lrmer_low_re_cost_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | water_systems.lrmer_low_re_cost_25_2025_start |
| out.emissions.electricity.water_systems.lrmer_low_re_cost_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | water_systems.lrmer_low_re_cost_30_2023_start |
| out.emissions.electricity.water_systems.lrmer_mid_case_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | water_systems.lrmer_mid_case_15_2023_start |
| out.emissions.electricity.water_systems.lrmer_mid_case_15_2025_start..co2e_kg | co2e_kg | emissions | electricity | water_systems.lrmer_mid_case_15_2025_start |
| out.emissions.electricity.water_systems.lrmer_mid_case_25_2025_start..co2e_kg | co2e_kg | emissions | electricity | water_systems.lrmer_mid_case_25_2025_start |
| out.emissions.electricity.water_systems.lrmer_mid_case_30_2023_start..co2e_kg | co2e_kg | emissions | electricity | water_systems.lrmer_mid_case_30_2023_start |
| out.emissions.electricity.winter_daily_average.egrid_2021_state..co2e_kg | co2e_kg | emissions | electricity | winter_daily_average.egrid_2021_state |
| out.emissions.electricity.winter_daily_average.egrid_2021_subregion..co2e_kg | co2e_kg | emissions | electricity | winter_daily_average.egrid_2021_subregion |
| out.emissions.electricity.winter_daily_average.lrmer_high_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | winter_daily_average.lrmer_high_re_cost_15_2023_start |
| out.emissions.electricity.winter_daily_average.lrmer_low_re_cost_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | winter_daily_average.lrmer_low_re_cost_15_2023_start |
| out.emissions.electricity.winter_daily_average.lrmer_mid_case_15_2023_start..co2e_kg | co2e_kg | emissions | electricity | winter_daily_average.lrmer_mid_case_15_2023_start |
| out.emissions.fuel_oil..co2e_kg | co2e_kg | emissions | fuel_oil |  |
| out.emissions.fuel_oil.enduse_group.hvac..co2e_kg | co2e_kg | emissions | fuel_oil | enduse_group.hvac |
| out.emissions.fuel_oil.heating..co2e_kg | co2e_kg | emissions | fuel_oil | heating |
| out.emissions.fuel_oil.interior_equipment..co2e_kg | co2e_kg | emissions | fuel_oil | interior_equipment |
| out.emissions.fuel_oil.water_systems..co2e_kg | co2e_kg | emissions | fuel_oil | water_systems |
| out.emissions.natural_gas..co2e_kg | co2e_kg | emissions | natural_gas |  |
| out.emissions.natural_gas.enduse_group.hvac..co2e_kg | co2e_kg | emissions | natural_gas | enduse_group.hvac |
| out.emissions.natural_gas.heating..co2e_kg | co2e_kg | emissions | natural_gas | heating |
| out.emissions.natural_gas.interior_equipment..co2e_kg | co2e_kg | emissions | natural_gas | interior_equipment |
| out.emissions.natural_gas.water_systems..co2e_kg | co2e_kg | emissions | natural_gas | water_systems |
| out.emissions.propane..co2e_kg | co2e_kg | emissions | propane |  |
| out.emissions.propane.enduse_group.hvac..co2e_kg | co2e_kg | emissions | propane | enduse_group.hvac |
| out.emissions.propane.heating..co2e_kg | co2e_kg | emissions | propane | heating |
| out.emissions.propane.interior_equipment..co2e_kg | co2e_kg | emissions | propane | interior_equipment |
| out.emissions.propane.water_systems..co2e_kg | co2e_kg | emissions | propane | water_systems |
| out.co_emissions.fuel_oil..co_kg | co_kg | co_emissions | fuel_oil |  |
| out.co_emissions.natural_gas..co_kg | co_kg | co_emissions | natural_gas |  |
| out.co_emissions.propane..co_kg | co_kg | co_emissions | propane |  |
| out.nox_emissions.fuel_oil..nox_kg | nox_kg | nox_emissions | fuel_oil |  |
| out.nox_emissions.natural_gas..nox_kg | nox_kg | nox_emissions | natural_gas |  |
| out.nox_emissions.propane..nox_kg | nox_kg | nox_emissions | propane |  |
| out.pm_emissions.fuel_oil..pm_kg | pm_kg | pm_emissions | fuel_oil |  |
| out.pm_emissions.natural_gas..pm_kg | pm_kg | pm_emissions | natural_gas |  |
| out.pm_emissions.propane..pm_kg | pm_kg | pm_emissions | propane |  |
| out.so2_emissions.fuel_oil..so2_kg | so2_kg | so2_emissions | fuel_oil |  |
| out.so2_emissions.natural_gas..so2_kg | so2_kg | so2_emissions | natural_gas |  |
| out.so2_emissions.propane..so2_kg | so2_kg | so2_emissions | propane |  |
| out.utility_bills.electricity_bill_max..usd | usd | utility_bills | electricity_bill_max |  |
| out.utility_bills.electricity_bill_max_label |  | utility_bills | electricity_bill_max_label |  |
| out.utility_bills.electricity_bill_mean..usd | usd | utility_bills | electricity_bill_mean |  |
| out.utility_bills.electricity_bill_mean_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_bill_mean_intensity |  |
| out.utility_bills.electricity_bill_median_high..usd | usd | utility_bills | electricity_bill_median_high |  |
| out.utility_bills.electricity_bill_median_high_label |  | utility_bills | electricity_bill_median_high_label |  |
| out.utility_bills.electricity_bill_median_low..usd | usd | utility_bills | electricity_bill_median_low |  |
| out.utility_bills.electricity_bill_median_low_label |  | utility_bills | electricity_bill_median_low_label |  |
| out.utility_bills.electricity_bill_min..usd | usd | utility_bills | electricity_bill_min |  |
| out.utility_bills.electricity_bill_min_label |  | utility_bills | electricity_bill_min_label |  |
| out.utility_bills.electricity_bill_num_bills |  | utility_bills | electricity_bill_num_bills |  |
| out.utility_bills.electricity_bill_savings_max_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_bill_savings_max_intensity |  |
| out.utility_bills.electricity_bill_savings_mean_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_bill_savings_mean_intensity |  |
| out.utility_bills.electricity_bill_savings_median_high_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_bill_savings_median_high_intensity |  |
| out.utility_bills.electricity_bill_savings_median_low_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_bill_savings_median_low_intensity |  |
| out.utility_bills.electricity_bill_savings_min_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_bill_savings_min_intensity |  |
| out.utility_bills.electricity_demandcharge_flat_bill_max..usd | usd | utility_bills | electricity_demandcharge_flat_bill_max |  |
| out.utility_bills.electricity_demandcharge_flat_bill_max_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_flat_bill_max_intensity |  |
| out.utility_bills.electricity_demandcharge_flat_bill_max_label |  | utility_bills | electricity_demandcharge_flat_bill_max_label |  |
| out.utility_bills.electricity_demandcharge_flat_bill_mean..usd | usd | utility_bills | electricity_demandcharge_flat_bill_mean |  |
| out.utility_bills.electricity_demandcharge_flat_bill_mean_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_flat_bill_mean_intensity |  |
| out.utility_bills.electricity_demandcharge_flat_bill_median_high..usd | usd | utility_bills | electricity_demandcharge_flat_bill_median_high |  |
| out.utility_bills.electricity_demandcharge_flat_bill_median_high_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_flat_bill_median_high_intensity |  |
| out.utility_bills.electricity_demandcharge_flat_bill_median_high_label |  | utility_bills | electricity_demandcharge_flat_bill_median_high_label |  |
| out.utility_bills.electricity_demandcharge_flat_bill_median_low..usd | usd | utility_bills | electricity_demandcharge_flat_bill_median_low |  |
| out.utility_bills.electricity_demandcharge_flat_bill_median_low_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_flat_bill_median_low_intensity |  |
| out.utility_bills.electricity_demandcharge_flat_bill_median_low_label |  | utility_bills | electricity_demandcharge_flat_bill_median_low_label |  |
| out.utility_bills.electricity_demandcharge_flat_bill_min..usd | usd | utility_bills | electricity_demandcharge_flat_bill_min |  |
| out.utility_bills.electricity_demandcharge_flat_bill_min_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_flat_bill_min_intensity |  |
| out.utility_bills.electricity_demandcharge_flat_bill_min_label |  | utility_bills | electricity_demandcharge_flat_bill_min_label |  |
| out.utility_bills.electricity_demandcharge_flat_bill_savings_max_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_flat_bill_savings_max_intensity |  |
| out.utility_bills.electricity_demandcharge_flat_bill_savings_mean_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_flat_bill_savings_mean_intensity |  |
| out.utility_bills.electricity_demandcharge_flat_bill_savings_median_high_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_flat_bill_savings_median_high_intensity |  |
| out.utility_bills.electricity_demandcharge_flat_bill_savings_median_low_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_flat_bill_savings_median_low_intensity |  |
| out.utility_bills.electricity_demandcharge_flat_bill_savings_min_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_flat_bill_savings_min_intensity |  |
| out.utility_bills.electricity_demandcharge_tou_bill_max..usd | usd | utility_bills | electricity_demandcharge_tou_bill_max |  |
| out.utility_bills.electricity_demandcharge_tou_bill_max_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_tou_bill_max_intensity |  |
| out.utility_bills.electricity_demandcharge_tou_bill_max_label |  | utility_bills | electricity_demandcharge_tou_bill_max_label |  |
| out.utility_bills.electricity_demandcharge_tou_bill_mean..usd | usd | utility_bills | electricity_demandcharge_tou_bill_mean |  |
| out.utility_bills.electricity_demandcharge_tou_bill_mean_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_tou_bill_mean_intensity |  |
| out.utility_bills.electricity_demandcharge_tou_bill_median_high..usd | usd | utility_bills | electricity_demandcharge_tou_bill_median_high |  |
| out.utility_bills.electricity_demandcharge_tou_bill_median_high_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_tou_bill_median_high_intensity |  |
| out.utility_bills.electricity_demandcharge_tou_bill_median_high_label |  | utility_bills | electricity_demandcharge_tou_bill_median_high_label |  |
| out.utility_bills.electricity_demandcharge_tou_bill_median_low..usd | usd | utility_bills | electricity_demandcharge_tou_bill_median_low |  |
| out.utility_bills.electricity_demandcharge_tou_bill_median_low_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_tou_bill_median_low_intensity |  |
| out.utility_bills.electricity_demandcharge_tou_bill_median_low_label |  | utility_bills | electricity_demandcharge_tou_bill_median_low_label |  |
| out.utility_bills.electricity_demandcharge_tou_bill_min..usd | usd | utility_bills | electricity_demandcharge_tou_bill_min |  |
| out.utility_bills.electricity_demandcharge_tou_bill_min_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_tou_bill_min_intensity |  |
| out.utility_bills.electricity_demandcharge_tou_bill_min_label |  | utility_bills | electricity_demandcharge_tou_bill_min_label |  |
| out.utility_bills.electricity_demandcharge_tou_bill_savings_max_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_tou_bill_savings_max_intensity |  |
| out.utility_bills.electricity_demandcharge_tou_bill_savings_mean_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_tou_bill_savings_mean_intensity |  |
| out.utility_bills.electricity_demandcharge_tou_bill_savings_median_high_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_tou_bill_savings_median_high_intensity |  |
| out.utility_bills.electricity_demandcharge_tou_bill_savings_median_low_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_tou_bill_savings_median_low_intensity |  |
| out.utility_bills.electricity_demandcharge_tou_bill_savings_min_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_demandcharge_tou_bill_savings_min_intensity |  |
| out.utility_bills.electricity_energycharge_bill_max..usd | usd | utility_bills | electricity_energycharge_bill_max |  |
| out.utility_bills.electricity_energycharge_bill_max_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_energycharge_bill_max_intensity |  |
| out.utility_bills.electricity_energycharge_bill_max_label |  | utility_bills | electricity_energycharge_bill_max_label |  |
| out.utility_bills.electricity_energycharge_bill_mean..usd | usd | utility_bills | electricity_energycharge_bill_mean |  |
| out.utility_bills.electricity_energycharge_bill_mean_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_energycharge_bill_mean_intensity |  |
| out.utility_bills.electricity_energycharge_bill_median_high..usd | usd | utility_bills | electricity_energycharge_bill_median_high |  |
| out.utility_bills.electricity_energycharge_bill_median_high_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_energycharge_bill_median_high_intensity |  |
| out.utility_bills.electricity_energycharge_bill_median_high_label |  | utility_bills | electricity_energycharge_bill_median_high_label |  |
| out.utility_bills.electricity_energycharge_bill_median_low..usd | usd | utility_bills | electricity_energycharge_bill_median_low |  |
| out.utility_bills.electricity_energycharge_bill_median_low_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_energycharge_bill_median_low_intensity |  |
| out.utility_bills.electricity_energycharge_bill_median_low_label |  | utility_bills | electricity_energycharge_bill_median_low_label |  |
| out.utility_bills.electricity_energycharge_bill_min..usd | usd | utility_bills | electricity_energycharge_bill_min |  |
| out.utility_bills.electricity_energycharge_bill_min_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_energycharge_bill_min_intensity |  |
| out.utility_bills.electricity_energycharge_bill_min_label |  | utility_bills | electricity_energycharge_bill_min_label |  |
| out.utility_bills.electricity_energycharge_bill_savings_max_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_energycharge_bill_savings_max_intensity |  |
| out.utility_bills.electricity_energycharge_bill_savings_mean_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_energycharge_bill_savings_mean_intensity |  |
| out.utility_bills.electricity_energycharge_bill_savings_median_high_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_energycharge_bill_savings_median_high_intensity |  |
| out.utility_bills.electricity_energycharge_bill_savings_median_low_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_energycharge_bill_savings_median_low_intensity |  |
| out.utility_bills.electricity_energycharge_bill_savings_min_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_energycharge_bill_savings_min_intensity |  |
| out.utility_bills.electricity_fixedcharge_bill_max..usd | usd | utility_bills | electricity_fixedcharge_bill_max |  |
| out.utility_bills.electricity_fixedcharge_bill_max_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_fixedcharge_bill_max_intensity |  |
| out.utility_bills.electricity_fixedcharge_bill_max_label |  | utility_bills | electricity_fixedcharge_bill_max_label |  |
| out.utility_bills.electricity_fixedcharge_bill_mean..usd | usd | utility_bills | electricity_fixedcharge_bill_mean |  |
| out.utility_bills.electricity_fixedcharge_bill_mean_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_fixedcharge_bill_mean_intensity |  |
| out.utility_bills.electricity_fixedcharge_bill_median_high..usd | usd | utility_bills | electricity_fixedcharge_bill_median_high |  |
| out.utility_bills.electricity_fixedcharge_bill_median_high_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_fixedcharge_bill_median_high_intensity |  |
| out.utility_bills.electricity_fixedcharge_bill_median_high_label |  | utility_bills | electricity_fixedcharge_bill_median_high_label |  |
| out.utility_bills.electricity_fixedcharge_bill_median_low..usd | usd | utility_bills | electricity_fixedcharge_bill_median_low |  |
| out.utility_bills.electricity_fixedcharge_bill_median_low_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_fixedcharge_bill_median_low_intensity |  |
| out.utility_bills.electricity_fixedcharge_bill_median_low_label |  | utility_bills | electricity_fixedcharge_bill_median_low_label |  |
| out.utility_bills.electricity_fixedcharge_bill_min..usd | usd | utility_bills | electricity_fixedcharge_bill_min |  |
| out.utility_bills.electricity_fixedcharge_bill_min_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_fixedcharge_bill_min_intensity |  |
| out.utility_bills.electricity_fixedcharge_bill_min_label |  | utility_bills | electricity_fixedcharge_bill_min_label |  |
| out.utility_bills.electricity_fixedcharge_bill_savings_max_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_fixedcharge_bill_savings_max_intensity |  |
| out.utility_bills.electricity_fixedcharge_bill_savings_mean_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_fixedcharge_bill_savings_mean_intensity |  |
| out.utility_bills.electricity_fixedcharge_bill_savings_median_high_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_fixedcharge_bill_savings_median_high_intensity |  |
| out.utility_bills.electricity_fixedcharge_bill_savings_median_low_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_fixedcharge_bill_savings_median_low_intensity |  |
| out.utility_bills.electricity_fixedcharge_bill_savings_min_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | electricity_fixedcharge_bill_savings_min_intensity |  |
| out.utility_bills.fuel_oil_bill_savings_state_average_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | fuel_oil_bill_savings_state_average_intensity |  |
| out.utility_bills.fuel_oil_bill_state_average_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | fuel_oil_bill_state_average_intensity |  |
| out.utility_bills.natural_gas_bill_savings_state_average_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | natural_gas_bill_savings_state_average_intensity |  |
| out.utility_bills.natural_gas_bill_state_average_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | natural_gas_bill_state_average_intensity |  |
| out.utility_bills.propane_bill_savings_state_average_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | propane_bill_savings_state_average_intensity |  |
| out.utility_bills.propane_bill_state_average_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | propane_bill_state_average_intensity |  |
| out.utility_bills.total_bill_mean_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | total_bill_mean_intensity |  |
| out.utility_bills.total_bill_savings_mean_intensity..usd_per_ft2 | usd_per_ft2 | utility_bills | total_bill_savings_mean_intensity |  |
| out.params.air_system_fan_power_minimum_flow_fraction |  | params | air_system_fan_power_minimum_flow_fraction |  |
| out.params.air_system_fan_static_pressure..inwc | inwc | params | air_system_fan_static_pressure |  |
| out.params.air_system_fan_total_efficiency |  | params | air_system_fan_total_efficiency |  |
| out.params.air_system_vav_avg_flow_ratio |  | params | air_system_vav_avg_flow_ratio |  |
| out.params.area_fraction_with_dcv |  | params | area_fraction_with_dcv |  |
| out.params.area_fraction_with_economizer |  | params | area_fraction_with_economizer |  |
| out.params.area_fraction_with_heat_recovery |  | params | area_fraction_with_heat_recovery |  |
| out.params.area_fraction_with_motorized_oa_damper |  | params | area_fraction_with_motorized_oa_damper |  |
| out.params.area_fraction_with_mz_vav_optimization |  | params | area_fraction_with_mz_vav_optimization |  |
| out.params.area_fraction_with_supply_air_temperature_reset |  | params | area_fraction_with_supply_air_temperature_reset |  |
| out.params.area_fraction_with_unoccupied_shutdown |  | params | area_fraction_with_unoccupied_shutdown |  |
| out.params.average_cooling_setpoint_max..c | c | params | average_cooling_setpoint_max |  |
| out.params.average_cooling_setpoint_min..c | c | params | average_cooling_setpoint_min |  |
| out.params.average_heating_setpoint_max..c | c | params | average_heating_setpoint_max |  |
| out.params.average_heating_setpoint_min..c | c | params | average_heating_setpoint_min |  |
| out.params.average_outdoor_air_fraction |  | params | average_outdoor_air_fraction |  |
| out.params.average_roof_absorptance |  | params | average_roof_absorptance |  |
| out.params.average_roof_u_value..btu_per_ft2_f_hr | btu_per_ft2_f_hr | params | average_roof_u_value |  |
| out.params.average_wall_u_value..btu_per_ft2_f_hr | btu_per_ft2_f_hr | params | average_wall_u_value |  |
| out.params.average_window_shgc |  | params | average_window_shgc |  |
| out.params.average_window_u_value..btu_per_ft2_f_hr | btu_per_ft2_f_hr | params | average_window_u_value |  |
| out.params.average_window_vlt |  | params | average_window_vlt |  |
| out.params.battery_capacity_kwh..kWh | kWh | params | battery_capacity_kwh |  |
| out.params.battery_max_charge_kw..kW | kW | params | battery_max_charge_kw |  |
| out.params.battery_max_discharge_kw..kW | kW | params | battery_max_discharge_kw |  |
| out.params.boiler_average_efficiency |  | params | boiler_average_efficiency |  |
| out.params.boiler_cap_weight_efficiency |  | params | boiler_cap_weight_efficiency |  |
| out.params.boiler_capacity..kbtu_per_hr | kbtu_per_hr | params | boiler_capacity |  |
| out.params.boiler_electric..j | j | params | boiler_electric |  |
| out.params.boiler_gas..j | j | params | boiler_gas |  |
| out.params.boiler_load..j | j | params | boiler_load |  |
| out.params.boiler_load_weight_efficiency |  | params | boiler_load_weight_efficiency |  |
| out.params.boiler_other_fuel..j | j | params | boiler_other_fuel |  |
| out.params.booster_water_heater_electric..j | j | params | booster_water_heater_electric |  |
| out.params.booster_water_heater_gas..j | j | params | booster_water_heater_gas |  |
| out.params.broiler_fuel_type |  | params | broiler_fuel_type |  |
| out.params.building_fraction_cooled |  | params | building_fraction_cooled |  |
| out.params.building_fraction_heated |  | params | building_fraction_heated |  |
| out.params.cdd50f |  | params | cdd50f |  |
| out.params.cdd65f |  | params | cdd65f |  |
| out.params.chiller_average_cop..cop | cop | params | chiller_average_cop |  |
| out.params.chiller_capacity..tons | tons | params | chiller_capacity |  |
| out.params.cooling_equipment_capacity..tons | tons | params | cooling_equipment_capacity |  |
| out.params.cooling_tower_water_use..m3 | m3 | params | cooling_tower_water_use |  |
| out.params.daylight_control_fraction |  | params | daylight_control_fraction |  |
| out.params.design_chiller_cop..cop | cop | params | design_chiller_cop |  |
| out.params.design_outdoor_air_flow_rate..m3_per_m2_s | m3_per_m2_s | params | design_outdoor_air_flow_rate |  |
| out.params.dining_type |  | params | dining_type |  |
| out.params.dx_cooling_average_cop..cop | cop | params | dx_cooling_average_cop |  |
| out.params.dx_cooling_capacity_tons..tons | tons | params | dx_cooling_capacity_tons |  |
| out.params.dx_cooling_design_cop..cop | cop | params | dx_cooling_design_cop |  |
| out.params.dx_cooling_design_eer_135_to_240_kbtuh..eer | eer | params | dx_cooling_design_eer_135_to_240_kbtuh |  |
| out.params.dx_cooling_design_eer_240_to_760_kbtuh..eer | eer | params | dx_cooling_design_eer_240_to_760_kbtuh |  |
| out.params.dx_cooling_design_eer_65_to_135_kbtuh..eer | eer | params | dx_cooling_design_eer_65_to_135_kbtuh |  |
| out.params.dx_cooling_design_eer_760_plus_kbtuh..eer | eer | params | dx_cooling_design_eer_760_plus_kbtuh |  |
| out.params.dx_cooling_design_ieer_135_to_240_kbtuh..ieer | ieer | params | dx_cooling_design_ieer_135_to_240_kbtuh |  |
| out.params.dx_cooling_design_ieer_240_to_760_kbtuh..ieer | ieer | params | dx_cooling_design_ieer_240_to_760_kbtuh |  |
| out.params.dx_cooling_design_ieer_65_to_135_kbtuh..ieer | ieer | params | dx_cooling_design_ieer_65_to_135_kbtuh |  |
| out.params.dx_cooling_design_ieer_760_plus_kbtuh..ieer | ieer | params | dx_cooling_design_ieer_760_plus_kbtuh |  |
| out.params.dx_cooling_design_seer_0_to_30_kbtuh..seer | seer | params | dx_cooling_design_seer_0_to_30_kbtuh |  |
| out.params.dx_cooling_design_seer_30_to_65_kbtuh..seer | seer | params | dx_cooling_design_seer_30_to_65_kbtuh |  |
| out.params.dx_cooling_electric..j | j | params | dx_cooling_electric |  |
| out.params.dx_cooling_load..j | j | params | dx_cooling_load |  |
| out.params.dx_heating_average_cop..cop | cop | params | dx_heating_average_cop |  |
| out.params.dx_heating_average_minimum_operating_temperature..c | c | params | dx_heating_average_minimum_operating_temperature |  |
| out.params.dx_heating_average_total_cop..cop | cop | params | dx_heating_average_total_cop |  |
| out.params.dx_heating_capacity_at_0f..kbtu_per_hr | kbtu_per_hr | params | dx_heating_capacity_at_0f |  |
| out.params.dx_heating_capacity_at_17f..kbtu_per_hr | kbtu_per_hr | params | dx_heating_capacity_at_17f |  |
| out.params.dx_heating_capacity_at_5f..kbtu_per_hr | kbtu_per_hr | params | dx_heating_capacity_at_5f |  |
| out.params.dx_heating_capacity_at_rated..kbtu_per_hr | kbtu_per_hr | params | dx_heating_capacity_at_rated |  |
| out.params.dx_heating_defrost_energy..kbtu | kbtu | params | dx_heating_defrost_energy |  |
| out.params.dx_heating_design_cop..cop | cop | params | dx_heating_design_cop |  |
| out.params.dx_heating_design_cop_0f..cop | cop | params | dx_heating_design_cop_0f |  |
| out.params.dx_heating_design_cop_135_to_240_kbtuh..cop | cop | params | dx_heating_design_cop_135_to_240_kbtuh |  |
| out.params.dx_heating_design_cop_17f..cop | cop | params | dx_heating_design_cop_17f |  |
| out.params.dx_heating_design_cop_240_plus_kbtuh..cop | cop | params | dx_heating_design_cop_240_plus_kbtuh |  |
| out.params.dx_heating_design_cop_5f..cop | cop | params | dx_heating_design_cop_5f |  |
| out.params.dx_heating_design_cop_65_to_135_kbtuh..cop | cop | params | dx_heating_design_cop_65_to_135_kbtuh |  |
| out.params.dx_heating_design_hspf_0_to_30_kbtuh..hspf | hspf | params | dx_heating_design_hspf_0_to_30_kbtuh |  |
| out.params.dx_heating_design_hspf_30_to_65_kbtuh..hspf | hspf | params | dx_heating_design_hspf_30_to_65_kbtuh |  |
| out.params.dx_heating_fraction_electric_defrost |  | params | dx_heating_fraction_electric_defrost |  |
| out.params.dx_heating_fraction_electric_supplemental |  | params | dx_heating_fraction_electric_supplemental |  |
| out.params.dx_heating_fraction_supplemental |  | params | dx_heating_fraction_supplemental |  |
| out.params.dx_heating_hours_below_minus_20f..hr | hr | params | dx_heating_hours_below_minus_20f |  |
| out.params.dx_heating_ratio_defrost |  | params | dx_heating_ratio_defrost |  |
| out.params.dx_heating_supplemental_capacity..kbtu_per_hr | kbtu_per_hr | params | dx_heating_supplemental_capacity |  |
| out.params.dx_heating_supplemental_capacity_electric..kbtu_per_hr | kbtu_per_hr | params | dx_heating_supplemental_capacity_electric |  |
| out.params.dx_heating_supplemental_capacity_gas..kbtu_per_hr | kbtu_per_hr | params | dx_heating_supplemental_capacity_gas |  |
| out.params.dx_heating_total_dx_electric..j | j | params | dx_heating_total_dx_electric |  |
| out.params.dx_heating_total_dx_load..j | j | params | dx_heating_total_dx_load |  |
| out.params.dx_heating_total_load..j | j | params | dx_heating_total_load |  |
| out.params.dx_heating_total_supplemental_electric..j | j | params | dx_heating_total_supplemental_electric |  |
| out.params.dx_heating_total_supplemental_gas..j | j | params | dx_heating_total_supplemental_gas |  |
| out.params.dx_heating_total_supplemental_load..j | j | params | dx_heating_total_supplemental_load |  |
| out.params.dx_heating_total_supplemental_load_electric..j | j | params | dx_heating_total_supplemental_load_electric |  |
| out.params.dx_heating_total_supplemental_load_gas..j | j | params | dx_heating_total_supplemental_load_gas |  |
| out.params.economizer_control_type |  | params | economizer_control_type |  |
| out.params.economizer_high_limit_enthalpy..j_per_kg | j_per_kg | params | economizer_high_limit_enthalpy |  |
| out.params.economizer_high_limit_temperature..c | c | params | economizer_high_limit_temperature |  |
| out.params.elevator_energy_consumption..kwh | kwh | params | elevator_energy_consumption |  |
| out.params.ext_roof_area..m2 | m2 | params | ext_roof_area |  |
| out.params.ext_wall_area..m2 | m2 | params | ext_wall_area |  |
| out.params.ext_window_area..m2 | m2 | params | ext_window_area |  |
| out.params.exterior_lighting_power..w | w | params | exterior_lighting_power |  |
| out.params.fluid_hx_demand_inlet_temp..c | c | params | fluid_hx_demand_inlet_temp |  |
| out.params.fluid_hx_demand_outlet_temp..c | c | params | fluid_hx_demand_outlet_temp |  |
| out.params.fluid_hx_supply_inlet_temp..c | c | params | fluid_hx_supply_inlet_temp |  |
| out.params.fluid_hx_supply_outlet_temp..c | c | params | fluid_hx_supply_outlet_temp |  |
| out.params.fluid_hx_transfer_energy..j | j | params | fluid_hx_transfer_energy |  |
| out.params.fryer_fuel_type |  | params | fryer_fuel_type |  |
| out.params.ghx_borehole_depth..ft | ft | params | ghx_borehole_depth |  |
| out.params.ghx_flow_rate..ft3_per_min | ft3_per_min | params | ghx_flow_rate |  |
| out.params.ghx_num_boreholes |  | params | ghx_num_boreholes |  |
| out.params.griddle_fuel_type |  | params | griddle_fuel_type |  |
| out.params.hdd50f |  | params | hdd50f |  |
| out.params.hdd65f |  | params | hdd65f |  |
| out.params.heating_equipment..kbtu_per_hr | kbtu_per_hr | params | heating_equipment |  |
| out.params.hot_water_loop_boiler_fraction |  | params | hot_water_loop_boiler_fraction |  |
| out.params.hot_water_loop_heat_pump_fraction |  | params | hot_water_loop_heat_pump_fraction |  |
| out.params.hot_water_loop_load..j | j | params | hot_water_loop_load |  |
| out.params.hot_water_volume..m3 | m3 | params | hot_water_volume |  |
| out.params.hours_above_65f..hr | hr | params | hours_above_65f |  |
| out.params.hours_below_0f..hr | hr | params | hours_below_0f |  |
| out.params.hours_below_17f..hr | hr | params | hours_below_17f |  |
| out.params.hours_below_50f..hr | hr | params | hours_below_50f |  |
| out.params.hours_below_5f..hr | hr | params | hours_below_5f |  |
| out.params.hours_cooling_setpoint_not_met..hr | hr | params | hours_cooling_setpoint_not_met |  |
| out.params.hours_heating_setpoint_not_met..hr | hr | params | hours_heating_setpoint_not_met |  |
| out.params.hp_water_heater_0_to_40_gal_capacity..w | w | params | hp_water_heater_0_to_40_gal_capacity |  |
| out.params.hp_water_heater_0_to_40_gal_cop..cop | cop | params | hp_water_heater_0_to_40_gal_cop |  |
| out.params.hp_water_heater_0_to_40_gal_total_volume..gal | gal | params | hp_water_heater_0_to_40_gal_total_volume |  |
| out.params.hp_water_heater_40_to_65_gal_capacity..w | w | params | hp_water_heater_40_to_65_gal_capacity |  |
| out.params.hp_water_heater_40_to_65_gal_cop..cop | cop | params | hp_water_heater_40_to_65_gal_cop |  |
| out.params.hp_water_heater_40_to_65_gal_total_volume..gal | gal | params | hp_water_heater_40_to_65_gal_total_volume |  |
| out.params.hp_water_heater_65_to_90_gal_capacity..w | w | params | hp_water_heater_65_to_90_gal_capacity |  |
| out.params.hp_water_heater_65_to_90_gal_cop..cop | cop | params | hp_water_heater_65_to_90_gal_cop |  |
| out.params.hp_water_heater_65_to_90_gal_total_volume..gal | gal | params | hp_water_heater_65_to_90_gal_total_volume |  |
| out.params.hp_water_heater_90_plus_capacity..w | w | params | hp_water_heater_90_plus_capacity |  |
| out.params.hp_water_heater_90_plus_gal_cop..cop | cop | params | hp_water_heater_90_plus_gal_cop |  |
| out.params.hp_water_heater_90_plus_gal_total_volume..gal | gal | params | hp_water_heater_90_plus_gal_total_volume |  |
| out.params.hp_water_heater_backup_electric..j | j | params | hp_water_heater_backup_electric |  |
| out.params.hp_water_heater_capacity..w | w | params | hp_water_heater_capacity |  |
| out.params.hp_water_heater_cop..cop | cop | params | hp_water_heater_cop |  |
| out.params.hp_water_heater_heat_pump_electric..j | j | params | hp_water_heater_heat_pump_electric |  |
| out.params.hp_water_heater_heat_pump_output..j | j | params | hp_water_heater_heat_pump_output |  |
| out.params.hp_water_heater_tank_output..j | j | params | hp_water_heater_tank_output |  |
| out.params.hp_water_heater_total_electric..j | j | params | hp_water_heater_total_electric |  |
| out.params.hp_water_heater_total_output..j | j | params | hp_water_heater_total_output |  |
| out.params.hp_water_heater_total_volume..gal | gal | params | hp_water_heater_total_volume |  |
| out.params.hp_water_heater_unmet_heat_transfer_demand..j | j | params | hp_water_heater_unmet_heat_transfer_demand |  |
| out.params.hvac_chiller_acc_capacity_fraction |  | params | hvac_chiller_acc_capacity_fraction |  |
| out.params.hvac_chiller_ecc_capacity_fraction |  | params | hvac_chiller_ecc_capacity_fraction |  |
| out.params.hvac_chiller_iplv_eer |  | params | hvac_chiller_iplv_eer |  |
| out.params.hvac_chiller_wcc_capacity_fraction |  | params | hvac_chiller_wcc_capacity_fraction |  |
| out.params.interior_electric_equipment_eflh..hr | hr | params | interior_electric_equipment_eflh |  |
| out.params.interior_electric_equipment_power_density..w_per_ft2 | w_per_ft2 | params | interior_electric_equipment_power_density |  |
| out.params.interior_lighting_eflh..hr | hr | params | interior_lighting_eflh |  |
| out.params.interior_lighting_power_density..w_per_ft2 | w_per_ft2 | params | interior_lighting_power_density |  |
| out.params.internal_mass_area_ratio |  | params | internal_mass_area_ratio |  |
| out.params.non_hp_water_heater_0_to_40_gal_total_volume..gal | gal | params | non_hp_water_heater_0_to_40_gal_total_volume |  |
| out.params.non_hp_water_heater_40_to_65_gal_total_volume..gal | gal | params | non_hp_water_heater_40_to_65_gal_total_volume |  |
| out.params.non_hp_water_heater_65_to_90_gal_total_volume..gal | gal | params | non_hp_water_heater_65_to_90_gal_total_volume |  |
| out.params.non_hp_water_heater_90_plus_gal_total_volume..gal | gal | params | non_hp_water_heater_90_plus_gal_total_volume |  |
| out.params.non_hp_water_heater_electric..j | j | params | non_hp_water_heater_electric |  |
| out.params.non_hp_water_heater_gas..j | j | params | non_hp_water_heater_gas |  |
| out.params.non_hp_water_heater_other_fuel..j | j | params | non_hp_water_heater_other_fuel |  |
| out.params.non_hp_water_heater_total_volume_gal..gal | gal | params | non_hp_water_heater_total_volume_gal |  |
| out.params.non_hp_water_heater_unmet_heat_transfer_demand..j | j | params | non_hp_water_heater_unmet_heat_transfer_demand |  |
| out.params.num_air_loops |  | params | num_air_loops |  |
| out.params.num_air_loops_dcv |  | params | num_air_loops_dcv |  |
| out.params.num_air_loops_economizer |  | params | num_air_loops_economizer |  |
| out.params.num_air_loops_heat_recovery |  | params | num_air_loops_heat_recovery |  |
| out.params.num_broilers |  | params | num_broilers |  |
| out.params.num_errors |  | params | num_errors |  |
| out.params.num_fryers |  | params | num_fryers |  |
| out.params.num_griddles |  | params | num_griddles |  |
| out.params.num_ovens |  | params | num_ovens |  |
| out.params.num_ranges |  | params | num_ranges |  |
| out.params.num_steamers |  | params | num_steamers |  |
| out.params.num_warnings |  | params | num_warnings |  |
| out.params.number_of_spaces |  | params | number_of_spaces |  |
| out.params.number_of_surfaces |  | params | number_of_surfaces |  |
| out.params.number_of_zones |  | params | number_of_zones |  |
| out.params.occupant_density_ppl_per_m_2..people_per_m2 | people_per_m2 | params | occupant_density_ppl_per_m_2 |  |
| out.params.occupant_eflh..hr | hr | params | occupant_eflh |  |
| out.params.oven_fuel_type |  | params | oven_fuel_type |  |
| out.params.primary_gas_coil_average_efficiency |  | params | primary_gas_coil_average_efficiency |  |
| out.params.primary_gas_coil_capacity..kbtu_per_hr | kbtu_per_hr | params | primary_gas_coil_capacity |  |
| out.params.pump_count_hvac_const_spd |  | params | pump_count_hvac_const_spd |  |
| out.params.pump_count_hvac_var_spd |  | params | pump_count_hvac_var_spd |  |
| out.params.pump_count_swh_const_spd |  | params | pump_count_swh_const_spd |  |
| out.params.pump_count_swh_var_spd |  | params | pump_count_swh_var_spd |  |
| out.params.pump_flow_weighted_avg_motor_efficiency |  | params | pump_flow_weighted_avg_motor_efficiency |  |
| out.params.pump_flow_weighted_avg_motor_efficiency_const_spd |  | params | pump_flow_weighted_avg_motor_efficiency_const_spd |  |
| out.params.pump_flow_weighted_avg_motor_efficiency_var_spd |  | params | pump_flow_weighted_avg_motor_efficiency_var_spd |  |
| out.params.pump_total_constant_speed_pump_power_w..W | W | params | pump_total_constant_speed_pump_power_w |  |
| out.params.pump_total_variable_speed_pump_power_w..W | W | params | pump_total_variable_speed_pump_power_w |  |
| out.params.pv_system_size..kW | kW | params | pv_system_size |  |
| out.params.range_fuel_type |  | params | range_fuel_type |  |
| out.params.smallest_space_floor_area..m2 | m2 | params | smallest_space_floor_area |  |
| out.params.steamer_fuel_type |  | params | steamer_fuel_type |  |
| out.params.supplemental_gas_coil_average_efficiency |  | params | supplemental_gas_coil_average_efficiency |  |
| out.params.supplemental_gas_coil_capacity..kbtu_per_hr | kbtu_per_hr | params | supplemental_gas_coil_capacity |  |
| out.params.unitary_sys_cycling_excess_electricity_cooling_pcnt |  | params | unitary_sys_cycling_excess_electricity_cooling_pcnt |  |
| out.params.unitary_sys_cycling_excess_electricity_heating_pcnt |  | params | unitary_sys_cycling_excess_electricity_heating_pcnt |  |
| out.params.unitary_sys_cycling_ratio_cooling |  | params | unitary_sys_cycling_ratio_cooling |  |
| out.params.unitary_sys_cycling_ratio_heating |  | params | unitary_sys_cycling_ratio_heating |  |
| out.params.vrf_area_average_indoor_unit_cooling_capacity..w | w | params | vrf_area_average_indoor_unit_cooling_capacity |  |
| out.params.vrf_area_average_indoor_unit_heating_capacity..w | w | params | vrf_area_average_indoor_unit_heating_capacity |  |
| out.params.vrf_average_line_height..m | m | params | vrf_average_line_height |  |
| out.params.vrf_average_line_length..m | m | params | vrf_average_line_length |  |
| out.params.vrf_average_num_compressors |  | params | vrf_average_num_compressors |  |
| out.params.vrf_average_outdoor_unit_cooling_capacity..w | w | params | vrf_average_outdoor_unit_cooling_capacity |  |
| out.params.vrf_average_outdoor_unit_heating_capacity..w | w | params | vrf_average_outdoor_unit_heating_capacity |  |
| out.params.vrf_cooling_average_cop |  | params | vrf_cooling_average_cop |  |
| out.params.vrf_cooling_design_cop |  | params | vrf_cooling_design_cop |  |
| out.params.vrf_cooling_design_cop_110f |  | params | vrf_cooling_design_cop_110f |  |
| out.params.vrf_cooling_design_cop_35f |  | params | vrf_cooling_design_cop_35f |  |
| out.params.vrf_cooling_design_cop_60f |  | params | vrf_cooling_design_cop_60f |  |
| out.params.vrf_cooling_design_cop_85f |  | params | vrf_cooling_design_cop_85f |  |
| out.params.vrf_heating_average_cop |  | params | vrf_heating_average_cop |  |
| out.params.vrf_heating_average_total_cop |  | params | vrf_heating_average_total_cop |  |
| out.params.vrf_heating_design_cop |  | params | vrf_heating_design_cop |  |
| out.params.vrf_heating_design_cop_0f |  | params | vrf_heating_design_cop_0f |  |
| out.params.vrf_heating_design_cop_20f |  | params | vrf_heating_design_cop_20f |  |
| out.params.vrf_heating_design_cop_40f |  | params | vrf_heating_design_cop_40f |  |
| out.params.vrf_heating_design_cop_minus22f |  | params | vrf_heating_design_cop_minus22f |  |
| out.params.vrf_heating_fraction_supplemental |  | params | vrf_heating_fraction_supplemental |  |
| out.params.vrf_heating_total_supplemental_electric..j | j | params | vrf_heating_total_supplemental_electric |  |
| out.params.vrf_heating_total_supplemental_gas..j | j | params | vrf_heating_total_supplemental_gas |  |
| out.params.vrf_heating_total_supplemental_load..j | j | params | vrf_heating_total_supplemental_load |  |
| out.params.vrf_heating_total_supplemental_load_electric..j | j | params | vrf_heating_total_supplemental_load_electric |  |
| out.params.vrf_heating_total_supplemental_load_gas..j | j | params | vrf_heating_total_supplemental_load_gas |  |
| out.params.vrf_temperature_type |  | params | vrf_temperature_type |  |
| out.params.vrf_total_cooling_load..j | j | params | vrf_total_cooling_load |  |
| out.params.vrf_total_heat_recovery..j | j | params | vrf_total_heat_recovery |  |
| out.params.vrf_total_heating_load..j | j | params | vrf_total_heating_load |  |
| out.params.vrf_total_indoor_unit_cooling_capacity..w | w | params | vrf_total_indoor_unit_cooling_capacity |  |
| out.params.vrf_total_indoor_unit_heating_capacity..w | w | params | vrf_total_indoor_unit_heating_capacity |  |
| out.params.vrf_total_outdoor_unit_cooling_capacity..w | w | params | vrf_total_outdoor_unit_cooling_capacity |  |
| out.params.vrf_total_outdoor_unit_heating_capacity..w | w | params | vrf_total_outdoor_unit_heating_capacity |  |
| out.params.wa_hp_cooling_average_cop..cop | cop | params | wa_hp_cooling_average_cop |  |
| out.params.wa_hp_cooling_capacity..w | w | params | wa_hp_cooling_capacity |  |
| out.params.wa_hp_cooling_design_cop..cop | cop | params | wa_hp_cooling_design_cop |  |
| out.params.wa_hp_cooling_electric..j | j | params | wa_hp_cooling_electric |  |
| out.params.wa_hp_cooling_load..j | j | params | wa_hp_cooling_load |  |
| out.params.wa_hp_heating_average_cop..cop | cop | params | wa_hp_heating_average_cop |  |
| out.params.wa_hp_heating_capacity..w | w | params | wa_hp_heating_capacity |  |
| out.params.wa_hp_heating_design_cop..cop | cop | params | wa_hp_heating_design_cop |  |
| out.params.wa_hp_heating_electric..j | j | params | wa_hp_heating_electric |  |
| out.params.wa_hp_heating_load..j | j | params | wa_hp_heating_load |  |
| out.params.window_to_wall_ratio |  | params | window_to_wall_ratio |  |
| out.params.ww_hp_cooling_average_cop..cop | cop | params | ww_hp_cooling_average_cop |  |
| out.params.ww_hp_cooling_cap_weight_cop..cop | cop | params | ww_hp_cooling_cap_weight_cop |  |
| out.params.ww_hp_cooling_capacity..kbtu_per_hr | kbtu_per_hr | params | ww_hp_cooling_capacity |  |
| out.params.ww_hp_cooling_load_weight_cop..cop | cop | params | ww_hp_cooling_load_weight_cop |  |
| out.params.ww_hp_cooling_source_inlet_temp..c | c | params | ww_hp_cooling_source_inlet_temp |  |
| out.params.ww_hp_cooling_total_electric..j | j | params | ww_hp_cooling_total_electric |  |
| out.params.ww_hp_cooling_total_load..j | j | params | ww_hp_cooling_total_load |  |
| out.params.ww_hp_heating_average_cop..cop | cop | params | ww_hp_heating_average_cop |  |
| out.params.ww_hp_heating_cap_weight_cop..cop | cop | params | ww_hp_heating_cap_weight_cop |  |
| out.params.ww_hp_heating_capacity..kbtu_per_hr | kbtu_per_hr | params | ww_hp_heating_capacity |  |
| out.params.ww_hp_heating_load_weight_cop..cop | cop | params | ww_hp_heating_load_weight_cop |  |
| out.params.ww_hp_heating_source_inlet_temp..c | c | params | ww_hp_heating_source_inlet_temp |  |
| out.params.ww_hp_heating_total_electric..j | j | params | ww_hp_heating_total_electric |  |
| out.params.ww_hp_heating_total_load..j | j | params | ww_hp_heating_total_load |  |
| out.params.zone_hvac_fan_power_minimum_flow_fraction |  | params | zone_hvac_fan_power_minimum_flow_fraction |  |
| out.params.zone_hvac_fan_static_pressure..inwc | inwc | params | zone_hvac_fan_static_pressure |  |
| out.params.zone_hvac_fan_total_efficiency |  | params | zone_hvac_fan_total_efficiency |  |

### Measure Upgrade Packages

#### release_1

| Upgrade ID | Package Name |
| --- | --- |
| 0 | Baseline |
| 1 | Variable Speed HP RTU, Electric Backup |
| 2 | Variable Speed HP RTU, Original Heating Fuel Backup |
| 3 | Variable Speed HP RTU, Electric Backup, Energy Recovery |
| 4 | Standard Performance HP RTU, Electric Backup |
| 5 | Standard Performance HP RTU using Lab Data, Electric Backup |
| 6 | Standard Performance HP RTU, Electric Backup + Roof Insulation |
| 7 | Standard Performance HP RTU, Electric Backup + New Windows |
| 8 | Standard Performance HP RTU, Electric Backup, 32F Minimum Compressor Lockout |
| 9 | Standard Performance HP RTU, Electric Backup, 2F Unoccupied Htg Thermostat Setback |
| 10 | Cold Climate Challenge HP RTU, Electric Backup |
| 11 | VRF with DOAS |
| 12 | VRF with 25pct Upsizing Allowance |
| 13 | DOAS HP Minisplits |
| 14 | HP Boiler, Electric Backup |
| 15 | HP Boiler, Gas Backup |
| 16 | Condensing Gas Boilers |
| 17 | Electric Resistance Boilers |
| 18 | Air Side Economizers for AHUs |
| 19 | Demand Control Ventilation |
| 20 | Energy Recovery for AHUs |
| 21 | Advanced RTU Controls |
| 22 | Unoccupied AHU Control |
| 23 | Ideal Thermal Air Loads |
| 24 | Hydronic Water-to-Water Geothermal Heat Pump |
| 25 | Packaged Water-to-Air Geothermal Heat Pump |
| 26 | Console Water-to-Air Geothermal Heat Pump |
| 27 | Chiller Replacement |
| 28 | Demand Flexibility, Thermostat Control, Load Shed for Daily Bldg Peak Reduction |
| 29 | Demand Flexibility, Thermostat Control, Load Shift for Daily Bldg Peak Reduction |
| 30 | Demand Flexibility, Lighting Control, Load Shed for Daily Bldg Peak Reduction |
| 31 | Demand Flexibility, Lighting Control, Load Shed for Daily GHG Emission Reduction |
| 32 | Demand Flexibility, Thermostat Control, Load Shed for Grid Peak Reduction |
| 33 | Demand Flexibility, Lighting Control, Load Shed for Grid Peak Reduction |
| 34 | Demand Flexibility, Plug Load Control (GEB Gem), Load Shed for Grid Peak Reduction |
| 35 | Demand Flexibility, Lighting Control (GEB Gem), Load Shed for Grid Peak Reduction |
| 36 | Demand Flexibility, Thermostat Control (GEB Gem), Load Shed for Grid Peak Reduction |
| 37 | Demand Flexibility, Preheat (GEB Gem), Load Shift for Grid Peak Reduction |
| 38 | Demand Flexibility, Precool (GEB Gem), Load Shift for Grid Peak Reduction |
| 39 | LED Lighting |
| 40 | Electric Kitchen Equipment |
| 41 | Photovoltaics with 40pct Roof Coverage |
| 42 | Wall Insulation |
| 43 | Roof Insulation |
| 44 | Secondary Windows |
| 45 | Window Film |
| 46 | New Windows |
| 47 | Package 1, Wall + Roof Insulation + New Windows |
| 48 | Package 2, LED Lighting + Variable Speed HP RTU or HP Boilers |
| 49 | Package 3, Package 2 with Standard Performance HP RTU |
| 50 | Package 4, Package 1 + Package 2 |
| 51 | Package 5, Variable Speed HP RTU or HP Boilers + Economizer + DCV + Energy Recovery |
| 52 | Package 6, Demand Flexibility, Lighting + Thermostat Control, Load Shed for Daily Bldg Peak Reduction |
| 53 | Package 7, Demand Flexibility, Lighting + Thermostat Control, Load Shed for Grid Peak Reduction |
| 54 | Package 8, Demand Flexibility, Lighting + Thermostat Control Load Shed for Daily Bldg Peak Reduction + PV |
| 55 | Package 9, Hydronic GHP or Packaged GHP or Console GHP |
| 56 | Package 10, Package 1 + Package 9 |
| 57 | Package 11, Package 10 + LED Lighting |

#### release_2

| Upgrade ID | Package Name |
| --- | --- |
| 0 | Baseline |
| 1 | Variable Speed HP RTU, Electric Backup |
| 2 | Variable Speed HP RTU, Original Heating Fuel Backup |
| 3 | Variable Speed HP RTU, Electric Backup, Energy Recovery |
| 4 | Standard Performance HP RTU, Electric Backup |
| 5 | Standard Performance HP RTU using Lab Data, Electric Backup |
| 6 | Standard Performance HP RTU, Electric Backup + Roof Insulation |
| 7 | Standard Performance HP RTU, Electric Backup + New Windows |
| 8 | Standard Performance HP RTU, Electric Backup, 32F Minimum Compressor Lockout |
| 9 | Standard Performance HP RTU, Electric Backup, 2F Unoccupied Htg Thermostat Setback |
| 10 | Cold Climate Challenge HP RTU, Electric Backup |
| 11 | VRF with DOAS |
| 12 | VRF with 25pct Upsizing Allowance |
| 13 | DOAS HP Minisplits |
| 14 | HP Boiler, Electric Backup |
| 15 | HP Boiler, Gas Backup |
| 16 | Condensing Gas Boilers |
| 17 | Electric Resistance Boilers |
| 18 | Air Side Economizers for AHUs |
| 19 | Demand Control Ventilation |
| 20 | Energy Recovery for AHUs |
| 21 | Advanced RTU Controls |
| 22 | Unoccupied AHU Control |
| 23 | Ideal Thermal Air Loads |
| 24 | Hydronic Water-to-Water Geothermal Heat Pump |
| 25 | Packaged Water-to-Air Geothermal Heat Pump |
| 26 | Console Water-to-Air Geothermal Heat Pump |
| 27 | Chiller Replacement |
| 28 | Demand Flexibility, Thermostat Control, Load Shed for Daily Bldg Peak Reduction |
| 29 | Demand Flexibility, Thermostat Control, Load Shift for Daily Bldg Peak Reduction |
| 30 | Demand Flexibility, Lighting Control, Load Shed for Daily Bldg Peak Reduction |
| 31 | Demand Flexibility, Lighting Control, Load Shed for Daily GHG Emission Reduction |
| 32 | Demand Flexibility, Thermostat Control, Load Shed for Grid Peak Reduction |
| 33 | Demand Flexibility, Lighting Control, Load Shed for Grid Peak Reduction |
| 34 | Demand Flexibility, Plug Load Control (GEB Gem), Load Shed for Grid Peak Reduction |
| 35 | Demand Flexibility, Lighting Control (GEB Gem), Load Shed for Grid Peak Reduction |
| 36 | Demand Flexibility, Thermostat Control (GEB Gem), Load Shed for Grid Peak Reduction |
| 37 | Demand Flexibility, Preheat (GEB Gem), Load Shift for Grid Peak Reduction |
| 38 | Demand Flexibility, Precool (GEB Gem), Load Shift for Grid Peak Reduction |
| 39 | LED Lighting |
| 40 | Lighting Controls |
| 41 | Electric Kitchen Equipment |
| 42 | Photovoltaics with 40pct Roof Coverage |
| 43 | Photovoltaics with 40pct Roof Coverage + Battery Storage |
| 44 | Wall Insulation |
| 45 | Roof Insulation |
| 46 | Secondary Windows |
| 47 | Window Film |
| 48 | New Windows |
| 49 | Code Envelope |
| 50 | Package 1, Wall + Roof Insulation + New Windows |
| 51 | Package 2, LED Lighting + Variable Speed HP RTU or HP Boilers |
| 52 | Package 3, Package 2 with Standard Performance HP RTU |
| 53 | Package 4, Package 1 + Package 2 |
| 54 | Package 5, Variable Speed HP RTU or HP Boilers + Economizer + DCV + Energy Recovery |
| 55 | Package 9, Hydronic GHP or Packaged GHP or Console GHP |
| 56 | Package 7, Demand Flexibility, Lighting + Thermostat Control, Load Shed for Grid Peak Reduction |
| 57 | Package 8, Demand Flexibility, Lighting + Thermostat Control Load Shed for Daily Bldg Peak Reduction + PV |
| 58 | Package 6, Demand Flexibility, Lighting + Thermostat Control, Load Shed for Daily Bldg Peak Reduction |
| 59 | Package 10, Package 1 + Package 9 |
| 60 | Package 11, Package 10 + LED Lighting |
| 61 | Package 12, Photovoltaics with 40pct Roof Coverage + Roof Insulation |

#### release_3

| Upgrade ID | Package Name |
| --- | --- |
| 0 | Baseline |
| 1 | Variable Speed HP RTU, Electric Backup |
| 2 | Variable Speed HP RTU, Original Heating Fuel Backup |
| 3 | Variable Speed HP RTU, Electric Backup, Energy Recovery |
| 4 | Standard Performance HP RTU, Electric Backup |
| 5 | Standard Performance HP RTU using Lab Data, Electric Backup |
| 6 | Standard Performance HP RTU, Electric Backup + Roof Insulation |
| 7 | Standard Performance HP RTU, Electric Backup + New Windows |
| 8 | Standard Performance HP RTU, Electric Backup, 32F Minimum Compressor Lockout |
| 9 | Standard Performance HP RTU, Electric Backup, 2F Unoccupied Htg Thermostat Setback |
| 10 | Commercial HVAC Challenge HP RTU, Electric Backup |
| 11 | Advanced RTU |
| 12 | VRF with DOAS |
| 13 | VRF with 25pct Upsizing Allowance |
| 14 | DOAS HP Minisplits |
| 15 | HP Boiler, Electric Backup |
| 16 | HP Boiler, Gas Backup |
| 17 | Condensing Gas Boilers |
| 18 | Electric Resistance Boilers |
| 19 | Air Side Economizers for AHUs |
| 20 | Demand Control Ventilation |
| 21 | Energy Recovery for AHUs |
| 22 | Advanced RTU Controls |
| 23 | Unoccupied AHU Control |
| 24 | Fan Static Pressure Reset for Multizone VAV |
| 25 | Thermostat Setbacks |
| 26 | VFD Pumps |
| 27 | Ideal Thermal Air Loads |
| 28 | Hydronic Water-to-Water Geothermal Heat Pump |
| 29 | Packaged Water-to-Air Geothermal Heat Pump |
| 30 | Console Water-to-Air Geothermal Heat Pump |
| 31 | Chiller Replacement |
| 32 | Demand Flexibility, Thermostat Control, Load Shed for Daily Bldg Peak Reduction |
| 33 | Demand Flexibility, Thermostat Control, Load Shift for Daily Bldg Peak Reduction |
| 34 | Demand Flexibility, Lighting Control, Load Shed for Daily Bldg Peak Reduction |
| 35 | Demand Flexibility, Lighting Control, Load Shed for Daily GHG Emission Reduction |
| 36 | Demand Flexibility, Thermostat Control, Load Shed for Grid Peak Reduction |
| 37 | Demand Flexibility, Lighting Control, Load Shed for Grid Peak Reduction |
| 38 | Demand Flexibility, Plug Load Control (GEB Gem), Load Shed for Grid Peak Reduction |
| 39 | Demand Flexibility, Lighting Control (GEB Gem), Load Shed for Grid Peak Reduction |
| 40 | Demand Flexibility, Thermostat Control (GEB Gem), Load Shed for Grid Peak Reduction |
| 41 | Demand Flexibility, Preheat (GEB Gem), Load Shift for Grid Peak Reduction |
| 42 | Demand Flexibility, Precool (GEB Gem), Load Shift for Grid Peak Reduction |
| 43 | LED Lighting |
| 44 | Lighting Controls |
| 45 | Electric Kitchen Equipment |
| 46 | Photovoltaics with 40pct Roof Coverage |
| 47 | Photovoltaics with 40pct Roof Coverage + Battery Storage |
| 48 | Wall Insulation |
| 49 | Roof Insulation |
| 50 | Secondary Windows |
| 51 | Window Film |
| 52 | New Windows |
| 53 | Code Envelope |
| 54 | Package 1, Wall + Roof Insulation + New Windows |
| 55 | Package 2, LED Lighting + Variable Speed HP RTU or HP Boilers |
| 56 | Package 3, Package 2 with Standard Performance HP RTU |
| 57 | Package 4, Package 1 + Package 2 |
| 58 | Package 5, Variable Speed HP RTU or HP Boilers + Economizer + DCV + Energy Recovery |
| 59 | Package 6, Hydronic GHP or Packaged GHP or Console GHP |
| 60 | Package 7, Demand Flexibility, Lighting + Thermostat Control, Load Shed for Grid Peak Reduction |
| 61 | Package 8, Demand Flexibility, Lighting + Thermostat Control Load Shed for Daily Bldg Peak Reduction + PV |
| 62 | Package 9, Demand Flexibility, Lighting + Thermostat Control, Load Shed for Daily Bldg Peak Reduction |
| 63 | Package 10, Package 1 + Package 6 |
| 64 | Package 11, Package 10 + LED Lighting |
| 65 | Package 12, Photovoltaics with 40pct Roof Coverage + Roof Insulation |

## ResStock

- Default release: `release_1` with `weather_year="amy2018"`
- OEDI path: `2025/resstock_amy2018_release_1/` (also supports `2025/resstock_amy2012_release_1/`)
- Record type: residential dwelling-unit record
- Building type column: `in.geometry_building_type_recs`
- Result variables: 385

### Building Types

- `Mobile Home`
- `Single-Family Detached`
- `Single-Family Attached`
- `Multi-Family with 2 - 4 Units`
- `Multi-Family with 5+ Units`

### Result Variables

| Name | Unit | Source | End Use | Metric |
| --- | --- | --- | --- | --- |
| out.params.door_area..ft2 | ft2 | params | door_area |  |
| out.params.duct_unconditioned_surface_area..ft2 | ft2 | params | duct_unconditioned_surface_area |  |
| out.params.floor_area_attic..ft2 | ft2 | params | floor_area_attic |  |
| out.params.floor_area_attic_insulation_increase..ft2_delta_r_value | ft2_delta_r_value | params | floor_area_attic_insulation_increase |  |
| out.params.floor_area_conditioned_infiltration_reduction..ft2_delta_ach50 | ft2_delta_ach50 | params | floor_area_conditioned_infiltration_reduction |  |
| out.params.floor_area_foundation..ft2 | ft2 | params | floor_area_foundation |  |
| out.params.floor_area_lighting..ft2 | ft2 | params | floor_area_lighting |  |
| out.params.flow_rate_mechanical_ventilation..cfm | cfm | params | flow_rate_mechanical_ventilation |  |
| out.params.rim_joist_area_above_grade_exterior..ft2 | ft2 | params | rim_joist_area_above_grade_exterior |  |
| out.params.roof_area..ft2 | ft2 | params | roof_area |  |
| out.params.size_cooling_system_primary..kbtu_per_hr | kbtu_per_hr | params | size_cooling_system_primary |  |
| out.params.size_heat_pump_backup_primary..kbtu_per_hr | kbtu_per_hr | params | size_heat_pump_backup_primary |  |
| out.params.size_heating_system_primary..kbtu_per_hr | kbtu_per_hr | params | size_heating_system_primary |  |
| out.params.size_heating_system_secondary..kbtu_per_hr | kbtu_per_hr | params | size_heating_system_secondary |  |
| out.params.size_water_heater..gal | gal | params | size_water_heater |  |
| out.params.slab_perimeter_exposed_conditioned..ft | ft | params | slab_perimeter_exposed_conditioned |  |
| out.params.wall_area_above_grade_conditioned..ft2 | ft2 | params | wall_area_above_grade_conditioned |  |
| out.params.wall_area_above_grade_exterior..ft2 | ft2 | params | wall_area_above_grade_exterior |  |
| out.params.wall_area_below_grade..ft2 | ft2 | params | wall_area_below_grade |  |
| out.params.window_area..ft2 | ft2 | params | window_area |  |
| out.params.hvac_geothermal_loop_borehole_trench_count |  | params | hvac_geothermal_loop_borehole_trench_count |  |
| out.params.hvac_geothermal_loop_borehole_trench_length..ft | ft | params | hvac_geothermal_loop_borehole_trench_length |  |
| out.electricity.ceiling_fan.energy_consumption..kwh | kwh | electricity | ceiling_fan | energy_consumption |
| out.electricity.clothes_dryer.energy_consumption..kwh | kwh | electricity | clothes_dryer | energy_consumption |
| out.electricity.clothes_washer.energy_consumption..kwh | kwh | electricity | clothes_washer | energy_consumption |
| out.electricity.cooling_fans_pumps.energy_consumption..kwh | kwh | electricity | cooling_fans_pumps | energy_consumption |
| out.electricity.cooling.energy_consumption..kwh | kwh | electricity | cooling | energy_consumption |
| out.electricity.dishwasher.energy_consumption..kwh | kwh | electricity | dishwasher | energy_consumption |
| out.electricity.ev_charging.energy_consumption..kwh | kwh | electricity | ev_charging | energy_consumption |
| out.electricity.freezer.energy_consumption..kwh | kwh | electricity | freezer | energy_consumption |
| out.electricity.heating_fans_pumps.energy_consumption..kwh | kwh | electricity | heating_fans_pumps | energy_consumption |
| out.electricity.heating_hp_bkup.energy_consumption..kwh | kwh | electricity | heating_hp_bkup | energy_consumption |
| out.electricity.heating_hp_bkup_fa.energy_consumption..kwh | kwh | electricity | heating_hp_bkup_fa | energy_consumption |
| out.electricity.heating.energy_consumption..kwh | kwh | electricity | heating | energy_consumption |
| out.electricity.permanent_spa_heat.energy_consumption..kwh | kwh | electricity | permanent_spa_heat | energy_consumption |
| out.electricity.permanent_spa_pump.energy_consumption..kwh | kwh | electricity | permanent_spa_pump | energy_consumption |
| out.electricity.hot_water.energy_consumption..kwh | kwh | electricity | hot_water | energy_consumption |
| out.electricity.hot_water_solar_th.energy_consumption..kwh | kwh | electricity | hot_water_solar_th | energy_consumption |
| out.electricity.lighting_exterior.energy_consumption..kwh | kwh | electricity | lighting_exterior | energy_consumption |
| out.electricity.lighting_garage.energy_consumption..kwh | kwh | electricity | lighting_garage | energy_consumption |
| out.electricity.lighting_interior.energy_consumption..kwh | kwh | electricity | lighting_interior | energy_consumption |
| out.electricity.mech_vent.energy_consumption..kwh | kwh | electricity | mech_vent | energy_consumption |
| out.electricity.plug_loads.energy_consumption..kwh | kwh | electricity | plug_loads | energy_consumption |
| out.electricity.pool_heater.energy_consumption..kwh | kwh | electricity | pool_heater | energy_consumption |
| out.electricity.pool_pump.energy_consumption..kwh | kwh | electricity | pool_pump | energy_consumption |
| out.electricity.pv.energy_consumption..kwh | kwh | electricity | pv | energy_consumption |
| out.electricity.range_oven.energy_consumption..kwh | kwh | electricity | range_oven | energy_consumption |
| out.electricity.refrigerator.energy_consumption..kwh | kwh | electricity | refrigerator | energy_consumption |
| out.electricity.television.energy_consumption..kwh | kwh | electricity | television | energy_consumption |
| out.electricity.well_pump.energy_consumption..kwh | kwh | electricity | well_pump | energy_consumption |
| out.fuel_oil.heating_hp_bkup.energy_consumption..kwh | kwh | fuel_oil | heating_hp_bkup | energy_consumption |
| out.fuel_oil.heating.energy_consumption..kwh | kwh | fuel_oil | heating | energy_consumption |
| out.fuel_oil.hot_water.energy_consumption..kwh | kwh | fuel_oil | hot_water | energy_consumption |
| out.natural_gas.clothes_dryer.energy_consumption..kwh | kwh | natural_gas | clothes_dryer | energy_consumption |
| out.natural_gas.fireplace.energy_consumption..kwh | kwh | natural_gas | fireplace | energy_consumption |
| out.natural_gas.grill.energy_consumption..kwh | kwh | natural_gas | grill | energy_consumption |
| out.natural_gas.heating_hp_bkup.energy_consumption..kwh | kwh | natural_gas | heating_hp_bkup | energy_consumption |
| out.natural_gas.heating.energy_consumption..kwh | kwh | natural_gas | heating | energy_consumption |
| out.natural_gas.permanent_spa_heat.energy_consumption..kwh | kwh | natural_gas | permanent_spa_heat | energy_consumption |
| out.natural_gas.hot_water.energy_consumption..kwh | kwh | natural_gas | hot_water | energy_consumption |
| out.natural_gas.lighting.energy_consumption..kwh | kwh | natural_gas | lighting | energy_consumption |
| out.natural_gas.pool_heater.energy_consumption..kwh | kwh | natural_gas | pool_heater | energy_consumption |
| out.natural_gas.range_oven.energy_consumption..kwh | kwh | natural_gas | range_oven | energy_consumption |
| out.propane.clothes_dryer.energy_consumption..kwh | kwh | propane | clothes_dryer | energy_consumption |
| out.propane.heating_hp_bkup.energy_consumption..kwh | kwh | propane | heating_hp_bkup | energy_consumption |
| out.propane.heating.energy_consumption..kwh | kwh | propane | heating | energy_consumption |
| out.propane.hot_water.energy_consumption..kwh | kwh | propane | hot_water | energy_consumption |
| out.propane.range_oven.energy_consumption..kwh | kwh | propane | range_oven | energy_consumption |
| out.site_energy.net.energy_consumption..kwh | kwh | site_energy | net | energy_consumption |
| out.site_energy.total.energy_consumption..kwh | kwh | site_energy | total | energy_consumption |
| out.electricity.net.energy_consumption..kwh | kwh | electricity | net | energy_consumption |
| out.electricity.total.energy_consumption..kwh | kwh | electricity | total | energy_consumption |
| out.fuel_oil.total.energy_consumption..kwh | kwh | fuel_oil | total | energy_consumption |
| out.natural_gas.total.energy_consumption..kwh | kwh | natural_gas | total | energy_consumption |
| out.propane.total.energy_consumption..kwh | kwh | propane | total | energy_consumption |
| out.hot_water.clothes_washer..gal | gal | hot_water | clothes_washer |  |
| out.hot_water.dishwasher..gal | gal | hot_water | dishwasher |  |
| out.hot_water.distribution_waste..gal | gal | hot_water | distribution_waste |  |
| out.hot_water.fixtures..gal | gal | hot_water | fixtures |  |
| out.capacity.cooling..btu_per_hr | btu_per_hr | capacity | cooling |  |
| out.capacity.heat_pump_backup..btu_per_hr | btu_per_hr | capacity | heat_pump_backup |  |
| out.capacity.heating..btu_per_hr | btu_per_hr | capacity | heating |  |
| out.load.cooling.energy_delivered..kbtu | kbtu | load | cooling | energy_delivered |
| out.load.heating.energy_delivered..kbtu | kbtu | load | heating | energy_delivered |
| out.load.hot_water.energy_delivered..kbtu | kbtu | load | hot_water | energy_delivered |
| out.load.hot_water.energy_solar_thermal..kbtu | kbtu | load | hot_water | energy_solar_thermal |
| out.load.hot_water.energy_tank_losses..kbtu | kbtu | load | hot_water | energy_tank_losses |
| out.load.cooling.peak..kbtu_per_hr | kbtu_per_hr | load | cooling | peak |
| out.load.heating.peak..kbtu_per_hr | kbtu_per_hr | load | heating | peak |
| out.qoi.electricity.maximum_daily_peak_summer..kw | kw | qoi | electricity | maximum_daily_peak_summer |
| out.qoi.electricity.maximum_daily_peak_winter..kw | kw | qoi | electricity | maximum_daily_peak_winter |
| out.unmet_hours.cooling..hr | hr | unmet_hours | cooling |  |
| out.unmet_hours.ev_driving..hr | hr | unmet_hours | ev_driving |  |
| out.unmet_hours.heating..hr | hr | unmet_hours | heating |  |
| out.emissions.electricity.lrmer_mid_case_25..co2e_kg | co2e_kg | emissions | electricity | lrmer_mid_case_25 |
| out.emissions.total.lrmer_mid_case_25..co2e_kg | co2e_kg | emissions | total | lrmer_mid_case_25 |
| out.emissions.electricity.lrmer_mid_case_15..co2e_kg | co2e_kg | emissions | electricity | lrmer_mid_case_15 |
| out.emissions.total.lrmer_mid_case_15..co2e_kg | co2e_kg | emissions | total | lrmer_mid_case_15 |
| out.emissions.electricity.lrmer_high_re_cost_25..co2e_kg | co2e_kg | emissions | electricity | lrmer_high_re_cost_25 |
| out.emissions.total.lrmer_high_re_cost_25..co2e_kg | co2e_kg | emissions | total | lrmer_high_re_cost_25 |
| out.emissions.electricity.lrmer_high_re_cost_15..co2e_kg | co2e_kg | emissions | electricity | lrmer_high_re_cost_15 |
| out.emissions.total.lrmer_high_re_cost_15..co2e_kg | co2e_kg | emissions | total | lrmer_high_re_cost_15 |
| out.emissions.electricity.lrmer_low_re_cost_25..co2e_kg | co2e_kg | emissions | electricity | lrmer_low_re_cost_25 |
| out.emissions.total.lrmer_low_re_cost_25..co2e_kg | co2e_kg | emissions | total | lrmer_low_re_cost_25 |
| out.emissions.electricity.lrmer_low_re_cost_15..co2e_kg | co2e_kg | emissions | electricity | lrmer_low_re_cost_15 |
| out.emissions.total.lrmer_low_re_cost_15..co2e_kg | co2e_kg | emissions | total | lrmer_low_re_cost_15 |
| out.emissions.electricity.lrmer_low_re_cost_high_ng_price_25..co2e_kg | co2e_kg | emissions | electricity | lrmer_low_re_cost_high_ng_price_25 |
| out.emissions.total.lrmer_low_re_cost_high_ng_price_25..co2e_kg | co2e_kg | emissions | total | lrmer_low_re_cost_high_ng_price_25 |
| out.emissions.electricity.lrmer_low_re_cost_high_ng_price_15..co2e_kg | co2e_kg | emissions | electricity | lrmer_low_re_cost_high_ng_price_15 |
| out.emissions.total.lrmer_low_re_cost_high_ng_price_15..co2e_kg | co2e_kg | emissions | total | lrmer_low_re_cost_high_ng_price_15 |
| out.emissions.electricity.lrmer_high_re_cost_low_ng_price_25..co2e_kg | co2e_kg | emissions | electricity | lrmer_high_re_cost_low_ng_price_25 |
| out.emissions.total.lrmer_high_re_cost_low_ng_price_25..co2e_kg | co2e_kg | emissions | total | lrmer_high_re_cost_low_ng_price_25 |
| out.emissions.electricity.lrmer_high_re_cost_low_ng_price_15..co2e_kg | co2e_kg | emissions | electricity | lrmer_high_re_cost_low_ng_price_15 |
| out.emissions.total.lrmer_high_re_cost_low_ng_price_15..co2e_kg | co2e_kg | emissions | total | lrmer_high_re_cost_low_ng_price_15 |
| out.emissions.electricity.aer_high_re_cost_avg..co2e_kg | co2e_kg | emissions | electricity | aer_high_re_cost_avg |
| out.emissions.total.aer_high_re_cost_avg..co2e_kg | co2e_kg | emissions | total | aer_high_re_cost_avg |
| out.emissions.electricity.aer_high_re_cost_low_ng_price_avg..co2e_kg | co2e_kg | emissions | electricity | aer_high_re_cost_low_ng_price_avg |
| out.emissions.total.aer_high_re_cost_low_ng_price_avg..co2e_kg | co2e_kg | emissions | total | aer_high_re_cost_low_ng_price_avg |
| out.emissions.electricity.aer_low_re_cost_avg..co2e_kg | co2e_kg | emissions | electricity | aer_low_re_cost_avg |
| out.emissions.total.aer_low_re_cost_avg..co2e_kg | co2e_kg | emissions | total | aer_low_re_cost_avg |
| out.emissions.electricity.aer_low_re_cost_high_ng_price_avg..co2e_kg | co2e_kg | emissions | electricity | aer_low_re_cost_high_ng_price_avg |
| out.emissions.total.aer_low_re_cost_high_ng_price_avg..co2e_kg | co2e_kg | emissions | total | aer_low_re_cost_high_ng_price_avg |
| out.emissions.electricity.aer_mid_case_avg..co2e_kg | co2e_kg | emissions | electricity | aer_mid_case_avg |
| out.emissions.total.aer_mid_case_avg..co2e_kg | co2e_kg | emissions | total | aer_mid_case_avg |
| out.utility_bills.electricity_bill..usd | usd | utility_bills | electricity_bill |  |
| out.utility_bills.fuel_oil_bill..usd | usd | utility_bills | fuel_oil_bill |  |
| out.utility_bills.natural_gas_bill..usd | usd | utility_bills | natural_gas_bill |  |
| out.utility_bills.propane_bill..usd | usd | utility_bills | propane_bill |  |
| out.utility_bills.total_bill..usd | usd | utility_bills | total_bill |  |
| out.params.panel_load_total_load.2023_nec_existing_dwelling_load_based..w | w | params | panel_load_total_load | 2023_nec_existing_dwelling_load_based |
| out.params.panel_load_occupied_capacity.2023_nec_existing_dwelling_load_based..a | a | params | panel_load_occupied_capacity | 2023_nec_existing_dwelling_load_based |
| out.params.panel_load_headroom_capacity.2023_nec_existing_dwelling_load_based..a | a | params | panel_load_headroom_capacity | 2023_nec_existing_dwelling_load_based |
| out.params.panel_load_clothes_dryer..w | w | params | panel_load_clothes_dryer |  |
| out.params.panel_load_cooling..w | w | params | panel_load_cooling |  |
| out.params.panel_load_dishwasher..w | w | params | panel_load_dishwasher |  |
| out.params.panel_load_ev_charging..w | w | params | panel_load_ev_charging |  |
| out.params.panel_load_heating..w | w | params | panel_load_heating |  |
| out.params.panel_load_hot_water..w | w | params | panel_load_hot_water |  |
| out.params.panel_load_mech_vent..w | w | params | panel_load_mech_vent |  |
| out.params.panel_load_other..w | w | params | panel_load_other |  |
| out.params.panel_load_permanent_spa_heat..w | w | params | panel_load_permanent_spa_heat |  |
| out.params.panel_load_permanent_spa_pump..w | w | params | panel_load_permanent_spa_pump |  |
| out.params.panel_load_pool_heater..w | w | params | panel_load_pool_heater |  |
| out.params.panel_load_pool_pump..w | w | params | panel_load_pool_pump |  |
| out.params.panel_load_range_oven..w | w | params | panel_load_range_oven |  |
| out.params.panel_load_well_pump..w | w | params | panel_load_well_pump |  |
| out.params.panel_breaker_space_occupied_count |  | params | panel_breaker_space_occupied_count |  |
| out.params.panel_breaker_space_headroom_count |  | params | panel_breaker_space_headroom_count |  |
| out.params.panel_breaker_space_clothes_dryer_count |  | params | panel_breaker_space_clothes_dryer_count |  |
| out.params.panel_breaker_space_cooling_count |  | params | panel_breaker_space_cooling_count |  |
| out.params.panel_breaker_space_dishwasher_count |  | params | panel_breaker_space_dishwasher_count |  |
| out.params.panel_breaker_space_ev_charging_count |  | params | panel_breaker_space_ev_charging_count |  |
| out.params.panel_breaker_space_heating_count |  | params | panel_breaker_space_heating_count |  |
| out.params.panel_breaker_space_hot_water_count |  | params | panel_breaker_space_hot_water_count |  |
| out.params.panel_breaker_space_mech_vent_count |  | params | panel_breaker_space_mech_vent_count |  |
| out.params.panel_breaker_space_other_count |  | params | panel_breaker_space_other_count |  |
| out.params.panel_breaker_space_permanent_spa_heat_count |  | params | panel_breaker_space_permanent_spa_heat_count |  |
| out.params.panel_breaker_space_permanent_spa_pump_count |  | params | panel_breaker_space_permanent_spa_pump_count |  |
| out.params.panel_breaker_space_pool_heater_count |  | params | panel_breaker_space_pool_heater_count |  |
| out.params.panel_breaker_space_pool_pump_count |  | params | panel_breaker_space_pool_pump_count |  |
| out.params.panel_breaker_space_range_oven_count |  | params | panel_breaker_space_range_oven_count |  |
| out.params.panel_breaker_space_well_pump_count |  | params | panel_breaker_space_well_pump_count |  |
| out.params.panel_load_total_load_savings.2023_nec_existing_dwelling_load_based..w | w | params | panel_load_total_load_savings | 2023_nec_existing_dwelling_load_based |
| out.params.panel_load_occupied_capacity_savings.2023_nec_existing_dwelling_load_based..a | a | params | panel_load_occupied_capacity_savings | 2023_nec_existing_dwelling_load_based |
| out.params.panel_breaker_space_occupied_savings_count |  | params | panel_breaker_space_occupied_savings_count |  |
| out.params.panel_constraint_capacity.2023_nec_existing_dwelling_load_based |  | params | panel_constraint_capacity | 2023_nec_existing_dwelling_load_based |
| out.params.panel_constraint_breaker_space |  | params | panel_constraint_breaker_space |  |
| out.params.panel_constraint_overall.2023_nec_existing_dwelling_load_based |  | params | panel_constraint_overall | 2023_nec_existing_dwelling_load_based |
| out.energy_burden..percentage | percentage | energy_burden |  |  |
| out.electricity.ceiling_fan.energy_savings..kwh | kwh | electricity | ceiling_fan | energy_savings |
| out.electricity.clothes_dryer.energy_savings..kwh | kwh | electricity | clothes_dryer | energy_savings |
| out.electricity.clothes_washer.energy_savings..kwh | kwh | electricity | clothes_washer | energy_savings |
| out.electricity.cooling_fans_pumps.energy_savings..kwh | kwh | electricity | cooling_fans_pumps | energy_savings |
| out.electricity.cooling.energy_savings..kwh | kwh | electricity | cooling | energy_savings |
| out.electricity.dishwasher.energy_savings..kwh | kwh | electricity | dishwasher | energy_savings |
| out.electricity.ev_charging.energy_savings..kwh | kwh | electricity | ev_charging | energy_savings |
| out.electricity.freezer.energy_savings..kwh | kwh | electricity | freezer | energy_savings |
| out.electricity.heating_fans_pumps.energy_savings..kwh | kwh | electricity | heating_fans_pumps | energy_savings |
| out.electricity.heating_hp_bkup.energy_savings..kwh | kwh | electricity | heating_hp_bkup | energy_savings |
| out.electricity.heating_hp_bkup_fa.energy_savings..kwh | kwh | electricity | heating_hp_bkup_fa | energy_savings |
| out.electricity.heating.energy_savings..kwh | kwh | electricity | heating | energy_savings |
| out.electricity.permanent_spa_heat.energy_savings..kwh | kwh | electricity | permanent_spa_heat | energy_savings |
| out.electricity.permanent_spa_pump.energy_savings..kwh | kwh | electricity | permanent_spa_pump | energy_savings |
| out.electricity.hot_water.energy_savings..kwh | kwh | electricity | hot_water | energy_savings |
| out.electricity.hot_water_solar_th.energy_savings..kwh | kwh | electricity | hot_water_solar_th | energy_savings |
| out.electricity.lighting_exterior.energy_savings..kwh | kwh | electricity | lighting_exterior | energy_savings |
| out.electricity.lighting_garage.energy_savings..kwh | kwh | electricity | lighting_garage | energy_savings |
| out.electricity.lighting_interior.energy_savings..kwh | kwh | electricity | lighting_interior | energy_savings |
| out.electricity.mech_vent.energy_savings..kwh | kwh | electricity | mech_vent | energy_savings |
| out.electricity.plug_loads.energy_savings..kwh | kwh | electricity | plug_loads | energy_savings |
| out.electricity.pool_heater.energy_savings..kwh | kwh | electricity | pool_heater | energy_savings |
| out.electricity.pool_pump.energy_savings..kwh | kwh | electricity | pool_pump | energy_savings |
| out.electricity.pv.energy_savings..kwh | kwh | electricity | pv | energy_savings |
| out.electricity.range_oven.energy_savings..kwh | kwh | electricity | range_oven | energy_savings |
| out.electricity.refrigerator.energy_savings..kwh | kwh | electricity | refrigerator | energy_savings |
| out.electricity.television.energy_savings..kwh | kwh | electricity | television | energy_savings |
| out.electricity.well_pump.energy_savings..kwh | kwh | electricity | well_pump | energy_savings |
| out.fuel_oil.heating_hp_bkup.energy_savings..kwh | kwh | fuel_oil | heating_hp_bkup | energy_savings |
| out.fuel_oil.heating.energy_savings..kwh | kwh | fuel_oil | heating | energy_savings |
| out.fuel_oil.hot_water.energy_savings..kwh | kwh | fuel_oil | hot_water | energy_savings |
| out.natural_gas.clothes_dryer.energy_savings..kwh | kwh | natural_gas | clothes_dryer | energy_savings |
| out.natural_gas.fireplace.energy_savings..kwh | kwh | natural_gas | fireplace | energy_savings |
| out.natural_gas.grill.energy_savings..kwh | kwh | natural_gas | grill | energy_savings |
| out.natural_gas.heating_hp_bkup.energy_savings..kwh | kwh | natural_gas | heating_hp_bkup | energy_savings |
| out.natural_gas.heating.energy_savings..kwh | kwh | natural_gas | heating | energy_savings |
| out.natural_gas.permanent_spa_heat.energy_savings..kwh | kwh | natural_gas | permanent_spa_heat | energy_savings |
| out.natural_gas.hot_water.energy_savings..kwh | kwh | natural_gas | hot_water | energy_savings |
| out.natural_gas.lighting.energy_savings..kwh | kwh | natural_gas | lighting | energy_savings |
| out.natural_gas.pool_heater.energy_savings..kwh | kwh | natural_gas | pool_heater | energy_savings |
| out.natural_gas.range_oven.energy_savings..kwh | kwh | natural_gas | range_oven | energy_savings |
| out.propane.clothes_dryer.energy_savings..kwh | kwh | propane | clothes_dryer | energy_savings |
| out.propane.heating_hp_bkup.energy_savings..kwh | kwh | propane | heating_hp_bkup | energy_savings |
| out.propane.heating.energy_savings..kwh | kwh | propane | heating | energy_savings |
| out.propane.hot_water.energy_savings..kwh | kwh | propane | hot_water | energy_savings |
| out.propane.range_oven.energy_savings..kwh | kwh | propane | range_oven | energy_savings |
| out.site_energy.net.energy_savings..kwh | kwh | site_energy | net | energy_savings |
| out.site_energy.total.energy_savings..kwh | kwh | site_energy | total | energy_savings |
| out.electricity.net.energy_savings..kwh | kwh | electricity | net | energy_savings |
| out.electricity.total.energy_savings..kwh | kwh | electricity | total | energy_savings |
| out.fuel_oil.total.energy_savings..kwh | kwh | fuel_oil | total | energy_savings |
| out.natural_gas.total.energy_savings..kwh | kwh | natural_gas | total | energy_savings |
| out.propane.total.energy_savings..kwh | kwh | propane | total | energy_savings |
| out.hot_water_savings.clothes_washer..gal | gal | hot_water_savings | clothes_washer |  |
| out.hot_water_savings.dishwasher..gal | gal | hot_water_savings | dishwasher |  |
| out.hot_water_savings.distribution_waste..gal | gal | hot_water_savings | distribution_waste |  |
| out.hot_water_savings.fixtures..gal | gal | hot_water_savings | fixtures |  |
| out.load.cooling.energy_delivered_savings..kbtu | kbtu | load | cooling | energy_delivered_savings |
| out.load.heating.energy_delivered_savings..kbtu | kbtu | load | heating | energy_delivered_savings |
| out.load.hot_water.energy_delivered_savings..kbtu | kbtu | load | hot_water | energy_delivered_savings |
| out.load.hot_water.energy_solar_thermal_savings..kbtu | kbtu | load | hot_water | energy_solar_thermal_savings |
| out.load.hot_water.energy_tank_losses_savings..kbtu | kbtu | load | hot_water | energy_tank_losses_savings |
| out.load.cooling.peak_savings..kbtu_per_hr | kbtu_per_hr | load | cooling | peak_savings |
| out.load.heating.peak_savings..kbtu_per_hr | kbtu_per_hr | load | heating | peak_savings |
| out.qoi.electricity.maximum_daily_peak_savings_summer..kw | kw | qoi | electricity | maximum_daily_peak_savings_summer |
| out.qoi.electricity.maximum_daily_peak_savings_winter..kw | kw | qoi | electricity | maximum_daily_peak_savings_winter |
| out.unmet_hours_reduction.cooling..hr | hr | unmet_hours_reduction | cooling |  |
| out.unmet_hours_reduction.heating..hr | hr | unmet_hours_reduction | heating |  |
| out.emissions.fuel_oil.total..co2e_kg | co2e_kg | emissions | fuel_oil | total |
| out.emissions.natural_gas.total..co2e_kg | co2e_kg | emissions | natural_gas | total |
| out.emissions.propane.total..co2e_kg | co2e_kg | emissions | propane | total |
| out.emissions_reduction.fuel_oil.total..co2e_kg | co2e_kg | emissions_reduction | fuel_oil | total |
| out.emissions_reduction.natural_gas.total..co2e_kg | co2e_kg | emissions_reduction | natural_gas | total |
| out.emissions_reduction.propane.total..co2e_kg | co2e_kg | emissions_reduction | propane | total |
| out.emissions_reduction.electricity.lrmer_mid_case_25..co2e_kg | co2e_kg | emissions_reduction | electricity | lrmer_mid_case_25 |
| out.emissions_reduction.total.lrmer_mid_case_25..co2e_kg | co2e_kg | emissions_reduction | total | lrmer_mid_case_25 |
| out.emissions_reduction.electricity.lrmer_mid_case_15..co2e_kg | co2e_kg | emissions_reduction | electricity | lrmer_mid_case_15 |
| out.emissions_reduction.total.lrmer_mid_case_15..co2e_kg | co2e_kg | emissions_reduction | total | lrmer_mid_case_15 |
| out.emissions_reduction.electricity.lrmer_high_re_cost_25..co2e_kg | co2e_kg | emissions_reduction | electricity | lrmer_high_re_cost_25 |
| out.emissions_reduction.total.lrmer_high_re_cost_25..co2e_kg | co2e_kg | emissions_reduction | total | lrmer_high_re_cost_25 |
| out.emissions_reduction.electricity.lrmer_high_re_cost_15..co2e_kg | co2e_kg | emissions_reduction | electricity | lrmer_high_re_cost_15 |
| out.emissions_reduction.total.lrmer_high_re_cost_15..co2e_kg | co2e_kg | emissions_reduction | total | lrmer_high_re_cost_15 |
| out.emissions_reduction.electricity.lrmer_low_re_cost_25..co2e_kg | co2e_kg | emissions_reduction | electricity | lrmer_low_re_cost_25 |
| out.emissions_reduction.total.lrmer_low_re_cost_25..co2e_kg | co2e_kg | emissions_reduction | total | lrmer_low_re_cost_25 |
| out.emissions_reduction.electricity.lrmer_low_re_cost_15..co2e_kg | co2e_kg | emissions_reduction | electricity | lrmer_low_re_cost_15 |
| out.emissions_reduction.total.lrmer_low_re_cost_15..co2e_kg | co2e_kg | emissions_reduction | total | lrmer_low_re_cost_15 |
| out.emissions_reduction.electricity.lrmer_low_re_cost_high_ng_price_25..co2e_kg | co2e_kg | emissions_reduction | electricity | lrmer_low_re_cost_high_ng_price_25 |
| out.emissions_reduction.total.lrmer_low_re_cost_high_ng_price_25..co2e_kg | co2e_kg | emissions_reduction | total | lrmer_low_re_cost_high_ng_price_25 |
| out.emissions_reduction.electricity.lrmer_low_re_cost_high_ng_price_15..co2e_kg | co2e_kg | emissions_reduction | electricity | lrmer_low_re_cost_high_ng_price_15 |
| out.emissions_reduction.total.lrmer_low_re_cost_high_ng_price_15..co2e_kg | co2e_kg | emissions_reduction | total | lrmer_low_re_cost_high_ng_price_15 |
| out.emissions_reduction.electricity.lrmer_high_re_cost_low_ng_price_25..co2e_kg | co2e_kg | emissions_reduction | electricity | lrmer_high_re_cost_low_ng_price_25 |
| out.emissions_reduction.total.lrmer_high_re_cost_low_ng_price_25..co2e_kg | co2e_kg | emissions_reduction | total | lrmer_high_re_cost_low_ng_price_25 |
| out.emissions_reduction.electricity.lrmer_high_re_cost_low_ng_price_15..co2e_kg | co2e_kg | emissions_reduction | electricity | lrmer_high_re_cost_low_ng_price_15 |
| out.emissions_reduction.total.lrmer_high_re_cost_low_ng_price_15..co2e_kg | co2e_kg | emissions_reduction | total | lrmer_high_re_cost_low_ng_price_15 |
| out.emissions_reduction.electricity.aer_high_re_cost_avg..co2e_kg | co2e_kg | emissions_reduction | electricity | aer_high_re_cost_avg |
| out.emissions_reduction.total.aer_high_re_cost_avg..co2e_kg | co2e_kg | emissions_reduction | total | aer_high_re_cost_avg |
| out.emissions_reduction.electricity.aer_high_re_cost_low_ng_price_avg..co2e_kg | co2e_kg | emissions_reduction | electricity | aer_high_re_cost_low_ng_price_avg |
| out.emissions_reduction.total.aer_high_re_cost_low_ng_price_avg..co2e_kg | co2e_kg | emissions_reduction | total | aer_high_re_cost_low_ng_price_avg |
| out.emissions_reduction.electricity.aer_low_re_cost_avg..co2e_kg | co2e_kg | emissions_reduction | electricity | aer_low_re_cost_avg |
| out.emissions_reduction.total.aer_low_re_cost_avg..co2e_kg | co2e_kg | emissions_reduction | total | aer_low_re_cost_avg |
| out.emissions_reduction.electricity.aer_low_re_cost_high_ng_price_avg..co2e_kg | co2e_kg | emissions_reduction | electricity | aer_low_re_cost_high_ng_price_avg |
| out.emissions_reduction.total.aer_low_re_cost_high_ng_price_avg..co2e_kg | co2e_kg | emissions_reduction | total | aer_low_re_cost_high_ng_price_avg |
| out.emissions_reduction.electricity.aer_mid_case_avg..co2e_kg | co2e_kg | emissions_reduction | electricity | aer_mid_case_avg |
| out.emissions_reduction.total.aer_mid_case_avg..co2e_kg | co2e_kg | emissions_reduction | total | aer_mid_case_avg |
| out.utility_bills.electricity_bill_savings..usd | usd | utility_bills | electricity_bill_savings |  |
| out.utility_bills.fuel_oil_bill_savings..usd | usd | utility_bills | fuel_oil_bill_savings |  |
| out.utility_bills.natural_gas_bill_savings..usd | usd | utility_bills | natural_gas_bill_savings |  |
| out.utility_bills.propane_bill_savings..usd | usd | utility_bills | propane_bill_savings |  |
| out.utility_bills.total_bill_savings..usd | usd | utility_bills | total_bill_savings |  |
| out.energy_burden_savings..percentage | percentage | energy_burden_savings |  |  |
| out.electricity.ceiling_fan.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | ceiling_fan | energy_consumption_intensity |
| out.electricity.ceiling_fan.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | ceiling_fan | energy_savings_intensity |
| out.electricity.clothes_dryer.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | clothes_dryer | energy_consumption_intensity |
| out.electricity.clothes_dryer.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | clothes_dryer | energy_savings_intensity |
| out.electricity.clothes_washer.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | clothes_washer | energy_consumption_intensity |
| out.electricity.clothes_washer.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | clothes_washer | energy_savings_intensity |
| out.electricity.cooling.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | cooling | energy_consumption_intensity |
| out.electricity.cooling.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | cooling | energy_savings_intensity |
| out.electricity.cooling_fans_pumps.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | cooling_fans_pumps | energy_consumption_intensity |
| out.electricity.cooling_fans_pumps.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | cooling_fans_pumps | energy_savings_intensity |
| out.electricity.dishwasher.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | dishwasher | energy_consumption_intensity |
| out.electricity.dishwasher.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | dishwasher | energy_savings_intensity |
| out.electricity.ev_charging.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | ev_charging | energy_consumption_intensity |
| out.electricity.ev_charging.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | ev_charging | energy_savings_intensity |
| out.electricity.freezer.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | freezer | energy_consumption_intensity |
| out.electricity.freezer.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | freezer | energy_savings_intensity |
| out.electricity.heating.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | heating | energy_consumption_intensity |
| out.electricity.heating.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | heating | energy_savings_intensity |
| out.electricity.heating_fans_pumps.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | heating_fans_pumps | energy_consumption_intensity |
| out.electricity.heating_fans_pumps.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | heating_fans_pumps | energy_savings_intensity |
| out.electricity.heating_hp_bkup.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | heating_hp_bkup | energy_consumption_intensity |
| out.electricity.heating_hp_bkup.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | heating_hp_bkup | energy_savings_intensity |
| out.electricity.heating_hp_bkup_fa.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | heating_hp_bkup_fa | energy_consumption_intensity |
| out.electricity.heating_hp_bkup_fa.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | heating_hp_bkup_fa | energy_savings_intensity |
| out.electricity.hot_water.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | hot_water | energy_consumption_intensity |
| out.electricity.hot_water.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | hot_water | energy_savings_intensity |
| out.electricity.hot_water_solar_th.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | hot_water_solar_th | energy_consumption_intensity |
| out.electricity.hot_water_solar_th.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | hot_water_solar_th | energy_savings_intensity |
| out.electricity.lighting_exterior.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | lighting_exterior | energy_consumption_intensity |
| out.electricity.lighting_exterior.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | lighting_exterior | energy_savings_intensity |
| out.electricity.lighting_garage.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | lighting_garage | energy_consumption_intensity |
| out.electricity.lighting_garage.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | lighting_garage | energy_savings_intensity |
| out.electricity.lighting_interior.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | lighting_interior | energy_consumption_intensity |
| out.electricity.lighting_interior.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | lighting_interior | energy_savings_intensity |
| out.electricity.mech_vent.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | mech_vent | energy_consumption_intensity |
| out.electricity.mech_vent.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | mech_vent | energy_savings_intensity |
| out.electricity.net.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | net | energy_consumption_intensity |
| out.electricity.net.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | net | energy_savings_intensity |
| out.electricity.permanent_spa_heat.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | permanent_spa_heat | energy_consumption_intensity |
| out.electricity.permanent_spa_heat.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | permanent_spa_heat | energy_savings_intensity |
| out.electricity.permanent_spa_pump.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | permanent_spa_pump | energy_consumption_intensity |
| out.electricity.permanent_spa_pump.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | permanent_spa_pump | energy_savings_intensity |
| out.electricity.plug_loads.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | plug_loads | energy_consumption_intensity |
| out.electricity.plug_loads.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | plug_loads | energy_savings_intensity |
| out.electricity.pool_heater.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | pool_heater | energy_consumption_intensity |
| out.electricity.pool_heater.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | pool_heater | energy_savings_intensity |
| out.electricity.pool_pump.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | pool_pump | energy_consumption_intensity |
| out.electricity.pool_pump.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | pool_pump | energy_savings_intensity |
| out.electricity.pv.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | pv | energy_consumption_intensity |
| out.electricity.pv.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | pv | energy_savings_intensity |
| out.electricity.range_oven.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | range_oven | energy_consumption_intensity |
| out.electricity.range_oven.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | range_oven | energy_savings_intensity |
| out.electricity.refrigerator.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | refrigerator | energy_consumption_intensity |
| out.electricity.refrigerator.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | refrigerator | energy_savings_intensity |
| out.electricity.television.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | television | energy_consumption_intensity |
| out.electricity.television.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | television | energy_savings_intensity |
| out.electricity.total.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | total | energy_consumption_intensity |
| out.electricity.total.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | total | energy_savings_intensity |
| out.electricity.well_pump.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | well_pump | energy_consumption_intensity |
| out.electricity.well_pump.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | electricity | well_pump | energy_savings_intensity |
| out.fuel_oil.heating.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | fuel_oil | heating | energy_consumption_intensity |
| out.fuel_oil.heating.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | fuel_oil | heating | energy_savings_intensity |
| out.fuel_oil.heating_hp_bkup.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | fuel_oil | heating_hp_bkup | energy_consumption_intensity |
| out.fuel_oil.heating_hp_bkup.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | fuel_oil | heating_hp_bkup | energy_savings_intensity |
| out.fuel_oil.hot_water.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | fuel_oil | hot_water | energy_consumption_intensity |
| out.fuel_oil.hot_water.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | fuel_oil | hot_water | energy_savings_intensity |
| out.fuel_oil.total.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | fuel_oil | total | energy_consumption_intensity |
| out.fuel_oil.total.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | fuel_oil | total | energy_savings_intensity |
| out.natural_gas.clothes_dryer.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | clothes_dryer | energy_consumption_intensity |
| out.natural_gas.clothes_dryer.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | clothes_dryer | energy_savings_intensity |
| out.natural_gas.fireplace.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | fireplace | energy_consumption_intensity |
| out.natural_gas.fireplace.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | fireplace | energy_savings_intensity |
| out.natural_gas.grill.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | grill | energy_consumption_intensity |
| out.natural_gas.grill.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | grill | energy_savings_intensity |
| out.natural_gas.heating.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | heating | energy_consumption_intensity |
| out.natural_gas.heating.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | heating | energy_savings_intensity |
| out.natural_gas.heating_hp_bkup.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | heating_hp_bkup | energy_consumption_intensity |
| out.natural_gas.heating_hp_bkup.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | heating_hp_bkup | energy_savings_intensity |
| out.natural_gas.hot_water.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | hot_water | energy_consumption_intensity |
| out.natural_gas.hot_water.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | hot_water | energy_savings_intensity |
| out.natural_gas.lighting.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | lighting | energy_consumption_intensity |
| out.natural_gas.lighting.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | lighting | energy_savings_intensity |
| out.natural_gas.permanent_spa_heat.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | permanent_spa_heat | energy_consumption_intensity |
| out.natural_gas.permanent_spa_heat.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | permanent_spa_heat | energy_savings_intensity |
| out.natural_gas.pool_heater.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | pool_heater | energy_consumption_intensity |
| out.natural_gas.pool_heater.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | pool_heater | energy_savings_intensity |
| out.natural_gas.range_oven.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | range_oven | energy_consumption_intensity |
| out.natural_gas.range_oven.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | range_oven | energy_savings_intensity |
| out.natural_gas.total.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | total | energy_consumption_intensity |
| out.natural_gas.total.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | natural_gas | total | energy_savings_intensity |
| out.propane.clothes_dryer.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | clothes_dryer | energy_consumption_intensity |
| out.propane.clothes_dryer.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | clothes_dryer | energy_savings_intensity |
| out.propane.heating.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | heating | energy_consumption_intensity |
| out.propane.heating.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | heating | energy_savings_intensity |
| out.propane.heating_hp_bkup.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | heating_hp_bkup | energy_consumption_intensity |
| out.propane.heating_hp_bkup.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | heating_hp_bkup | energy_savings_intensity |
| out.propane.hot_water.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | hot_water | energy_consumption_intensity |
| out.propane.hot_water.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | hot_water | energy_savings_intensity |
| out.propane.range_oven.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | range_oven | energy_consumption_intensity |
| out.propane.range_oven.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | range_oven | energy_savings_intensity |
| out.propane.total.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | total | energy_consumption_intensity |
| out.propane.total.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | propane | total | energy_savings_intensity |
| out.site_energy.net.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | site_energy | net | energy_consumption_intensity |
| out.site_energy.net.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | site_energy | net | energy_savings_intensity |
| out.site_energy.total.energy_consumption_intensity..kwh_per_ft2 | kwh_per_ft2 | site_energy | total | energy_consumption_intensity |
| out.site_energy.total.energy_savings_intensity..kwh_per_ft2 | kwh_per_ft2 | site_energy | total | energy_savings_intensity |

### Measure Upgrade Packages

#### release_1

| Upgrade ID | Package Name |
| --- | --- |
| 0 | Baseline |
| 1 | Natural Gas Furnace 95% AFUE for All Dwellings with Ducts |
| 2 | Propane or Fuel Oil Furnace 95% AFUE |
| 3 | Minimum Efficiency Boilers, Furnaces, and Air Conditioners Circa 2025 |
| 4 | Typical Cold Climate Ducted Air Source Heat Pump with Detailed Performance Data |
| 5 | Dual Fuel Heating System |
| 6 | Single-Speed Geothermal Heat Pump with Thermally Enhanced Grout and Pipes |
| 7 | Dual-Speed Geothermal Heat Pump with Thermally Enhanced Grout and Pipes |
| 8 | Variable-Speed Geothermal Heat Pump with Thermally Enhanced Grout and Pipes |
| 9 | Heat Pumps Water Heater |
| 10 | High Efficiency Natural Gas Tankless Water Heater |
| 11 | Air Sealing |
| 12 | Attic Floor Insulation for Unfinished Attics |
| 13 | Duct Sealing and Insulation |
| 14 | Drill and Fill Wall Insulation with Air Sealing |
| 15 | Air Sealing + Attic Floor Insulation + Duct sealing |
| 16 | Air Sealing + Attic Floor Insulation + Duct sealing + Drill and Fill Wall Insulation |
| 17 | EnergyStar Windows |
| 18 | Package - Dual-Speed Geothermal Heat Pump with Thermally Enhanced Grout and Pipes with Air Sealing with Attic Floor Insulation with Duct Sealing |
| 19 | Electric Vehicle Adoption with Level 1 Charging |
| 20 | Electric Vehicle Adoption with Level 2 Charging |
| 21 | Efficient Electric Vehicle Adoption with Level 2 Charging |
| 22 | Electric Vehicle Adoption with Level 2 Charging and Demand Flexibility |
| 23 | Efficient Electric Vehicle Adoption with Level 2 Charging and Demand Flexibility |
| 24 | HVAC Demand Flexibility - On-peak Load Shedding, 2F Offset |
| 25 | HVAC Demand Flexibility - Pre-peak Load Shifting, 2F Offset, 4hr Pre-peak Duration |
| 26 | HVAC Demand Flexibility - On-peak Load Shedding, 4F Offset |
| 27 | HVAC Demand Flexibility - Pre-peak Load Shifting, 4F Offset, 4hr Pre-peak Duration |
| 28 | HVAC Demand Flexibility - Pre-peak Load Shifting, 2F Offset, 1hr Pre-peak Duration |
| 29 | General Air Sealing |
| 30 | General Air Sealing, Attic Floor Insulation, and Duct Sealing |
| 31 | Dual-Speed Geothermal Heat Pump with Thermally Enhanced Grout and Pipes, General Air Sealing, Attic Floor Insulation, and Duct Sealing |
| 32 | Variable-Speed Geothermal Heat Pump with Thermally Enhanced Grout and Pipes, General Air Sealing, Attic Floor Insulation, and Duct Sealing |
