"""Time-series helpers shared by the package, the API, and the MCP server.

BuildStock (ComStock and ResStock) per-building time series are *period-ending*: a full 2018 year at
15-minute resolution runs from 2018-01-01 00:15 to 2019-01-01 00:00, where each timestamp labels the
interval that just ended. Resampling those timestamps directly to months or years puts the year's last
interval into a separate, nearly empty "2019-01" bucket and shifts every period boundary by one interval.
`to_period_start()` relabels each row by the start of its interval so calendar resampling is exact.
"""

from __future__ import annotations

import pandas as pd

RESAMPLE_FREQUENCIES: dict[str, str | None] = {
    "native": None,
    "hourly": "h",
    "daily": "D",
    "monthly": "MS",
    "annual": "YS",
}


def infer_interval(index: pd.DatetimeIndex) -> pd.Timedelta | None:
    """Most common spacing between consecutive timestamps (None if fewer than two)."""
    if len(index) < 2:
        return None
    deltas = pd.Series(index.sort_values()).diff().dropna()
    return deltas.mode().iloc[0] if not deltas.empty else None


def is_period_ending(index: pd.DatetimeIndex, interval: pd.Timedelta | None = None) -> bool:
    """True if `index` looks like BuildStock's period-ending convention: stepping back one interval from
    the first timestamp lands exactly on midnight January 1st (e.g. first stamp 00:15 at 15-minute data)."""
    interval = interval if interval is not None else infer_interval(index)
    if interval is None or len(index) == 0:
        return False
    start = index.min() - interval
    return bool(start == start.normalize() and start.month == 1 and start.day == 1)


def to_period_start(data_frame: pd.DataFrame, timestamp_column: str = "timestamp") -> pd.DataFrame:
    """Return a copy whose timestamps (column `timestamp_column`, or a DatetimeIndex) label interval starts.

    Frames that are already period-starting (or too short to tell) are returned unchanged."""
    uses_column = timestamp_column in data_frame.columns
    index = pd.DatetimeIndex(pd.to_datetime(data_frame[timestamp_column] if uses_column else data_frame.index))
    interval = infer_interval(index)
    if not is_period_ending(index, interval):
        return data_frame
    shifted = data_frame.copy()
    if uses_column:
        shifted[timestamp_column] = index - interval
    else:
        shifted.index = index - interval
    return shifted


def resample_time_series(
    data_frame: pd.DataFrame,
    resample: str,
    columns: list[str] | None = None,
    timestamp_column: str = "timestamp",
) -> pd.DataFrame:
    """Sum `columns` (default: every numeric column) to `resample` periods ("native", "hourly", "daily",
    "monthly", "annual"), after converting period-ending stamps to period starts. Returns a frame indexed by
    period start."""
    if resample not in RESAMPLE_FREQUENCIES:
        raise ValueError(f"resample must be one of: {', '.join(RESAMPLE_FREQUENCIES)}")
    frame = to_period_start(data_frame, timestamp_column)
    if timestamp_column in frame.columns:
        frame = frame.set_index(pd.DatetimeIndex(pd.to_datetime(frame[timestamp_column]))).drop(columns=[timestamp_column])
    selected = columns if columns is not None else list(frame.select_dtypes("number").columns)
    frame = frame[selected]
    freq = RESAMPLE_FREQUENCIES[resample]
    return frame if freq is None else frame.resample(freq).sum()
