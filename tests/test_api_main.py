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
            "/api/metadata/summary",
            "/api/timeseries/composite",
            "/api/measures",
            "/api/locations/states",
            "/api/locations/counties",
            "/api/measures/compare",
            "/api/export/mos",
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


class TestAppEndpointsIntegration:
    """Real-network tests against a small state (DE) -- mirrors the rest of the repo's integration tests."""

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
        assert len(body["warnings"]) == 1
        assert "SmallOffice" in body["warnings"][0]

    @pytest.mark.integration
    def test_timeseries_composite_multi_component_sqft_mode_scales_linearly(self, client: TestClient) -> None:
        payload: dict[str, Any] = {
            "components": [
                {"product": "comstock", "building_type": "SmallOffice", "fraction": 0.67, "sqft": 40_000},
                {"product": "comstock", "building_type": "RetailStandalone", "fraction": 0.33, "sqft": 20_000},
            ],
            "state": "DE",
            "resample": "hourly",
        }
        response = client.post("/api/timeseries/composite", json=payload)
        assert response.status_code == 200
        body = response.json()

        doubled = {**payload, "components": [{**c, "sqft": c["sqft"] * 2} for c in payload["components"]]}
        response_doubled = client.post("/api/timeseries/composite", json=doubled)
        assert response_doubled.status_code == 200
        body_doubled = response_doubled.json()

        column = "out.electricity.total.energy_consumption"
        assert body_doubled["series"][0][column] == pytest.approx(2 * body["series"][0][column], rel=1e-6)

    @pytest.mark.integration
    def test_timeseries_composite_multi_component_sqft_mode_warns_out_of_bounds_for_one_component(self, client: TestClient) -> None:
        """Only the out-of-bounds component should generate a warning -- a reasonably-sized component
        alongside it shouldn't."""
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
        assert len(body["warnings"]) == 1
        assert "SmallOffice" in body["warnings"][0]
        assert "RetailStandalone" not in body["warnings"][0]

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
        assert any(line.startswith("#WARNING:") and "SmallOffice" in line for line in lines)
        # The extra warning comment line pushes the matrix declaration one line further down.
        assert lines[8].startswith("double tab1(")

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
