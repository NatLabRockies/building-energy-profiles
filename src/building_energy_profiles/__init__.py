"""Download and analyze NLR BuildStock datasets."""

from ._base import BuildStockProcessor, BuildStockRelease, MetadataPartition
from .building_condition import (
    DEFAULT_BAND as BUILDING_CONDITION_DEFAULT_BAND,
)
from .building_condition import (
    BuildingConditionSelection,
    select_building_condition_sample,
)
from .characteristics import COOLING_TYPES, FUELS, BuildingCharacteristics
from .composite import (
    CompositeBuildingType,
    CompositeComponent,
    combine_composite_time_series,
    find_nearest_sqft_bldg_id,
    normalize_time_series_columns,
    pull_composite_time_series,
    pull_sized_time_series,
    resolve_fraction_weights,
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
    refine_building_type_for_sqft,
)
from .issue_profiles import CATALOG as ISSUE_PROFILE_CATALOG
from .issue_profiles import IssueFlag, IssueProfileInfo, annual_bills, cohort_index, multi_year_profiles, pool_euis, pool_profiles
from .location import list_available_counties, list_available_states
from .matching import find_nearest_buildings, site_eui_kbtu_per_ft2, stack_upgrade_states
from .portfolio import (
    CombinedMetric,
    ComponentEstimate,
    MetricStats,
    PortfolioComponent,
    PortfolioEnergyEstimate,
    estimate_portfolio_energy,
)
from .resstock import ResStockProcessor
from .timeseries import is_period_ending, resample_time_series, to_period_start

__all__ = [
    "BUILDING_CONDITION_DEFAULT_BAND",
    "COOLING_TYPES",
    "FUELS",
    "ISSUE_PROFILE_CATALOG",
    "BuildStock",
    "BuildStockCatalog",
    "BuildStockDataDictionary",
    "BuildStockProcessor",
    "BuildStockRelease",
    "BuildingCharacteristics",
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
    "IssueFlag",
    "IssueProfileInfo",
    "MeasureSavings",
    "MetadataPartition",
    "MetricStats",
    "PortfolioComponent",
    "PortfolioEnergyEstimate",
    "ResStockProcessor",
    "ResultVariable",
    "annual_bills",
    "cohort_index",
    "combine_composite_time_series",
    "compare_composite_measures",
    "data_dictionary",
    "energy_star_crosswalk",
    "energy_star_property_types_for_buildstock_type",
    "estimate_portfolio_energy",
    "find_nearest_buildings",
    "find_nearest_sqft_bldg_id",
    "is_period_ending",
    "list_available_counties",
    "list_available_states",
    "list_energy_star_property_types",
    "map_energy_star_property_type",
    "multi_year_profiles",
    "normalize_time_series_columns",
    "pool_euis",
    "pool_profiles",
    "pull_composite_time_series",
    "pull_sized_time_series",
    "refine_building_type_for_sqft",
    "resample_time_series",
    "resolve_fraction_weights",
    "result_variables_from_columns",
    "select_building_condition_sample",
    "site_eui_kbtu_per_ft2",
    "stack_upgrade_states",
    "summarize_composite_metadata",
    "to_period_start",
]
