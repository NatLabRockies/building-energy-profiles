"""Unit tests for the Modelica .mos thermal-load export (api/mos_export.py). All synthetic data -- no
network calls.
"""

import pandas as pd
import pytest

from api.mos_export import MosExportError, build_thermal_load_mos


def _make_frame(periods: int = 4, freq: str = "15min") -> pd.DataFrame:
    timestamps = pd.date_range("2018-01-01", periods=periods, freq=freq)
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "out.electricity.heating.energy_consumption": 1.0,
            "out.natural_gas.heating.energy_consumption": 0.5,
            "out.electricity.cooling.energy_consumption": 0.25,
        }
    )


class TestBuildThermalLoadMos:
    @pytest.mark.unit
    def test_header_matches_mos_format(self):
        mos_text = build_thermal_load_mos(
            _make_frame(),
            heating_columns=["out.electricity.heating.energy_consumption", "out.natural_gas.heating.energy_consumption"],
            cooling_columns=["out.electricity.cooling.energy_consumption"],
        )
        lines = mos_text.splitlines()

        assert lines[0] == "#1"
        assert all(line.startswith("#") for line in lines[1:7])
        assert lines[7] == "double tab1(4,3)"

    @pytest.mark.unit
    def test_time_column_starts_at_zero_and_increments_by_interval_seconds(self):
        mos_text = build_thermal_load_mos(
            _make_frame(periods=4, freq="15min"),
            heating_columns=["out.electricity.heating.energy_consumption"],
            cooling_columns=["out.electricity.cooling.energy_consumption"],
        )
        data_rows = mos_text.splitlines()[8:]
        times = [float(row.split()[0]) for row in data_rows]

        assert times == [0.0, 900.0, 1800.0, 2700.0]

    @pytest.mark.unit
    def test_sums_multiple_heating_columns_and_converts_to_average_power_watts(self):
        # 15-minute interval => interval_hours = 0.25; heating = (1.0 + 0.5) kWh / 0.25 h = 6.0 kW = 6000 W
        mos_text = build_thermal_load_mos(
            _make_frame(periods=2, freq="15min"),
            heating_columns=["out.electricity.heating.energy_consumption", "out.natural_gas.heating.energy_consumption"],
            cooling_columns=["out.electricity.cooling.energy_consumption"],
        )
        first_row = mos_text.splitlines()[8].split()

        assert float(first_row[1]) == pytest.approx(6000.0)
        # cooling = 0.25 kWh / 0.25 h = 1.0 kW = 1000 W
        assert float(first_row[2]) == pytest.approx(1000.0)

    @pytest.mark.unit
    def test_hourly_interval_converts_correctly(self):
        # 1-hour interval => interval_hours = 1.0; heating = 1.0 kWh / 1 h = 1.0 kW = 1000 W
        mos_text = build_thermal_load_mos(
            _make_frame(periods=3, freq="1h"),
            heating_columns=["out.electricity.heating.energy_consumption"],
            cooling_columns=[],
        )
        first_row = mos_text.splitlines()[8].split()

        assert float(first_row[1]) == pytest.approx(1000.0)
        assert float(first_row[2]) == pytest.approx(0.0)

    @pytest.mark.unit
    def test_cooling_only_export_zeros_out_heating(self):
        mos_text = build_thermal_load_mos(
            _make_frame(periods=2),
            heating_columns=[],
            cooling_columns=["out.electricity.cooling.energy_consumption"],
        )
        first_row = mos_text.splitlines()[8].split()

        assert float(first_row[1]) == 0.0
        assert float(first_row[2]) > 0.0

    @pytest.mark.unit
    def test_empty_dataframe_raises(self):
        empty = pd.DataFrame(columns=["timestamp", "out.electricity.heating.energy_consumption"])
        with pytest.raises(MosExportError, match="empty"):
            build_thermal_load_mos(empty, heating_columns=["out.electricity.heating.energy_consumption"], cooling_columns=[])

    @pytest.mark.unit
    def test_missing_timestamp_column_raises(self):
        frame = _make_frame().drop(columns=["timestamp"])
        with pytest.raises(MosExportError, match="timestamp"):
            build_thermal_load_mos(frame, heating_columns=["out.electricity.heating.energy_consumption"], cooling_columns=[])

    @pytest.mark.unit
    def test_no_heating_or_cooling_columns_raises(self):
        with pytest.raises(MosExportError, match="heating or cooling"):
            build_thermal_load_mos(_make_frame(), heating_columns=[], cooling_columns=[])

    @pytest.mark.unit
    def test_missing_requested_column_raises(self):
        with pytest.raises(MosExportError, match="not present"):
            build_thermal_load_mos(_make_frame(), heating_columns=["out.does_not_exist"], cooling_columns=[])

    @pytest.mark.unit
    def test_irregular_interval_raises(self):
        frame = _make_frame(periods=3)
        # Make the interval between rows irregular.
        frame.loc[2, "timestamp"] = frame.loc[2, "timestamp"] + pd.Timedelta(hours=5)
        with pytest.raises(MosExportError, match="regular"):
            build_thermal_load_mos(frame, heating_columns=["out.electricity.heating.energy_consumption"], cooling_columns=[])

    @pytest.mark.unit
    def test_row_count_matches_declared_matrix_size(self):
        mos_text = build_thermal_load_mos(
            _make_frame(periods=10),
            heating_columns=["out.electricity.heating.energy_consumption"],
            cooling_columns=["out.electricity.cooling.energy_consumption"],
        )
        lines = mos_text.splitlines()
        data_rows = lines[8:]

        assert lines[7] == "double tab1(10,3)"
        assert len(data_rows) == 10
