#models.py
# ─────────────────────────────────────────────────────────────
# Request and Response schemas — validates all API input/output
# ─────────────────────────────────────────────────────────────

from pydantic import BaseModel, Field
from typing   import Optional

# ── Request schemas ───────────────────────────────────────────

class TextAnalysisRequest(BaseModel):
    """Single text analysis request."""
    text           : str   = Field(..., min_length=10,
                                   description="Text to analyze")
    sentiment      : Optional[float] = Field(
                        default=None,
                        ge=-1.0, le=1.0,
                        description="Pre-computed sentiment (-1 to +1). "
                                    "If None, will be estimated from text."
                    )
    include_rag    : bool  = Field(
                        default=False,
                        description="Include RAG-powered LLM response"
                    )
    top_k          : int   = Field(
                        default=5, ge=1, le=20,
                        description="Number of similar posts to retrieve"
                    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "text"       : "I feel completely hopeless and can't stop worrying",
                "sentiment"  : -0.75,
                "include_rag": True,
                "top_k"      : 5
            }
        }
    }


class BatchAnalysisRequest(BaseModel):
    """Batch analysis for multiple texts."""
    texts       : list[str] = Field(..., min_length=1,
                                    description="List of texts to analyze")
    include_rag : bool      = Field(default=False)


# ── Response schemas ──────────────────────────────────────────

class KeywordDetail(BaseModel):
    matched_high  : list[str]
    matched_medium: list[str]
    matched_low   : list[str]
    match_counts  : dict


class SentimentDetail(BaseModel):
    base_sentiment    : float
    adjusted_sentiment: float
    negation_detected : bool
    intensifier_boost : float
    polarity          : str


class RiskScores(BaseModel):
    keyword_score  : float
    sentiment_score: float
    label_score    : float
    composite_score: float


class RiskAnalysisResponse(BaseModel):
    """Full risk analysis response for a single text."""
    text            : str
    composite_score : float
    risk_level      : str
    risk_label      : str
    scores          : RiskScores
    keyword_detail  : KeywordDetail
    sentiment_detail: SentimentDetail
    rag_response    : Optional[str] = None
    similar_posts   : Optional[list[dict]] = None


class BatchAnalysisResponse(BaseModel):
    """Batch analysis response."""
    total_analyzed : int
    results        : list[RiskAnalysisResponse]
    summary        : dict


class HealthResponse(BaseModel):
    """API health check response."""
    status         : str
    model_loaded   : bool
    index_loaded   : bool
    total_vectors  : int


print("✅ Schemas defined")