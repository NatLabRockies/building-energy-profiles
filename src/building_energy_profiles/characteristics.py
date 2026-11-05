"""Constrain BuildStock samples on building characteristics beyond type, geography, and floor area.

A `BuildingCharacteristics` narrows a ComStock/ResStock metadata sample to buildings that look like a real
building in ways that matter for its energy use -- most importantly *which fuels it uses*. For example, a
gas-heated office should be represented by gas-heated ComStock offices, not by the full office sample
(which in Washington, DC mixes gas, electric, and district-heated buildings and so badly misallocates
energy between meters).

Two kinds of constraints are supported:

* **Input characteristics** (`heating_fuel`, `water_heating_fuel`, `attributes`) match `in.*` metadata
  columns. They describe the modeled building itself, so they are identical across upgrades.
* **Fuel-presence characteristics** (`has_natural_gas`, `has_district_heating`, `has_district_cooling`)
  test whether the building uses that fuel at all (annual consumption > 0). They catch uses that input
  columns miss -- e.g. an electrically heated ComStock building with gas cooking or gas water heating.
  They are always evaluated on the **baseline** (upgrade "0") annual results, so the same buildings are
  kept for every upgrade and baseline-vs-upgrade comparisons stay like-for-like even when an upgrade
  removes a fuel (e.g. electrification).

Fuel names are product-neutral (`"natural_gas"`, `"electricity"`, `"district_heating"`, `"propane"`,
`"fuel_oil"`, `"other"`) and mapped onto each product's own vocabulary (ComStock "NaturalGas" vs.
ResStock "Natural Gas").
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

# Product-neutral fuel name -> {product: [values used in that product's in.*fuel columns]}
FUEL_VALUES: dict[str, dict[str, tuple[str, ...]]] = {
    "electricity": {"comstock": ("Electricity",), "resstock": ("Electricity",)},
    "natural_gas": {"comstock": ("NaturalGas",), "resstock": ("Natural Gas",)},
    "district_heating": {"comstock": ("DistrictHeating",), "resstock": ()},
    "propane": {"comstock": ("Propane",), "resstock": ("Propane",)},
    "fuel_oil": {"comstock": ("FuelOil",), "resstock": ("Fuel Oil",)},
    "other": {"comstock": (), "resstock": ("Other Fuel",)},
}
FUELS: tuple[str, ...] = tuple(FUEL_VALUES)

# Product-neutral cooling system name -> {product: [values used in that product's cooling-type column]}.
# The cooling-side counterpart of `heating_fuel`: `cooling_type="district"` selects buildings served by district
# chilled water from their *inputs*, while `has_district_cooling` does so from baseline *results* (identical in
# ComStock baseline; they differ only if an upgrade replaces the cooling plant).
COOLING_VALUES: dict[str, dict[str, tuple[str, ...]]] = {
    "district": {"comstock": ("District",), "resstock": ()},
    "chiller": {"comstock": ("WCC", "ACC"), "resstock": ()},
    "dx": {"comstock": ("DX",), "resstock": ("Central AC", "Room AC")},
    "heat_pump": {"comstock": ("ASHP", "WSHP", "GSHP"), "resstock": ("Ducted Heat Pump", "Non-Ducted Heat Pump")},
    "none": {"comstock": (), "resstock": ("None",)},
}
COOLING_TYPES: tuple[str, ...] = tuple(COOLING_VALUES)
_COOLING_COLUMNS: dict[str, str] = {"comstock": "in.hvac_cool_type", "resstock": "in.hvac_cooling_type"}

# Least to most important: which constraint to give up first when a sample is too small.
RELAXATION_ORDER: tuple[str, ...] = (
    "attributes",
    "has_natural_gas",
    "water_heating_fuel",
    "cooling_type",
    "has_district_cooling",
    "heating_fuel",
    "has_district_heating",
)

# Product -> (heating fuel column, water heating fuel column)
_FUEL_COLUMNS: dict[str, tuple[str, str]] = {
    "comstock": ("in.heating_fuel", "in.service_water_heating_fuel"),
    "resstock": ("in.heating_fuel", "in.water_heater_fuel"),
}

# Fuel-presence flag -> annual-results column (baseline consumption > 0 means "has")
_PRESENCE_COLUMNS: dict[str, str] = {
    "has_natural_gas": "out.natural_gas.total.energy_consumption",
    "has_district_heating": "out.district_heating.total.energy_consumption",
    "has_district_cooling": "out.district_cooling.total.energy_consumption",
}


def _normalize_fuels(
    value: str | Iterable[str] | None, argument: str, vocabulary: Mapping[str, Any] = FUEL_VALUES
) -> tuple[str, ...] | None:
    if value is None:
        return None
    fuels = (value,) if isinstance(value, str) else tuple(value)
    normalized = tuple(fuel.strip().lower().replace(" ", "_").replace("-", "_") for fuel in fuels)
    unknown = [fuel for fuel in normalized if fuel not in vocabulary]
    if unknown or not normalized:
        raise ValueError(f"Unknown {argument} {unknown or list(fuels)}; expected one or more of {list(vocabulary)}.")
    return normalized


def _find_column(columns: pd.Index, prefix: str) -> str | None:
    """Return `prefix` or `prefix..<unit>` (annual metadata columns carry a unit suffix)."""
    if prefix in columns:
        return prefix
    return next((column for column in columns if column.startswith(prefix + "..")), None)


@dataclass(frozen=True)
class BuildingCharacteristics:
    """Optional constraints applied to a processor's metadata sample. Every field defaults to "no constraint".

    Attributes:
        heating_fuel: keep buildings whose primary space-heating fuel is one of these (product-neutral names,
            see `FUELS`), e.g. `"natural_gas"` or `("electricity", "district_heating")`.
        water_heating_fuel: same, for the (service) water heating fuel.
        cooling_type: keep buildings whose space-cooling system is one of these (product-neutral names, see
            `COOLING_TYPES`): `"district"` (district chilled water), `"chiller"` (water- or air-cooled chiller),
            `"dx"`, `"heat_pump"` or `"none"`. ResStock has no district cooling or chillers.
        has_natural_gas: `True` keeps only buildings with baseline natural gas use; `False` keeps only
            buildings with none (all-electric or other fuels).
        has_district_heating: `True`/`False` on baseline district heating use (ComStock only; ResStock models
            no district heating, so `True` yields an empty sample and `False` keeps everything).
        has_district_cooling: as `has_district_heating`, for district chilled water.
        attributes: exact-match constraints on any other metadata column, `{column: value or [values]}`,
            e.g. `{"in.hvac_category": "Small Packaged Unit"}`.
    """

    heating_fuel: tuple[str, ...] | None = None
    water_heating_fuel: tuple[str, ...] | None = None
    cooling_type: tuple[str, ...] | None = None
    has_natural_gas: bool | None = None
    has_district_heating: bool | None = None
    has_district_cooling: bool | None = None
    attributes: Mapping[str, tuple[Any, ...]] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "heating_fuel", _normalize_fuels(self.heating_fuel, "heating_fuel"))
        object.__setattr__(self, "water_heating_fuel", _normalize_fuels(self.water_heating_fuel, "water_heating_fuel"))
        object.__setattr__(self, "cooling_type", _normalize_fuels(self.cooling_type, "cooling_type", COOLING_VALUES))
        attributes = {
            str(column): (tuple(values) if isinstance(values, (list, tuple, set, frozenset)) else (values,))
            for column, values in dict(self.attributes or {}).items()
        }
        object.__setattr__(self, "attributes", attributes)

    @classmethod
    def coerce(cls, value: BuildingCharacteristics | Mapping[str, Any] | None) -> BuildingCharacteristics | None:
        """Accept a `BuildingCharacteristics`, a plain dict of its fields (e.g. from JSON/MCP), or None."""
        if value is None or isinstance(value, BuildingCharacteristics):
            return None if value is not None and value.is_empty else value
        unknown = set(value) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"Unknown building characteristics {sorted(unknown)}; expected any of {sorted(cls.__dataclass_fields__)}.")
        result = cls(**dict(value))
        return None if result.is_empty else result

    @property
    def is_empty(self) -> bool:
        return not self.to_dict()

    @property
    def uses_baseline_results(self) -> bool:
        """True if any fuel-presence flag is set (these are evaluated on baseline annual results)."""
        return any(getattr(self, flag) is not None for flag in _PRESENCE_COLUMNS)

    def to_dict(self) -> dict[str, Any]:
        """The constraints that are actually set, JSON-friendly."""
        result: dict[str, Any] = {}
        for name in ("heating_fuel", "water_heating_fuel", "cooling_type"):
            if getattr(self, name):
                result[name] = list(getattr(self, name))
        for name in _PRESENCE_COLUMNS:
            if getattr(self, name) is not None:
                result[name] = getattr(self, name)
        if self.attributes:
            result["attributes"] = {column: list(values) for column, values in sorted(self.attributes.items())}
        return result

    def label(self) -> str:
        """A short, filesystem-safe, stable label used in cache file names ("" when unconstrained)."""
        if self.is_empty:
            return ""
        parts = []
        if self.heating_fuel:
            parts.append("hf_" + "+".join(self.heating_fuel))
        if self.water_heating_fuel:
            parts.append("whf_" + "+".join(self.water_heating_fuel))
        if self.cooling_type:
            parts.append("ct_" + "+".join(self.cooling_type))
        for name, short in (("has_natural_gas", "ng"), ("has_district_heating", "dh"), ("has_district_cooling", "dc")):
            if getattr(self, name) is not None:
                parts.append(f"{short}{int(getattr(self, name))}")
        if self.attributes:
            digest = hashlib.blake2b(
                json.dumps(self.to_dict()["attributes"], sort_keys=True, default=str).encode(), digest_size=4
            ).hexdigest()
            parts.append(f"attr_{digest}")
        return "-".join(parts)

    def apply_inputs(self, meta_df: pd.DataFrame, product: str) -> pd.DataFrame:
        """Apply the input-column constraints (fuels and `attributes`)."""
        product = product.strip().lower()
        heating_column, water_column = _FUEL_COLUMNS[product]
        for fuels, column in ((self.heating_fuel, heating_column), (self.water_heating_fuel, water_column)):
            if fuels:
                values = [value for fuel in fuels for value in FUEL_VALUES[fuel][product]]
                if column not in meta_df.columns:
                    raise KeyError(f"Metadata has no '{column}' column to filter on.")
                meta_df = meta_df[meta_df[column].isin(values)]
        if self.cooling_type:
            column = _COOLING_COLUMNS[product]
            values = [value for kind in self.cooling_type for value in COOLING_VALUES[kind][product]]
            if column not in meta_df.columns:
                raise KeyError(f"Metadata has no '{column}' column to filter on.")
            meta_df = meta_df[meta_df[column].isin(values)]
        for column, values in self.attributes.items():
            if column not in meta_df.columns:
                raise KeyError(f"Metadata has no '{column}' column to filter on.")
            meta_df = meta_df[meta_df[column].isin(values)]
        return meta_df

    def presence_mask(self, baseline_df: pd.DataFrame) -> pd.Series:
        """Boolean mask over `baseline_df` rows for the fuel-presence constraints."""
        mask = pd.Series(True, index=baseline_df.index)
        for flag, prefix in _PRESENCE_COLUMNS.items():
            wanted = getattr(self, flag)
            if wanted is None:
                continue
            column = _find_column(baseline_df.columns, prefix)
            has = baseline_df[column].fillna(0) > 0 if column else pd.Series(False, index=baseline_df.index)
            mask &= has if wanted else ~has
        return mask

    def without(self, *names: str) -> BuildingCharacteristics | None:
        """A copy with the named constraints removed (None if nothing is left)."""
        return BuildingCharacteristics.coerce({k: v for k, v in self.to_dict().items() if k not in names})

    def apply_with_relaxation(
        self,
        meta_df: pd.DataFrame,
        product: str,
        min_count: int,
        order: Iterable[str] = RELAXATION_ORDER,
        baseline_df: pd.DataFrame | None = None,
    ) -> tuple[pd.DataFrame, BuildingCharacteristics | None, list[str]]:
        """Apply the constraints; if fewer than `min_count` buildings remain, drop constraints one at a time in
        `order` (least to most important) until enough remain.

        Dropping everything at once (the obvious fallback) throws away the most informative constraint too -- e.g.
        a steam-heated building with no chilled water would lose `has_district_heating` along with
        `has_district_cooling`. Relaxing one at a time keeps the plant type as long as possible.

        Returns:
            (filtered metadata, the characteristics actually used, the names that were dropped).
        """
        current: BuildingCharacteristics | None = self
        dropped: list[str] = []
        remaining = [name for name in order if name in self.to_dict()]
        while True:
            result = current.apply(meta_df, product, baseline_df) if current else meta_df
            if len(result) >= min_count or current is None:
                return result, current, dropped
            if not remaining:  # every ordered constraint is gone; drop whatever is left
                dropped += list(current.to_dict())
                current = None
                continue
            name = remaining.pop(0)
            dropped.append(name)
            current = current.without(name)

    def apply(self, meta_df: pd.DataFrame, product: str, baseline_df: pd.DataFrame | None = None) -> pd.DataFrame:
        """Filter `meta_df`. `baseline_df` (the baseline upgrade's metadata for the same scope) is required
        only when fuel-presence flags are set and `meta_df` is not itself baseline metadata."""
        meta_df = self.apply_inputs(meta_df, product)
        if self.uses_baseline_results:
            reference = meta_df if baseline_df is None else baseline_df
            keep = set(reference.loc[self.presence_mask(reference), "bldg_id"])
            meta_df = meta_df[meta_df["bldg_id"].isin(keep)]
        return meta_df
