"""
routes/prediction_routes.py
---------------------------
POST /predict/   →   XGBoost phishing/legitimate prediction

Route responsibility: request validation → service call → response.
No ML logic lives here.

KNOWN LIMITATION — Feature extraction:
    This endpoint currently accepts pre-extracted numeric features
    (50 floats in training-column order) rather than a raw URL string.
    A URL-only interface requires a FeatureExtractor service that does not
    yet exist in this project. That is a separate future task.
    The 50 expected features (in order) are defined in services/dependencies.py.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.dependencies import prediction_service
from services.feature_schema import BaseFeatureRequest

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/predict", tags=["Prediction"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class PredictionRequest(BaseFeatureRequest):
    """
    50 numeric features extracted from a URL, in training-column order.
    Column order: URLLength, DomainLength, IsDomainIP, ... NoOfExternalRef.
    See services/feature_schema.py -> FEATURE_NAMES for the full ordered list.
    """
    pass


class PredictionResponse(BaseModel):
    analysis_id: str
    prediction: int          # 0 = Phishing, 1 = Legitimate (matches model.classes_ and dataset label)
    label: str               # "Legitimate" | "Phishing"
    phishing_probability: float
    legitimate_probability: float



# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=PredictionResponse,
    summary="Predict whether a URL is phishing or legitimate",
    description=(
        "Accepts 50 numeric URL features (in training column order) and returns "
        "the XGBoost model's prediction along with class probabilities. "
        "NOTE: A future FeatureExtractor service will allow raw URL input instead."
    ),
)
def predict(request: PredictionRequest) -> PredictionResponse:
    try:
        import uuid
        result = prediction_service.predict(request.features)
        result["analysis_id"] = "pred-" + uuid.uuid4().hex[:10]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}")

    return PredictionResponse(**result)

