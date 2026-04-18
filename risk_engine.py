# risk_engine.py contents — paste this entire cell
# ─────────────────────────────────────────────────────────────
# STEP 3: Risk Engine
# ─────────────────────────────────────────────────────────────

import re
import numpy as np
from collections import defaultdict

# ── Inline constants (replaces config import) ─────────────────
RISK_THRESHOLDS = {"high": 65, "medium": 35}
RISK_WEIGHTS    = {"high": 3.0, "medium": 2.0, "low": 1.0}
SCORE_WEIGHTS   = {"keyword": 0.50, "sentiment": 0.30, "label": 0.20}

# ── Lexicon ───────────────────────────────────────────────────
RISK_LEXICON = {
    "high": [
        "suicidal", "suicide", "end my life", "kill myself",
        "don't want to live", "want to die", "no reason to live",
        "better off dead", "can't go on", "ending it all",
        "hopeless", "worthless", "trapped", "unbearable",
        "breaking down", "falling apart", "can't take it anymore",
        "no way out", "give up", "nothing matters",
        "self harm", "cutting", "hurting myself"
    ],
    "medium": [
        "panic attack", "anxiety", "anxious", "overwhelmed",
        "can't breathe", "heart racing", "constant worry",
        "spiraling", "on edge", "depressed", "depression",
        "crying", "empty inside", "exhausted", "drained",
        "numb", "no motivation", "can't get out of bed",
        "can't sleep", "insomnia", "isolating", "withdrawing"
    ],
    "low": [
        "stressed", "stress", "worried", "nervous",
        "frustrated", "annoyed", "upset", "tired",
        "difficult", "hard time", "struggling", "not great",
        "feeling down", "rough day", "pressure", "bit anxious"
    ]
}

NEGATIONS    = {"not", "never", "no", "nobody", "nothing",
                "neither", "nor", "cannot", "can't", "won't"}

INTENSIFIERS = {
    "very": 1.3, "extremely": 1.5, "incredibly": 1.5,
    "absolutely": 1.4, "completely": 1.4, "totally": 1.3,
    "so": 1.2,   "really": 1.2,  "deeply": 1.3, "terribly": 1.4
}

RISK_LABELS = {"high": "🔴 HIGH", "medium": "🟡 MEDIUM", "low": "🟢 LOW"}


# ── Scorer functions ──────────────────────────────────────────

def keyword_risk_score(text: str) -> dict:
    text_lower  = str(text).lower()
    matched     = defaultdict(list)
    total_score = 0.0

    for level, keywords in RISK_LEXICON.items():
        for kw in keywords:
            if kw in text_lower:
                matched[level].append(kw)
                total_score += RISK_WEIGHTS[level]

    word_count       = max(len(text_lower.split()), 1)
    normalized_score = (total_score / word_count) * 100

    return {
        "raw_score"       : round(total_score, 3),
        "normalized_score": round(normalized_score, 4),
        "matched_high"    : matched["high"],
        "matched_medium"  : matched["medium"],
        "matched_low"     : matched["low"],
        "match_counts"    : {
            "high"  : len(matched["high"]),
            "medium": len(matched["medium"]),
            "low"   : len(matched["low"])
        }
    }


def sentiment_risk_score(text: str, base_sentiment: float) -> dict:
    tokens   = str(text).lower().split()
    modifier = 1.0
    negated  = False

    for token in tokens:
        if token in NEGATIONS:
            negated = True
        if token in INTENSIFIERS:
            modifier *= INTENSIFIERS[token]

    adjusted = base_sentiment * modifier
    if negated and base_sentiment > 0:
        adjusted = -abs(adjusted) * 0.5

    adjusted = max(-1.0, min(1.0, adjusted))

    return {
        "base_sentiment"    : round(base_sentiment, 4),
        "adjusted_sentiment": round(adjusted, 4),
        "negation_detected" : negated,
        "intensifier_boost" : round(modifier, 3),
        "polarity"          : "negative" if adjusted < -0.1
                              else "positive" if adjusted > 0.1
                              else "neutral"
    }


def composite_risk_score(text     : str,
                         sentiment: float,
                         label    : int = 0) -> dict:
    kw         = keyword_risk_score(text)
    kw_score   = min(kw["normalized_score"] * 10, 100)

    sent       = sentiment_risk_score(text, sentiment)
    sent_score = ((1.0 - sent["adjusted_sentiment"]) / 2.0) * 100
    label_score = label * 100

    final_score = (
        SCORE_WEIGHTS["keyword"]   * kw_score   +
        SCORE_WEIGHTS["sentiment"] * sent_score +
        SCORE_WEIGHTS["label"]     * label_score
    )

    return {
        "keyword_score"   : round(kw_score,    2),
        "sentiment_score" : round(sent_score,  2),
        "label_score"     : round(label_score, 2),
        "composite_score" : round(final_score, 2),
        "keyword_detail"  : kw,
        "sentiment_detail": sent
    }


def classify_risk(composite_score: float) -> str:
    if composite_score >= RISK_THRESHOLDS["high"]:
        return "high"
    elif composite_score >= RISK_THRESHOLDS["medium"]:
        return "medium"
    else:
        return "low"


def full_risk_assessment(text     : str,
                         sentiment: float = 0.0,
                         label    : int   = 0) -> dict:
    scores     = composite_risk_score(text, sentiment, label)
    risk_level = classify_risk(scores["composite_score"])

    return {
        **scores,
        "risk_level"     : risk_level,
        "risk_label"     : RISK_LABELS[risk_level],
        "high_keywords"  : scores["keyword_detail"]["matched_high"],
        "medium_keywords": scores["keyword_detail"]["matched_medium"]
    }

print("✅ Risk engine ready")