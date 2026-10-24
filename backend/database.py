"""
backend/database.py
-------------------
SQLite database layer with SQLAlchemy for PhishGuard-AI.
Persistently stores user feedback, predictions, verification workflow,
and provides aggregate telemetry statistics.
"""

import json
import os
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    func,
    desc,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# ---------------------------------------------------------------------------
# Database Configuration
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "phishguard.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# SQLite connection args for multithreaded FastAPI requests
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ---------------------------------------------------------------------------
# Privacy / Redaction Utility
# ---------------------------------------------------------------------------
_SENSITIVE_PARAM_KEYS = {
    "token", "auth", "key", "password", "pass", "pwd", "secret", "session",
    "sessid", "sid", "code", "access_token", "refresh_token", "api_key",
    "signature", "sig", "credential", "user", "username", "email",
}


def sanitize_url(raw_url: str) -> str:
    """
    Privacy-preserving URL sanitizer:
    - Normalizes scheme and host
    - Redacts sensitive query parameter values while preserving param keys
    - Removes private fragment identifiers
    """
    if not raw_url:
        return ""
    try:
        norm = raw_url.strip()
        if not re.match(r"^https?://", norm, re.I):
            norm = "http://" + norm
        parsed = urllib.parse.urlsplit(norm)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path

        if not parsed.query:
            return urllib.parse.urlunsplit((scheme, netloc, path, "", ""))

        # Redact query params
        query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        sanitized_pairs = []
        for k, v in query_pairs:
            k_lower = k.lower()
            if any(sens in k_lower for sens in _SENSITIVE_PARAM_KEYS) or len(v) > 32:
                sanitized_pairs.append((k, "[REDACTED]"))
            else:
                sanitized_pairs.append((k, v))

        new_query = urllib.parse.urlencode(sanitized_pairs, safe="[]:")
        return urllib.parse.urlunsplit((scheme, netloc, path, new_query, ""))

    except Exception:
        # Fallback to just origin
        return raw_url[:120]


# ---------------------------------------------------------------------------
# Feedback Model
# ---------------------------------------------------------------------------
class FeedbackRecord(Base):
    __tablename__ = "feedback_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    analysis_id = Column(String(64), index=True, nullable=True)
    url = Column(String(2048), nullable=False)
    registered_domain = Column(String(255), index=True, nullable=True)
    model_prediction = Column(String(32), nullable=False)   # "Phishing" | "Legitimate"
    user_verdict = Column(String(32), nullable=False)       # "Phishing" | "Legitimate"
    is_agreement = Column(Boolean, nullable=False, default=False)
    phishing_probability = Column(Float, nullable=True)
    legitimate_probability = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    comment = Column(String(1000), nullable=True)
    verification_status = Column(String(32), default="pending", index=True) # "pending" | "verified" | "rejected"
    reviewer_id = Column(String(128), nullable=True)
    review_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    model_version = Column(String(64), default="xgboost_v1.0")
    extracted_features = Column(Text, nullable=True)  # JSON string of 50 floats if provided
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feedback_id": self.id,
            "analysis_id": self.analysis_id,
            "url": self.url,
            "registered_domain": self.registered_domain,
            "model_prediction": self.model_prediction,
            "user_verdict": self.user_verdict,
            "is_agreement": self.is_agreement,
            "phishing_probability": self.phishing_probability,
            "legitimate_probability": self.legitimate_probability,
            "confidence": self.confidence,
            "comment": self.comment,
            "verification_status": self.verification_status,
            "reviewer_id": self.reviewer_id,
            "review_notes": self.review_notes,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "model_version": self.model_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Database Initialization & Session Dependency
# ---------------------------------------------------------------------------
def init_db():
    """Create tables if they do not exist."""
    if DATABASE_URL.startswith("sqlite:///"):
        db_file = DATABASE_URL.replace("sqlite:///", "")
        db_dir = os.path.dirname(os.path.abspath(db_file))
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
