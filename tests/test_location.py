"""Unit tests for list_available_states()/list_available_counties()."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from building_energy_profiles._base import BuildStockProcessor
from building_energy_profiles.comstock import ComStockProcessor
from building_energy_profiles.location import list_available_counties, list_available_states
from building_energy_profiles.resstock import ResStockProcessor


class TestListAvailableStates:
    def test_returns_sorted_states_from_processor(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        def fake_available_states(self: BuildStockProcessor) -> list[str]:
            return ["RI", "DE", "CA"]

        monkeypatch.setattr(BuildStockProcessor, "available_states", fake_available_states)

        result = list_available_states("comstock", save_dir=tmp_path)

        assert result == ["CA", "DE", "RI"]

    def test_uses_comstock_processor_for_comstock_product(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        seen: list[type] = []

        def fake_available_states(self: BuildStockProcessor) -> list[str]:
            seen.append(type(self))
            return ["DE"]

        monkeypatch.setattr(BuildStockProcessor, "available_states", fake_available_states)

        list_available_states("comstock", save_dir=tmp_path)

        assert seen == [ComStockProcessor]

    def test_uses_resstock_processor_for_resstock_product(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        seen: list[type] = []

        def fake_available_states(self: BuildStockProcessor) -> list[str]:
            seen.append(type(self))
            return ["DE"]

        monkeypatch.setattr(BuildStockProcessor, "available_states", fake_available_states)

        list_available_states("resstock", save_dir=tmp_path)

        assert seen == [ResStockProcessor]


class TestListAvailableCounties:
    def test_strips_state_prefix_and_sorts(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        metadata = pd.DataFrame(
            {
                "bldg_id": [1, 2, 3, 4],
                "in.county_name": ["DE, New Castle County", "DE, Kent County", "DE, Kent County", "DE, Sussex County"],
            }
        )

        def fake_process_metadata(self: BuildStockProcessor, save_dir: Path) -> pd.DataFrame:
            return metadata

        monkeypatch.setattr(BuildStockProcessor, "process_metadata", fake_process_metadata)

        result = list_available_counties("comstock", "DE", save_dir=tmp_path)

        assert result == ["Kent County", "New Castle County", "Sussex County"]

    def test_keeps_names_without_matching_state_prefix_as_is(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        metadata = pd.DataFrame({"bldg_id": [1], "in.county_name": ["Some Other Format"]})

        def fake_process_metadata(self: BuildStockProcessor, save_dir: Path) -> pd.DataFrame:
            return metadata

        monkeypatch.setattr(BuildStockProcessor, "process_metadata", fake_process_metadata)

        result = list_available_counties("comstock", "DE", save_dir=tmp_path)

        assert result == ["Some Other Format"]

    def test_empty_metadata_returns_empty_list(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        def fake_process_metadata(self: BuildStockProcessor, save_dir: Path) -> pd.DataFrame:
            return pd.DataFrame()

        monkeypatch.setattr(BuildStockProcessor, "process_metadata", fake_process_metadata)

        result = list_available_counties("comstock", "DE", save_dir=tmp_path)

        assert result == []

    def test_missing_county_name_column_returns_empty_list(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        metadata = pd.DataFrame({"bldg_id": [1, 2]})

        def fake_process_metadata(self: BuildStockProcessor, save_dir: Path) -> pd.DataFrame:
            return metadata

        monkeypatch.setattr(BuildStockProcessor, "process_metadata", fake_process_metadata)

        result = list_available_counties("comstock", "DE", save_dir=tmp_path)

        assert result == []

    def test_uses_resstock_processor_for_resstock_product(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        seen: list[type] = []
        metadata = pd.DataFrame({"bldg_id": [1], "in.county_name": ["DE, Kent County"]})

        def fake_process_metadata(self: BuildStockProcessor, save_dir: Path) -> pd.DataFrame:
            seen.append(type(self))
            return metadata

        monkeypatch.setattr(BuildStockProcessor, "process_metadata", fake_process_metadata)

        list_available_counties("resstock", "DE", save_dir=tmp_path)

        assert seen == [ResStockProcessor]
