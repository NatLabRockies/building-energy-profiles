"""Export BuildStock time series as Modelica-readable ".mos" boundary-condition files.

Modelica's ASCII table format (used by `Modelica.Blocks.Sources.CombiTimeTable` and throughout the IBPSA/
Buildings libraries for weather files and other time-varying boundary conditions) looks like:

```
#1
#<free-form comment lines>
double tab1(<nrows>,<ncolumns>)
<time_0> <col1_0> <col2_0> ...
<time_1> <col1_1> <col2_1> ...
...
```

- The file must start with the literal line `#1` (the MOS table format version marker).
- Any number of `#`-prefixed comment lines may follow.
- Each table is declared as `<type> <name>(<rows>,<columns>)` (we always use `double`).
- Data rows are whitespace-separated numbers, one row per line, `<columns>` values per row. The first
  column is time in seconds, strictly increasing, and (by Modelica convention) starting at 0.

This module treats "thermal loads" as heating/cooling *end-use energy consumption* (the sum of every
fuel's heating or cooling energy input for the composite building, converted from energy-per-interval to
average power), not a delivered zone/coil load -- BuildStock's published time series report end-use energy
consumption, not raw thermal loads, so this is the closest available proxy. That approximation is called
out explicitly in both the API response and the file's own header comments.
"""

from __future__ import annotations

import pandas as pd


class MosExportError(ValueError):
    """Raised when a composite time series can't be converted to a thermal-load .mos file."""


def _interval_hours(timestamps: pd.Series) -> float:
    """Infer the (assumed-constant) interval length, in hours, from a sorted timestamp series."""
    if len(timestamps) < 2:
        raise MosExportError("Need at least 2 time steps to infer the data interval.")
    diffs = timestamps.diff().dropna().dt.total_seconds()
    median_seconds = diffs.median()
    if not median_seconds or median_seconds <= 0:
        raise MosExportError("Could not infer a positive, regular time interval from the time series.")
    # The energy-per-interval -> average-power conversion assumes every row spans the same interval, so a
    # single outlier gap (e.g. missing time steps) would silently skew the whole export -- reject anything
    # that isn't uniform to within a second.
    if (diffs - median_seconds).abs().max() > 1.0:
        raise MosExportError("Time series does not have a regular time interval (gaps or irregular spacing detected).")
    return float(median_seconds) / 3600.0


def _energy_columns_to_average_power_kw(data_frame: pd.DataFrame, columns: list[str], interval_hours: float) -> pd.Series:
    """Sum `columns` (energy per interval, in kWh) and convert to average power over the interval, in kW."""
    missing = [column for column in columns if column not in data_frame.columns]
    if missing:
        raise MosExportError(f"Columns not present in the composite time series: {missing}")
    total_energy_kwh = data_frame[columns].astype(float).sum(axis=1)
    return total_energy_kwh / interval_hours


def build_thermal_load_mos(
    data_frame: pd.DataFrame,
    heating_columns: list[str],
    cooling_columns: list[str],
    timestamp_column: str = "timestamp",
    table_name: str = "tab1",
    title: str = "BuildStock composite thermal loads",
    extra_comments: list[str] | None = None,
) -> str:
    """Build a Modelica ".mos" ASCII table with columns `[time_s, heating_load_W, cooling_load_W]`.

    `data_frame` is a combined/composite time series (e.g. from `combine_composite_time_series()` or
    `pull_composite_time_series()`) with a datetime `timestamp_column` and one or more heating/cooling
    end-use energy-consumption columns (in kWh per interval). Each of `heating_columns`/`cooling_columns`
    is summed across fuels, converted from energy-per-interval to average power over that interval (in
    Watts), and written as one column. Time is written in seconds, starting at 0 at the first timestamp.

    `extra_comments`, if given, are written as additional "#WARNING: ..."-prefixed lines right after the
    title -- e.g. a data-quality warning that a sqft-mode target square footage falls outside the observed
    range of the underlying BuildStock sample (see `api.services._sqft_bounds_warning`).

    Raises `MosExportError` if the data frame is empty, the timestamp interval isn't regular, or any
    requested column is missing.
    """
    if data_frame.empty:
        raise MosExportError("Cannot export an empty time series to .mos.")
    if timestamp_column not in data_frame.columns:
        raise MosExportError(f"'{timestamp_column}' column not present in the composite time series.")
    if not heating_columns and not cooling_columns:
        raise MosExportError("At least one heating or cooling column must be provided.")

    sorted_frame = data_frame.sort_values(timestamp_column).reset_index(drop=True)
    timestamps = pd.to_datetime(sorted_frame[timestamp_column])
    interval_hours = _interval_hours(timestamps)

    heating_kw = (
        _energy_columns_to_average_power_kw(sorted_frame, heating_columns, interval_hours)
        if heating_columns
        else pd.Series(0.0, index=sorted_frame.index)
    )
    cooling_kw = (
        _energy_columns_to_average_power_kw(sorted_frame, cooling_columns, interval_hours)
        if cooling_columns
        else pd.Series(0.0, index=sorted_frame.index)
    )

    time_seconds = (timestamps - timestamps.iloc[0]).dt.total_seconds()
    heating_w = heating_kw * 1000.0
    cooling_w = cooling_kw * 1000.0

    n_rows = len(sorted_frame)
    n_columns = 3

    lines = [
        "#1",
        f"#{title}",
        *(f"#WARNING: {comment}" for comment in (extra_comments or [])),
        "#Column 1: time (s), starting at 0 at the first time step",
        "#Column 2: heating end-use energy consumption, converted to average power (W)",
        "#Column 3: cooling end-use energy consumption, converted to average power (W)",
        "#NOTE: these are HVAC end-use energy-consumption proxies from BuildStock published time series,",
        "#not directly-simulated zone/coil thermal loads -- treat as an approximation.",
        f"double {table_name}({n_rows},{n_columns})",
    ]
    lines.extend(f"{t:.1f} {h:.3f} {c:.3f}" for t, h, c in zip(time_seconds.tolist(), heating_w.tolist(), cooling_w.tolist()))
    return "\n".join(lines) + "\n"
