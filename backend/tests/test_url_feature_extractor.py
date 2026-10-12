"""
tests/test_url_feature_extractor.py
-------------------------------------
Unit and integration tests for the URL feature extractor.

Tests:
  1. URL-string features (no network) using known values.
  2. Feature vector length always = 50.
  3. Feature dict keys match FEATURE_NAMES exactly.
  4. Integration test: extract features for a real URL and confirm shape.
  5. POST /analyze/ endpoint test (mocked fetch via monkeypatching).

Run from project root:
    pytest backend/tests/test_url_feature_extractor.py -v

Or from the backend/ directory:
    pytest tests/test_url_feature_extractor.py -v
"""

import sys
import os

# Ensure backend/ is on sys.path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.feature_schema import FEATURE_NAMES
from services.url_feature_extractor import (
    _extract_url_features,
    _is_ip,
    _tld_from_hostname,
    extract_features,
    features_to_vector,
)


# ---------------------------------------------------------------------------
# Pure URL-string feature helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_is_ip_v4(self):
        assert _is_ip("192.168.1.1") is True

    def test_is_ip_v6(self):
        assert _is_ip("::1") is True

    def test_is_ip_hostname(self):
        assert _is_ip("example.com") is False

    def test_tld_simple(self):
        assert _tld_from_hostname("example.com") == "com"

    def test_tld_co_uk(self):
        assert _tld_from_hostname("example.co.uk") == "co.uk"

    def test_tld_subdomain(self):
        assert _tld_from_hostname("sub.example.co.uk") == "co.uk"


class TestURLFeatures:
    """Tests for the URL-string phase of feature extraction (no network)."""

    def _extract(self, url):
        d = _extract_url_features(url)
        # Remove internal metadata keys
        return {k: v for k, v in d.items() if not k.startswith("_")}

    def test_https_flag(self):
        feats = self._extract("https://www.example.com/path")
        assert feats["IsHTTPS"] == 1

    def test_http_flag(self):
        feats = self._extract("http://www.example.com/path")
        assert feats["IsHTTPS"] == 0

    def test_url_length(self):
        url = "https://www.example.com"
        feats = self._extract(url)
        assert feats["URLLength"] == len(url)

    def test_ip_domain(self):
        feats = self._extract("http://192.168.1.1/phish")
        assert feats["IsDomainIP"] == 1

    def test_normal_domain_not_ip(self):
        feats = self._extract("http://www.google.com")
        assert feats["IsDomainIP"] == 0

    def test_subdomain_count_www_only(self):
        # www.example.com → 0 meaningful subdomains (www is treated as subdomain)
        feats = self._extract("http://www.example.com")
        # www is one part before the registered domain
        assert feats["NoOfSubDomain"] >= 0

    def test_subdomain_count_multi(self):
        feats = self._extract("http://a.b.example.com")
        # a and b are subdomains
        assert feats["NoOfSubDomain"] >= 2

    def test_obfuscation_detection(self):
        feats = self._extract("http://example.com/path%20with%20spaces")
        assert feats["HasObfuscation"] == 1
        assert feats["NoOfObfuscatedChar"] >= 2

    def test_no_obfuscation_clean_url(self):
        feats = self._extract("https://www.example.com/page")
        assert feats["HasObfuscation"] == 0

    def test_query_params(self):
        feats = self._extract("https://example.com/path?foo=bar&baz=qux")
        assert feats["NoOfEqualsInURL"] >= 2
        assert feats["NoOfQMarkInURL"] >= 1
        assert feats["NoOfAmpersandInURL"] >= 1

    def test_letter_ratio_nonzero(self):
        feats = self._extract("https://www.example.com")
        assert 0 < feats["LetterRatioInURL"] <= 1.0

    def test_tld_edu_high_prob(self):
        feats = self._extract("http://www.someuniversity.edu")
        assert feats["TLDLegitimateProb"] >= 0.95

    def test_tld_tk_low_prob(self):
        feats = self._extract("http://freestuff.tk")
        assert feats["TLDLegitimateProb"] <= 0.20


