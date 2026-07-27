"""Fast access to packaged BuildStock metadata dictionaries.

The dictionary is intentionally stored as plain JSON alongside the package so
tools can parse it without importing Python, while this module exposes a small
Python-friendly API for interactive use.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from importlib import resources
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class ResultVariable:
    """A parsed annual result column and its unit metadata."""

    name: str
    unit: str | None
    source: str | None
    end_use: str | None
    metric: str | None

    @classmethod
    def from_name(cls, name: str) -> ResultVariable:
        """Parse a BuildStock-style output variable name."""
        unit = name.rsplit("..", 1)[1] if ".." in name else None
        base_name = name.split("..", 1)[0]
        parts = base_name.split(".")

        source = parts[1] if len(parts) > 1 else None
        end_use = parts[2] if len(parts) > 2 else None
        metric = ".".join(parts[3:]) if len(parts) > 3 else None
        return cls(name=name, unit=unit, source=source, end_use=end_use, metric=metric)


@dataclass(frozen=True)
class BuildStockDataDictionary:
    """Packaged metadata for one BuildStock product."""

    product: str
    default_release: str
    record_type: str
    building_type_column: str
    building_types: tuple[str, ...]
    result_variables: tuple[ResultVariable, ...]
    measure_upgrade_packages: Mapping[str, Mapping[str, str]]

    @property
    def result_variable_names(self) -> tuple[str, ...]:
        """Return just the result variable column names."""
        return tuple(variable.name for variable in self.result_variables)

    @property
    def result_units(self) -> tuple[str, ...]:
        """Return all non-empty units used by the product's result variables."""
        return tuple(sorted({variable.unit for variable in self.result_variables if variable.unit is not None}))

    def result_variables_by_unit(
        self, unit: str | None = None
    ) -> dict[str | None, tuple[ResultVariable, ...]] | tuple[ResultVariable, ...]:
        """Group result variables by unit, or return variables for a single unit."""
        grouped: dict[str | None, list[ResultVariable]] = {}
        for variable in self.result_variables:
            grouped.setdefault(variable.unit, []).append(variable)

        frozen = {key: tuple(values) for key, values in grouped.items()}
        if unit is not None:
            return frozen.get(unit, ())
        return frozen

    def upgrade_packages(self, release: str | None = None) -> Mapping[str, str]:
        """Return upgrade id -> package name for a release.

        If `release` is omitted, the product's default supported release is used.
        """
        selected_release = release or self.default_release
        try:
            return self.measure_upgrade_packages[selected_release]
        except KeyError as exc:
            supported = ", ".join(self.measure_upgrade_packages)
            raise ValueError(
                f"Unsupported {self.product} upgrade-package release '{selected_release}'. Supported releases are: {supported}."
            ) from exc


@dataclass(frozen=True)
class BuildStockCatalog:
    """Grouped access to all packaged BuildStock data dictionaries."""

    products: Mapping[str, BuildStockDataDictionary]

    def __getitem__(self, product_key: str) -> BuildStockDataDictionary:
        return self.products[product_key]

    @property
    def building_types(self) -> Mapping[str, tuple[str, ...]]:
        """Return product key -> building or housing type values."""
        return {key: dictionary.building_types for key, dictionary in self.products.items()}

    @property
    def result_variables(self) -> Mapping[str, tuple[ResultVariable, ...]]:
        """Return product key -> annual result variables."""
        return {key: dictionary.result_variables for key, dictionary in self.products.items()}

    @property
    def measure_upgrade_packages(self) -> Mapping[str, Mapping[str, Mapping[str, str]]]:
        """Return product key -> release -> upgrade id -> package name."""
        return {key: dictionary.measure_upgrade_packages for key, dictionary in self.products.items()}


def result_variables_from_columns(columns: Iterable[str]) -> tuple[ResultVariable, ...]:
    """Parse output variables from a metadata DataFrame's columns."""
    return tuple(ResultVariable.from_name(column) for column in columns if column.startswith("out."))


@cache
def _raw_data_dictionary() -> Mapping[str, Any]:
    data_path = resources.files("buildstock_processor").joinpath("data_dictionary.json")
    with data_path.open(encoding="utf-8") as file:
        loaded: dict[str, Any] = json.load(file)
    return MappingProxyType(loaded)


@cache
def data_dictionary(product_key: str) -> BuildStockDataDictionary:
    """Return the packaged data dictionary for `comstock` or `resstock`."""
    raw = _raw_data_dictionary()[product_key]
    return BuildStockDataDictionary(
        product=raw["product"],
        default_release=raw["default_release"],
        record_type=raw["record_type"],
        building_type_column=raw["building_type_column"],
        building_types=tuple(raw["building_types"]),
        result_variables=tuple(ResultVariable(**variable) for variable in raw["result_variables"]),
        measure_upgrade_packages=raw["measure_upgrade_packages"],
    )


BuildStock = BuildStockCatalog(
    products={
        "comstock": data_dictionary("comstock"),
        "resstock": data_dictionary("resstock"),
    }
)
