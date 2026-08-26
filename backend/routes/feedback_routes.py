import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import Literal, Optional

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/feedback", tags=["Feedback"])

# ---------------------------------------------------------------------------
# Feedback storage — lightweight JSON file in ml/models/
# (no database dependency; easy to swap for a DB later)
# ---------------------------------------------------------------------------
_BASE_DIR = Path(__file__).resolve().parents[2]   # project root
_FEEDBACK_FILE = _BASE_DIR / "ml" / "models" / "feedback.json"
_FEEDBACK_LOCK = threading.Lock()


def _load_feedback() -> list:
    if _FEEDBACK_FILE.exists():
        try:
            with open(_FEEDBACK_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_feedback(records: list) -> None:
    _FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class FeedbackRequest(BaseModel):
    """
    User submits feedback on a single prediction.

    Fields:
        url              — the URL that was analysed
        model_prediction — what the model said: "Phishing" | "Legitimate"
        user_verdict     — what the user believes: "Phishing" | "Legitimate"
        comment          — optional free-text comment (max 1000 chars)
    """
    url: str
    model_prediction: Literal["Phishing", "Legitimate"]
    user_verdict: Literal["Phishing", "Legitimate"]
    comment: Optional[str] = None

    @field_validator("url")
    @classmethod
    def url_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("url must not be blank")
        return v.strip()

    @field_validator("comment")
    @classmethod
    def cap_comment_length(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 1000:
            raise ValueError("comment must be 1000 characters or fewer")
        return v


class FeedbackResponse(BaseModel):
    message: str
    feedback_id: int          # 1-based index in the feedback file
    is_correct: bool          # True when model_prediction == user_verdict


class FeedbackStatsResponse(BaseModel):
    total_feedback: int
    correct_predictions: int
    incorrect_predictions: int
    accuracy_rate: float      # 0.0 – 1.0

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=FeedbackResponse,
    summary="Submit user feedback on a URL prediction",
    description=(
        "Stores the user's verdict alongside the model's prediction. "
        "Feedback is appended to ml/models/feedback.json."
    ),
    status_code=201,
)
def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """
    POST /feedback/

    Body:
        {
          "url": "https://...",
          "model_prediction": "Phishing",
          "user_verdict": "Legitimate",
          "comment": "This is actually my bank!"
        }

    Returns:
        Confirmation with a feedback_id and correctness flag.
    """
    with _FEEDBACK_LOCK:
        records = _load_feedback()

        record = {
            "feedback_id": len(records) + 1,
            "url": request.url,
            "model_prediction": request.model_prediction,
            "user_verdict": request.user_verdict,
            "is_correct": request.model_prediction == request.user_verdict,
            "comment": request.comment,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

        records.append(record)

        try:
            _save_feedback(records)
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Could not save feedback: {str(exc)}"
            )

    return FeedbackResponse(
        message="Feedback recorded. Thank you!",
        feedback_id=record["feedback_id"],
        is_correct=record["is_correct"],
    )


@router.get(
    "/stats",
    response_model=FeedbackStatsResponse,
    summary="Get aggregated feedback statistics",
    description="Returns total feedback count, correct/incorrect breakdown, and model accuracy rate.",
)
def get_feedback_stats() -> FeedbackStatsResponse:
    """
    GET /feedback/stats

    Returns aggregate statistics over all stored feedback.
    """
    records = _load_feedback()
    total = len(records)
    correct = sum(1 for r in records if r.get("is_correct", False))
    incorrect = total - correct
    accuracy = correct / total if total > 0 else 0.0

    return FeedbackStatsResponse(
        total_feedback=total,
        correct_predictions=correct,
        incorrect_predictions=incorrect,
        accuracy_rate=round(accuracy, 4),
    )
