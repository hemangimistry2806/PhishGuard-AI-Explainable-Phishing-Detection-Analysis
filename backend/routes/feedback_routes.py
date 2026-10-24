"""
routes/feedback_routes.py
--------------------------
Persistent Feedback API backed by SQLite/SQLAlchemy.
Handles submission, telemetry statistics, reviewer verification workflow,
and candidate training data export.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from database import FeedbackRecord, get_db, sanitize_url
from services.url_feature_extractor import extract_registered_domain

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["Feedback"])

REVIEWER_SECRET_KEY = os.getenv("REVIEWER_SECRET_KEY", "phishguard-admin-review-key-2026")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class FeedbackRequest(BaseModel):
    """User feedback submission schema."""
    url: str
    model_prediction: Literal["Phishing", "Legitimate"]
    user_verdict: Literal["Phishing", "Legitimate"]
    comment: Optional[str] = Field(None, max_length=1000)
    analysis_id: Optional[str] = None
    phishing_probability: Optional[float] = None
    legitimate_probability: Optional[float] = None
    extracted_features: Optional[List[float]] = None

    @field_validator("url")
    @classmethod
    def url_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("url must not be blank")
        return v.strip()

    @field_validator("comment")
    @classmethod
    def cap_comment_length(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v.strip()) > 1000:
            raise ValueError("comment must be 1000 characters or fewer")
        return v.strip() if v else None


class FeedbackResponse(BaseModel):
    message: str
    feedback_id: int
    is_correct: bool               # Legacy compatibility for frontend
    is_agreement: bool
    verification_status: str
    sanitized_url: str


class FeedbackStatsResponse(BaseModel):
    total_feedback: int
    correct_predictions: int       # Model and user agreed
    incorrect_predictions: int     # Model and user disagreed
    accuracy_rate: float           # agreements / total
    agreement_rate: float
    reported_phishing_count: int
    reported_legitimate_count: int
    predicted_phishing_count: int
    predicted_legitimate_count: int
    potential_false_positives: int # Model: Phishing, User: Legitimate
    potential_false_negatives: int # Model: Legitimate, User: Phishing
    pending_count: int
    verified_count: int
    rejected_count: int
    top_domains: List[Dict[str, Any]]
    trends_recent: List[Dict[str, Any]]
    disagreement_confidence_distribution: Dict[str, int]


class ReviewFeedbackRequest(BaseModel):
    verification_status: Literal["verified", "rejected", "pending"]
    reviewer_id: str = Field(..., min_length=2, max_length=128)
    review_notes: Optional[str] = Field(None, max_length=1000)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=FeedbackResponse,
    summary="Submit user feedback on a URL prediction",
    status_code=status.HTTP_201_CREATED,
)
def submit_feedback(
    request: FeedbackRequest,
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """
    POST /feedback/
    Persists feedback to SQLite, performs privacy-preserving URL redaction,
    extracts the registered domain, and sets initial status to 'pending'.
    """
    sanitized = sanitize_url(request.url)
    registered_dom = extract_registered_domain(request.url)

    is_agreement = (request.model_prediction == request.user_verdict)

    confidence = None
    if request.model_prediction == "Phishing" and request.phishing_probability is not None:
        confidence = float(request.phishing_probability)
    elif request.model_prediction == "Legitimate" and request.legitimate_probability is not None:
        confidence = float(request.legitimate_probability)

    features_json = None
    if request.extracted_features and len(request.extracted_features) == 50:
        try:
            features_json = json.dumps(request.extracted_features)
        except Exception:
            pass

    record = FeedbackRecord(
        analysis_id=request.analysis_id,
        url=sanitized,
        registered_domain=registered_dom,
        model_prediction=request.model_prediction,
        user_verdict=request.user_verdict,
        is_agreement=is_agreement,
        phishing_probability=request.phishing_probability,
        legitimate_probability=request.legitimate_probability,
        confidence=confidence,
        comment=request.comment,
        verification_status="pending",
        model_version="xgboost_v1.0",
        extracted_features=features_json,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return FeedbackResponse(
        message="Feedback recorded and securely stored in database.",
        feedback_id=record.id,
        is_correct=record.is_agreement,
        is_agreement=record.is_agreement,
        verification_status=record.verification_status,
        sanitized_url=record.url,
    )


@router.get(
    "/stats",
    response_model=FeedbackStatsResponse,
    summary="Get comprehensive feedback statistics from SQLite",
)
def get_feedback_stats(db: Session = Depends(get_db)) -> FeedbackStatsResponse:
    """
    GET /feedback/stats
    Calculates aggregated metrics, potential error classifications, verification counts,
    and domain trends from persisted SQLite records.
    """
    records = db.query(FeedbackRecord).all()
    total = len(records)

    if total == 0:
        return FeedbackStatsResponse(
            total_feedback=0,
            correct_predictions=0,
            incorrect_predictions=0,
            accuracy_rate=0.0,
            agreement_rate=0.0,
            reported_phishing_count=0,
            reported_legitimate_count=0,
            predicted_phishing_count=0,
            predicted_legitimate_count=0,
            potential_false_positives=0,
            potential_false_negatives=0,
            pending_count=0,
            verified_count=0,
            rejected_count=0,
            top_domains=[],
            trends_recent=[],
            disagreement_confidence_distribution={"high": 0, "medium": 0, "low": 0},
        )

    agreed = sum(1 for r in records if r.is_agreement)
    disagreed = total - agreed
    agreement_rate = round(agreed / total, 4)

    reported_phish = sum(1 for r in records if r.user_verdict == "Phishing")
    reported_legit = sum(1 for r in records if r.user_verdict == "Legitimate")
    pred_phish = sum(1 for r in records if r.model_prediction == "Phishing")
    pred_legit = sum(1 for r in records if r.model_prediction == "Legitimate")

    # Potential false positives: model says Phishing, user reports Legitimate
    fp_count = sum(1 for r in records if r.model_prediction == "Phishing" and r.user_verdict == "Legitimate")
    # Potential false negatives: model says Legitimate, user reports Phishing
    fn_count = sum(1 for r in records if r.model_prediction == "Legitimate" and r.user_verdict == "Phishing")

    pending_c = sum(1 for r in records if r.verification_status == "pending")
    verified_c = sum(1 for r in records if r.verification_status == "verified")
    rejected_c = sum(1 for r in records if r.verification_status == "rejected")

    # Top domains
    domain_counts: Dict[str, Dict[str, int]] = {}
    for r in records:
        dom = r.registered_domain or "unknown"
        if dom not in domain_counts:
            domain_counts[dom] = {"total": 0, "disagreements": 0}
        domain_counts[dom]["total"] += 1
        if not r.is_agreement:
            domain_counts[dom]["disagreements"] += 1

    top_doms = [
        {"domain": d, "total": v["total"], "disagreements": v["disagreements"]}
        for d, v in sorted(domain_counts.items(), key=lambda x: x[1]["total"], reverse=True)[:5]
    ]

    # Confidence distribution for disagreements
    conf_dist = {"high": 0, "medium": 0, "low": 0}
    for r in records:
        if not r.is_agreement and r.confidence is not None:
            if r.confidence >= 0.80:
                conf_dist["high"] += 1
            elif r.confidence >= 0.60:
                conf_dist["medium"] += 1
            else:
                conf_dist["low"] += 1

    # Trends recent (group by date YYYY-MM-DD)
    date_buckets: Dict[str, Dict[str, int]] = {}
    for r in records:
        d_str = r.created_at.strftime("%Y-%m-%d") if r.created_at else "undated"
        if d_str not in date_buckets:
            date_buckets[d_str] = {"date": d_str, "total": 0, "agreements": 0, "disagreements": 0}
        date_buckets[d_str]["total"] += 1
        if r.is_agreement:
            date_buckets[d_str]["agreements"] += 1
        else:
            date_buckets[d_str]["disagreements"] += 1

    trends = sorted(date_buckets.values(), key=lambda x: x["date"], reverse=True)[:7]

    return FeedbackStatsResponse(
        total_feedback=total,
        correct_predictions=agreed,
        incorrect_predictions=disagreed,
        accuracy_rate=agreement_rate,
        agreement_rate=agreement_rate,
        reported_phishing_count=reported_phish,
        reported_legitimate_count=reported_legit,
        predicted_phishing_count=pred_phish,
        predicted_legitimate_count=pred_legit,
        potential_false_positives=fp_count,
        potential_false_negatives=fn_count,
        pending_count=pending_c,
        verified_count=verified_c,
        rejected_count=rejected_c,
        top_domains=top_doms,
        trends_recent=trends,
        disagreement_confidence_distribution=conf_dist,
    )


@router.get(
    "/list",
    summary="List feedback entries with optional filtering",
)
def list_feedback(
    status_filter: Optional[str] = Query(None, alias="status"),
    disagreements_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """GET /feedback/list with pagination and filters."""
    query = db.query(FeedbackRecord)
    if status_filter:
        query = query.filter(FeedbackRecord.verification_status == status_filter)
    if disagreements_only:
        query = query.filter(FeedbackRecord.is_agreement == False)

    total_matched = query.count()
    records = query.order_by(desc(FeedbackRecord.created_at)).offset(offset).limit(limit).all()

    return {
        "total": total_matched,
        "offset": offset,
        "limit": limit,
        "records": [r.to_dict() for r in records],
    }


@router.patch(
    "/{feedback_id}/review",
    summary="Review and change verification status (Authorized reviewers only)",
)
def review_feedback(
    feedback_id: int,
    review: ReviewFeedbackRequest,
    x_reviewer_key: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    PATCH /feedback/{feedback_id}/review
    Requires X-Reviewer-Key header for authorization.
    Updates verification status to verified, rejected, or pending.
    """
    if not x_reviewer_key or x_reviewer_key != REVIEWER_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Valid X-Reviewer-Key header is required to perform feedback reviews."
        )

    record = db.query(FeedbackRecord).filter(FeedbackRecord.id == feedback_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Feedback ID {feedback_id} not found.")

    record.verification_status = review.verification_status
    record.reviewer_id = review.reviewer_id
    record.review_notes = review.review_notes
    record.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(record)

    return {
        "message": f"Feedback ID {feedback_id} status updated to '{record.verification_status}'.",
        "record": record.to_dict(),
    }


@router.get(
    "/candidate-dataset",
    summary="Export verified feedback for offline candidate model evaluation",
)
def export_candidate_dataset(
    x_reviewer_key: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    GET /feedback/candidate-dataset
    Exports ONLY verified feedback with full feature references.
    Pending or rejected feedback is strictly excluded.
    The production model is NEVER automatically retrained.
    """
    if not x_reviewer_key or x_reviewer_key != REVIEWER_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Reviewer access key required."
        )

    verified_records = db.query(FeedbackRecord).filter(
        FeedbackRecord.verification_status == "verified"
    ).all()

    candidate_samples = []
    for r in verified_records:
        label_int = 0 if r.user_verdict == "Phishing" else 1
        features = None
        if r.extracted_features:
            try:
                features = json.loads(r.extracted_features)
            except Exception:
                features = None

        candidate_samples.append({
            "feedback_id": r.id,
            "url": r.url,
            "registered_domain": r.registered_domain,
            "verified_label": r.user_verdict,
            "label_int": label_int,
            "reviewer_id": r.reviewer_id,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "has_feature_vector": features is not None,
            "features": features,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "candidate_samples_count": len(candidate_samples),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "policy": "Verified human ground-truth only; models must be evaluated separately offline.",
        "samples": candidate_samples,
    }
