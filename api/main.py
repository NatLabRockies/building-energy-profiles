"""FastAPI app for the composite building explorer: ENERGY STAR -> BuildStock composite building types,
metadata/time-series exploration, measure comparisons, and Modelica ".mos" thermal-load export.

Run locally with:

    uv run --group api uvicorn api.main:app --reload --port 8000

The Angular frontend in `webapp/` expects this to be reachable at `http://localhost:8000` by default (see
`webapp/src/environments/environment.ts`).
"""

from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from api import services
from api.config import Settings
from api.schemas import (
    AvailableCountiesResponse,
    AvailableStatesResponse,
    BuildingDistributionRequest,
    BuildingDistributionResponse,
    CompositeResolveRequest,
    CompositeResolveResponse,
    EnergyStarTypeInfo,
    FilterOptionsRequest,
    FilterOptionsResponse,
    MeasuresCompareRequest,
    MeasuresCompareResponse,
    MeasuresListResponse,
    MetadataSummaryRequest,
    MetadataSummaryResponse,
    MosExportRequest,
    TimeseriesRequest,
    TimeseriesResponse,
)
from api.services import ServiceError

settings = Settings.from_env()

app = FastAPI(
    title="BuildStock Composite Building Explorer API",
    description=(
        "Model a building as an ENERGY STAR property type (or a floor-area-weighted mix of several), "
        "explore its ComStock/ResStock annual metadata and time series, compare a handful of upgrade "
        "measures, and export thermal loads as a Modelica .mos file."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ServiceError)
def _handle_service_error(_request: object, exc: ServiceError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"ok": False, "error_type": "ServiceError", "error": str(exc)})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/energy-star-types", response_model=list[EnergyStarTypeInfo])
def get_energy_star_types() -> list[EnergyStarTypeInfo]:
    """List every packaged ENERGY STAR Portfolio Manager property type and its BuildStock crosswalk entry."""
    return services.list_energy_star_types()


@app.post("/api/composite/resolve", response_model=CompositeResolveResponse)
def post_composite_resolve(request: CompositeResolveRequest) -> CompositeResolveResponse:
    """Resolve one or more ENERGY STAR property types (+ floor-area fractions/sqft) to BuildStock building
    types, dropping/flagging any that don't map to a real ComStock/ResStock building type.

    In sqft mode, passing `state` also auto-selects a representative bldg_id per component (the real
    sampled building closest in floor area to its `sqft`), persisted onto the response's `resolvable` list
    so every downstream page (Dashboard/Timeseries/Measures) uses the same building consistently instead of
    each independently guessing one."""
    return services.resolve_composite(request, settings)


@app.post("/api/composite/building-distribution", response_model=BuildingDistributionResponse)
def post_composite_building_distribution(request: BuildingDistributionRequest) -> BuildingDistributionResponse:
    """For each composite component, compute a site-EUI distribution (histogram + smoothed density curve)
    across every sampled building of that type in this state/county, plus percentile/mean markers -- lets
    the frontend show a "PDF" chart and let a user pick a representative building either by clicking a
    point on the curve or via a quick percentile/mean shortcut, instead of always defaulting to the first
    building found (or the closest sqft match)."""
    return services.get_building_distributions(request, settings)


@app.post("/api/composite/filter-options", response_model=FilterOptionsResponse)
def post_composite_filter_options(request: FilterOptionsRequest) -> FilterOptionsResponse:
    """For each composite component, list curated metadata columns (vintage, HVAC type, stories, wall
    construction, etc. -- see `services.CURATED_FILTER_COLUMNS`) with their distinct values/counts in the
    current sample, so a caller can build a "narrow the population" filter UI without exposing all of
    BuildStock's raw `in.*` columns (mostly identifiers or too granular to be a useful filter)."""
    return services.get_filter_options(request, settings)


@app.post("/api/metadata/summary", response_model=MetadataSummaryResponse)
def post_metadata_summary(request: MetadataSummaryRequest) -> MetadataSummaryResponse:
    """Download annual metadata for each composite component and return a fraction-weighted energy/EUI/
    end-use summary suitable for dashboard cards and charts."""
    return services.get_metadata_summary(request, settings)


@app.post("/api/timeseries/composite", response_model=TimeseriesResponse)
def post_timeseries_composite(request: TimeseriesRequest) -> TimeseriesResponse:
    """Download and combine time series for the composite, returning an (optionally hourly-resampled)
    8760-style series suitable for a heat map or load duration curve."""
    return services.get_composite_timeseries(request, settings)


@app.get("/api/measures", response_model=MeasuresListResponse)
def get_measures(
    product: str = Query(..., pattern="^(comstock|resstock)$"),
    release: str | None = None,
) -> MeasuresListResponse:
    """List the upgrade packages ("measures") available for a product/release, to pick a handful from."""
    return services.list_measures(product, settings, release=release)


@app.get("/api/locations/states", response_model=AvailableStatesResponse)
def get_available_states(
    product: str = Query(..., pattern="^(comstock|resstock)$"),
    release: str | None = None,
) -> AvailableStatesResponse:
    """List every 2-letter state abbreviation with published metadata for a product/release, for a state
    dropdown."""
    return services.list_available_states(product, settings, release=release)


@app.get("/api/locations/counties", response_model=AvailableCountiesResponse)
def get_available_counties(
    product: str = Query(..., pattern="^(comstock|resstock)$"),
    state: str = Query(..., min_length=2, max_length=2),
    release: str | None = None,
) -> AvailableCountiesResponse:
    """List every distinct county name actually published for a state, for a county dropdown dependent on
    the selected state. Not every county is guaranteed to be represented -- see the response's `note`."""
    return services.list_available_counties(product, state.upper(), settings, release=release)


@app.post("/api/measures/compare", response_model=MeasuresCompareResponse)
def post_measures_compare(request: MeasuresCompareRequest) -> MeasuresCompareResponse:
    """Compare the composite's annual energy under a baseline upgrade vs. one or more comparison upgrades."""
    return services.compare_measures(request, settings)


@app.post("/api/export/mos")
def post_export_mos(request: MosExportRequest) -> PlainTextResponse:
    """Download the composite's heating/cooling end-use energy as a Modelica ".mos" boundary-condition
    file (see api/mos_export.py for the exact format and its "thermal load" caveat)."""
    mos_text, filename = services.export_mos(request, settings)
    return PlainTextResponse(
        content=mos_text,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
