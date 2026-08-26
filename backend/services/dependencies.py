"""
services/dependencies.py
------------------------
Shared service singletons for PhishGuard AI.

All three services are instantiated ONCE at application startup (on first
import). Both prediction_routes and explanation_routes import from here so
that the XGBoost model is loaded exactly once into memory.

KNOWN ISSUE — LLM provider mismatch:
    llm_service.LLMService reads OPENAI_API_KEY from the environment, but the
    project .env currently contains OPENROUTER_API_KEY and GEMINI_API_KEY.
    Until the llm_service is updated to use one of those keys, _llm_service
    will be None and all LLM explanations will be skipped gracefully.
    This is a provider-configuration issue to be resolved separately — do NOT
    add fake credentials or silently switch providers here.

KNOWN LIMITATION — Feature extraction:
    The current /predict and /explain endpoints accept a pre-extracted
    `features: List[float]` (50 numeric values in training column order).
    A URL-only user-facing interface requires a dedicated FeatureExtractor
    service that does not yet exist in this project. That is a separate
    future task and has NOT been fabricated here.
"""

from typing import Optional

from services.prediction_service import PredictionService
from services.shap_service import SHAPService
from services.llm_service import LLMService

# ---------------------------------------------------------------------------
# PredictionService — loads xgboost_model.pkl once
# ---------------------------------------------------------------------------
prediction_service = PredictionService()

# ---------------------------------------------------------------------------
# SHAPService — receives the already-loaded model; no second load
# ---------------------------------------------------------------------------
shap_service = SHAPService(prediction_service.model)

# ---------------------------------------------------------------------------
# LLMService — gracefully None when OPENAI_API_KEY is not configured
# (see KNOWN ISSUE note above)
# ---------------------------------------------------------------------------
try:
    llm_service: Optional[LLMService] = LLMService()
except ValueError:
    llm_service = None
