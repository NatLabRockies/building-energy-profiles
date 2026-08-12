"""Download and analyze NLR BuildStock datasets."""

from ._base import BuildStockProcessor, BuildStockRelease, MetadataPartition
from .building_condition import (
    DEFAULT_BAND as BUILDING_CONDITION_DEFAULT_BAND,
)
from .building_condition import (
    BuildingConditionSelection,
    select_building_condition_sample,
)
from .composite import (
    CompositeBuildingType,
    CompositeComponent,
    combine_composite_time_series,
    find_nearest_sqft_bldg_id,
    normalize_time_series_columns,
    pull_composite_time_series,
)
from .composite_metadata import (
    ComponentMetadataSummary,
    CompositeMeasuresComparison,
    CompositeMetadataSummary,
    EndUseValue,
    MeasureSavings,
    compare_composite_measures,
    summarize_composite_metadata,
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
from .location import list_available_counties, list_available_states
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
    "BUILDING_CONDITION_DEFAULT_BAND",
    "BuildStock",
    "BuildStockCatalog",
    "BuildStockDataDictionary",
    "BuildStockProcessor",
    "BuildStockRelease",
    "BuildingConditionSelection",
    "ComStockProcessor",
    "CombinedMetric",
    "ComponentEstimate",
    "ComponentMetadataSummary",
    "CompositeBuildingType",
    "CompositeComponent",
    "CompositeMeasuresComparison",
    "CompositeMetadataSummary",
    "EndUseValue",
    "EnergyStarMapping",
    "MeasureSavings",
    "MetadataPartition",
    "MetricStats",
    "PortfolioComponent",
    "PortfolioEnergyEstimate",
    "ResStockProcessor",
    "ResultVariable",
    "combine_composite_time_series",
    "compare_composite_measures",
    "data_dictionary",
    "energy_star_crosswalk",
    "energy_star_property_types_for_buildstock_type",
    "estimate_portfolio_energy",
    "find_nearest_sqft_bldg_id",
    "list_available_counties",
    "list_available_states",
    "list_energy_star_property_types",
    "map_energy_star_property_type",
    "normalize_time_series_columns",
    "pull_composite_time_series",
    "result_variables_from_columns",
    "select_building_condition_sample",
    "summarize_composite_metadata",
]
