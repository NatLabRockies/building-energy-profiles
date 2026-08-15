"""Fast access to the packaged ENERGY STAR Portfolio Manager -> BuildStock building-type crosswalk.

ENERGY STAR Portfolio Manager's "property type" taxonomy (used for benchmarking and 1-100 ENERGY STAR
scores) is much finer-grained and differently organized than BuildStock's building types, which come from
DOE's commercial prototype building models (ComStock, 15 types) and simplified residential housing
categories (ResStock, 5 types). Several ENERGY STAR property types have no close BuildStock equivalent at
all (e.g. "Zoo", "Swimming Pool", open-air stadiums, parking structures).

This crosswalk is a best-effort approximation authored for building_energy_profiles -- it is not an official
NLR or EPA publication. Each entry records a `match_quality` ("exact", "approximate", or "unmapped") and
`notes` explaining the reasoning, so callers can decide whether an approximate match is good enough for
their use case. The dictionary is stored as plain JSON alongside this module so tools can parse it without
importing Python, while this module exposes a small Python-friendly lookup API for interactive use.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any


@dataclass(frozen=True)
class EnergyStarMapping:
    """One ENERGY STAR Portfolio Manager property type mapped to its closest-fit BuildStock building type.

    `buildstock_product` ("comstock" or "resstock") and `buildstock_building_type` are `None` when
    `match_quality` is "unmapped" (no reasonable BuildStock building type exists for that property type).
    `match_quality` is one of "exact", "approximate", or "unmapped".
    """

    energy_star_property_type: str
    buildstock_product: str | None
    buildstock_building_type: str | None
    match_quality: str
    notes: str


@cache
def _raw_energy_star_crosswalk() -> tuple[Mapping[str, Any], ...]:
    data_path = resources.files("building_energy_profiles").joinpath("energy_star_crosswalk.json")
    with data_path.open(encoding="utf-8") as file:
        loaded: list[dict[str, Any]] = json.load(file)
    return tuple(loaded)


@cache
def energy_star_crosswalk() -> tuple[EnergyStarMapping, ...]:
    """Return the packaged ENERGY STAR Portfolio Manager -> BuildStock building-type crosswalk."""
    return tuple(
        EnergyStarMapping(
            energy_star_property_type=row["energy_star_property_type"],
            buildstock_product=row["buildstock_product"],
            buildstock_building_type=row["buildstock_building_type"],
            match_quality=row["match_quality"],
            notes=row["notes"],
        )
        for row in _raw_energy_star_crosswalk()
    )


@cache
def _crosswalk_by_property_type() -> Mapping[str, EnergyStarMapping]:
    return {mapping.energy_star_property_type.casefold(): mapping for mapping in energy_star_crosswalk()}


def list_energy_star_property_types() -> tuple[str, ...]:
    """Return every packaged ENERGY STAR Portfolio Manager property type name."""
    return tuple(mapping.energy_star_property_type for mapping in energy_star_crosswalk())


def map_energy_star_property_type(property_type: str) -> EnergyStarMapping | None:
    """Look up the BuildStock crosswalk entry for an ENERGY STAR Portfolio Manager property type.

    Matching is case-insensitive but otherwise exact (e.g. "bank branch" matches "Bank Branch"). Returns
    `None` if `property_type` isn't one of the packaged ENERGY STAR Portfolio Manager property types --
    see `list_energy_star_property_types()` for the full supported list.
    """
    return _crosswalk_by_property_type().get(property_type.strip().casefold())


# DOE commercial reference/prototype building total floor areas (sq ft) for ComStock's three office-size
# building types (Deru et al., "U.S. Department of Energy Commercial Reference Building Models of the
# National Building Stock", NREL/TP-5500-46861, 2011) -- these are the "typical" sizes each prototype was
# originally built to represent, used here only to size-tier a *generic* ENERGY STAR property type once an
# actual target square footage is known (see `_SIZE_TIERED_PROPERTY_TYPES`/`refine_building_type_for_sqft`).
_OFFICE_SIZE_TIERS: tuple[tuple[str, float], ...] = (
    ("SmallOffice", 5_500.0),
    ("MediumOffice", 53_600.0),
    ("LargeOffice", 498_588.0),
)

# ENERGY STAR property type (casefolded) -> its size tiers, restricted to property types whose crosswalk
# entry is explicitly a size-ambiguous default (see that entry's own `notes`, e.g. "Office" -> MediumOffice,
# "used as the default... Use SmallOffice/LargeOffice when building size is known") -- NOT every property
# type that happens to map to an office building type as a rough proxy for unrelated reasons (e.g.
# "Laboratory" -> LargeOffice, chosen for its plug-load profile rather than size), which should keep their
# crosswalk mapping regardless of any entered square footage.
_SIZE_TIERED_PROPERTY_TYPES: dict[str, tuple[tuple[str, float], ...]] = {
    "office": _OFFICE_SIZE_TIERS,
}


def refine_building_type_for_sqft(property_type: str, sqft: float) -> str | None:
    """Refine a generic, size-ambiguous ENERGY STAR property type's crosswalk building type using an actual
    target square footage -- e.g. "Office" (crosswalk default: MediumOffice) resolves to "SmallOffice" for
    a 5,000 sqft building or "LargeOffice" for a 300,000 sqft one, picking whichever of `_OFFICE_SIZE_TIERS`
    is the best fit for `sqft`.

    Comparison is done on a log scale (comparing `sqft` against the geometric-mean breakpoint between each
    pair of adjacent tiers) since the reference floor areas span nearly two orders of magnitude -- a plain
    linear nearest-value comparison would almost always pick the largest tier.

    Returns `None` -- meaning "keep the crosswalk's original static mapping" -- if `property_type` isn't
    one of the packaged size-tiered types (see `_SIZE_TIERED_PROPERTY_TYPES`) or `sqft` isn't positive.
    """
    tiers = _SIZE_TIERED_PROPERTY_TYPES.get(property_type.strip().casefold())
    if not tiers or sqft <= 0:
        return None
    log_sqft = math.log(sqft)
    return min(tiers, key=lambda tier: abs(math.log(tier[1]) - log_sqft))[0]


def energy_star_property_types_for_buildstock_type(buildstock_product: str, buildstock_building_type: str) -> tuple[str, ...]:
    """Reverse lookup: return every ENERGY STAR property type that maps to a given BuildStock product +
    building type (e.g. `energy_star_property_types_for_buildstock_type("comstock", "SmallOffice")`).
    """
    product = buildstock_product.strip().casefold()
    building_type_cf = buildstock_building_type.strip().casefold()
    return tuple(
        mapping.energy_star_property_type
        for mapping in energy_star_crosswalk()
        if mapping.buildstock_product is not None
        and mapping.buildstock_product.casefold() == product
        and mapping.buildstock_building_type is not None
        and mapping.buildstock_building_type.casefold() == building_type_cf
    )
