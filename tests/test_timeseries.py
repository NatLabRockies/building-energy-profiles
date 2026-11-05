"""Unit tests for period-ending time series handling (no network)."""

import pandas as pd
import pytest

from building_energy_profiles import is_period_ending, resample_time_series, to_period_start


def _year(period_ending: bool = True, freq: str = "15min") -> pd.DataFrame:
    start = pd.Timestamp("2018-01-01") + (pd.Timedelta(freq) if period_ending else pd.Timedelta(0))
    index = pd.date_range(start, periods=35040 if freq == "15min" else 8760, freq=freq)
    return pd.DataFrame({"timestamp": index, "kwh": 1.0, "label": "x"})


def test_detects_buildstock_period_ending():
    assert is_period_ending(pd.DatetimeIndex(_year()["timestamp"]))
    assert not is_period_ending(pd.DatetimeIndex(_year(period_ending=False)["timestamp"]))


def test_to_period_start_shifts_one_interval():
    shifted = to_period_start(_year())
    assert shifted["timestamp"].iloc[0] == pd.Timestamp("2018-01-01 00:00")
    assert shifted["timestamp"].iloc[-1] == pd.Timestamp("2018-12-31 23:45")


def test_to_period_start_leaves_period_start_data_alone():
    frame = _year(period_ending=False)
    assert to_period_start(frame) is frame


@pytest.mark.parametrize(("resample", "periods"), [("monthly", 12), ("annual", 1), ("daily", 365), ("hourly", 8760)])
def test_resample_has_no_stub_period(resample, periods):
    result = resample_time_series(_year(), resample, ["kwh"])
    assert len(result) == periods
    assert result.index[0] == pd.Timestamp("2018-01-01")
    assert result["kwh"].sum() == pytest.approx(35040)


def test_monthly_totals_are_exact():
    result = resample_time_series(_year(), "monthly", ["kwh"])
    assert result["kwh"].iloc[0] == 31 * 96  # all of January, including the 00:00 Feb 1 period-ending stamp
    assert result["kwh"].iloc[-1] == 31 * 96


def test_hourly_input_and_datetime_index():
    frame = _year(freq="1h").set_index("timestamp")
    result = resample_time_series(frame, "monthly", ["kwh"])
    assert len(result) == 12
    assert result["kwh"].sum() == 8760


def test_default_columns_are_numeric_and_native_passthrough():
    result = resample_time_series(_year(), "native")
    assert list(result.columns) == ["kwh"]
    assert len(result) == 35040


def test_bad_resample_raises():
    with pytest.raises(ValueError, match="resample must be one of"):
        resample_time_series(_year(), "weekly")
