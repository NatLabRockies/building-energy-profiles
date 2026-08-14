"""Tests for the FastAPI app (api/main.py).

`test_app_registers_expected_routes` and the offline-endpoint tests are fast unit tests (no network).
The remaining tests exercise real endpoints end-to-end against real ComStock data and are marked
`@pytest.mark.integration`, matching the rest of this repo's test suite.
"""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import api.main as main_module
from api.config import Settings
from api.main import app
from building_energy_profiles.comstock import ComStockProcessor


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # `api.main.settings` is built once at import time from env vars, so route handlers close over that
    # module-level name -- replacing it here (rather than setting an env var after import) is what
    # actually reaches the request handlers, redirecting the download cache to a throwaway tmp_path.
    monkeypatch.setattr(main_module, "settings", Settings(cache_dir=tmp_path, default_state="DE", cors_origins=["http://localhost:4200"]))
    return TestClient(app)


class TestAppRoutes:
    @pytest.mark.unit
    def test_app_registers_expected_routes(self) -> None:
        paths = {route.path for route in app.routes if hasattr(route, "path")}

        assert {
            "/api/health",
            "/api/energy-star-types",
            "/api/composite/resolve",
            "/api/composite/building-distribution",
            "/api/composite/filter-options",
            "/api/metadata/summary",
            "/api/timeseries/composite",
            "/api/measures",
            "/api/locations/states",
            "/api/locations/counties",
            "/api/measures/compare",
            "/api/export/mos",
            "/api/composite/model-download",
        }.issubset(paths)

    @pytest.mark.unit
    def test_health(self, client: TestClient) -> None:
        response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.unit
    def test_get_energy_star_types(self, client: TestClient) -> None:
        response = client.get("/api/energy-star-types")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 84
        assert any(item["energy_star_property_type"] == "Bank Branch" for item in body)

    @pytest.mark.unit
    def test_composite_resolve(self, client: TestClient) -> None:
        response = client.post(
            "/api/composite/resolve",
            json={"components": [{"energy_star_property_type": "Zoo", "fraction": 1.0}]},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["unmapped"] == ["Zoo"]
        assert body["resolvable"] == []

    @pytest.mark.unit
    def test_composite_resolve_rejects_empty_components(self, client: TestClient) -> None:
        response = client.post("/api/composite/resolve", json={"components": []})

        assert response.status_code == 422

    @pytest.mark.unit
    def test_composite_resolve_rejects_out_of_range_fraction(self, client: TestClient) -> None:
        response = client.post(
            "/api/composite/resolve",
            json={"components": [{"energy_star_property_type": "Bank Branch", "fraction": 1.5}]},
        )

        assert response.status_code == 422

    @pytest.mark.unit
    def test_measures_rejects_unknown_product(self, client: TestClient) -> None:
        response = client.get("/api/measures", params={"product": "not-a-product"})

        assert response.status_code == 422

    @pytest.mark.unit
    def test_model_download_redirects_to_comstock_url(self, client: TestClient) -> None:
        response = client.get(
            "/api/composite/model-download",
            params={"product": "comstock", "bldg_id": 1, "upgrade": "0"},
            follow_redirects=False,
        )

        assert response.status_code in (302, 307)
        assert response.headers["location"].endswith("building_energy_models/upgrade=00/bldg0000001-up00.osm.gz")

    @pytest.mark.unit
    def test_model_download_redirects_to_resstock_url(self, client: TestClient) -> None:
        response = client.get(
            "/api/composite/model-download",
            params={"product": "resstock", "bldg_id": 1, "upgrade": "5"},
            follow_redirects=False,
        )

        assert response.status_code in (302, 307)
        # ResStock's upgrade folder isn't zero-padded, unlike the "-up05" filename suffix.
        assert response.headers["location"].endswith("building_energy_models/upgrade=5/bldg0000001-up05.zip")

    @pytest.mark.unit
    def test_model_download_rejects_unknown_product(self, client: TestClient) -> None:
        response = client.get("/api/composite/model-download", params={"product": "not-a-product", "bldg_id": 1})

        assert response.status_code == 422

    @pytest.mark.unit
    def test_model_download_rejects_non_positive_bldg_id(self, client: TestClient) -> None:
        response = client.get("/api/composite/model-download", params={"product": "comstock", "bldg_id": 0})

        assert response.status_code == 422


class TestAppEndpointsIntegration:
    """Real-network tests against a small state (DE) -- mirrors the rest of the repo's integration tests."""

    @pytest.mark.integration
    def test_composite_resolve_sqft_mode_with_state_auto_selects_bldg_id(self, client: TestClient) -> None:
        response = client.post(
            "/api/composite/resolve",
            json={
                "components": [{"energy_star_property_type": "Office", "sqft": 45_000}],
                "state": "DE",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["resolvable"][0]["bldg_id"] is not None
        assert body["components"][0]["bldg_id"] == body["resolvable"][0]["bldg_id"]

    @pytest.mark.integration
    def test_building_distribution_single_component(self, client: TestClient) -> None:
        response = client.post(
            "/api/composite/building-distribution",
            json={
                "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0}],
                "state": "DE",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert len(body["distributions"]) == 1
        distribution = body["distributions"][0]
        assert distribution["building_type"] == "SmallOffice"
        assert distribution["sample_size"] > 0
        assert len(distribution["points"]) > 0
        assert set(distribution["percentile_buildings"]) == {"p5", "p25", "median", "p75", "p95", "mean"}
        # Points are sorted ascending by value -- percentile markers should follow the same order.
        p5 = distribution["percentile_buildings"]["p5"]["value"]
        p95 = distribution["percentile_buildings"]["p95"]["value"]
        assert p5 <= p95

    @pytest.mark.integration
    def test_building_distribution_composite_mix(self, client: TestClient) -> None:
        response = client.post(
            "/api/composite/building-distribution",
            json={
                "components": [
                    {"product": "comstock", "building_type": "SmallOffice", "fraction": 0.7},
                    {"product": "comstock", "building_type": "RetailStandalone", "fraction": 0.3},
                ],
                "state": "DE",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert {d["building_type"] for d in body["distributions"]} == {"SmallOffice", "RetailStandalone"}

    @pytest.mark.integration
    def test_filter_options_lists_curated_columns_with_value_counts(self, client: TestClient) -> None:
        response = client.post(
            "/api/composite/filter-options",
            json={
                "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0}],
                "state": "DE",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        component = body["components"][0]
        assert component["building_type"] == "SmallOffice"
        columns_by_name = {c["column"]: c for c in component["columns"]}
        assert "in.vintage" in columns_by_name
        assert columns_by_name["in.vintage"]["display_name"] == "Vintage"
        assert len(columns_by_name["in.vintage"]["values"]) > 1
        assert all(v["count"] > 0 for v in columns_by_name["in.vintage"]["values"])

    @pytest.mark.integration
    def test_building_distribution_respects_component_filters(self, client: TestClient) -> None:
        # First, find a real vintage value actually present for this component.
        filter_response = client.post(
            "/api/composite/filter-options",
            json={
                "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0}],
                "state": "DE",
            },
        )
        vintage_values = filter_response.json()["components"][0]["columns"]
        vintage_column = next(c for c in vintage_values if c["column"] == "in.vintage")
        one_vintage = vintage_column["values"][0]["value"]
        expected_count = vintage_column["values"][0]["count"]

        response = client.post(
            "/api/composite/building-distribution",
            json={
                "components": [
                    {
                        "product": "comstock",
                        "building_type": "SmallOffice",
                        "fraction": 1.0,
                        "filters": {"in.vintage": [one_vintage]},
                    }
                ],
                "state": "DE",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["distributions"][0]["sample_size"] == expected_count

    @pytest.mark.integration
    def test_metadata_summary_single_component(self, client: TestClient) -> None:
        response = client.post(
            "/api/metadata/summary",
            json={
                "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0}],
                "state": "DE",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["weighted_building_count"] > 0
        assert body["weighted_annual_site_energy_kwh"] > 0
        assert len(body["by_fuel"]) > 0
        assert len(body["by_end_use"]) > 0
        # No bldg_id pinned -- selected-building fields stay unset/None.
        assert body["components"][0]["selected_bldg_id"] is None
        assert body["weighted_selected_building_site_eui_kbtu_per_ft2"] is None

    @pytest.mark.integration
    def test_metadata_summary_reports_selected_building_alongside_sample_average(self, client: TestClient) -> None:
        # First, pull a real bldg_id from this component's own distribution so the pin is guaranteed valid.
        distribution_response = client.post(
            "/api/composite/building-distribution",
            json={
                "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0}],
                "state": "DE",
            },
        )
        bldg_id = distribution_response.json()["distributions"][0]["percentile_buildings"]["p95"]["bldg_id"]

        response = client.post(
            "/api/metadata/summary",
            json={
                "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0, "bldg_id": bldg_id}],
                "state": "DE",
            },
        )

        assert response.status_code == 200
        body = response.json()
        component = body["components"][0]
        assert component["selected_bldg_id"] == bldg_id
        assert component["selected_site_eui_kbtu_per_ft2"] is not None
        # A single-component composite's selected-building weighted total should equal that one
        # component's own selected EUI (nothing else to average against).
        assert body["weighted_selected_building_site_eui_kbtu_per_ft2"] == pytest.approx(component["selected_site_eui_kbtu_per_ft2"])
        # The population-average EUI should generally differ from one specific (here, high-percentile)
        # building's own EUI -- this is the exact distinction the Dashboard needs to surface.
        assert component["site_eui_kbtu_per_ft2"] != pytest.approx(component["selected_site_eui_kbtu_per_ft2"])

    @pytest.mark.integration
    def test_metadata_summary_composite_mix(self, client: TestClient) -> None:
        response = client.post(
            "/api/metadata/summary",
            json={
                "components": [
                    {"product": "comstock", "building_type": "SmallOffice", "fraction": 0.7},
                    {"product": "comstock", "building_type": "RetailStandalone", "fraction": 0.3},
                ],
                "state": "DE",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body["components"]) == 2

    @pytest.mark.integration
    def test_metadata_summary_sqft_mode_scales_energy_but_not_eui(self, client: TestClient) -> None:
        """sqft mode should scale absolute floor area/energy to the entered square footage, while EUI
        (an intensity, kBtu/ft2) stays the same regardless of how much floor area was entered."""
        payload: dict[str, Any] = {
            "components": [
                {"product": "comstock", "building_type": "SmallOffice", "fraction": 0.67, "sqft": 40_000},
                {"product": "comstock", "building_type": "RetailStandalone", "fraction": 0.33, "sqft": 20_000},
            ],
            "state": "DE",
        }
        response = client.post("/api/metadata/summary", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["weighted_avg_sqft"] == pytest.approx(60_000)

        doubled = {
            "components": [{**c, "sqft": c["sqft"] * 2} for c in payload["components"]],
            "state": "DE",
        }
        response_doubled = client.post("/api/metadata/summary", json=doubled)
        assert response_doubled.status_code == 200
        body_doubled = response_doubled.json()

        assert body_doubled["weighted_avg_sqft"] == pytest.approx(120_000)
        assert body_doubled["weighted_annual_site_energy_kwh"] == pytest.approx(2 * body["weighted_annual_site_energy_kwh"], rel=1e-6)
        assert body_doubled["weighted_site_eui_kbtu_per_ft2"] == pytest.approx(body["weighted_site_eui_kbtu_per_ft2"], rel=1e-6)

    @pytest.mark.integration
    def test_metadata_summary_sqft_mode_warns_when_target_outside_observed_range(self, client: TestClient) -> None:
        """Entering a target square footage far outside what's actually sampled for that building type
        (e.g. a 1 sqft "office" nobody actually built at that size) should surface a clear out-of-bounds
        warning rather than silently extrapolating."""
        response = client.post(
            "/api/metadata/summary",
            json={
                "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0, "sqft": 1.0}],
                "state": "DE",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body["warnings"]) == 1
        assert "SmallOffice" in body["warnings"][0]
        assert "outside" in body["warnings"][0]

    @pytest.mark.integration
    def test_metadata_summary_sqft_mode_no_warning_within_observed_range(self, client: TestClient) -> None:
        """A target square footage matching an actual sampled building's size shouldn't warn."""
        fraction_response = client.post(
            "/api/metadata/summary",
            json={"components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0}], "state": "DE"},
        )
        avg_sqft = fraction_response.json()["components"][0]["avg_sqft"]

        response = client.post(
            "/api/metadata/summary",
            json={
                "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0, "sqft": avg_sqft}],
                "state": "DE",
            },
        )

        assert response.status_code == 200
        assert response.json()["warnings"] == []

    @pytest.mark.integration
    def test_timeseries_composite_hourly_returns_8760_rows(self, client: TestClient) -> None:
        response = client.post(
            "/api/timeseries/composite",
            json={
                "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0}],
                "state": "DE",
                "resample": "hourly",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["row_count"] == 8760
        first_series_row = body["series"][0]
        assert "out.electricity.total.energy_consumption" in first_series_row
        # Column names must survive intact (regression check for the itertuples() dotted-name bug).
        assert "_1" not in first_series_row

    @pytest.mark.integration
    def test_timeseries_composite_single_component_sqft_mode_scales_linearly(self, client: TestClient) -> None:
        payload: dict[str, Any] = {
            "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0, "sqft": 40_000}],
            "state": "DE",
            "resample": "hourly",
        }
        response = client.post("/api/timeseries/composite", json=payload)
        assert response.status_code == 200
        body = response.json()

        doubled = {**payload, "components": [{**payload["components"][0], "sqft": 80_000}]}
        response_doubled = client.post("/api/timeseries/composite", json=doubled)
        assert response_doubled.status_code == 200
        body_doubled = response_doubled.json()

        column = "out.electricity.total.energy_consumption"
        assert body_doubled["series"][0][column] == pytest.approx(2 * body["series"][0][column], rel=1e-6)

    @pytest.mark.integration
    def test_timeseries_composite_single_component_sqft_mode_warns_out_of_bounds(self, client: TestClient) -> None:
        response = client.post(
            "/api/timeseries/composite",
            json={
                "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0, "sqft": 1.0}],
                "state": "DE",
                "resample": "hourly",
            },
        )

        assert response.status_code == 200
        body = response.json()
        # An extreme (1 sqft) target triggers both the out-of-bounds warning and the scaling-note message
        # (the modeled building is nowhere near 1 sqft, so the scale factor is reported too).
        assert any("outside" in w and "SmallOffice" in w for w in body["warnings"])
        assert any("scaled by" in w and "SmallOffice" in w for w in body["warnings"])

    @pytest.mark.integration
    def test_timeseries_composite_multi_component_sqft_mode_scales_linearly(self, client: TestClient, tmp_path: Path) -> None:
        """Pin `bldg_ids` so both calls scale the *same* representative buildings -- otherwise a doubled
        target_sqft can (correctly) pick a different, better-matching building for the new size, breaking
        the linear-scaling invariant this test checks (see find_nearest_sqft_bldg_id())."""
        components: list[dict[str, Any]] = [
            {"product": "comstock", "building_type": "SmallOffice", "fraction": 0.67, "sqft": 40_000},
            {"product": "comstock", "building_type": "RetailStandalone", "fraction": 0.33, "sqft": 20_000},
        ]
        bldg_ids: dict[str, int] = {}
        for entry in components:
            processor = ComStockProcessor(
                state="DE", county_name="All", building_type=str(entry["building_type"]), upgrade="0", base_dir=tmp_path / "comstock"
            )
            metadata = processor.process_metadata(save_dir=processor.base_dir)
            bldg_ids[f"{entry['product']}:{entry['building_type']}"] = int(metadata["bldg_id"].iloc[0])

        payload: dict[str, Any] = {"components": components, "state": "DE", "resample": "hourly", "bldg_ids": bldg_ids}
        response = client.post("/api/timeseries/composite", json=payload)
        assert response.status_code == 200
        body = response.json()

        doubled = {**payload, "components": [{**c, "sqft": c["sqft"] * 2} for c in components]}
        response_doubled = client.post("/api/timeseries/composite", json=doubled)
        assert response_doubled.status_code == 200
        body_doubled = response_doubled.json()

        column = "out.electricity.total.energy_consumption"
        assert body_doubled["series"][0][column] == pytest.approx(2 * body["series"][0][column], rel=1e-6)

    @pytest.mark.integration
    def test_timeseries_composite_multi_component_sqft_mode_warns_out_of_bounds_for_one_component(self, client: TestClient) -> None:
        """Only the out-of-bounds component should generate the "outside the ... range" bounds warning -- a
        reasonably-sized component alongside it shouldn't (though either may still get a scaling note if
        its resolved building isn't an exact size match)."""
        response = client.post(
            "/api/timeseries/composite",
            json={
                "components": [
                    {"product": "comstock", "building_type": "SmallOffice", "fraction": 0.9, "sqft": 1.0},
                    {"product": "comstock", "building_type": "RetailStandalone", "fraction": 0.1, "sqft": 20_000},
                ],
                "state": "DE",
                "resample": "hourly",
            },
        )

        assert response.status_code == 200
        body = response.json()
        bounds_warnings = [w for w in body["warnings"] if "outside" in w]
        assert len(bounds_warnings) == 1
        assert "SmallOffice" in bounds_warnings[0]
        assert "RetailStandalone" not in bounds_warnings[0]

    @pytest.mark.integration
    def test_timeseries_composite_single_component_product_prefixed_upgrade_matches_bare(self, client: TestClient) -> None:
        """For a single-product composite, a product-prefixed upgrade (e.g. "comstock:1") should give the
        exact same result as the bare upgrade ("1") -- prefixing only changes behavior for mixed
        composites."""
        base_payload = {
            "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0}],
            "state": "DE",
            "resample": "hourly",
        }
        response_bare = client.post("/api/timeseries/composite", json={**base_payload, "upgrade": "1"})
        response_prefixed = client.post("/api/timeseries/composite", json={**base_payload, "upgrade": "comstock:1"})

        assert response_bare.status_code == 200
        assert response_prefixed.status_code == 200
        column = "out.electricity.total.energy_consumption"
        assert response_prefixed.json()["series"][0][column] == pytest.approx(response_bare.json()["series"][0][column], rel=1e-6)

    @pytest.mark.integration
    def test_timeseries_composite_mixed_product_prefixed_upgrade_isolates_target_component(self, client: TestClient) -> None:
        """A product-prefixed upgrade must only change the matching product's component's contribution to
        the combined series -- the other product's component should be pulled at baseline ("0") instead of
        also getting the same upgrade id applied to its own (unrelated) catalog."""
        payload = {
            "components": [
                {"product": "comstock", "building_type": "SmallOffice", "fraction": 0.5},
                {"product": "resstock", "building_type": "Single-Family Detached", "fraction": 0.5},
            ],
            "state": "DE",
            "resample": "hourly",
        }
        response_prefixed = client.post("/api/timeseries/composite", json={**payload, "upgrade": "comstock:1"})
        response_bare = client.post("/api/timeseries/composite", json={**payload, "upgrade": "1"})

        assert response_prefixed.status_code == 200
        assert response_bare.status_code == 200
        # Natural gas -- the ResStock furnace measure ("upgrade 1") changes gas use, not electricity.
        column = "out.natural_gas.total.energy_consumption"
        # The bare (legacy) upgrade incorrectly also reapplies ResStock's own unrelated upgrade "1" to the
        # residential component, while the prefixed upgrade correctly leaves it at baseline -- so the two
        # combined series must differ somewhere across the year (comparing the annual sum is more robust
        # than any single hour, which could coincidentally match).
        prefixed_total = sum(row[column] for row in response_prefixed.json()["series"])
        bare_total = sum(row[column] for row in response_bare.json()["series"])
        assert prefixed_total != pytest.approx(bare_total)

    @pytest.mark.integration
    def test_measures_list(self, client: TestClient) -> None:
        response = client.get("/api/measures", params={"product": "comstock"})

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert any(m["id"] == "0" for m in body["measures"])
        assert all(m["product"] == "comstock" for m in body["measures"])

    @pytest.mark.integration
    def test_locations_states(self, client: TestClient) -> None:
        response = client.get("/api/locations/states", params={"product": "comstock"})

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["product"] == "comstock"
        assert "DE" in body["states"]

    @pytest.mark.integration
    def test_locations_counties(self, client: TestClient) -> None:
        response = client.get("/api/locations/counties", params={"product": "comstock", "state": "DE"})

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["state"] == "DE"
        assert "Kent County" in body["counties"]
        assert "All" in body["note"]

    @pytest.mark.integration
    def test_measures_compare(self, client: TestClient) -> None:
        response = client.post(
            "/api/measures/compare",
            json={
                "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0}],
                "state": "DE",
                "baseline_upgrade": "0",
                "comparison_upgrades": ["1"],
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert "out.site_energy.total.energy_consumption" in body["results"]

    @pytest.mark.integration
    def test_measures_compare_by_end_use_matches_result_totals(self, client: TestClient) -> None:
        """baseline_by_end_use/by_end_use should sum (roughly) to the same site energy totals already
        returned in `results`, since they're built from the same underlying per-component scale/upgrade
        logic -- just split out by end-use category instead of by requested column."""
        response = client.post(
            "/api/measures/compare",
            json={
                "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0}],
                "state": "DE",
                "baseline_upgrade": "0",
                "comparison_upgrades": ["1"],
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body["baseline_by_end_use"]) > 0
        selection = "1"
        assert selection in body["by_end_use"]
        assert len(body["by_end_use"][selection]) > 0
        # Every entry in both lists should be a real, non-negative annual energy value.
        for entry in body["baseline_by_end_use"] + body["by_end_use"][selection]:
            assert entry["annual_energy_kwh"] >= 0

    @pytest.mark.integration
    def test_measures_compare_by_end_use_isolates_mixed_composite_correctly(self, client: TestClient) -> None:
        """Like the annual `results`, a product-prefixed selection's by_end_use breakdown must reflect only
        that product's component changing -- the other product's end-use totals should match its own
        baseline exactly (they were never touched by this selection)."""
        payload = {
            "components": [
                {"product": "comstock", "building_type": "SmallOffice", "fraction": 0.5},
                {"product": "resstock", "building_type": "Single-Family Detached", "fraction": 0.5},
            ],
            "state": "DE",
            "baseline_upgrade": "0",
            "comparison_upgrades": ["comstock:1"],
        }
        response = client.post("/api/measures/compare", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert len(body["baseline_by_end_use"]) > 0
        assert len(body["by_end_use"]["comstock:1"]) > 0

    @pytest.mark.integration
    def test_measures_compare_single_component_prefixed_selection_matches_bare_selection(self, client: TestClient) -> None:
        """For a single-product composite, a product-prefixed selection (e.g. "comstock:1") should be
        equivalent to the legacy bare selection ("1") -- prefixing only changes behavior for mixed
        composites."""
        base_payload = {
            "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0}],
            "state": "DE",
            "baseline_upgrade": "0",
        }
        response_bare = client.post("/api/measures/compare", json={**base_payload, "comparison_upgrades": ["1"]})
        response_prefixed = client.post("/api/measures/compare", json={**base_payload, "comparison_upgrades": ["comstock:1"]})
        assert response_bare.status_code == 200
        assert response_prefixed.status_code == 200

        column = "out.site_energy.total.energy_consumption"
        bare = response_bare.json()["results"][column][0]
        prefixed = response_prefixed.json()["results"][column][0]
        assert bare["product"] is None
        assert prefixed["product"] == "comstock"
        assert bare["absolute_savings_kwh"] == pytest.approx(prefixed["absolute_savings_kwh"], rel=1e-6)

    @pytest.mark.integration
    def test_measures_compare_mixed_composite_prefixed_selection_isolates_target_product(self, client: TestClient) -> None:
        """A product-prefixed selection must only change the matching product's component -- the other
        product's component should stay at its own baseline for that comparison, rather than silently
        reapplying an unrelated upgrade that happens to share the same numeric id (e.g. ComStock upgrade
        "1" is an HVAC measure; ResStock upgrade "1" is an unrelated furnace measure)."""
        payload = {
            "components": [
                {"product": "comstock", "building_type": "SmallOffice", "fraction": 0.5},
                {"product": "resstock", "building_type": "Single-Family Detached", "fraction": 0.5},
            ],
            "state": "DE",
            "baseline_upgrade": "0",
        }
        response_prefixed = client.post("/api/measures/compare", json={**payload, "comparison_upgrades": ["comstock:1"]})
        response_bare = client.post("/api/measures/compare", json={**payload, "comparison_upgrades": ["1"]})
        assert response_prefixed.status_code == 200
        assert response_bare.status_code == 200

        column = "out.site_energy.total.energy_consumption"
        prefixed = response_prefixed.json()["results"][column][0]
        bare = response_bare.json()["results"][column][0]
        assert prefixed["product"] == "comstock"
        assert bare["product"] is None
        # The bare (legacy) selection incorrectly also reapplies ResStock's own unrelated upgrade "1" to
        # the residential component, while the prefixed selection correctly leaves it at baseline -- so
        # they must differ.
        assert prefixed["absolute_savings_kwh"] != pytest.approx(bare["absolute_savings_kwh"])

    @pytest.mark.integration
    def test_measures_compare_sqft_mode_scales_linearly(self, client: TestClient) -> None:
        payload: dict[str, Any] = {
            "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0, "sqft": 50_000}],
            "state": "DE",
            "baseline_upgrade": "0",
            "comparison_upgrades": ["1"],
        }
        response = client.post("/api/measures/compare", json=payload)
        assert response.status_code == 200
        body = response.json()

        doubled = {**payload, "components": [{**payload["components"][0], "sqft": 100_000}]}
        response_doubled = client.post("/api/measures/compare", json=doubled)
        assert response_doubled.status_code == 200
        body_doubled = response_doubled.json()

        column = "out.site_energy.total.energy_consumption"
        baseline = body["results"][column][0]["baseline_kwh"]
        baseline_doubled = body_doubled["results"][column][0]["baseline_kwh"]
        assert baseline_doubled == pytest.approx(2 * baseline, rel=1e-6)

    @pytest.mark.integration
    def test_measures_compare_sqft_mode_warns_out_of_bounds(self, client: TestClient) -> None:
        response = client.post(
            "/api/measures/compare",
            json={
                "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0, "sqft": 1.0}],
                "state": "DE",
                "baseline_upgrade": "0",
                "comparison_upgrades": ["1"],
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body["warnings"]) == 1
        assert "SmallOffice" in body["warnings"][0]

    @pytest.mark.integration
    def test_export_mos_returns_downloadable_file(self, client: TestClient) -> None:
        response = client.post(
            "/api/export/mos",
            json={
                "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0}],
                "state": "DE",
            },
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert "attachment" in response.headers["content-disposition"]
        lines = response.text.splitlines()
        assert lines[0] == "#1"
        assert lines[7].startswith("double tab1(")

    @pytest.mark.integration
    def test_export_mos_sqft_mode_notes_target_floor_area(self, client: TestClient) -> None:
        response = client.post(
            "/api/export/mos",
            json={
                "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0, "sqft": 40_000}],
                "state": "DE",
            },
        )

        assert response.status_code == 200
        lines = response.text.splitlines()
        assert "target floor area=40,000 sqft" in lines[1]
        # The matrix declaration line shifts down by however many "#WARNING:" comment lines were embedded
        # (e.g. if 40,000 sqft happens to be outside SmallOffice's observed sample range in this state).
        warning_line_count = sum(1 for line in lines if line.startswith("#WARNING:"))
        assert lines[7 + warning_line_count].startswith("double tab1(")

    @pytest.mark.integration
    def test_export_mos_sqft_mode_embeds_out_of_bounds_warning(self, client: TestClient) -> None:
        response = client.post(
            "/api/export/mos",
            json={
                "components": [{"product": "comstock", "building_type": "SmallOffice", "fraction": 1.0, "sqft": 1.0}],
                "state": "DE",
            },
        )

        assert response.status_code == 200
        lines = response.text.splitlines()
        warning_lines = [line for line in lines if line.startswith("#WARNING:")]
        # An extreme (1 sqft) target triggers both the out-of-bounds warning and the scaling-note message.
        assert any("outside" in line and "SmallOffice" in line for line in warning_lines)
        assert any("scaled by" in line and "SmallOffice" in line for line in warning_lines)
        # Each warning comment line pushes the matrix declaration further down.
        matrix_line_index = 7 + len(warning_lines)
        assert lines[matrix_line_index].startswith("double tab1(")

    @pytest.mark.integration
    def test_service_error_returns_400(self, client: TestClient) -> None:
        response = client.post(
            "/api/metadata/summary",
            json={
                "components": [{"product": "comstock", "building_type": "NotARealBuildingType", "fraction": 1.0}],
                "state": "DE",
            },
        )

        assert response.status_code == 400
        body = response.json()
        assert body["ok"] is False
        assert body["error_type"] == "ServiceError"
