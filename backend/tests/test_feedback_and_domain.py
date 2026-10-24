"""
backend/tests/test_feedback_and_domain.py
-----------------------------------------
Comprehensive regression tests for:
1. SQLite feedback persistence & lifecycle
2. Disagreement & potential false positive/negative calculations
3. Privacy URL redaction
4. Reviewer verification authorization
5. Candidate training dataset export
6. Public Suffix List registered domain extraction
7. SSRF safety and scheme validation
8. Model evaluation report endpoint
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app import app
from database import Base, FeedbackRecord, engine, SessionLocal, sanitize_url
from services.url_feature_extractor import extract_registered_domain, _check_ssrf, extract_features

# Create tables immediately on import
Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c



@pytest.fixture(autouse=True)
def clean_db():
    """Wipe feedback records before each test to guarantee isolated counts."""
    db = SessionLocal()
    try:
        db.query(FeedbackRecord).delete()
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. Privacy & URL Redaction
# ---------------------------------------------------------------------------
class TestPrivacySanitization:
    def test_sanitize_removes_tokens_and_passwords(self):
        url = "https://bank.com/login?token=secret123456789abcdef&user=john&account=998877"
        sanitized = sanitize_url(url)
        assert "secret123456789abcdef" not in sanitized
        assert "[REDACTED]" in sanitized
        assert "bank.com" in sanitized

    def test_sanitize_leaves_clean_urls_intact(self):
        url = "https://example.com/products/view?category=electronics"
        sanitized = sanitize_url(url)
        assert "example.com" in sanitized
        assert "category=electronics" in sanitized


# ---------------------------------------------------------------------------
# 2. Public Suffix List & Domain Parsing
# ---------------------------------------------------------------------------
class TestDomainExtractionPSL:
    def test_subdomain_deceptive_brand_spoofing(self):
        url = "https://google.com.kill-credential.net/login"
        reg_domain = extract_registered_domain(url)
        assert reg_domain == "kill-credential.net", f"Expected kill-credential.net, got {reg_domain}"

    def test_multi_part_tld_co_uk(self):
        url = "https://sub.portal.service.co.uk/account"
        reg_domain = extract_registered_domain(url)
        assert reg_domain == "service.co.uk"

    def test_ip_address_domain(self):
        url = "http://192.168.1.1:8080/admin"
        reg_domain = extract_registered_domain(url)
        assert reg_domain == "192.168.1.1"


# ---------------------------------------------------------------------------
# 3. SSRF Protection & Scheme Validation
# ---------------------------------------------------------------------------
class TestSSRFAndSchemeValidation:
    def test_localhost_blocked(self):
        is_ssrf, reason = _check_ssrf("127.0.0.1")
        assert is_ssrf is True
        assert "restricted" in reason.lower() or "local" in reason.lower()

    def test_cloud_metadata_blocked(self):
        is_ssrf, reason = _check_ssrf("169.254.169.254")
        assert is_ssrf is True

    def test_private_subnet_blocked(self):
        is_ssrf, reason = _check_ssrf("10.0.0.5")
        assert is_ssrf is True

    def test_unsupported_scheme_rejected(self):
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            extract_features("ftp://malicious.com/payload.exe")

    def test_file_scheme_rejected(self):
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            extract_features("file:///etc/passwd")


# ---------------------------------------------------------------------------
# 4. Feedback Submission & Persistence
# ---------------------------------------------------------------------------
class TestFeedbackPipeline:
    def test_empty_database_stats(self, client):
        resp = client.get("/feedback/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_feedback"] == 0
        assert data["correct_predictions"] == 0
        assert data["potential_false_positives"] == 0
        assert data["potential_false_negatives"] == 0

    def test_submit_feedback_agreement(self, client):
        payload = {
            "url": "https://trusted-portal.com/login?token=secretXYZ12345",
            "model_prediction": "Legitimate",
            "user_verdict": "Legitimate",
            "comment": "Confirmed official site",
            "legitimate_probability": 0.98,
            "phishing_probability": 0.02,
        }
        resp = client.post("/feedback/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["feedback_id"] > 0
        assert data["is_agreement"] is True
        assert data["verification_status"] == "pending"
        assert "secretXYZ12345" not in data["sanitized_url"]

    def test_potential_false_positive_and_negative_metrics(self, client):
        # 1. Potential False Positive: Model says Phishing, User says Legitimate
        client.post("/feedback/", json={
            "url": "https://my-local-credit-union.org",
            "model_prediction": "Phishing",
            "user_verdict": "Legitimate",
            "comment": "False alarm on small bank",
            "phishing_probability": 0.85,
        })
        # 2. Potential False Negative: Model says Legitimate, User says Phishing
        client.post("/feedback/", json={
            "url": "http://paypal-security-update.xyz",
            "model_prediction": "Legitimate",
            "user_verdict": "Phishing",
            "comment": "Brand new phishing attack",
            "legitimate_probability": 0.91,
        })
        # 3. Agreement: Model says Phishing, User says Phishing
        client.post("/feedback/", json={
            "url": "http://chase-bank-verify.top",
            "model_prediction": "Phishing",
            "user_verdict": "Phishing",
            "comment": "Obvious phishing",
            "phishing_probability": 0.99,
        })

        stats_resp = client.get("/feedback/stats")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()

        assert stats["total_feedback"] == 3
        assert stats["correct_predictions"] == 1
        assert stats["incorrect_predictions"] == 2
        assert stats["potential_false_positives"] == 1
        assert stats["potential_false_negatives"] == 1
        assert stats["pending_count"] == 3
        assert stats["verified_count"] == 0

    def test_reviewer_workflow_and_candidate_export(self, client):
        # Submit feedback
        post_resp = client.post("/feedback/", json={
            "url": "http://steampowered-login.com.fake.ru",
            "model_prediction": "Legitimate",
            "user_verdict": "Phishing",
            "extracted_features": [0.0] * 50,
        })
        fid = post_resp.json()["feedback_id"]

        # Review without token -> 401
        rev_fail = client.patch(f"/feedback/{fid}/review", json={
            "verification_status": "verified",
            "reviewer_id": "security_auditor_1"
        })
        assert rev_fail.status_code == 401

        # Review with token -> 200
        admin_headers = {"X-Reviewer-Key": "phishguard-admin-review-key-2026"}
        rev_ok = client.patch(f"/feedback/{fid}/review", headers=admin_headers, json={
            "verification_status": "verified",
            "reviewer_id": "security_auditor_1",
            "review_notes": "Ground truth confirmed via WHOIS & threat intel"
        })
        assert rev_ok.status_code == 200
        assert rev_ok.json()["record"]["verification_status"] == "verified"

        # Candidate dataset export
        cand_resp = client.get("/feedback/candidate-dataset", headers=admin_headers)
        assert cand_resp.status_code == 200
        cand_data = cand_resp.json()
        assert cand_data["candidate_samples_count"] >= 1
        sample = cand_data["samples"][0]
        assert sample["verified_label"] == "Phishing"
        assert sample["label_int"] == 0
        assert sample["has_feature_vector"] is True


# ---------------------------------------------------------------------------
# 5. Model Evaluation Endpoint
# ---------------------------------------------------------------------------
class TestModelEvaluationEndpoint:
    def test_get_model_evaluation(self, client):
        resp = client.get("/model/evaluation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "Completed"
        assert "production_model_baseline" in data
        assert "domain_disjoint_evaluation" in data
        assert data["domain_disjoint_evaluation"]["verified_domain_overlap"] == 0
