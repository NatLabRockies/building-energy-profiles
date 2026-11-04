"""Issue profiles: what a real building's utility bills say about its record.

Placing a building's bills against BuildStock (the simulated stock) and against its own history turns a
benchmarking record into a short list of *issue profiles* -- recognizable signatures with likely causes,
such as a probably vacant building, a missing meter, a misclassified property type, electrification or a
retrofit. Each flag is a screening hint for a data steward, not a verified cause.

Two families of checks:

- **Pool checks** (`pool_profiles`): the building's annual EUI per fuel is placed in the distribution of
  its candidate BuildStock pool (same type, location, metered-fuel constraints and floor-area band, e.g. from
  `BuildingCharacteristics.apply_with_relaxation`). Use bills from the BuildStock weather year (AMY2018), or
  later bills divided by a peer-cohort index (`cohort_index`).
- **Multi-year checks** (`multi_year_profiles`): each year is compared with the building's own baseline year
  after dividing by the median change of its peers (`cohort_index`), which removes what every building in the
  city shared (weather, COVID-19, rates). No BuildStock data is needed for these.

Bills are monthly energy in kBtu per fuel (`bills_to_kbtu` converts electricity from kWh). Thresholds are
module constants chosen on 141 metered buildings in Washington, DC (validation V10-V12) and can be changed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .building_condition import KWH_TO_KBTU, _find_column

FUELS = ("electricity", "natural_gas", "district_heating", "district_cooling")
WINTER_MONTHS = (12, 1, 2)

# ---- thresholds (see module docstring) ----
LOW_PCT, HIGH_PCT = 5.0, 95.0  # pool percentile limits
PARTIAL_OTHER_MIN_RATIO = 0.6  # the other fuel must be at least 0.6x its pool median for "partial meter coverage"
MISCLASS_REPORTED_Z, MISCLASS_BEST_Z, MISCLASS_RATIO = 2.0, 1.5, 0.6
MIN_GAS_SHARE = 0.05  # gas checks only when gas was >= 5 % of site energy in the baseline year
MONTH_GAP_FRACTION = 0.2  # a month below 20 % of the median month is a gap
STABLE_BAND = (0.8, 1.25)
ONE_YEAR_RATIO, AGREE_RATIO, STEP_RATIO = 2.0, 1.3, 1.4
BASELINE_DIFF_RATIO = 1.4
COVERAGE_RATIO, RISE_RATIO, DECLINE_RATIO = 2.5, 1.3, 0.85
ELECTRIFICATION_GAIN = 0.1  # electricity gained / gas lost
PARTIAL_RATIO = 0.4  # the low fuel's ratio to its pool median is below 0.4x the other fuel's
SHAPE_CHANGE_PCT = 25.0


@dataclass(frozen=True)
class IssueProfileInfo:
    """Catalog entry: what the profile looks like, what usually causes it, and what to ask for next."""

    name: str
    category: str  # "data", "metering", "building change", "plausibility"
    signature: str
    likely_causes: str
    next_data: str


CATALOG: dict[str, IssueProfileInfo] = {
    p.name: p
    for p in (
        IssueProfileInfo(
            "low use",
            "plausibility",
            "Site EUI below the 5th percentile of the BuildStock pool",
            "Vacancy or partial occupancy; floor area overstated; a meter missing",
            "Occupancy / vacancy rate; floor area source; list of meters",
        ),
        IssueProfileInfo(
            "high use",
            "plausibility",
            "Site EUI above the 95th percentile of the BuildStock pool",
            "24/7 operation; loads BuildStock does not model (data center, lab, parking garage); campus; floor area understated",
            "Property uses incl. parking and data center (ENERGY STAR Portfolio Manager); operating hours; floor area",
        ),
        IssueProfileInfo(
            "partial meter coverage",
            "metering",
            "One fuel far below the pool while the other is typical",
            "Tenant meters not aggregated; a fuel not reported",
            "Metered areas (whole building vs common area); tenant / aggregated utility data",
        ),
        IssueProfileInfo(
            "possible misclassification",
            "plausibility",
            "Bills fit another building type's pool far better than the reported type",
            "Property type wrong or a mixed-use building reported as one type",
            "Property use breakdown (ENERGY STAR Portfolio Manager)",
        ),
        IssueProfileInfo(
            "profile shape outside envelope",
            "plausibility",
            "Most monthly shares outside the pool's 5-95 % band",
            "Systems or operations differ from the simulated stock (heating fuel, schedules)",
            "HVAC system and heating fuel; operating schedule",
        ),
        IssueProfileInfo(
            "one-year data anomaly",
            "data",
            "One year more than 2x away from both neighbouring years, which agree",
            "Billing or entry error; estimated bills; meter swapped",
            "Bills for that year; meter change log",
        ),
        IssueProfileInfo(
            "monthly bill gap",
            "data",
            "A month below 20 % of the median month",
            "Missing or estimated bill; meter read shifted",
            "Monthly bills / meter reads",
        ),
        IssueProfileInfo(
            "baseline differs from all later years",
            "data",
            "Every later year agrees, and all differ from the baseline year",
            "Bad baseline bills, or a lasting change right after the baseline",
            "Baseline-year bills; change log",
        ),
        IssueProfileInfo(
            "meter added",
            "metering",
            "A fuel that was absent appears and stays",
            "Meter added to the record; new fuel supply",
            "Meter list and start dates",
        ),
        IssueProfileInfo(
            "coverage expanded",
            "metering",
            "Use rises 2.5x or more and stays",
            "Meters or buildings added to the property; campus aggregation",
            "Property boundary and meter list by year",
        ),
        IssueProfileInfo(
            "gas meter dropped",
            "metering",
            "Gas falls to near zero with no electricity response",
            "Gas meter removed from the record; switch to district steam not reported",
            "Meter list; fuel supply",
        ),
        IssueProfileInfo(
            "electrification / fuel switch",
            "building change",
            "Gas falls while electricity holds or its winter share rises",
            "Heat pumps, electric water heating or kitchen; boiler replaced",
            "Equipment changes; permits",
        ),
        IssueProfileInfo(
            "persistent step down",
            "building change",
            "Electricity steps down by 1/1.4 or more and stays",
            "Vacancy, tenant loss, closure; boundary change",
            "Occupancy by year; property boundary",
        ),
        IssueProfileInfo(
            "steady improvement",
            "building change",
            "Use declines year after year to 0.8x or less",
            "Retrofits, operations improvement, building performance standard compliance",
            "Projects completed; BPS pathway",
        ),
        IssueProfileInfo(
            "load added / intensification",
            "building change",
            "Use rises to 1.3x or more and stays",
            "New tenant or process load; longer hours; electrified loads",
            "Tenant and equipment changes",
        ),
        IssueProfileInfo(
            "seasonal shape change",
            "building change",
            "Monthly shape changes while annual use is steady",
            "Controls, setpoints or HVAC changed",
            "Controls / HVAC changes",
        ),
        IssueProfileInfo("stable", "none", "Moves with its peers", "", ""),
    )
}


@dataclass
class IssueFlag:
    """One issue profile found for a building, with the numbers behind it."""

    profile: str
    evidence: str
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def info(self) -> IssueProfileInfo:
        return CATALOG[self.profile]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.update(
            category=self.info.category, signature=self.info.signature, likely_causes=self.info.likely_causes, next_data=self.info.next_data
        )
        return d


# ------------------------------------------------------------------ bills
def bills_to_kbtu(monthly: pd.DataFrame, electricity_kwh_column: str = "electricity_kwh") -> pd.DataFrame:
    """Return a copy with an ``electricity`` column in kBtu from an electricity column in kWh."""
    out = monthly.copy()
    if electricity_kwh_column in out:
        out["electricity"] = pd.to_numeric(out[electricity_kwh_column], errors="coerce") * KWH_TO_KBTU
    return out


def annual_bills(monthly: pd.DataFrame, *, fuels: Sequence[str] = FUELS) -> pd.DataFrame:
    """Annual totals per fuel (kBtu) from monthly bills with ``year``, ``month`` and fuel columns (kBtu).

    Only years with 12 electricity months are kept. Adds ``site``, ``elec_winter_frac`` (Dec-Feb share of
    annual electricity), ``month_gap`` (any month below `MONTH_GAP_FRACTION` of the median month) and
    ``site_shape`` (12 monthly shares of annual site energy).
    """
    m = monthly.copy()
    for f in fuels:
        if f not in m:
            m[f] = np.nan
    rows = []
    for year, grp in m.groupby("year"):
        d = grp.groupby("month")[list(fuels)].sum(min_count=1).reindex(range(1, 13))
        if d["electricity"].notna().sum() < 12:
            continue
        d = d.fillna(0.0)
        site = d.sum(axis=1)
        e = d["electricity"]
        rows.append(
            {
                "year": int(year),
                **{f: float(d[f].sum()) for f in fuels},
                "site": float(site.sum()),
                "elec_winter_frac": float(e[list(WINTER_MONTHS)].sum() / max(e.sum(), 1e-9)),
                "month_gap": bool((e < MONTH_GAP_FRACTION * e.median()).any() or (site < MONTH_GAP_FRACTION * site.median()).any()),
                "site_shape": (site / max(site.sum(), 1e-9)).to_numpy(),
            }
        )
    return pd.DataFrame(rows).set_index("year") if rows else pd.DataFrame()


def cohort_index(
    annual: pd.DataFrame,
    *,
    building_col: str,
    group_col: str,
    baseline_year: int = 2018,
    fuels: Sequence[str] = ("electricity", "natural_gas", "site"),
    min_n: int = 5,
) -> pd.DataFrame:
    """Median ratio of each year's use to the baseline year, per peer group and fuel.

    `annual` is long format: one row per building and year with `building_col`, `group_col`, ``year`` and
    fuel columns. Ratios outside 1/3-3 are ignored; groups with fewer than `min_n` buildings fall back to the
    median over all groups. Returns columns group, year, fuel, index, n.
    """
    base = annual[annual.year == baseline_year].set_index(building_col)
    out = []
    for (g, y), grp in annual.groupby([group_col, "year"]):
        d = grp[grp[building_col].isin(base.index)]
        for f in fuels:
            b0 = base.loc[d[building_col], f].to_numpy(float)
            v = d[f].to_numpy(float)
            ok = (b0 > 0) & (v > 0)
            r = v[ok] / b0[ok]
            r = r[(r > 1 / 3) & (r < 3)]
            out.append(
                {
                    "group": g,
                    "year": int(y),
                    "fuel": f,
                    "index": float(np.median(r)) if len(r) >= min_n else np.nan,
                    "n": len(r),
                    "_ratios": r.tolist(),
                }
            )
    ci = pd.DataFrame(out)
    if ci.empty:
        return ci
    pooled = ci.explode("_ratios")
    pooled["_ratios"] = pd.to_numeric(pooled["_ratios"], errors="coerce")
    allg = pooled.groupby(["year", "fuel"])["_ratios"].median().rename("all").reset_index()
    ci = ci.drop(columns="_ratios").merge(allg, on=["year", "fuel"])
    ci["index"] = ci["index"].fillna(ci.pop("all"))
    return ci


def _index_lookup(index: pd.DataFrame | Mapping | None, group: str | None):
    if index is None:
        return lambda _year, _fuel: 1.0
    if isinstance(index, pd.DataFrame):
        d = index if group is None or "group" not in index else index[index.group == group]
        table = {(int(r.year), r.fuel): float(r["index"]) for _, r in d.iterrows()}
    else:
        table = dict(index)
    return lambda year, fuel: table.get((int(year), fuel), 1.0) or 1.0


# ------------------------------------------------------------------ multi-year
def residuals(
    annual: pd.DataFrame, *, baseline_year: int = 2018, index: pd.DataFrame | Mapping | None = None, group: str | None = None
) -> pd.DataFrame:
    """Use in each year relative to `baseline_year`, divided by the peer-cohort index (1.0 = moved with peers)."""
    if baseline_year not in annual.index:
        raise ValueError(f"baseline year {baseline_year} has no complete bills")
    look = _index_lookup(index, group)
    b0 = annual.loc[baseline_year]
    res = pd.DataFrame(index=annual.index)
    for f in ("electricity", "natural_gas", "site"):
        res[f] = [(annual.loc[y, f] / b0[f] if b0[f] > 0 else np.nan) / look(y, f) for y in annual.index]
    return res


def multi_year_profiles(
    annual: pd.DataFrame, *, baseline_year: int = 2018, index: pd.DataFrame | Mapping | None = None, group: str | None = None
) -> list[IssueFlag]:
    """Issue profiles from a building's own history (needs the baseline year and at least two later years)."""
    annual = annual.sort_index()
    res = residuals(annual, baseline_year=baseline_year, index=index, group=group)
    later = annual[annual.index > baseline_year]
    if len(later) < 2:
        return []
    flags: list[IssueFlag] = []
    b0 = annual.loc[baseline_year]
    gas_share0 = b0.natural_gas / b0.site if b0.site else 0.0
    fuels_checked = ["electricity"] + (["natural_gas"] if gas_share0 >= MIN_GAS_SHARE else [])
    last2 = res[res.index >= res.index.max() - 1]
    lg = lambda f: np.log(res[f].clip(lower=1e-3)).to_numpy()  # noqa: E731

    bad_years: set[int] = set()
    for f in fuels_checked:
        x = lg(f)
        for i in range(1, len(x) - 1):
            if abs(x[i - 1] - x[i + 1]) < np.log(AGREE_RATIO) and abs(x[i] - (x[i - 1] + x[i + 1]) / 2) > np.log(ONE_YEAR_RATIO):
                flags.append(
                    IssueFlag(
                        "one-year data anomaly",
                        f"{f} in {res.index[i]} is {np.exp(x[i]):.2f}x vs neighbours {np.exp(x[i - 1]):.2f}x / {np.exp(x[i + 1]):.2f}x",
                        {"year": float(res.index[i])},
                    )
                )
                bad_years.add(int(res.index[i]))
                break
    # trend and step checks ignore a year already explained as a one-year anomaly
    res_c = res.drop(index=list(bad_years))
    last2 = res_c[res_c.index >= res_c.index.max() - 1]
    if annual.month_gap.any():
        yrs = [int(y) for y in annual.index[annual.month_gap]]
        flags.append(IssueFlag("monthly bill gap", f"month below {MONTH_GAP_FRACTION:.0%} of the median month in {yrs}"))
    for f in [*fuels_checked, "site"]:
        x = lg(f)[1:]
        if len(x) >= 3 and np.ptp(x) < np.log(AGREE_RATIO) and abs(x.mean()) > np.log(BASELINE_DIFF_RATIO):
            flags.append(
                IssueFlag(
                    "baseline differs from all later years",
                    f"{f} in every later year ≈ {np.exp(x.mean()):.2f}x {baseline_year}",
                    {"ratio": float(np.exp(x.mean()))},
                )
            )
            break
    for f in ("natural_gas", "district_heating", "district_cooling"):
        if b0[f] <= 0.02 * b0.site and (later[f] > np.maximum(0.05 * later.site, 3 * b0[f])).sum() >= 2:
            flags.append(
                IssueFlag(
                    "meter added",
                    f"{f} {b0[f] / max(b0.site, 1):.1%} of site in {baseline_year}, "
                    f"{later[f].iloc[-1] / max(later.site.iloc[-1], 1):.1%} in {later.index[-1]}",
                )
            )
            break
    if gas_share0 >= MIN_GAS_SHARE:
        g_last = float(res.natural_gas[res.index >= res.index.max() - 1].mean())
        ew = later.tail(2).elec_winter_frac.mean() - b0.elec_winter_frac
        # energy balance: electric heat replacing gas adds at least ~10 % of the lost gas energy as electricity
        # (heat-pump COP up to ~4 with losses), or shifts electricity toward winter
        elec_gain = (float(res.electricity[res.index >= res.index.max() - 1].mean()) - 1) * b0.electricity
        gas_loss = (1 - g_last) * b0.natural_gas
        elec_ratio_last2 = float(res.electricity[res.index >= res.index.max() - 1].mean())
        elec_up = (elec_gain >= ELECTRIFICATION_GAIN * gas_loss and elec_ratio_last2 >= 1.03) or ew >= 0.03
        m = {
            "gas_ratio": g_last,
            "elec_ratio": float(last2.electricity.mean()),
            "winter_share_change": float(ew),
            "elec_gain_over_gas_loss": float(elec_gain / max(gas_loss, 1e-9)),
        }
        if g_last < 0.1 and not elec_up:
            flags.append(IssueFlag("gas meter dropped", f"gas {g_last:.2f}x {baseline_year}, electricity unchanged", m))
        elif g_last < 0.5 and elec_up:
            flags.append(
                IssueFlag(
                    "electrification / fuel switch",
                    f"gas {g_last:.2f}x, electricity {last2.electricity.mean():.2f}x, winter electricity share {ew:+.1%}",
                    m,
                )
            )
    le = np.log(res_c.electricity.clip(lower=1e-3)).to_numpy()
    for i in range(1, len(le)):
        after = le[i:]
        if len(after) < 2 or np.ptp(after) > np.log(AGREE_RATIO):
            continue
        de = after.mean() - le[:i].mean()
        if de < -np.log(STEP_RATIO):
            flags.append(
                IssueFlag(
                    "persistent step down", f"electricity {np.exp(de):.2f}x from {res_c.index[i]} on", {"year": float(res_c.index[i])}
                )
            )
            break
    s = res_c.site.to_numpy()
    if len(s) >= 4 and np.ptp(s) > 0 and not any(f.profile == "persistent step down" for f in flags):
        rho = float(np.corrcoef(pd.Series(s).rank(), pd.Series(res_c.index).rank())[0, 1])
        if last2.site.mean() <= DECLINE_RATIO and rho <= -0.7:
            flags.append(
                IssueFlag("steady improvement", f"site {last2.site.mean():.2f}x, rank trend {rho:.2f}", {"ratio": float(last2.site.mean())})
            )
    if last2.site.mean() >= COVERAGE_RATIO or last2.electricity.mean() >= COVERAGE_RATIO:
        flags.append(IssueFlag("coverage expanded", f"site {last2.site.mean():.2f}x, electricity {last2.electricity.mean():.2f}x"))
    elif last2.site.mean() >= RISE_RATIO:
        flags.append(IssueFlag("load added / intensification", f"site {last2.site.mean():.2f}x", {"ratio": float(last2.site.mean())}))
    sh0, shl = np.asarray(annual.loc[baseline_year, "site_shape"]), np.asarray(annual.iloc[-1]["site_shape"])
    shape_change = float(np.sqrt(np.mean((shl - sh0) ** 2)) * 12 * 100)
    if shape_change > SHAPE_CHANGE_PCT and STABLE_BAND[0] <= res.site.iloc[-1] <= STABLE_BAND[1] and not annual.month_gap.any():
        flags.append(
            IssueFlag(
                "seasonal shape change",
                f"monthly shares changed {shape_change:.0f} % (RMS / mean share)",
                {"shape_change_pct": shape_change},
            )
        )
    return _explain_away(flags) or [IssueFlag("stable", "moved with its peers")]


