# Usage Guide

This guide covers the common workflows supported by `building_energy_profiles`. For assumptions and known constraints,
read [Data Model and Limitations](limitations.md).

## Install from the Repository

The project requires Python 3.12 or newer and uses `uv` for dependency management.

```bash
pip install uv
uv sync --group dev
```

Run scripts and notebooks through the project environment:

```bash
uv run python your_script.py
uv run jupyter lab
```

## Prepare Local Directories

Processors cache downloaded metadata and derived CSV files under `base_dir`. Create parent directories before
constructing a processor.

```python
from pathlib import Path

data_dir = Path("datasets")
comstock_dir = data_dir / "comstock"
resstock_dir = data_dir / "resstock"

comstock_dir.mkdir(parents=True, exist_ok=True)
resstock_dir.mkdir(parents=True, exist_ok=True)
```

## Search ComStock

ComStock records are commercial whole buildings. The example below searches a group of counties and applies local
building-type and floor-area filters.

```python
from building_energy_profiles import ComStockProcessor

comstock_processor = ComStockProcessor(
    state="CO",
    county_name=[
        "Denver County",
        "Arapahoe County",
        "Jefferson County",
    ],
    building_type="SmallOffice",
    upgrade="0",
    base_dir=comstock_dir,
    min_sqft=1_000,
    max_sqft=10_000,
)

buildings = comstock_processor.process_metadata(save_dir=comstock_dir)

print(buildings[[
    "bldg_id",
    "in.state",
    "in.county_name",
    "in.comstock_building_type",
    "in.sqft..ft2",
    "out.site_energy.total.energy_consumption..kwh",
]].head())
```

`county_name` accepts one county, a list of counties, or `"All"`. With ComStock, county values are passed without
the state prefix, such as `"Denver County"`; the processor matches them to metadata values such as
`"CO, Denver County"`.

## Search ResStock

ResStock records are residential dwelling units. A multifamily result is one sampled unit with context describing
its containing building.

```python
from building_energy_profiles import ResStockProcessor

resstock_processor = ResStockProcessor(
    state="DC",
    county_name="All",
    building_type="Multi-Family with 5+ Units",
    upgrade="0",
    base_dir=resstock_dir,
)

units = resstock_processor.process_metadata(save_dir=resstock_dir)

print(units[[
    "bldg_id",
    "in.geometry_building_type_recs",
    "in.geometry_building_number_units_mf",
    "in.geometry_building_horizontal_location_mf",
    "in.geometry_building_level_mf",
    "in.sqft..ft2",
    "weight",
]].head())
```

Supported residential building types are:

- `Mobile Home`
- `Single-Family Detached`
- `Single-Family Attached`
- `Multi-Family with 2 - 4 Units`
- `Multi-Family with 5+ Units`
- `All`

ResStock county values do not contain the state prefix. Pass `"Kent County"`, not `"DE, Kent County"`.

Both processors use the same OEDI release path structure. The publication year is the directory below the common
building-stock prefix, followed by a folder named `<product>_<weather_year>_<release>`. For example, the default
processors read from `2025/comstock_amy2018_release_3/` and `2025/resstock_amy2018_release_1/`; ResStock can also
use `weather_year="amy2012"`, which reads from `2025/resstock_amy2012_release_1/`.

## Download Time Series

Pass metadata rows directly to `process_building_time_series()`. Start with a small sample: each row can trigger
an annual parquet download.

```python
timeseries_dir = comstock_dir / "time_series"
timeseries_dir.mkdir(parents=True, exist_ok=True)

selected = (
    buildings
    .sort_values(
        "out.site_energy.total.energy_consumption..kwh",
        ascending=False,
    )
    .drop_duplicates("bldg_id")
    .head(3)
)

paths, building_ids = comstock_processor.process_building_time_series(
    selected,
    save_dir=timeseries_dir,
)

for path, building_id in zip(paths, building_ids):
    if not path.exists():
        raise FileNotFoundError(
            f"Time series for {building_id} was not downloaded: {path}"
        )
```

The downloader caches files by building ID and upgrade. Existing files are reused.

Time series timestamps are **period-ending** (a full 2018 year at 15-minute resolution runs from
2018-01-01 00:15 to 2019-01-01 00:00). Use `resample_time_series()` (or `to_period_start()`) before calendar
aggregation; a plain `resample("MS")` on raw timestamps creates a near-empty extra "2019-01" period and moves
one interval into the wrong month at every boundary.

```python
from building_energy_profiles import resample_time_series

monthly = resample_time_series(pd.read_parquet(paths[0]), "monthly", ["out.electricity.total.energy_consumption"])
assert len(monthly) == 12
```

## Constrain on Building Characteristics

