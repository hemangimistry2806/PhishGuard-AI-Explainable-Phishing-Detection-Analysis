"""
routes/analyze_routes.py
------------------------
POST /analyze/   →   full pipeline: URL → feature extraction → XGBoost + SHAP

This endpoint accepts a **raw URL string** and returns a prediction with
SHAP explanations by running the FeatureExtractor service in-process.

Unlike /predict/ and /explain/ (which require pre-extracted feature vectors
from the PhiUSIIL benchmark dataset), this endpoint works on any URL.

KNOWN LIMITATIONS:
  - Feature extraction approximates some values (see url_feature_extractor.py).
  - Pages that block crawlers (Cloudflare, login-walls, etc.) will have
    HTML-based features defaulted to 0, reducing prediction confidence.
  - The model was trained on a static dataset; accuracy on novel phishing
    campaigns may differ from published benchmark results.
  - Slow or offline URLs may timeout (default 8 s).

These limitations are surfaced to the caller via the `warnings` and
`fetch_error` fields in the response.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from services.dependencies import (
    prediction_service as _prediction_service,
    shap_service as _shap_service,
    llm_service as _llm_service,
)
from services.feature_schema import FEATURE_NAMES
from services.url_feature_extractor import extract_features, features_to_vector

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/analyze", tags=["URL Analysis"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    """Raw URL to analyze end-to-end."""
    url: str
    include_explanation: bool = True   # set False to skip SHAP+LLM (faster)

    @field_validator("url")
    @classmethod
    def url_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("url must not be blank")
        return v.strip()


class SHAPFeature(BaseModel):
    feature: str
    shap_value: float


class AnalyzeResponse(BaseModel):
    url: str
    prediction: int
    label: str
    phishing_probability: float
    legitimate_probability: float
    # Extracted feature vector sent to the model (for transparency)
    extracted_features: List[float]
    # SHAP explanation (None when include_explanation=False)
    shap_features: Optional[List[SHAPFeature]]
    llm_explanation: Optional[str]
    # Honest reporting of approximation issues
    fetch_error: Optional[str]
    warnings: List[str]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=AnalyzeResponse,
    summary="Analyze any URL end-to-end (feature extraction + prediction + explanation)",
    description=(
        "Accepts a raw URL string, extracts 50 features by fetching the page, "
        "runs the XGBoost prediction, and optionally returns SHAP feature "
        "importances and a natural-language LLM explanation. "
        "Limitations: some features are approximated; pages that block bots "
        "will have HTML features defaulted to 0."
    ),
)
def analyze_url(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    POST /analyze/

    Body:
        { "url": "https://...", "include_explanation": true }
    """
    # 1. Feature extraction
    try:
        feature_dict = extract_features(request.url, timeout=8.0)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Feature extraction failed: {str(exc)}"
        )

    fetch_error: Optional[str] = feature_dict.get("_fetch_error")
    warnings: List[str] = feature_dict.get("_warnings", [])
    feature_vector = features_to_vector(feature_dict)

    # 2. Prediction
    try:
        pred_result = _prediction_service.predict(feature_vector)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(exc)}"
        )

    # 3. SHAP explanation (optional)
    shap_feats: Optional[List[SHAPFeature]] = None
    llm_text: Optional[str] = None

    if request.include_explanation:
        try:
            raw_shap = _shap_service.explain(feature_vector, FEATURE_NAMES)
            shap_feats = [SHAPFeature(**f) for f in raw_shap]
        except Exception as exc:
            logger.warning("SHAP explanation failed: %s", exc)
            warnings.append(f"SHAP explanation could not be generated: {str(exc)}")

        # 4. LLM explanation (optional, non-fatal)
        if _llm_service is not None and shap_feats is not None:
            try:
                llm_text = _llm_service.generate_explanation(
                    url=request.url,
                    prediction=pred_result["label"],
                    shap_features=[{"feature": f.feature, "shap_value": f.shap_value}
                                   for f in shap_feats],
                )
            except Exception as exc:
                llm_text = f"[LLM explanation unavailable: {str(exc)[:120]}]"

    return AnalyzeResponse(
        url=request.url,
        prediction=pred_result["prediction"],
        label=pred_result["label"],
        phishing_probability=pred_result["phishing_probability"],
        legitimate_probability=pred_result["legitimate_probability"],
        extracted_features=feature_vector,
        shap_features=shap_feats,
        llm_explanation=llm_text,
        fetch_error=fetch_error,
        warnings=warnings,
    )
