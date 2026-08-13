# Data Model and Limitations

This package is a focused downloader and local analysis helper for published ComStock and ResStock files. It is
not a general BuildStock query service, simulation engine, or authoritative building registry.

## Supported Releases

The code supports only the explicitly registered layouts:

| Dataset | Supported releases | Default |
| --- | --- | --- |
| ComStock AMY2018 | `2025/comstock_amy2018_release_1` through `2025/comstock_amy2018_release_3` | `release_3` |
| ResStock | `2025/resstock_amy2018_release_1` or `2025/resstock_amy2012_release_1` | `release_1`, `weather_year="amy2018"` |

New OEDI releases are not automatically compatible. Directory layouts, columns, upgrade IDs, and crosswalk files
can change. Add and test a release in `src/building_energy_profiles/comstock.py` or
`src/building_energy_profiles/resstock.py` before using it.

The `release` argument is always the `release_N` component. The year directory and weather-year component are
resolved by the processor's release registry and, for ResStock, the `weather_year` argument.

## ComStock and ResStock Records Mean Different Things

ComStock records represent modeled commercial buildings.

ResStock records represent independently sampled dwelling units. A row categorized as
`Multi-Family with 5+ Units` is one unit in a multifamily building, not the whole building. ResStock provides
context such as:

- Number of units in the containing building.
- Horizontal unit location.
- Building level.
- Unit floor area.

It does not provide a shared physical-building ID that links sampled units into one reconstructable building.
Multiplying a unit's load or floor area by its building unit count is an approximation that assumes all units
behave like that sampled unit.

## Weights and Duplicate Rows

Weights are required for stock-level totals, but their meaning differs:

- ComStock `weight` scales a geographic metadata row to represented commercial buildings.
- ResStock `weight` scales one sampled dwelling unit to represented dwelling units.

A ComStock `bldg_id` can appear more than once for an upgrade because the modeled building can represent multiple
census tracts. These rows can have different weights and demographic attributes.

- Keep the rows and weights for stock totals.
- Deduplicate by `bldg_id` and `upgrade` for unique simulated-building comparisons.

Never sum raw unweighted sample rows and describe the result as the Washington, DC, state, or national stock.

## Multifamily Whole-Building Estimates

For a transparent illustrative estimate:

```text
estimated building value = sampled unit value * units in building
estimated building multiplier = unit weight / units in building
```

This preserves aggregate represented floor area or energy because the unit count cancels when the multiplier is
applied. It does not recover:

- Diversity among units.
- Different corner, middle, top, or bottom unit loads.
- Common-area energy.
- Central plant or shared-system behavior not allocated to the sampled unit.
- A real building's coincident peak demand.

Use ResStock unit-level results for residential stock analysis. Use the whole-building estimate only when its
homogeneous-unit assumption is acceptable and clearly labeled.

## Filter Scope and Download Cost

Filters are applied after published parquet partitions are downloaded:

- ComStock metadata is partitioned by state and county code, but the processor does not map requested county names
  to partition codes before downloading. A county filter therefore does not reduce the state's metadata download.
- ResStock metadata is partitioned only by state. County, building type, and floor-area filters are local.
- `state="All"` discovers and downloads every available state partition. For ComStock this can involve thousands
  of small state/county files and can be slow.
- With ComStock, a county filter is ignored when `state="All"` because a county name alone is not nationally
  unique.

Start with one state and a baseline upgrade. Avoid calling `process_metadata_for_upgrades()` without an explicit
upgrade list until the expected download size is understood.

## Time-Series Semantics

Time-series files are downloaded one record at a time. Passing a large metadata DataFrame can create many network
requests and substantial disk use.

Published schemas differ by dataset and release. In currently supported data:

- ResStock interval energy columns may end in `.energy_consumption..kwh`.
- ComStock interval energy columns may end in `.energy_consumption`.
- Interval energy is kWh, not kW. Divide by interval duration in hours to calculate average kW.
- A ResStock time series is a dwelling-unit profile, even when its metadata building type is multifamily.

Inspect columns and timestamps instead of assuming a fixed schema or interval.

## Cache Behavior

The package uses file existence as its cache:

- Raw metadata partitions are reused when their expected files exist.
- Filtered metadata CSV names include release, geography, building type, floor-area range, and upgrade.
- Time-series files are reused by building ID and upgrade.
- Upgrade lookups and crosswalks are cached locally.

There is no checksum validation, expiration policy, or automatic refresh. Delete the relevant cached file when a
published source changes or when a clean download is required.

Do not point different datasets or incompatible release layouts at the same cache directory.

## Network and Failure Handling

Downloads use the public OEDI S3 endpoints and require network access. The downloader has finite request timeouts
but currently has no retry policy, exponential backoff, checksum verification, or resumable transfer.

For time-series downloads, inspect returned paths before analysis. A failed HTTP response is reported to the
console, but callers should still verify that each expected file exists and is readable.

Concurrent downloads use a fixed worker count optimized for network-bound work. Performance depends on OEDI,
network latency, local disk speed, and the number of small partitions.

## Upgrade Comparisons

Upgrade IDs are not stable across releases. Do not assume upgrade `"1"` has the same meaning everywhere.

- Use `list_upgrades()` to inspect the configured release.
- Use `get_measure_crosswalk()` and `find_upgrade_id()` for cross-release matching.
- A release crosswalk may cover only that release and earlier releases.
- ComStock crosswalks are CSV; ResStock crosswalks are Excel.

Upgrade metadata represents modeled scenarios, not measured post-retrofit outcomes. Recommendations based on
dominant end uses should be treated as screening guidance and confirmed through engineering analysis.

## Reproducibility

For reproducible analysis, record:

- Dataset and release.
- Upgrade ID and resolved package name.
- State, counties, building type, and floor-area filters.
- Whether duplicate ComStock geographic rows were retained.
- Whether stock weights were applied.
- Any ResStock whole-building approximation.
- Cache state or source retrieval date.
- Time-series interval and column normalization.

The example notebooks are executable documentation, but their committed outputs are stripped by pre-commit.
Render or execute them locally, or use the HTML artifacts generated by CI.