Type, geography, and floor area are often not enough to represent a real building. The biggest remaining
difference is usually **fuel**: in Washington, DC, ComStock offices are a mix of gas-, electric-, and
district-heated buildings, so an unconstrained office sample spreads heating energy across meters that a
specific building does not have. Pass `characteristics=` to either processor (or to a composite/portfolio
component) to keep only buildings that match:

```python
from building_energy_profiles import BuildingCharacteristics, ComStockProcessor

gas_offices = ComStockProcessor(
    state="DC",
    county_name="All",
    building_type="MediumOffice",
    upgrade="0",
    base_dir=comstock_dir,
    characteristics={"heating_fuel": "natural_gas", "has_district_heating": False},
).process_metadata(save_dir=comstock_dir)
```

| Field | Meaning |
| --- | --- |
| `heating_fuel` | Primary space-heating fuel(s), from `in.heating_fuel`. |
| `water_heating_fuel` | Water-heating fuel(s), from `in.service_water_heating_fuel` (ComStock) or `in.water_heater_fuel` (ResStock). |
| `cooling_type` | Space-cooling system(s): `district`, `chiller`, `dx`, `heat_pump`, `none`, from `in.hvac_cool_type` (ComStock) or `in.hvac_cooling_type` (ResStock). ResStock has no `district` or `chiller`. |
| `has_natural_gas` | `True`/`False`: the building uses any natural gas (baseline annual gas > 0), e.g. an electrically heated building with gas water heating or cooking still counts. |
| `has_district_heating` / `has_district_cooling` | `True`/`False` on baseline district heating / chilled water use. ResStock models neither. |
| `attributes` | Exact match on any other metadata column, e.g. `{"in.hvac_category": "Small Packaged Unit"}`. |

Fuel names are product-neutral (`natural_gas`, `electricity`, `district_heating`, `propane`, `fuel_oil`,
`other`) and are mapped to each product's own values. The `has_*` flags are always judged on the baseline
(upgrade `"0"`) results, so a gas building stays in the sample for an electrification upgrade and
baseline-vs-upgrade comparisons remain like-for-like. Constrained samples are cached under their own file
name (the constraint label, e.g. `hf_natural_gas-dh0`, is added to the selected-metadata CSV name).

District heating is a real end use in ComStock: district-heated buildings report it in
`out.district_heating.*` (heating and water-systems end uses, annual and time series) and include it in
`out.site_energy.total`; most district-heated ComStock buildings are also district-cooled (`out.district_cooling.*`),
which lowers their electricity. Keep those
buildings when the real building is on a steam/hot-water loop; exclude them (`has_district_heating=False, has_district_cooling=False`)
when comparing against gas and electric bills only.

District cooling is handled the same way. In ComStock DC (release 3) 40 buildings are district-cooled (24 large
offices, 8 medium offices, 5 primary schools, 3 hospitals); 35 of them are also district-heated. District chilled
water is reported in `out.district_cooling.cooling.*` and `out.district_cooling.total.*` (annual and 15-min), is
included in `out.site_energy.total`, and is a median 52% of these buildings' site energy -- so their electricity is
far below an electrically cooled building's. `cooling_type="district"` (inputs) and `has_district_cooling=True`
(baseline results) select the same buildings in the baseline; use the input form when the real building's plant is
known, and match a chilled-water meter (ENERGY STAR "District Chilled Water") against `out.district_cooling.total`.

## Download Building Energy Models

Each sampled building also has a published energy model file on the OEDI data lake -- a gzipped OpenStudio
`.osm.gz` model for ComStock, or a `.zip` archive (bundling the OSM with its supporting files) for ResStock.
`download_building_models()` mirrors `process_building_time_series()`'s shape and caching behavior for these:

```python
models_dir = comstock_dir / "models"
models_dir.mkdir(parents=True, exist_ok=True)

paths, building_ids = comstock_processor.download_building_models(
    selected,
    save_dir=models_dir,
)
```

To download just one building's model without a metadata DataFrame, use `download_building_model()`:

```python
model_path = comstock_processor.download_building_model(building_id=12345, save_dir=models_dir)
```

`model_file_url()`/`model_file_name()` build the underlying OEDI URL/filename without downloading anything,
if you just need the link (e.g. to hand off to another tool).

## Normalize Time-Series Columns

Published ComStock and ResStock time-series schemas are similar but not identical. In currently supported releases,
ResStock energy columns include a `..kwh` suffix while ComStock columns may not. Normalize before concatenating
the stocks.

```python
import pandas as pd


def read_time_series(path):
    frame = pd.read_parquet(path)
    rename = {
        column: column.removesuffix("..kwh")
        for column in frame.columns
        if column.endswith(".energy_consumption..kwh")
    }
    frame = frame.rename(columns=rename)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    return frame
```

Energy consumption is reported per interval in kWh. Convert it to average interval demand in kW using the actual
interval duration:

