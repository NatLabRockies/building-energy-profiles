"""Download and analyze NLR BuildStock datasets."""

from ._base import BuildStockProcessor, BuildStockRelease, MetadataPartition
from .composite import (
    CompositeBuildingType,
    CompositeComponent,
    combine_composite_time_series,
    normalize_time_series_columns,
    pull_composite_time_series,
)
from .comstock import ComStockProcessor
from .data_dictionary import (
    BuildStock,
    BuildStockCatalog,
    BuildStockDataDictionary,
    ResultVariable,
    data_dictionary,
    result_variables_from_columns,
)
from .energy_star_crosswalk import (
    EnergyStarMapping,
    energy_star_crosswalk,
    energy_star_property_types_for_buildstock_type,
    list_energy_star_property_types,
    map_energy_star_property_type,
)
from .portfolio import (
    CombinedMetric,
    ComponentEstimate,
    MetricStats,
    PortfolioComponent,
    PortfolioEnergyEstimate,
    estimate_portfolio_energy,
)
from .resstock import ResStockProcessor

__all__ = [
    "BuildStock",
    "BuildStockCatalog",
    "BuildStockDataDictionary",
    "BuildStockProcessor",
    "BuildStockRelease",
    "ComStockProcessor",
    "CombinedMetric",
    "ComponentEstimate",
    "CompositeBuildingType",
    "CompositeComponent",
    "EnergyStarMapping",
    "MetadataPartition",
    "MetricStats",
    "PortfolioComponent",
    "PortfolioEnergyEstimate",
    "ResStockProcessor",
    "ResultVariable",
    "combine_composite_time_series",
    "data_dictionary",
    "energy_star_crosswalk",
    "energy_star_property_types_for_buildstock_type",
    "estimate_portfolio_energy",
    "list_energy_star_property_types",
    "map_energy_star_property_type",
    "normalize_time_series_columns",
    "pull_composite_time_series",
    "result_variables_from_columns",
]