# a profile listed here makes the profiles it maps to redundant (they are consequences of it)
EXPLAINS = {
    "baseline differs from all later years": {
        "load added / intensification",
        "coverage expanded",
        "persistent step down",
        "steady improvement",
    },
    "meter added": {"load added / intensification", "coverage expanded", "baseline differs from all later years"},
    "gas meter dropped": {"steady improvement"},
    "electrification / fuel switch": {"steady improvement"},
    "coverage expanded": {"load added / intensification"},
}


def _explain_away(flags: list[IssueFlag]) -> list[IssueFlag]:
    names = {f.profile for f in flags}
    drop: set[str] = set().union(*(EXPLAINS.get(n, set()) for n in names)) if names else set()
    return [f for f in flags if f.profile not in drop]


# ------------------------------------------------------------------ pool checks
def pool_euis(metadata: pd.DataFrame, sqft_column: str | None = None) -> pd.DataFrame:
    """Annual EUI (kBtu/ft2) per fuel and site for each pool building (BuildStock metadata, kWh outputs)."""
    sqft_col = sqft_column or _find_column(metadata.columns, "in.sqft")
    if sqft_col is None:
        raise ValueError("no floor-area column in metadata")
    sqft = pd.to_numeric(metadata[sqft_col], errors="coerce").where(lambda s: s > 0)
    out = pd.DataFrame(index=metadata.index)
    for f in (*FUELS, "fuel_oil", "propane"):
        col = _find_column(metadata.columns, f"out.{f}.total.energy_consumption")
        out[f] = pd.to_numeric(metadata[col], errors="coerce").fillna(0) * KWH_TO_KBTU / sqft if col else 0.0
    out["site"] = out.sum(axis=1)
    return out.dropna()


