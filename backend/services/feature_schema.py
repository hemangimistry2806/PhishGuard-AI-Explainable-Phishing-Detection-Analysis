"""
services/feature_schema.py
--------------------------
Centralized schema for the 50 numeric features expected by the XGBoost model.
"""

from typing import List
from pydantic import BaseModel, field_validator

FEATURE_NAMES: List[str] = [
    "URLLength", "DomainLength", "IsDomainIP",
    "URLSimilarityIndex", "CharContinuationRate", "TLDLegitimateProb",
    "URLCharProb", "TLDLength", "NoOfSubDomain", "HasObfuscation",
    "NoOfObfuscatedChar", "ObfuscationRatio", "NoOfLettersInURL",
    "LetterRatioInURL", "NoOfDegitsInURL", "DegitRatioInURL",
    "NoOfEqualsInURL", "NoOfQMarkInURL", "NoOfAmpersandInURL",
    "NoOfOtherSpecialCharsInURL", "SpacialCharRatioInURL", "IsHTTPS",
    "LineOfCode", "LargestLineLength", "HasTitle",
    "DomainTitleMatchScore", "URLTitleMatchScore", "HasFavicon",
    "Robots", "IsResponsive", "NoOfURLRedirect", "NoOfSelfRedirect",
    "HasDescription", "NoOfPopup", "NoOfiFrame", "HasExternalFormSubmit",
    "HasSocialNet", "HasSubmitButton", "HasHiddenFields",
    "HasPasswordField", "Bank", "Pay", "Crypto", "HasCopyrightInfo",
    "NoOfImage", "NoOfCSS", "NoOfJS", "NoOfSelfRef",
    "NoOfEmptyRef", "NoOfExternalRef",
]

class BaseFeatureRequest(BaseModel):
    """
    Base schema to validate that incoming features exactly match
    the expected 50-feature array for inference.
    """
    features: List[float]

    @field_validator("features")
    @classmethod
    def must_have_correct_length(cls, v: List[float]) -> List[float]:
        if not v:
            raise ValueError("features list must not be empty")
        if len(v) != 50:
            raise ValueError(
                f"Expected exactly 50 features (model was trained on 50 columns); "
                f"received {len(v)}"
            )
        return v