```python
frame = read_time_series(paths[0])
interval_hours = (
    frame["timestamp"].sort_values().diff().median().total_seconds() / 3600
)
frame["electricity_demand_kw"] = (
    frame["out.electricity.total.energy_consumption"] / interval_hours
)
```

Do not label interval kWh directly as kW. For example, a 15-minute interval uses `kWh / 0.25 hours`.

## Apply Stock Weights

### ComStock

ComStock `weight` scales a metadata row to represented commercial buildings. A building can appear in multiple
geographic rows, each with its own weight, so preserve those rows when calculating stock totals.

```python
buildings["weighted_floor_area_ft2"] = (
    buildings["in.sqft..ft2"] * buildings["weight"]
)
buildings["weighted_total_site_energy_kwh"] = (
    buildings["out.site_energy.total.energy_consumption..kwh"]
    * buildings["weight"]
)

represented_floor_area = buildings["weighted_floor_area_ft2"].sum()
represented_total_energy = buildings["weighted_total_site_energy_kwh"].sum()
```

If the goal is simulated building performance rather than stock totals, deduplicate by `bldg_id` instead of
summing repeated geographic rows.

### ResStock

ResStock `weight` scales a sampled dwelling unit to represented dwelling units.

```python
units["weighted_unit_floor_area_ft2"] = (
    units["in.sqft..ft2"] * units["weight"]
)
units["weighted_total_site_energy_kwh"] = (
    units["out.site_energy.total.energy_consumption..kwh"]
    * units["weight"]
)
```

There is no shared physical-building identifier for sampled multifamily units. If an analysis requires an
illustrative whole-building estimate, one explicit approximation is:

```python
number_units = units["in.geometry_building_number_units_mf"]

units["estimated_building_floor_area_ft2"] = (
    units["in.sqft..ft2"] * number_units
)
units["estimated_building_total_energy_kwh"] = (
    units["out.site_energy.total.energy_consumption..kwh"] * number_units
)
units["estimated_building_multiplier"] = units["weight"] / number_units
```

This assumes every unit in the building behaves like the sampled unit. It is useful for transparent scenario
plots, not for reconstructing an actual multifamily building. Notice that applying the estimated building
multiplier cancels the unit-count assumption for aggregate floor area and energy:

```text
(unit value * units per building) * (unit weight / units per building)
= unit value * unit weight
```

## Compare Upgrade Packages

List packages for the configured release:

```python
upgrades = comstock_processor.list_upgrades(save_dir=comstock_dir)
for upgrade_id, name in upgrades.items():
    print(upgrade_id, name)
```

Compare selected packages for the same modeled records:

```python
comparison = comstock_processor.process_metadata_for_upgrades(
    save_dir=comstock_dir,
    upgrades=["0", "1"],
)

annual_energy = comparison.pivot_table(
    index="bldg_id",
    columns="upgrade",
    values="out.site_energy.total.energy_consumption..kwh",
    aggfunc="first",
)
```

Upgrade IDs are release-specific. Use the measure crosswalk when comparing releases:

```python
upgrade_id = comstock_processor.find_upgrade_id(
    save_dir=comstock_dir,
    measure_id="hvac_0005",
    target_release="release_1",
)
```

## Composite ("Mixed-Use") Building Types

Real buildings are often not well represented by a single BuildStock building type -- e.g. a building that
is 70% office space over 30% ground-floor retail. `CompositeBuildingType` models this as a fraction-weighted
combination of two or more `(product, building_type)` components (fractions must sum to 1.0).

```python
from building_energy_profiles import CompositeBuildingType, pull_composite_time_series

office_retail = CompositeBuildingType.from_fractions(
    "70% MediumOffice / 30% RetailStripmall",
    {
        ("comstock", "MediumOffice"): 0.7,
        ("comstock", "RetailStripmall"): 0.3,
    },
)

combined, components = pull_composite_time_series(
    office_retail,
    save_dir=composite_dir,
    state="DE",
)
```

`pull_composite_time_series()` downloads one representative building's time series per component (via
`process_building_time_series()`, same as any other time series download), then auto-stitches every
component into a single synthetic composite time series with `combine_composite_time_series()`:

```text
composite[column][t] = sum(component.fraction * component_series[column][t] for component in composite)
```

Components can mix ComStock and ResStock (e.g. ground-floor retail under apartments). Column names are
normalized first with `normalize_time_series_columns()`, since ResStock time series carry a `..kwh`-style
unit suffix that ComStock's don't:

```python
mixed_use = CompositeBuildingType.from_fractions(
    "55% Ground-Floor Retail / 45% Apartments",
    {
        ("comstock", "RetailStripmall"): 0.55,
        ("resstock", "Multi-Family with 5+ Units"): 0.45,
    },
)
```

