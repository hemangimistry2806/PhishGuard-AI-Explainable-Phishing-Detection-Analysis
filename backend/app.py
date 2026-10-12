import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.prediction_routes import router as prediction_router
from routes.explanation_routes import router as explanation_router
from routes.feedback_routes import router as feedback_router
from routes.analyze_routes import router as analyze_router

# ---------------------------------------------------------------------------
# Load environment variables from project-root .env
# ---------------------------------------------------------------------------
load_dotenv(
    dotenv_path=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".env"
    )
)

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Services (PredictionService, SHAPService, LLMService) are instantiated
    # once at import time via services/dependencies.py — not lazily per request.
    # If model loading fails (e.g. wrong path), the error surfaces here at startup.
    print("PhishGuard AI backend started.")
    yield
    print("PhishGuard AI backend shutting down.")


app = FastAPI(
    title="PhishGuard AI",
    description=(
        "Explainable Phishing Detection API. "
        "Predict whether a URL is phishing or legitimate using XGBoost, "
        "get SHAP-based feature importance, and receive LLM-generated explanations. "
        "POST /analyze/ accepts any raw URL and runs full feature extraction + prediction. "
        "POST /predict/ and /explain/ require pre-extracted 50-feature vectors."
    ),
    version="1.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow all origins during development; tighten in production
# ---------------------------------------------------------------------------
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------
app.include_router(prediction_router)
app.include_router(explanation_router)
app.include_router(feedback_router)
app.include_router(analyze_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "PhishGuard AI"}


# ---------------------------------------------------------------------------
# Entry point (for direct `python app.py` runs)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
