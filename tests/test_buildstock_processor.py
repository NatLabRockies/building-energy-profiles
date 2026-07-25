"""
Unit tests for shared BuildStockProcessor utility functions (scope_label, sqft_label, validate_release).

These are pure functions with no network calls, used by both ComStockProcessor and ResStockProcessor to
build cache filenames and validate release identifiers.
"""

import pytest

from buildstock_processor import BuildStockRelease, scope_label, sqft_label, validate_release


class TestScopeLabel:
    """Test cases for scope_label(), which builds a filesystem-safe county_name cache-filename component."""

    @pytest.mark.unit
    def test_all_sentinel_passthrough(self):
        assert scope_label("All") == "All"

    @pytest.mark.unit
    def test_single_county_passthrough(self):
        assert scope_label("Kent County") == "Kent County"

    @pytest.mark.unit
    def test_multiple_counties_sorted_and_joined(self):
        # Order shouldn't matter -- the label should be stable/sorted so cache filenames are deterministic.
        assert scope_label(["Arapahoe County", "Denver County"]) == scope_label(["Denver County", "Arapahoe County"])
        assert scope_label(["Denver County", "Arapahoe County"]) == "Arapahoe County+Denver County"

    @pytest.mark.unit
    def test_different_county_lists_produce_different_labels(self):
        assert scope_label(["Denver County", "Arapahoe County"]) != scope_label(["Denver County", "Jefferson County"])


class TestSqftLabel:
    """Test cases for sqft_label(), which builds a filesystem-safe square-footage-range cache-filename component."""

    @pytest.mark.unit
    def test_no_bounds_is_all(self):
        assert sqft_label(None, None) == "All"

    @pytest.mark.unit
    def test_min_only(self):
        assert sqft_label(1000, None) == "1000-maxsqft"

    @pytest.mark.unit
    def test_max_only(self):
        assert sqft_label(None, 10000) == "0-10000sqft"

    @pytest.mark.unit
    def test_both_bounds(self):
        assert sqft_label(1000, 10000) == "1000-10000sqft"

    @pytest.mark.unit
    def test_different_bounds_produce_different_labels(self):
        assert sqft_label(None, 10000) != sqft_label(None, 20000)
        assert sqft_label(None, 10000) != sqft_label(None, None)


class TestValidateRelease:
    """Test cases for validate_release()."""

    @pytest.mark.unit
    def test_supported_release_does_not_raise(self):
        releases = {"release_1": BuildStockRelease(year="2025", folder="foo_release_1", label="Foo Release 1")}
        validate_release("release_1", releases, "Foo")  # should not raise

    @pytest.mark.unit
    def test_unsupported_release_raises_with_product_name(self):
        releases = {"release_1": BuildStockRelease(year="2025", folder="foo_release_1", label="Foo Release 1")}
        with pytest.raises(ValueError, match="Unsupported Foo release 'release_99'"):
            validate_release("release_99", releases, "Foo")