def _robust_z(value: float, values: np.ndarray) -> float:
    q1, med, q3 = np.nanpercentile(values, [25, 50, 75])
    return (value - med) / max((q3 - q1) / 1.349, 1e-3)


SHAPE_FEATURES = ("elec_summer", "elec_base", "gas_winter")


def shape_features(electricity: Sequence[float], natural_gas: Sequence[float] | None = None) -> dict[str, float]:
    """Monthly-shape features from 12 monthly values: summer (Jun-Sep) and minimum-month electricity relative to its
    mean, and winter (Dec-Feb) gas relative to its mean (gas only if present)."""
    e = np.asarray(electricity, float)
    out: dict[str, float] = {}
    if e.mean() > 0:
        out["elec_summer"] = float(e[5:9].mean() / e.mean())
        out["elec_base"] = float(e.min() / e.mean())
    if natural_gas is not None:
        g = np.asarray(natural_gas, float)
        if g.mean() > 0:
            out["gas_winter"] = float(g[[11, 0, 1]].mean() / g.mean())
    return out


def type_fit(bill_eui: Mapping[str, float], pool: pd.DataFrame, bill_shape: Mapping[str, float] | None = None) -> float:
    """RMS robust z-distance of a building's features from a pool.

    Annual features: ln site EUI, ln electricity EUI and gas share. If `bill_shape` (see `shape_features`) is given
    and the pool has the same columns, the monthly-shape features are added -- they separate types with similar
    annual use (offices, hotels, multifamily) much better (validation V12).
    """
    eps = 1e-3
    feats = {
        "ln_site": (np.log(max(bill_eui["site"], eps)), np.log(pool.site.clip(lower=eps))),
        "ln_elec": (np.log(max(bill_eui["electricity"], eps)), np.log(pool.electricity.clip(lower=eps))),
        "gas_share": (bill_eui.get("natural_gas", 0) / max(bill_eui["site"], eps), pool.natural_gas / pool.site.clip(lower=eps)),
    }
    for k, v in (bill_shape or {}).items():
        if k in pool and pool[k].notna().sum() >= 5:
            feats[k] = (v, pool[k].dropna())
    z = [_robust_z(v, np.asarray(p, float)) for v, p in feats.values()]
    return float(np.sqrt(np.mean(np.square(z))))


