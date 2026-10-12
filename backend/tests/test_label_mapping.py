import os
import sys
import pytest
import numpy as np

# Add project root to sys.path so backend imports resolve
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.services.prediction_service import PredictionService
from backend.services.feature_schema import FEATURE_NAMES


# Exact 50-feature vector from PhiUSIIL dataset row 0 (URL: https://www.southbankmosaics.com, label: 1 = Legitimate)
LEGITIMATE_SAMPLE_50 = [
    31.0, 24.0, 0.0, 100.0, 1.0, 0.5229071, 0.061933179, 3.0, 1.0, 0.0,
    0.0, 0.0, 18.0, 0.581, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0,
    0.032, 1.0, 558.0, 9381.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0,
    0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0,
    1.0, 0.0, 0.0, 1.0, 34.0, 20.0, 28.0, 119.0, 0.0, 124.0
]

# Exact 50-feature vector from PhiUSIIL dataset row 11 (URL: http://www.teramill.com, label: 0 = Phishing)
PHISHING_SAMPLE_50 = [
    22.0, 16.0, 0.0, 82.6446281, 1.0, 0.5229071, 0.06741797, 3.0, 1.0, 0.0,
    0.0, 0.0, 10.0, 0.455, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0,
    0.045, 0.0, 2.0, 87.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0
]


class TestLabelAndProbabilityMapping:
    """
    Regression tests verifying that model classes, dataset ground truth labels,
    and prediction probabilities are correctly aligned throughout PredictionService.
    """

    @pytest.fixture(scope="class")
    def service(self):
        return PredictionService()

    def test_model_classes_ordering(self, service):
        """Confirm model.classes_ is [0, 1] where 0=Phishing and 1=Legitimate."""
        classes = list(service.model.classes_)
        assert classes == [0, 1], f"Expected classes [0, 1], got {classes}"

    def test_legitimate_sample_classification(self, service):
        """A benchmark legitimate URL sample (CSV label=1) must return Legitimate with low phishing probability."""
        result = service.predict(LEGITIMATE_SAMPLE_50)

        assert result["prediction"] == 1, f"Expected prediction 1, got {result['prediction']}"
        assert result["label"] == "Legitimate", f"Expected label 'Legitimate', got {result['label']}"
        assert result["legitimate_probability"] > 0.9, f"Expected legitimate_probability > 0.9, got {result['legitimate_probability']}"
        assert result["phishing_probability"] < 0.1, f"Expected phishing_probability < 0.1, got {result['phishing_probability']}"
        assert abs(result["phishing_probability"] + result["legitimate_probability"] - 1.0) < 1e-4

    def test_phishing_sample_classification(self, service):
        """A benchmark phishing URL sample (CSV label=0) must return Phishing with high phishing probability."""
        result = service.predict(PHISHING_SAMPLE_50)

        assert result["prediction"] == 0, f"Expected prediction 0, got {result['prediction']}"
        assert result["label"] == "Phishing", f"Expected label 'Phishing', got {result['label']}"
        assert result["phishing_probability"] > 0.9, f"Expected phishing_probability > 0.9, got {result['phishing_probability']}"
        assert result["legitimate_probability"] < 0.1, f"Expected legitimate_probability < 0.1, got {result['legitimate_probability']}"
        assert abs(result["phishing_probability"] + result["legitimate_probability"] - 1.0) < 1e-4

    def test_probability_index_mapping(self, service):
        """Directly compare predict_proba indices against assigned probabilities."""
        X = np.array(LEGITIMATE_SAMPLE_50).reshape(1, -1)
        raw_probs = service.model.predict_proba(X)[0]

        result = service.predict(LEGITIMATE_SAMPLE_50)
        # raw_probs[0] is class 0 (Phishing)
        # raw_probs[1] is class 1 (Legitimate)
        assert abs(result["phishing_probability"] - float(raw_probs[0])) < 1e-6
        assert abs(result["legitimate_probability"] - float(raw_probs[1])) < 1e-6

    def test_all_frontend_benchmark_samples_match_predictions(self, service):
        """
        Verify that all 30 benchmark samples provided to the frontend UI
        produce predictions and probabilities matching their expected labels.
        Directly guards against the sample-result mismatch reported in UI recordings.
        """
        import json
        samples_path = os.path.join(project_root, "frontend", "src", "data", "samples", "samples.js")
        assert os.path.exists(samples_path), f"samples.js not found at {samples_path}"

        with open(samples_path, "r", encoding="utf-8") as f:
            text = f.read()

        start = text.find("[")
        end = text.rfind("]") + 1
        samples = json.loads(text[start:end])
        assert len(samples) >= 30, f"Expected at least 30 samples, found {len(samples)}"

        for i, sample in enumerate(samples):
            url = sample["url"]
            expected_label = sample["label"]
            features = sample["features"]
            assert len(features) == 50, f"Sample {url} has {len(features)} features, expected 50"

            res = service.predict(features)
            assert res["label"] == expected_label, (
                f"Sample #{i} ({url}) expected {expected_label} but model predicted {res['label']} "
                f"(prediction={res['prediction']}, phish_prob={res['phishing_probability']:.4f})"
            )

            if expected_label == "Phishing":
                assert res["prediction"] == 0
                assert res["phishing_probability"] > 0.5
            else:
                assert res["prediction"] == 1
                assert res["legitimate_probability"] > 0.5


class TestAPILabelEndpointIntegration:
    """Integration test verifying HTTP endpoints return the corrected mapping."""

    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        try:
            from app import app
            c = TestClient(app, raise_server_exceptions=False)
            return c
        except Exception as e:
            pytest.skip(f"Could not load FastAPI app: {e}")

    def test_predict_endpoint_legitimate(self, client):
        resp = client.post("/predict/", json={"features": LEGITIMATE_SAMPLE_50})
        assert resp.status_code == 200
        data = resp.json()
        assert data["prediction"] == 1
        assert data["label"] == "Legitimate"
        assert data["legitimate_probability"] > 0.9
        assert data["phishing_probability"] < 0.1

    def test_predict_endpoint_phishing(self, client):
        resp = client.post("/predict/", json={"features": PHISHING_SAMPLE_50})
        assert resp.status_code == 200
        data = resp.json()
        assert data["prediction"] == 0
        assert data["label"] == "Phishing"
        assert data["phishing_probability"] > 0.9
        assert data["legitimate_probability"] < 0.1
