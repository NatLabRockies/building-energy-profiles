# Usage Guide

This guide covers the common workflows supported by `buildstock_processor`. For assumptions and known constraints,
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
from buildstock_processor import ComStockProcessor

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
from buildstock_processor import ResStockProcessor

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

## Notebook Examples

- [`01_data_sampling_example.ipynb`](../01_data_sampling_example.ipynb) demonstrates basic ComStock sampling.
- [`02_washington_dc_stock_analysis.ipynb`](../02_washington_dc_stock_analysis.ipynb) combines DC offices and
  multifamily units, plots gross floor area and total site energy, applies stock multipliers, downloads selected
  time series, and builds measure recommendations.

Execute a notebook without modifying its committed outputs:

```bash
uv run jupyter nbconvert \
  --to html \
  --execute 02_washington_dc_stock_analysis.ipynb \
  --output dc-stock-analysis.html
```
