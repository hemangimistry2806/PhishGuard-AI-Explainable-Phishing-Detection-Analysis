import threading
from fastapi.testclient import TestClient
from app import app
from services.dependencies import prediction_service, shap_service

client = TestClient(app)

def run_tests():
    valid_features = [0.0] * 50
    invalid_features_49 = [0.0] * 49
    invalid_features_51 = [0.0] * 51
    non_numeric_features = [0.0] * 49 + ["not_a_number"]
    
    print("Running Tests...\n")
    
    # ---------------------------------------------------------
    # 1. /predict tests
    # ---------------------------------------------------------
    r = client.post("/predict", json={"features": valid_features})
    assert r.status_code == 200, "Expected 200 for 50 features in /predict"
    
    r = client.post("/predict", json={"features": invalid_features_49})
    assert r.status_code == 422, "Expected 422 for 49 features in /predict"
    
    r = client.post("/predict", json={"features": invalid_features_51})
    assert r.status_code == 422, "Expected 422 for 51 features in /predict"
    
    r = client.post("/predict", json={})
    assert r.status_code == 422, "Expected 422 for missing features in /predict"
    
    r = client.post("/predict", json={"features": non_numeric_features})
    assert r.status_code == 422, "Expected 422 for non-numeric features in /predict"
    
    print("✔ /predict tests passed")

    # ---------------------------------------------------------
    # 2. /explain tests
    # ---------------------------------------------------------
    url_payload = {"url": "http://example.com"}
    
    r = client.post("/explain", json={**url_payload, "features": valid_features})
    assert r.status_code == 200, "Expected 200 for 50 features in /explain"
    
    r = client.post("/explain", json={**url_payload, "features": invalid_features_49})
    assert r.status_code == 422, "Expected 422 for 49 features in /explain"
    
    r = client.post("/explain", json={**url_payload, "features": invalid_features_51})
    assert r.status_code == 422, "Expected 422 for 51 features in /explain"
    
    r = client.post("/explain", json={**url_payload})
    assert r.status_code == 422, "Expected 422 for missing features in /explain"
    
    r = client.post("/explain", json={**url_payload, "features": non_numeric_features})
    assert r.status_code == 422, "Expected 422 for non-numeric features in /explain"

    print("✔ /explain tests passed")

    # ---------------------------------------------------------
    # 3. Shared Model tests
    # ---------------------------------------------------------
    # Check if they reference the exact same underlying model instance
    assert prediction_service.model is shap_service.explainer.model, "XGBoost model is not loaded through a shared instance"
    print("✔ Shared Model tests passed")

    # ---------------------------------------------------------
    # 4. Feedback tests
    # ---------------------------------------------------------
    # Concurrent POST requests
    def post_feedback(i):
        client.post("/feedback", json={
            "url": f"http://example.com/{i}",
            "model_prediction": "Phishing",
            "user_verdict": "Legitimate",
            "comment": f"Test {i}"
        })
    
    threads = []
    for i in range(10):
        t = threading.Thread(target=post_feedback, args=(i,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    r = client.get("/feedback/stats")
    assert r.status_code == 200, "Expected 200 for GET /feedback/stats"
    stats = r.json()
    assert stats["total_feedback"] >= 10, "Expected at least 10 feedback items"
    print("✔ Feedback tests passed")
    
    print("\nAll tests completed successfully!")

if __name__ == "__main__":
    run_tests()