def pool_profiles(
    annual_kbtu: Mapping[str, float],
    gfa_ft2: float,
    pool: pd.DataFrame,
    *,
    reported_type: str | None = None,
    type_pools: Mapping[str, pd.DataFrame] | None = None,
    bill_shape: Mapping[str, float] | None = None,
) -> tuple[list[IssueFlag], dict[str, float]]:
    """Plausibility flags for one year of bills placed in a BuildStock pool.

    Args:
        annual_kbtu: annual use per fuel in kBtu (``electricity``, ``natural_gas``, ``district_heating``, ``district_cooling``).
        gfa_ft2: the building's gross floor area.
        pool: per-building EUIs of the candidate pool (`pool_euis` of the constrained metadata sample).
        reported_type: the building's reported type (key into `type_pools`), for the misclassification check.
        type_pools: pools of every candidate type ({type: `pool_euis(...)`}) for the misclassification check.
        bill_shape: optional monthly-shape features of the bills (`shape_features`); used when the type pools carry them.

    Returns:
        (flags, metrics) where metrics holds the pool percentiles and type-fit distances.
    """
    eui = {f: float(annual_kbtu.get(f, 0.0)) / gfa_ft2 for f in FUELS}
    eui["site"] = sum(eui.values())
    pct = {f"pct_{f}": float((pool[f] < eui[f]).mean() * 100) for f in ("site", "electricity", "natural_gas")}
    metrics: dict[str, float] = {**pct, "site_eui": eui["site"], "pool_site_p50": float(pool.site.median()), "pool_n": float(len(pool))}
    flags: list[IssueFlag] = []
    has_gas = (
        eui["natural_gas"] > 0.01 * eui["site"]
        or float(pool.natural_gas.median()) > 0.01 * float(pool.site.median())
    )
    pe, pg = pct["pct_electricity"], pct["pct_natural_gas"]
    re_ = eui["electricity"] / max(float(pool.electricity.median()), 1e-9)
    rg = eui["natural_gas"] / max(float(pool.natural_gas.median()), 1e-9)
    # one fuel low against the pool AND against the building's own other fuel (a vacant building is low in both)
    if has_gas and min(pe, pg) < LOW_PCT and min(re_, rg) < PARTIAL_RATIO * max(re_, rg) and max(re_, rg) >= PARTIAL_OTHER_MIN_RATIO:
        low = "electricity" if re_ < rg else "natural gas"
        flags.append(
            IssueFlag(
                "partial meter coverage",
                f"{low} {min(re_, rg):.2f}x the pool median while the other fuel is {max(re_, rg):.2f}x",
                {**pct, "elec_ratio": re_, "gas_ratio": rg},
            )
        )
    if pct["pct_site"] < LOW_PCT:
        flags.append(
            IssueFlag(
                "low use",
                f"site EUI {eui['site']:.0f} kBtu/ft² is at the {pct['pct_site']:.0f}th percentile (pool median {metrics['pool_site_p50']:.0f})",
                pct,
            )
        )
    if pct["pct_site"] > HIGH_PCT:
        flags.append(
            IssueFlag(
                "high use",
                f"site EUI {eui['site']:.0f} kBtu/ft² is at the {pct['pct_site']:.0f}th percentile (pool median {metrics['pool_site_p50']:.0f})",
                pct,
            )
        )
    if type_pools and reported_type in type_pools and len(type_pools[reported_type]) >= 5:
        fits = {t: type_fit(eui, p, bill_shape) for t, p in type_pools.items() if len(p) >= 5}
        best = min(fits, key=fits.get)
        metrics.update({f"fit_{t}": v for t, v in fits.items()})
        r = fits[reported_type]
        if best != reported_type and r > MISCLASS_REPORTED_Z and fits[best] < MISCLASS_BEST_Z and fits[best] < MISCLASS_RATIO * r:
            flags.append(
                IssueFlag(
                    "possible misclassification",
                    f"fits {best} (z {fits[best]:.1f}) far better than {reported_type} (z {r:.1f})",
                    {"fit_best": fits[best], "fit_reported": r},
                )
            )
    return flags, metrics


def shape_outside_envelope(bill_shares: Sequence[float], pool_shares: np.ndarray, *, min_months: int = 6) -> tuple[bool, int]:
    """True if at least `min_months` of the 12 monthly shares fall outside the pool's 5-95 % band."""
    lo, hi = np.percentile(np.asarray(pool_shares, float), [5, 95], axis=0)
    b = np.asarray(bill_shares, float)
    n = int(((b < lo) | (b > hi)).sum())
    return n >= min_months, n