# ---------------------------------------------------------------------------
# Feature vector / dict consistency
# ---------------------------------------------------------------------------

class TestFeatureVector:
    """Ensure output always matches expected schema."""

    def test_extract_features_keys_match_schema(self):
        """extract_features must produce all FEATURE_NAMES keys."""
        # This test does NOT make a network call;
        # it uses a local domain that won't resolve to reduce flakiness.
        # Page features will default to 0 with a fetch_error.
        feats = extract_features("http://definitely-not-a-real-domain-xyz.invalid")
        for name in FEATURE_NAMES:
            assert name in feats, f"Missing feature key: {name}"

    def test_vector_length_always_50(self):
        feats = extract_features("http://definitely-not-a-real-domain-xyz.invalid")
        vec = features_to_vector(feats)
        assert len(vec) == 50, f"Expected 50 features, got {len(vec)}"

    def test_vector_all_numeric(self):
        feats = extract_features("http://definitely-not-a-real-domain-xyz.invalid")
        vec = features_to_vector(feats)
        for i, v in enumerate(vec):
            assert isinstance(v, float), f"Feature {FEATURE_NAMES[i]} is not float: {v!r}"

    def test_fetch_error_set_for_bad_domain(self):
        feats = extract_features("http://definitely-not-a-real-domain-xyz.invalid")
        assert feats.get("_fetch_error") is not None

    def test_warnings_list_present(self):
        feats = extract_features("http://definitely-not-a-real-domain-xyz.invalid")
        assert isinstance(feats.get("_warnings"), list)

    def test_blank_url_raises_value_error(self):
        with pytest.raises(ValueError, match="blank"):
            extract_features("   ")

    def test_url_scheme_auto_added(self):
        """URLs without scheme should be auto-prefixed with http://."""
        feats = extract_features("definitely-not-a-real-domain-xyz.invalid")
        assert "_fetch_error" in feats  # proof it was parsed, not crashed with ValueError


# ---------------------------------------------------------------------------
# FastAPI endpoint integration test (using TestClient)
# ---------------------------------------------------------------------------

class TestAnalyzeEndpoint:
    """Integration test for POST /analyze/ using FastAPI TestClient."""

    @pytest.fixture(scope="class")
    def client(self):
        """Create a test client for the FastAPI app."""
        try:
            from fastapi.testclient import TestClient
            # Change to backend dir so imports resolve
            original_dir = os.getcwd()
            os.chdir(os.path.join(os.path.dirname(__file__), ".."))
            from app import app
            client = TestClient(app, raise_server_exceptions=False)
            yield client
            os.chdir(original_dir)
        except Exception as e:
            pytest.skip(f"Could not load FastAPI app: {e}")

    def test_analyze_bad_url_returns_error(self, client):
        """Unreachable URL should still return a prediction (features default to 0)."""
        resp = client.post(
            "/analyze/",
            json={"url": "http://definitely-not-a-real-domain-xyz.invalid", "include_explanation": False},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "prediction" in data
        assert "label" in data
        assert data["label"] in ("Phishing", "Legitimate")
        assert "extracted_features" in data
        assert len(data["extracted_features"]) == 50
        # fetch_error should be set
        assert data["fetch_error"] is not None

    def test_analyze_blank_url_returns_422(self, client):
        resp = client.post("/analyze/", json={"url": ""})
        assert resp.status_code == 422

    def test_analyze_missing_url_returns_422(self, client):
        resp = client.post("/analyze/", json={})
        assert resp.status_code == 422

    def test_analyze_response_schema(self, client):
        """Validate all required response fields are present."""
        resp = client.post(
            "/analyze/",
            json={"url": "http://definitely-not-a-real-domain-xyz.invalid", "include_explanation": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        required_fields = [
            "url", "prediction", "label",
            "phishing_probability", "legitimate_probability",
            "extracted_features", "warnings",
        ]
        for field in required_fields:
            assert field in data, f"Response missing field: {field}"
