# Extending Building Energy Profiles

`BuildStockProcessor` is an abstract base class for datasets that use the common OEDI BuildStock conventions.
It is exported from the top-level package:

```python
from buildstock_processor import (
    BuildStockProcessor,
    BuildStockRelease,
    MetadataPartition,
)
```

Users normally instantiate `ComStockProcessor` or `ResStockProcessor`. The abstract class is an extension point
for maintainers adding another compatible dataset or a newly published layout.

## What the Base Class Owns

The base class provides concrete implementations for:

- Public S3 object listing and file downloading.
- Raw metadata partition caching.
- Parallel partition downloads.
- Parquet concatenation.
- Square-footage filtering.
- Filtered metadata CSV naming and caching.
- Single-upgrade metadata processing.
- Multi-upgrade metadata combination.
- Upgrade lookup loading.
- Individual-record time-series downloads.

This keeps the network, cache, and orchestration behavior consistent across datasets.

## Required Dataset Hooks

A concrete subclass must implement:

| Hook | Responsibility |
| --- | --- |
| `_metadata_partitions()` | Discover the state or state/county partitions required by the configured scope. |
| `_metadata_partition_cache_name()` | Name one raw metadata parquet in the local cache. |
| `_metadata_partition_url()` | Build the public URL for one partition and upgrade. |
| `_filter_metadata()` | Apply dataset-specific geography and building-type filters. |
| `get_measure_crosswalk()` | Load the dataset's crosswalk format. |
| `find_upgrade_id()` | Resolve a stable measure ID for a target release. |

The subclass constructor must also set:

- `product_name`
- `state`
- `county_name`
- `building_type`
- `upgrade`
- `release`
- `base_dir`
- `min_sqft`
- `max_sqft`
- `base_url`
- `metadata_url`
- `time_series_url`
- `_metadata_key_prefix`

For a published OEDI layout, store the publication year separately from the release identifier. URL construction
should follow `<year>/<product>_<weather_year>_<release>/`; for example,
`2025/comstock_amy2018_release_3/`. Keep `release` as `release_N` so upgrade lookup and cache naming remain
consistent across datasets.

## Minimal Subclass Shape

```python
from pathlib import Path

import pandas as pd

from buildstock_processor import (
    BuildStockProcessor,
    MetadataPartition,
)


class ExampleStockProcessor(BuildStockProcessor):
    product_name = "ExampleStock"

    def __init__(
        self,
        state: str,
        county_name: str | list[str],
        building_type: str,
        upgrade: str,
        base_dir: Path,
    ) -> None:
        self.state = state
        self.county_name = county_name
        self.building_type = building_type
        self.upgrade = upgrade
        self.base_dir = base_dir
        self.release = "release_1"
        self.min_sqft = None
        self.max_sqft = None

        self.base_url = "https://example.invalid/example_stock/"
        self.metadata_url = self.base_url + "metadata"
        self.time_series_url = self.base_url + "timeseries_individual_buildings"
        self._metadata_key_prefix = "example_stock/metadata/"

    def _metadata_partitions(self) -> list[MetadataPartition]:
        states = self._available_states() if self.state == "All" else [self.state]
        return [MetadataPartition(state=state) for state in states]

    def _metadata_partition_cache_name(
        self,
        partition: MetadataPartition,
        upgrade: str,
    ) -> str:
        return f"{partition.state}-upgrade{upgrade}.parquet"

    def _metadata_partition_url(
        self,
        partition: MetadataPartition,
        upgrade: str,
    ) -> str:
        return (
            f"{self.metadata_url}/state={partition.state}/"
            f"{partition.state}_upgrade{upgrade}.parquet"
        )

    def _filter_metadata(self, frame: pd.DataFrame) -> pd.DataFrame:
        if self.building_type != "All":
            frame = frame[
                frame["in.example_building_type"] == self.building_type
            ]
        return frame

    def get_measure_crosswalk(self, save_dir: Path) -> pd.DataFrame:
        raise NotImplementedError

    def find_upgrade_id(
        self,
        save_dir: Path,
        measure_id: str,
        target_release: str | None = None,
    ) -> str | None:
        raise NotImplementedError
```

Calling `process_metadata()`, `process_metadata_for_upgrades()`, `list_upgrades()`, and
`process_building_time_series()` then uses the shared base implementation.

## Design Boundary

Use a subclass only when the dataset follows the same broad workflow: published metadata partitions, upgrade
packages, and per-record time-series files.

Do not force a dataset into this abstraction when it requires fundamentally different authentication, query
semantics, storage, or simulation orchestration. In that case, composition around the lower-level download helpers
is clearer than adding conditionals to the base class.

## Tests for a New Dataset

At minimum, add tests for:

- Constructor validation and release URL construction.
- Partition discovery, URL generation, and cache filenames.
- Geography, building-type, and floor-area filtering.
- First-run downloads and cached reruns.
- Empty metadata and time-series selections.
- A small real metadata download.
- A small real time-series download.
- Upgrade lookup and crosswalk behavior.

The base class itself is abstract and cannot be instantiated. Tests should verify that the concrete subclass uses
the inherited metadata workflows rather than reimplementing them.
