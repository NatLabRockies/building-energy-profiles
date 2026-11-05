"""Nearest-match selection of BuildStock buildings against a real building's known attributes.

`find_nearest_buildings()` ranks the rows of a (type- and characteristic-filtered) metadata sample by how
close each simulated building is to a target building, using any of:

- floor area (`sqft`), and
- annual site energy use intensity (`site_eui_kbtu_per_ft2`, kBtu/ft2, the ENERGY STAR convention).

Each attribute contributes a log-ratio, ``ln(x_i / x_target)``, so a building twice as large and one half
as large are equally far away and attributes with very different units are comparable. The distance is

    d_i = sqrt( sum_j w_j * ln(x_ij / x_j,target)^2 )

The single closest building (`k=1`) is the *one-shot* profile; the `k` closest buildings are the sample
that a *scaled* or *composite* profile averages and then scales to the target floor area.

Hard constraints (fuels, district energy, ...) are applied before matching with
`BuildingCharacteristics.apply()`; this module only ranks what is left.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .building_condition import KWH_TO_KBTU, _find_column

SITE_ENERGY_COLUMN = "out.site_energy.total.energy_consumption"
DISTANCE_COLUMN = "match_distance"
RANK_COLUMN = "match_rank"


def site_eui_kbtu_per_ft2(metadata: pd.DataFrame, sqft_column: str | None = None, energy_column: str = SITE_ENERGY_COLUMN) -> pd.Series:
    """Annual site EUI (kBtu/ft2) of every row; NaN where floor area or energy is missing or zero."""
    sqft_col = sqft_column or _find_column(metadata.columns, "in.sqft")
    energy_col = _find_column(metadata.columns, energy_column)
    if sqft_col is None or energy_col is None:
        raise ValueError(f"Could not find both a floor-area column and {energy_column!r} in metadata.")
    sqft = pd.to_numeric(metadata[sqft_col], errors="coerce").where(lambda s: s > 0)
    energy = pd.to_numeric(metadata[energy_col], errors="coerce")
    return (energy * KWH_TO_KBTU / sqft).replace([np.inf, -np.inf], np.nan)


# alias: `find_nearest_buildings` has a parameter with the same name as the public function
_eui = site_eui_kbtu_per_ft2


def find_nearest_buildings(
    metadata: pd.DataFrame,
    *,
    sqft: float | None = None,
    site_eui_kbtu_per_ft2: float | None = None,
    k: int = 1,
    targets: dict[str, float] | None = None,
    floor: float = 0.01,
    weights: dict[str, float] | None = None,
    sqft_column: str | None = None,
    energy_column: str = SITE_ENERGY_COLUMN,
) -> pd.DataFrame:
    """Return the `k` rows of `metadata` closest to the target building, nearest first.

    Args:
        metadata: candidate buildings, already filtered to the building type(s), location and constraints.
        sqft: target floor area (ft2). Omit for dwelling-unit products (ResStock), whose rows are units.
        site_eui_kbtu_per_ft2: target annual site EUI (kBtu/ft2), e.g. from utility bills or ENERGY STAR.
            Use a year other than the evaluation year when the result is later compared with the same meters.
        k: number of buildings to return (1 = one-shot). Capped at the number of valid candidates.
        targets: further attributes to match, as {metadata column: target value}, e.g. a natural-gas share of
            site energy ``{"gas_share": 0.05}``. Matched with the same log-ratio as the built-in attributes.
        floor: values of `targets` (and their candidates) below this are raised to it, so that shares near zero
            stay finite (default 0.01).
        weights: per-attribute weights, keys ``"sqft"``, ``"site_eui"`` and the `targets` columns (default 1.0).
        sqft_column: floor-area column; auto-detected (``in.sqft`` family) if not given.
        energy_column: annual site-energy column used for EUI; a ``..<unit>`` suffix is tolerated.

    Returns:
        A copy of the selected rows with `match_distance` and `match_rank` (1 = closest) columns added.

    Raises:
        ValueError: if no target attribute is given, `k` < 1, or no candidate has the needed attributes.
    """
    if sqft is None and site_eui_kbtu_per_ft2 is None and not targets:
        raise ValueError("Give at least one target attribute: sqft, site_eui_kbtu_per_ft2 and/or targets.")
    if k < 1:
        raise ValueError("k must be >= 1.")
    if metadata.empty:
        raise ValueError("Cannot match against empty metadata.")
    w = {"sqft": 1.0, "site_eui": 1.0, **dict.fromkeys(targets or {}, 1.0), **(weights or {})}

    sq_col = sqft_column or _find_column(metadata.columns, "in.sqft")
    terms: list[pd.Series] = []
    if sqft is not None:
        if sqft <= 0:
            raise ValueError("sqft must be positive.")
        if sq_col is None:
            raise ValueError("Could not find a floor-area column (in.sqft*) to match sqft against.")
        area = pd.to_numeric(metadata[sq_col], errors="coerce").where(lambda s: s > 0)
        terms.append(w["sqft"] * np.log(area / sqft) ** 2)
    if site_eui_kbtu_per_ft2 is not None:
        if site_eui_kbtu_per_ft2 <= 0:
            raise ValueError("site_eui_kbtu_per_ft2 must be positive.")
        eui = _eui(metadata, sq_col, energy_column)
        terms.append(w["site_eui"] * np.log(eui.where(eui > 0) / site_eui_kbtu_per_ft2) ** 2)
    for column, target in (targets or {}).items():
        if column not in metadata.columns:
            raise ValueError(f"Target column {column!r} is not in metadata.")
        values = pd.to_numeric(metadata[column], errors="coerce").clip(lower=floor)
        terms.append(w[column] * np.log(values / max(target, floor)) ** 2)

    distance = np.sqrt(sum(terms))
    ranked = metadata.assign(**{DISTANCE_COLUMN: distance}).dropna(subset=[DISTANCE_COLUMN])
    if ranked.empty:
        raise ValueError("No candidate building has valid values for the requested target attributes.")
    ranked = ranked.sort_values(DISTANCE_COLUMN, kind="stable").head(k)
    return ranked.assign(**{RANK_COLUMN: range(1, len(ranked) + 1)})


def stack_upgrade_states(
    metadata_by_upgrade: dict[int | str, pd.DataFrame],
    *,
    baseline_upgrade: int | str = 0,
    applicable_only: bool = True,
    bldg_id_column: str = "bldg_id",
) -> pd.DataFrame:
    """Combine baseline and upgrade metadata into one candidate pool of (building, upgrade) states.

    Real buildings are not all in the ComStock baseline condition: many have had LED lighting, controls,
    new windows or boilers. Matching against every applicable upgrade state of every sampled building lets
    `find_nearest_buildings()` pick, for example, "office 1234 with LED lighting" when that state is closer to
    the building's bills than any baseline building.

    Args:
        metadata_by_upgrade: {upgrade id: metadata} for the baseline and each candidate upgrade, already filtered
            to the same buildings (type, location, constraints). Constraints should be judged on the baseline.
        baseline_upgrade: the key of the baseline entry; its rows are always kept.
        applicable_only: drop upgrade rows whose ``applicability`` column is false (the measure did not apply,
            so the row repeats the baseline).
        bldg_id_column: the building identifier column.

    Returns:
        One frame with an ``upgrade`` column (the dictionary key) and a ``state_id`` column
        (``"<bldg_id>-<upgrade>"``) that identifies each candidate; duplicate rows per state are dropped.
    """
    frames = []
    for upgrade, frame in metadata_by_upgrade.items():
        f = frame.drop_duplicates(bldg_id_column)
        if applicable_only and str(upgrade) != str(baseline_upgrade) and "applicability" in f.columns:
            f = f[f["applicability"].astype(str).str.lower().isin(["true", "1", "1.0"])]
        frames.append(f.assign(upgrade=str(upgrade)))
    if not frames:
        raise ValueError("metadata_by_upgrade is empty.")
    stacked = pd.concat(frames, ignore_index=True)
    return stacked.assign(state_id=stacked[bldg_id_column].astype(str) + "-" + stacked["upgrade"])


__all__ = ["DISTANCE_COLUMN", "RANK_COLUMN", "find_nearest_buildings", "site_eui_kbtu_per_ft2", "stack_upgrade_states"]
