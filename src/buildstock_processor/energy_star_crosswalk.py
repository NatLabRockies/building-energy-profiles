"""Fast access to the packaged ENERGY STAR Portfolio Manager -> BuildStock building-type crosswalk.

ENERGY STAR Portfolio Manager's "property type" taxonomy (used for benchmarking and 1-100 ENERGY STAR
scores) is much finer-grained and differently organized than BuildStock's building types, which come from
DOE's commercial prototype building models (ComStock, 15 types) and simplified residential housing
categories (ResStock, 5 types). Several ENERGY STAR property types have no close BuildStock equivalent at
all (e.g. "Zoo", "Swimming Pool", open-air stadiums, parking structures).

This crosswalk is a best-effort approximation authored for buildstock_processor -- it is not an official
NREL or EPA publication. Each entry records a `match_quality` ("exact", "approximate", or "unmapped") and
`notes` explaining the reasoning, so callers can decide whether an approximate match is good enough for
their use case. The dictionary is stored as plain JSON alongside this module so tools can parse it without
importing Python, while this module exposes a small Python-friendly lookup API for interactive use.
"""

from __future__ import annotations

import json
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
    data_path = resources.files("buildstock_processor").joinpath("energy_star_crosswalk.json")
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
