"""Tests for issue-profile screening (synthetic bills with known faults)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from building_energy_profiles import issue_profiles as ip

YEARS = range(2018, 2023)
ELEC = np.array([10, 9, 9, 8, 9, 11, 12, 12, 10, 9, 9, 10], float) * 1000
GAS = np.array([20, 18, 14, 8, 4, 2, 2, 2, 3, 6, 12, 18], float) * 1000


def bills(elec_scale=None, gas_scale=None, mutate=None, years=YEARS):
    rows = []
    for y in years:
        e = ELEC * (elec_scale or {}).get(y, 1.0)
        g = GAS * (gas_scale or {}).get(y, 1.0)
        for mth in range(12):
            rows.append({"year": y, "month": mth + 1, "electricity": e[mth], "natural_gas": g[mth]})
    df = pd.DataFrame(rows)
    if mutate:
        mutate(df)
    return ip.annual_bills(df)


def names(flags):
    return {f.profile for f in flags}


def test_catalog_has_causes_for_every_profile():
    assert all(p.likely_causes for n, p in ip.CATALOG.items() if n != "stable")


def test_bills_to_kbtu():
    out = ip.bills_to_kbtu(pd.DataFrame({"electricity_kwh": [1000.0]}))
    assert out.electricity.iloc[0] == pytest.approx(3412.142, rel=1e-4)


def test_annual_bills_drops_incomplete_years():
    df = pd.DataFrame({"year": [2018] * 11, "month": range(1, 12), "electricity": 1.0})
    assert ip.annual_bills(df).empty


def test_stable():
    assert names(ip.multi_year_profiles(bills())) == {"stable"}


def test_peer_index_removes_shared_change():
    a = bills(elec_scale={2020: 0.7, 2021: 0.7, 2022: 0.7}, gas_scale={2020: 0.7, 2021: 0.7, 2022: 0.7})
    idx = {(y, f): (0.7 if y >= 2020 else 1.0) for y in YEARS for f in ("electricity", "natural_gas", "site")}
    assert "persistent step down" in names(ip.multi_year_profiles(a))
    assert names(ip.multi_year_profiles(a, index=idx)) == {"stable"}


def test_one_year_anomaly():
    assert "one-year data anomaly" in names(ip.multi_year_profiles(bills(elec_scale={2020: 0.3})))


def test_monthly_gap():
    def gap(df):
        df.loc[(df.year == 2019) & (df.month == 3), ["electricity", "natural_gas"]] = 1.0

    assert "monthly bill gap" in names(ip.multi_year_profiles(bills(mutate=gap)))


def test_baseline_differs():
    s = dict.fromkeys(range(2019, 2023), 1.6)
    assert "baseline differs from all later years" in names(ip.multi_year_profiles(bills(elec_scale=s, gas_scale=s)))


def test_meter_added():
    def no_gas_2018(df):
        df.loc[df.year == 2018, "natural_gas"] = 0.0

    assert "meter added" in names(ip.multi_year_profiles(bills(mutate=no_gas_2018)))


def test_gas_meter_dropped_vs_electrification():
    gone = {2021: 0.0, 2022: 0.0}
    assert "gas meter dropped" in names(ip.multi_year_profiles(bills(gas_scale=gone)))
    up = {2021: 1.4, 2022: 1.4}
    assert "electrification / fuel switch" in names(ip.multi_year_profiles(bills(gas_scale={2021: 0.2, 2022: 0.2}, elec_scale=up)))


def test_step_down_and_improvement():
    step = {2020: 0.5, 2021: 0.5, 2022: 0.5}
    assert "persistent step down" in names(ip.multi_year_profiles(bills(elec_scale=step, gas_scale=step)))
    trend = {2019: 0.93, 2020: 0.86, 2021: 0.8, 2022: 0.74}
    assert "steady improvement" in names(ip.multi_year_profiles(bills(elec_scale=trend, gas_scale=trend)))


def test_coverage_and_load_added():
    big = {2020: 3.0, 2021: 3.0, 2022: 3.0}
    assert "coverage expanded" in names(ip.multi_year_profiles(bills(elec_scale=big, gas_scale=big)))
    more = {2021: 1.4, 2022: 1.4}
    assert "load added / intensification" in names(ip.multi_year_profiles(bills(elec_scale=more, gas_scale=more)))


def test_seasonal_shape_change():
    def flatten_gas(df):
        df.loc[df.year == 2022, "natural_gas"] = GAS.sum() / 12

    assert "seasonal shape change" in names(ip.multi_year_profiles(bills(mutate=flatten_gas)))


def test_pre_baseline_years_are_ignored():
    early = {2016: 2.0, 2017: 2.0}
    a = bills(elec_scale=early, gas_scale=early, years=range(2016, 2023))
    assert names(ip.multi_year_profiles(a)) == {"stable"}


def test_cohort_index_fallback_pools_small_groups():
    rows = [
        {
            "b": b,
            "g": "A" if b < 3 else "B",
            "year": y,
            "electricity": 100.0 * (0.8 if y == 2020 else 1.0),
            "natural_gas": 10.0,
            "site": 110.0,
        }
        for b in range(6)
        for y in (2018, 2020)
    ]
    ci = ip.cohort_index(pd.DataFrame(rows), building_col="b", group_col="g")
    idx = ci[(ci.year == 2020) & (ci.fuel == "electricity")]["index"]
    assert idx.tolist() == pytest.approx([0.8, 0.8])  # each group has 3 < min_n, but 6 pooled ratios do


def test_cohort_index_median_and_fallback():
    rows = [
        {
            "b": b,
            "g": "A" if b < 6 else "B",
            "year": y,
            "electricity": 100.0 * (0.8 if y == 2020 else 1.0),
            "natural_gas": 10.0,
            "site": 110.0,
        }
        for b in range(8)
        for y in (2018, 2020)
    ]
    ci = ip.cohort_index(pd.DataFrame(rows), building_col="b", group_col="g")
    a = ci[(ci.group == "A") & (ci.year == 2020) & (ci.fuel == "electricity")]["index"].iloc[0]
    b = ci[(ci.group == "B") & (ci.year == 2020) & (ci.fuel == "electricity")]["index"].iloc[0]
    assert a == pytest.approx(0.8)
    assert b == pytest.approx(0.8)  # B has 2 buildings < min_n -> falls back to all-group median


def _pool(n=50, seed=0, elec=40.0, gas=20.0):
    rng = np.random.default_rng(seed)
    sq = rng.uniform(5e4, 2e5, n)
    md = pd.DataFrame(
        {
            "in.sqft..ft2": sq,
            "out.electricity.total.energy_consumption..kwh": rng.normal(elec, 4, n) * sq / ip.KWH_TO_KBTU,
            "out.natural_gas.total.energy_consumption..kwh": rng.normal(gas, 3, n) * sq / ip.KWH_TO_KBTU,
        }
    )
    return ip.pool_euis(md)


def test_pool_low_high_partial():
    pool = _pool()
    gfa = 1e5
    flags, m = ip.pool_profiles({"electricity": 40 * gfa, "natural_gas": 20 * gfa}, gfa, pool)
    assert flags == []
    assert 20 < m["pct_site"] < 80
    assert "low use" in names(ip.pool_profiles({"electricity": 15 * gfa, "natural_gas": 8 * gfa}, gfa, pool)[0])
    assert "high use" in names(ip.pool_profiles({"electricity": 80 * gfa, "natural_gas": 40 * gfa}, gfa, pool)[0])
    assert "partial meter coverage" in names(ip.pool_profiles({"electricity": 8 * gfa, "natural_gas": 20 * gfa}, gfa, pool)[0])


def test_partial_meter_when_gas_bills_are_missing():
    pool, gfa = _pool(), 1e5
    assert "partial meter coverage" in names(ip.pool_profiles({"electricity": 40 * gfa}, gfa, pool)[0])
    all_electric = _pool(gas=0.0)
    all_electric["natural_gas"] = 0.0
    assert "partial meter coverage" not in names(ip.pool_profiles({"electricity": 40 * gfa}, gfa, all_electric)[0])


def test_misclassification_skipped_for_small_pools():
    gfa = 1e5
    annual = {"electricity": 60 * gfa, "natural_gas": 40 * gfa}
    small_reported = {"Office": _pool(n=3, seed=1), "Hotel": _pool(elec=60, gas=40, seed=2)}
    flags, _ = ip.pool_profiles(annual, gfa, small_reported["Hotel"], reported_type="Office", type_pools=small_reported)
    assert "possible misclassification" not in names(flags)
    all_small = {"Office": _pool(n=3, seed=1), "Hotel": _pool(n=3, seed=2)}
    flags, m = ip.pool_profiles(annual, gfa, _pool(), reported_type="Office", type_pools=all_small)
    assert "possible misclassification" not in names(flags)
    assert not any(k.startswith("fit_") for k in m)


def test_misclassification():
    pools = {"Office": _pool(elec=40, gas=5, seed=1), "Hotel": _pool(elec=60, gas=40, seed=2)}
    gfa = 1e5
    flags, m = ip.pool_profiles(
        {"electricity": 60 * gfa, "natural_gas": 40 * gfa}, gfa, pools["Office"], reported_type="Office", type_pools=pools
    )
    assert "possible misclassification" in names(flags)
    assert m["fit_Hotel"] < m["fit_Office"]


def test_shape_envelope():
    rng = np.random.default_rng(3)
    pool = np.abs(rng.normal(1 / 12, 0.005, (100, 12)))
    pool = pool / pool.sum(axis=1, keepdims=True)
    out, n = ip.shape_outside_envelope(np.r_[np.full(6, 0.15), np.full(6, 0.0167)], pool)
    assert out
    assert n >= 6


def test_flag_to_dict_carries_catalog():
    d = ip.IssueFlag("low use", "x").to_dict()
    assert d["category"] == "plausibility"
    assert "Vacancy" in d["likely_causes"]
