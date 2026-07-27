# BuildStock Processor

A Python package for downloading and analyzing NREL ComStock and ResStock metadata, annual results, upgrade
packages, and individual-building time series from the public OEDI data lake.

The package exposes two processors:

- `ComStockProcessor` for commercial whole-building records.
- `ResStockProcessor` for residential dwelling-unit records.

Both use shared download, cache, filtering, upgrade-lookup, and time-series infrastructure. They remain separate
because their releases, metadata partitioning, building types, crosswalk formats, and record semantics differ.

## Installation

Install [uv](https://docs.astral.sh/uv/) and sync the project's dependencies:

```bash
pip install uv
uv sync --group dev
```

The project uses a standard `src/` package layout. `uv sync` installs `buildstock_processor` into the project
environment as an editable package.

## Documentation

- [Usage guide](docs/usage.md): installation, searches, time series, upgrades, weights, total-energy calculations,
  and schema normalization.
- [Data model and limitations](docs/limitations.md): releases, download scope, caching, duplicate records,
  multifamily semantics, time-series differences, and network behavior.
- [Extending the package](docs/extending.md): the `BuildStockProcessor` abstract contract and how to add
  another BuildStock dataset.
- [Basic ComStock notebook](01_data_sampling_example.ipynb).
- [Washington, DC office and multifamily analysis](02_washington_dc_stock_analysis.ipynb), including gross floor
  area, total site energy, stock multipliers, demand profiles, monthly end uses, and measure recommendations.

## Quick Start

```python
from pathlib import Path

from buildstock_processor import ComStockProcessor, ResStockProcessor

comstock_dir = Path("datasets/comstock")
comstock_dir.mkdir(parents=True, exist_ok=True)

offices = ComStockProcessor(
    state="DC",
    county_name="All",
    building_type="SmallOffice",
    upgrade="0",
    base_dir=comstock_dir,
).process_metadata(save_dir=comstock_dir)

resstock_dir = Path("datasets/resstock")
resstock_dir.mkdir(parents=True, exist_ok=True)

multifamily_units = ResStockProcessor(
    state="DC",
    county_name="All",
    building_type="Multi-Family with 5+ Units",
    upgrade="0",
    base_dir=resstock_dir,
).process_metadata(save_dir=resstock_dir)
```

ComStock rows represent commercial buildings. ResStock rows represent independently sampled dwelling units,
including units in multifamily buildings; they are not whole-building records. Read
[Data model and limitations](docs/limitations.md) before combining or weighting the two stocks.

## Package Layout

```text
src/buildstock_processor/
|-- __init__.py   # public processors and abstract extension types
|-- _base.py      # BuildStockProcessor ABC and shared workflows
|-- comstock.py   # ComStock implementation and releases
`-- resstock.py   # ResStock implementation and releases
```

## ComStockProcessor Class

The `ComStockProcessor` class is located in `src/buildstock_processor/comstock.py` and provides methods to
download and process ComStock building data.

### Initialization

```python
from pathlib import Path
from buildstock_processor import ComStockProcessor

# Initialize the processor
processor = ComStockProcessor(
    state="CA",           # 2-letter state abbreviation
    county_name="All",    # County name, a list of county names, or "All" (see "Searching for Buildings" below)
    building_type="All",  # Building type or "All"
    upgrade="0",          # Upgrade identifier (0 = baseline)
    base_dir=Path("./datasets/comstock"),  # Local directory to save data
    release="release_3",  # Optional: which ComStock release to use (see "Supported Releases" below)
    min_sqft=None,        # Optional: only include buildings at least this large
    max_sqft=None,        # Optional: only include buildings at most this large
)
```

### Supported Releases

ComStock is periodically republished with updated building samples, results, and file layouts. `ComStockProcessor`
supports the last three published releases of the ComStock AMY2018 dataset, selected via the `release` argument:

| `release` value | Description                |
|------------------|-----------------------------|
| `"release_1"`    | ComStock AMY2018 Release 1  |
| `"release_2"`    | ComStock AMY2018 Release 2  |
| `"release_3"`    | ComStock AMY2018 Release 3 (default) |

If `release` is omitted, the most recent supported release is used. Passing an unsupported value raises a `ValueError`
listing the currently supported releases. The full set of supported releases and their on-disk locations are defined
in `SUPPORTED_RELEASES` in `src/buildstock_processor/comstock.py` — when NREL publishes a new release, add it there and drop the
oldest entry to keep a rolling window of three supported releases.

### Methods

#### `process_metadata(save_dir: Path) -> pd.DataFrame`
Downloads and processes ComStock metadata with filtering based on the class constraints.

- ComStock metadata is published per state/county/upgrade partition (not as a single national file), so this
  discovers the relevant partitions for the requested state (or every available state, if `state="All"`) and
  downloads them in parallel
- Filters by county and building type as specified during initialization
- Saves filtered results as a CSV file (namespaced by release, so different releases don't collide)
- Returns a pandas DataFrame with the filtered metadata

> **Note:** Because metadata is only partitioned by state and county (not building type), requesting a specific
> `county_name` does not reduce how many files are downloaded, and `state="All"` downloads every state's and
> county's partition files, which can be a large number of downloads.

#### `process_building_time_series(data_frame, save_dir: Path) -> tuple`
Downloads time series data for buildings specified in the input DataFrame using parallel execution.

- Uses multi-threading to download building time series files efficiently
- Skips downloading files that already exist locally
- Downloads from the ComStock AWS S3 bucket
- Returns paths and building IDs of downloaded files

### Searching for Buildings, Then Downloading Their Time Series

`process_metadata()`'s constraints (`county_name`, `building_type`, `min_sqft`/`max_sqft`) act as a search: find
the buildings matching some criteria, then pass the resulting DataFrame straight to
`process_building_time_series()` to download time series data only for those buildings.

- **`county_name`** accepts a single county, `"All"`, or a **list of counties**, which is useful for querying a
  metro area that spans several counties (a single `state`/county partition can't represent that on its own).
- **`min_sqft`/`max_sqft`** filter by building square footage (`in.sqft..ft2`).

```python
# All office buildings under 10,000 sqft in the Denver metro area
processor = ComStockProcessor(
    state="CO",
    county_name=["Denver County", "Arapahoe County", "Jefferson County", "Adams County", "Douglas County", "Broomfield County"],
    building_type="SmallOffice",
    upgrade="0",
    base_dir=base_dir,
    max_sqft=10_000,
)
matching_buildings = processor.process_metadata(save_dir=base_dir)

# Download time series data only for the buildings that matched
timeseries_dir = base_dir / "timeseries"
timeseries_dir.mkdir(exist_ok=True)
paths, building_ids = processor.process_building_time_series(matching_buildings, save_dir=timeseries_dir)
```

> **Note:** Since metadata is only partitioned by state and county (not building type or square footage),
> `min_sqft`/`max_sqft` and requesting specific counties don't reduce how many partition files are downloaded --
> they're applied locally, after downloading, the same way `building_type` already is. Cache filenames (the
> `..._selected_metadata.csv` files) encode all of these filters, so different searches against the same
> state/upgrade don't collide with each other's cached results.

### Comparing Buildings Across Measure Packages

Each ComStock "upgrade" represents a different energy-efficiency measure package (e.g. a heat pump RTU, VRF
system, or envelope upgrade) applied to the same baseline building sample. `ComStockProcessor` provides methods
to discover those packages and download metadata for several of them at once, so you can compare how a building
performs under different packages.

#### `list_upgrades(save_dir: Path) -> dict[str, str]`
Downloads (and caches) the release's `upgrades_lookup.json`, returning a mapping of upgrade id -> package name,
e.g. `{"0": "Baseline", "1": "Variable Speed HP RTU, Electric Backup", ...}`. **Which upgrade ids exist, and what
they mean, is different for every release** (release_1, release_2, and release_3 each have a different number of
packages and, in some cases, different ids for what looks like the same package).

#### `process_metadata_for_upgrades(save_dir: Path, upgrades: list[str] | None = None) -> pd.DataFrame`
Downloads and combines metadata for multiple upgrades into a single DataFrame (reusing the same per-upgrade
download/caching as `process_metadata()`). Every row already has an `upgrade` id column and an `in.upgrade_name`
column, so you can group by `bldg_id` to compare a building's results (energy consumption, savings, etc.) across
packages. If `upgrades` is omitted, every upgrade available for the release is downloaded and combined.

```python
# Compare Delaware small offices under the baseline vs. a heat pump RTU package
processor = ComStockProcessor(
    state="DE", county_name="All", building_type="SmallOffice", upgrade="0", base_dir=base_dir
)
combined_df = processor.process_metadata_for_upgrades(save_dir=base_dir, upgrades=["0", "1"])

# One row per building per package, ready to compare
combined_df.groupby("bldg_id").apply(
    lambda g: g.set_index("upgrade")["out.site_energy.total.energy_consumption..kwh"]
)
```

> **Note:** A building can appear more than once per upgrade in the "full" metadata (it may be reused to
> represent multiple census tracts, each with its own `weight`). If you only need each building's simulated
> performance, group/filter by `bldg_id` and `upgrade` and take the first row of each group.

#### Comparing measure packages *across releases*

Because upgrade ids aren't stable between releases, ComStock also publishes a `measure_name_crosswalk.csv` that
maps a stable `measure_id` (e.g. `"hvac_0005"`) to the upgrade id/name used for that measure in each release.

- **`get_measure_crosswalk(save_dir: Path) -> pd.DataFrame`** — downloads (and caches) the crosswalk table for
  the configured release. A release's crosswalk only covers itself and *earlier* releases, so `release_3`
  (the newest) has the most complete crosswalk, covering all three currently-supported releases.
- **`find_upgrade_id(save_dir: Path, measure_id: str, target_release: str | None = None) -> str | None`** —
  looks up the upgrade id for a stable `measure_id` in a specific release (defaults to the processor's own
  release). Returns `None` if that measure wasn't included in the target release, and raises a `ValueError` if
  the target release isn't covered by the currently loaded crosswalk.

```python
processor = ComStockProcessor(
    state="DE", county_name="All", building_type="All", upgrade="0", base_dir=base_dir, release="release_3"
)

# "Heat Pump RTU" happens to be upgrade "1" in every currently-supported release, but that's not
# guaranteed for every measure -- use find_upgrade_id() rather than hardcoding ids across releases.
upgrade_id_r3 = processor.find_upgrade_id(save_dir=base_dir, measure_id="hvac_0005")               # "1"
upgrade_id_r1 = processor.find_upgrade_id(save_dir=base_dir, measure_id="hvac_0005", target_release="release_1")  # "1"
```

### Usage Example

```python
from pathlib import Path
from buildstock_processor import ComStockProcessor

# Set up directories
base_dir = Path("./datasets/comstock")
timeseries_dir = base_dir / "timeseries"
for d in [base_dir, timeseries_dir]:
    d.mkdir(parents=True, exist_ok=True)

# Initialize processor for California data
processor = ComStockProcessor(
    state="CA",
    county_name="All",
    building_type="All",
    upgrade="0",
    base_dir=base_dir,
)

# Download and filter metadata
metadata_df = processor.process_metadata(save_dir=base_dir)

# Download time series data for buildings in metadata
paths, building_ids = processor.process_building_time_series(
    metadata_df,
    save_dir=timeseries_dir
)
```

### Data Source

The processor downloads data from the ComStock dataset hosted on AWS S3. For example, the default release:
- **Base URL**: `https://oedi-data-lake.s3.amazonaws.com/nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/2025/comstock_amy2018_release_3/`
- **Data Explorer**: [OpenEI Data Lake Explorer](https://data.openei.org/s3_viewer?bucket=oedi-data-lake&prefix=nrel-pds-building-stock%2Fend-use-load-profiles-for-us-building-stock%2F2025%2Fcomstock_amy2018_release_3%2F)

### Performance Features

- **Parallel Downloads**: Uses ThreadPoolExecutor for concurrent file downloads
- **Smart Caching**: Skips downloading files that already exist locally
- **Progress Tracking**: Shows download progress with tqdm progress bars
- **Efficient Filtering**: Uses pandas parquet filtering for large datasets

## ResStockProcessor Class

The `ResStockProcessor` class (in `src/buildstock_processor/resstock.py`) provides the same interface for NREL's
**residential** building stock dataset, ResStock, which is hosted on the same OEDI data lake. It shares
its download/caching/upgrade-lookup infrastructure with `ComStockProcessor` via a common
abstract `BuildStockProcessor` base class (`src/buildstock_processor/_base.py`), but has its own metadata layout and
release registry, since ResStock's file structure and building-type categories differ from ComStock's.

```python
from pathlib import Path
from buildstock_processor import ResStockProcessor

processor = ResStockProcessor(
    state="CA",
    county_name="All",
    building_type="Multi-Family with 5+ Units",  # see "Handling Multifamily Buildings" below
    upgrade="0",
    base_dir=Path("./datasets/resstock"),
)
metadata_df = processor.process_metadata(save_dir=processor.base_dir)
```

### Key differences from ComStockProcessor

- **Metadata partitioning**: ResStock metadata is partitioned only by **state** (e.g.
  `state=DE/DE_upgrade0.parquet`), not by state *and* county like ComStock. Specifying `county_name` doesn't
  reduce how much is downloaded (there's only one file per state/upgrade); it's filtered locally afterward.
- **`county_name` format**: ResStock's `in.county_name` values don't include the state prefix ComStock uses
  -- pass `"Kent County"`, not `"DE, Kent County"`. Like ComStock, `county_name` also accepts a list of
  counties for metro-area-style searches, and `min_sqft`/`max_sqft` filter by dwelling unit square footage --
  see "Searching for Buildings, Then Downloading Their Time Series" above.
- **`building_type` values**: use one of `RESSTOCK_BUILDING_TYPES` (ResStock's residential housing
  categories), not ComStock's commercial building types:
  - `Mobile Home`, `Single-Family Detached`, `Single-Family Attached`, `Multi-Family with 2 - 4 Units`,
    `Multi-Family with 5+ Units`
- **Releases**: only `"release_1"` (the default) is currently supported. Unlike ComStock, ResStock hasn't
  been fully remastered into a single consistent layout across multiple releases yet -- see
  `SUPPORTED_RELEASES` in `src/buildstock_processor/resstock.py` for notes on adding more releases later.
- **Measure crosswalk format**: `get_measure_crosswalk()` downloads an **Excel** file
  (`measure_name_crosswalk_res_{year}_{release}.xlsx`), not a csv like ComStock (this is why
  [`openpyxl`](https://openpyxl.readthedocs.io/) is a dependency).

### Handling Multifamily Buildings

ResStock simulates **individual dwelling units**, not whole buildings: a single "Multi-Family with 5+ Units"
row is one apartment unit, not the building it's in. There's no shared "building id" tying multiple sampled
units back to the same real building -- each unit is an independently sampled, weighted record. Relevant
columns:

- `in.geometry_building_type_recs` — the housing type (one of `RESSTOCK_BUILDING_TYPES`); filter/group on
  this to select multifamily units.
- `in.geometry_building_number_units_mf` — how many units are in that unit's (whole) building.
- `in.geometry_building_horizontal_location_mf` / `in.geometry_building_level_mf` — the unit's position
  within the building (corner/middle, top/bottom floor), which affects heat transfer through shared
  walls/floors/ceilings with neighboring units.
- `weight` / `in.units_represented` — the sampling weight used to scale a simulated unit up to the full
  housing stock population.

```python
processor = ResStockProcessor(
    state="DE", county_name="All", building_type="Multi-Family with 5+ Units", upgrade="0", base_dir=base_dir
)
multifamily_units_df = processor.process_metadata(save_dir=base_dir)

# Weighted total number of real housing units this sample represents
multifamily_units_df["weight"].sum()
```

### `process_metadata_for_upgrades`, `list_upgrades`, `get_measure_crosswalk`, `find_upgrade_id`

`ResStockProcessor` supports the same measure-package comparison methods documented above for
`ComStockProcessor` (`process_metadata_for_upgrades`, `list_upgrades`, `get_measure_crosswalk`,
`find_upgrade_id`) -- the only difference is the crosswalk file format (xlsx, not csv) and building-type
values (residential, not commercial), described above.

## Development

The processor includes comprehensive unit and integration tests validating both `ComStockProcessor`
(`tests/test_comstock_processor.py`) and `ResStockProcessor` (`tests/test_resstock_processor.py`).

### Running Tests

Run specific test categories:

```bash
# Unit tests only (fast)
uv run pytest tests/ -m "unit" -v

# Integration tests (downloads small datasets)
uv run pytest tests/ -m "integration" -v

# All tests including large dataset downloads
TEST_DATA=true uv run pytest tests/ -m "integration" -v

# Run all tests
uv run pytest tests -v
```

### Test Categories

- **Unit tests**: Fast tests that verify initialization and basic functionality
- **Integration tests**: Tests that download and process real ComStock and ResStock data. `test_all_state_filter`
  mocks state discovery down to a couple of small states so it can exercise the real `state="All"`
  code path without downloading every state's/county's metadata partition.

Execute the notebooks as integration checks:

```bash
uv run jupyter nbconvert --to html --execute 01_data_sampling_example.ipynb
uv run jupyter nbconvert --to html --execute 02_washington_dc_stock_analysis.ipynb
```

### Committing

Before pushing changes to GitHub, run `pre-commit` to format the code consistently. `pre-commit` is installed as part of the `dev` dependency group, so run it via `uv`:

```bash
uv run pre-commit run --all-files
```

If this doesn't work, try:

```bash
uv sync --group dev
uv run pre-commit run --all-files
```
