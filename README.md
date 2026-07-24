# ComStock Processor

A Python class to help download ComStock data locally for analysis. The `ComStockProcessor` class provides an easy interface to download metadata and time series data from the ComStock dataset hosted on AWS S3.

## Installation

Install [uv](https://docs.astral.sh/uv/) and sync the project's dependencies:

```bash
pip install uv
uv sync --group dev
```

## ComStockProcessor Class

The `ComStockProcessor` class is located in `lib/comstock_processor.py` and provides methods to download and process ComStock building data.

### Initialization

```python
from pathlib import Path
from lib.comstock_processor import ComStockProcessor

# Initialize the processor
processor = ComStockProcessor(
    state="CA",           # 2-letter state abbreviation
    county_name="All",    # County name or "All"
    building_type="All",  # Building type or "All"
    upgrade="0",          # Upgrade identifier (0 = baseline)
    base_dir=Path("./datasets/comstock"),  # Local directory to save data
    release="release_3",  # Optional: which ComStock release to use (see "Supported Releases" below)
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
in `SUPPORTED_RELEASES` in `comstock_processor.py` — when NREL publishes a new release, add it there and drop the
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
from lib.comstock_processor import ComStockProcessor

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

## Development

## Testing

The ComStock processor includes comprehensive unit and integration tests that validate the downloading and processing functionality.

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
- **Integration tests**: Tests that download and process real ComStock data. `test_all_state_filter`
  mocks state discovery down to a couple of small states so it can exercise the real `state="All"`
  code path without downloading every state's/county's metadata partition.

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