A ResStock row is a single dwelling unit, not a whole building, so mixing products can't be a bare
fraction-weighted blend -- half of a 50,000 sqft office next to half of a 900 sqft apartment would put
almost no multifamily in the result. Composites that mix ComStock and ResStock are therefore sized by floor
area automatically: the composite's gross floor area is anchored on the ComStock component(s) (or given
explicitly via `total_sqft`), each component takes `fraction * total_sqft` of it, and its weight is that
area divided by its own representative size -- which for a ResStock component is a dwelling-unit multiplier.
"50% MediumOffice + 50% Multi-Family with 5+ Units", with a 50,000 sqft office, means 25,000 sqft of
apartments, i.e. ~28 units of ~900 sqft each.

```python
combined, components = pull_composite_time_series(
    mixed_use,
    save_dir=composite_dir,
    state="DE",
    total_sqft=120_000,  # optional: size the whole building explicitly instead of inferring it
)
```

`summarize_composite_metadata()` reports each component's resulting `unit_multiplier` (the number of
representative buildings/dwelling units its floor area works out to) alongside its scaled annual energy.

If you already downloaded component time series yourself (e.g. for specific hand-picked buildings), skip
the download step and call `combine_composite_time_series()` directly with a
`{(product, building_type): DataFrame}` mapping. If fractions don't sum to exactly 1.0 (e.g. percentages
that don't sum perfectly due to rounding), fix them with `composite.normalized()`.

## Notebook Examples

- [`01_data_sampling_example.ipynb`](../01_data_sampling_example.ipynb) demonstrates basic ComStock sampling.
- [`02_washington_dc_stock_analysis.ipynb`](../02_washington_dc_stock_analysis.ipynb) combines DC offices and
  multifamily units, plots gross floor area and total site energy, applies stock multipliers, downloads selected
  time series, and builds measure recommendations.
- [`03_composite_building_example.ipynb`](../03_composite_building_example.ipynb) demonstrates
  `CompositeBuildingType` and `pull_composite_time_series()`/`combine_composite_time_series()`: modeling a
  mixed-use building as a fraction-weighted combination of BuildStock building types (including a
  cross-product example mixing ComStock and ResStock components).

Execute a notebook without modifying its committed outputs:

```bash
uv run jupyter nbconvert \
  --to html \
  --execute 02_washington_dc_stock_analysis.ipynb \
  --output dc-stock-analysis.html
```

## Find the Closest Matching Buildings

`find_nearest_buildings` ranks a metadata sample by how close each simulated building is to a real one, using the
log-ratio distance `d = sqrt(sum_j w_j * ln(x_j / x_j,target)^2)` over floor area and/or annual site EUI (kBtu/ft2).
Apply type, location and `BuildingCharacteristics` constraints first; the function only ranks what is left.

```python
from building_energy_profiles import BuildingCharacteristics, find_nearest_buildings

offices = meta[meta["in.comstock_building_type"].isin(["MediumOffice", "LargeOffice"])]
offices = BuildingCharacteristics(heating_fuel="natural_gas", has_district_heating=False).apply(offices, "comstock")

one_shot = find_nearest_buildings(offices, sqft=115_882, site_eui_kbtu_per_ft2=53.7, k=1)   # use as published
scaled = find_nearest_buildings(offices, sqft=115_882, site_eui_kbtu_per_ft2=53.7, k=10)    # average intensity x floor area
```

The result carries `match_distance` and `match_rank` columns. For ResStock (one dwelling unit per row), match on EUI only.
If the EUI target comes from the same bills you will compare against, take it from a different year.

## Issue profiles: what a building's bills say about its record

`building_energy_profiles.issue_profiles` screens real utility bills against BuildStock and against the building's
own history. Each flag carries evidence, likely causes and the next data to request (`CATALOG`); they are screening
hints for a data steward, not verified causes.

```python
from building_energy_profiles import BuildingCharacteristics, issue_profiles as ip

annual = ip.annual_bills(monthly)             # monthly: year, month, electricity, natural_gas, ... in kBtu
pool = ip.pool_euis(constrained_metadata)      # the lookup's candidate pool (type, fuels, floor-area band)
flags, metrics = ip.pool_profiles(annual.loc[2018], gfa, pool, reported_type="Office",
                                  type_pools={"Office": office_pool, "Hotel": hotel_pool})

# later years: divide by the peers' median change (weather, COVID-19) before comparing with the baseline
index = ip.cohort_index(all_buildings_annual, building_col="property_id", group_col="type_group")
flags += ip.multi_year_profiles(annual, baseline_year=2018, index=index, group="Office")
```

Pool checks need bills from the BuildStock weather year (AMY2018) or later bills divided by the peer index.
Multi-year checks need no BuildStock data. The MCP server exposes both as `screen_issue_profiles`.
