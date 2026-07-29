"""Discover which states/counties actually have published BuildStock metadata.

Useful for building a UI (e.g. a state dropdown, then a dependent county dropdown) that only offers
selections the underlying dataset can actually answer, instead of a free-text field that silently returns
zero rows for an unpublished state/county.

`list_available_states()` is cheap: it lists S3 "state=" partition folder names directly, without
downloading any metadata. `list_available_counties()` is more expensive: ComStock partitions metadata by
county at the S3 level using FIPS-style codes (e.g. "G1000010"), not human-readable names, and ResStock
doesn't partition by county at all (see `resstock.py`'s module docstring) -- so for both products, getting
real county *names* means downloading/caching that state's full metadata and reading its distinct
`in.county_name` values instead of just listing partition folders.

Not every county in a state is guaranteed to have its own published sample (BuildStock's sampling is
probabilistic, not exhaustive per-county) -- `county_name="All"` is always a safe fallback that includes the
whole state regardless of which counties are (or aren't) individually represented.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .comstock import ComStockProcessor
from .resstock import ResStockProcessor


def _build_processor(product: str, save_dir: Path, state: str = "All", release: str | None = None) -> ComStockProcessor | ResStockProcessor:
    processor_cls: type[ComStockProcessor | ResStockProcessor] = (
        ComStockProcessor if product.strip().lower() == "comstock" else ResStockProcessor
    )
    kwargs: dict[str, Any] = {
        "state": state,
        "county_name": "All",
        "building_type": "All",
        "upgrade": "0",
        "base_dir": save_dir,
    }
    if release:
        kwargs["release"] = release
    return processor_cls(**kwargs)


def list_available_states(product: str, save_dir: Path, release: str | None = None) -> list[str]:
    """Return every 2-letter state abbreviation with published metadata for `product`'s (default, unless
    `release` overrides it) release. Fast -- no metadata is downloaded.
    """
    processor = _build_processor(product, save_dir, release=release)
    return sorted(processor.available_states())


def list_available_counties(product: str, state: str, save_dir: Path, release: str | None = None) -> list[str]:
    """Return every distinct county name actually published for `state` in `product`'s metadata (e.g.
    "Kent County" -- the "STATE, " prefix `in.county_name` carries internally is stripped so results match
    `county_name` filter values directly).

    Downloads/caches `state`'s full metadata (building_type="All", upgrade="0") if not already cached --
    see module docstring for why this can't just list S3 partitions the way `list_available_states()` does.
    Returns `[]` if `state` has no published metadata at all (rather than raising), so a caller can fall
    back to offering only "All".
    """
    processor = _build_processor(product, save_dir, state=state, release=release)
    metadata = processor.process_metadata(save_dir=processor.base_dir)
    if metadata.empty or "in.county_name" not in metadata.columns:
        return []
    prefix = f"{state}, "
    names = {(name.removeprefix(prefix)) for name in metadata["in.county_name"].dropna().unique()}
    return sorted(names)


__all__ = ["list_available_counties", "list_available_states"]
