# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import List, Optional

from services.dependencies import (
    prediction_service as _prediction_service,
    shap_service as _shap_service,
    llm_service as _llm_service,
)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/explain", tags=["Explanation"])

from services.feature_schema import FEATURE_NAMES, BaseFeatureRequest

# ---------------------------------------------------------------------------
# Service instances (singleton per process) imported from dependencies.py
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ExplanationRequest(BaseFeatureRequest):
    """
    Client sends the original URL string plus the 50 numeric features
    so that both SHAP and the LLM can use them.
    """
    url: str

    @field_validator("url")
    @classmethod
    def url_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("url must not be blank")
        return v.strip()


class SHAPFeature(BaseModel):
    feature: str
    shap_value: float


class ExplanationResponse(BaseModel):
    url: str
    prediction: int
    label: str
    phishing_probability: float
    legitimate_probability: float
    shap_features: List[SHAPFeature]   # sorted by |shap_value| descending
    llm_explanation: Optional[str]     # None when LLM key is unavailable

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=ExplanationResponse,
    summary="Get SHAP + LLM explanation for a URL prediction",
    description=(
        "Runs the full explainability pipeline: XGBoost prediction → "
        "SHAP feature importance → LLM natural-language explanation. "
        "llm_explanation is null when OPENAI_API_KEY is not configured."
    ),
)
def explain(request: ExplanationRequest) -> ExplanationResponse:
    """
    POST /explain/

    Body:
        { "url": "https://...", "features": [<float>, ...] }

    Returns:
        Full prediction + sorted SHAP features + LLM explanation
    """
    # 1. Prediction
    try:
        pred_result = _prediction_service.predict(request.features)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction step failed: {str(exc)}"
        )

    # 2. SHAP explanation
    feature_names = FEATURE_NAMES[: len(request.features)]  # safe slice
    try:
        shap_features = _shap_service.explain(request.features, feature_names)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"SHAP explanation failed: {str(exc)}"
        )

    # 3. LLM natural-language explanation (optional — skipped if no key)
    llm_text: Optional[str] = None
    if _llm_service is not None:
        try:
            llm_text = _llm_service.generate_explanation(
                url=request.url,
                prediction=pred_result["label"],
                shap_features=shap_features,
            )
        except Exception as exc:
            # Non-fatal: return partial result with a note
            llm_text = f"[LLM explanation unavailable: {str(exc)}]"

    return ExplanationResponse(
        url=request.url,
        prediction=pred_result["prediction"],
        label=pred_result["label"],
        phishing_probability=pred_result["phishing_probability"],
        legitimate_probability=pred_result["legitimate_probability"],
        shap_features=[SHAPFeature(**f) for f in shap_features],
        llm_explanation=llm_text,
    )
