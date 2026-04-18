"""
Module 2: Risk Classification Engine
=====================================
Maps composite + construct scores → risk tier + intervention flags.

Tiers (5-level PRD schema):
  NONE     — No indicators, clean text
  LOW      — Subclinical stress
  MODERATE — Emerging symptoms
  HIGH     — Significant distress, professional referral recommended
  CRISIS   — Severe / suicidal ideation, immediate intervention required
"""

from dataclasses import dataclass
from scoring.indicators import ScoringResult


# ─────────────────────────────────────────────
# RISK TIERS  (5-level)
# ─────────────────────────────────────────────

RISK_TIERS = {
    "NONE": {
        "range": (0.00, 0.10),
        "label": "No Risk Detected",
        "color": "grey",
        "urgency": 0,
        "description": "No meaningful risk indicators detected.",
        "professional_referral": False,
        "crisis_protocol": False,
    },
    "LOW": {
        "range": (0.10, 0.30),
        "label": "Low Risk",
        "color": "green",
        "urgency": 1,
        "description": "Subclinical. Maintenance and resilience-building recommended.",
        "professional_referral": False,
        "crisis_protocol": False,
    },
    "MODERATE": {
        "range": (0.30, 0.55),
        "label": "Moderate Risk",
        "color": "yellow",
        "urgency": 2,
        "description": "Emerging symptoms. Evidence-based self-help + monitoring.",
        "professional_referral": False,
        "crisis_protocol": False,
    },
    "HIGH": {
        "range": (0.55, 0.75),
        "label": "High Risk",
        "color": "orange",
        "urgency": 3,
        "description": "Significant distress. Professional evaluation recommended.",
        "professional_referral": True,
        "crisis_protocol": False,
    },
    "CRISIS": {
        "range": (0.75, 1.01),
        "label": "Crisis — Immediate Support Required",
        "color": "red",
        "urgency": 4,
        "description": "Severe risk indicators. Immediate professional support and crisis protocol activated.",
        "professional_referral": True,
        "crisis_protocol": True,
    },
}


# ─────────────────────────────────────────────
# OVERRIDE RULES (construct-specific escalation)
# ─────────────────────────────────────────────

def apply_override_rules(tier: str, scoring: ScoringResult) -> tuple[str, list[str]]:
    """
    Escalate tier based on specific construct combinations.
    Returns (final_tier, list_of_triggered_rules).
    """
    flags = []
    current_urgency = RISK_TIERS[tier]["urgency"]

    # Rule 1: Substance use above threshold → escalate 1 level
    substance = scoring.raw_inputs.get("substance", 0)
    if substance >= 7:
        flags.append("HIGH_SUBSTANCE_USE: Escalated due to frequent substance use")
        current_urgency = max(current_urgency, 3)

    # Rule 2: Both constructs high (>0.6) → escalate to CRISIS minimum
    if scoring.anxiety_score > 0.60 and scoring.burnout_score > 0.60:
        flags.append("DUAL_CONSTRUCT_HIGH: Both anxiety and burnout at high levels")
        current_urgency = max(current_urgency, 4)

    # Rule 3: Sleep < 4 hrs is an acute somatic crisis signal
    sleep = scoring.raw_inputs.get("sleep", 7)
    if sleep < 4:
        flags.append("ACUTE_SLEEP_DEPRIVATION: <4 hrs — somatic escalation")
        current_urgency = max(current_urgency, 3)

    # Rule 4: Social isolation + high stress → elevated anxiety risk
    social = scoring.raw_inputs.get("social", 5)
    stress = scoring.raw_inputs.get("stress", 5)
    if social <= 2 and stress >= 8:
        flags.append("ISOLATION_STRESS_COMBO: Loneliness + acute stress co-occurring")
        current_urgency = max(current_urgency, 3)

    # Map urgency back to tier label (0=NONE, 1=LOW, 2=MODERATE, 3=HIGH, 4=CRISIS)
    urgency_to_tier = {0: "NONE", 1: "LOW", 2: "MODERATE", 3: "HIGH", 4: "CRISIS"}
    final_tier = urgency_to_tier[current_urgency]

    if final_tier != tier:
        flags.insert(0, f"TIER_ESCALATED: {tier} → {final_tier}")

    return final_tier, flags


# ─────────────────────────────────────────────
# CLASSIFICATION OUTPUT
# ─────────────────────────────────────────────

@dataclass
class RiskClassification:
    tier: str                       # NONE | LOW | MODERATE | HIGH | CRISIS
    tier_info: dict
    anxiety_tier: str               # construct-specific tier
    burnout_tier: str
    override_flags: list[str]       # escalation rules triggered
    scoring: ScoringResult
    rag_query: str                  # pre-built query for RAG lookup


def _score_to_tier(score: float) -> str:
    for tier, info in RISK_TIERS.items():
        lo, hi = info["range"]
        if lo <= score < hi:
            return tier
    return "CRISIS"


def classify(scoring: ScoringResult) -> RiskClassification:
    # Base classification from composite score
    base_tier = _score_to_tier(scoring.composite_score)

    # Apply override rules
    final_tier, flags = apply_override_rules(base_tier, scoring)

    # Construct-specific tiers (for granular suggestions)
    anxiety_tier = _score_to_tier(scoring.anxiety_score)
    burnout_tier = _score_to_tier(scoring.burnout_score)

    # Build RAG query from dominant factors + tiers
    dominant_str = ", ".join(scoring.dominant_factors)
    rag_query = (
        f"Mental health support for {final_tier.lower()} risk. "
        f"Primary concerns: {dominant_str}. "
        f"Anxiety severity: {anxiety_tier.lower()}. "
        f"Burnout likelihood: {burnout_tier.lower()}. "
        f"Constructs: anxiety_severity, burnout_likelihood."
    )

    return RiskClassification(
        tier=final_tier,
        tier_info=RISK_TIERS[final_tier],
        anxiety_tier=anxiety_tier,
        burnout_tier=burnout_tier,
        override_flags=flags,
        scoring=scoring,
        rag_query=rag_query,
    )


# ─────────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────────
if __name__ == "__main__":
    from scoring.indicators import compute_scores

    inputs = {
        "stress": 8, "mood": 3, "social": 2,
        "sleep": 3.5, "appetite": 4,
        "concentration": 3, "activity": 1, "substance": 7,
    }
    scoring = compute_scores(inputs)
    result = classify(scoring)

    print(f"\n{'='*50}")
    print(f"RISK TIER        : {result.tier}")
    print(f"Anxiety Tier     : {result.anxiety_tier}")
    print(f"Burnout Tier     : {result.burnout_tier}")
    print(f"Crisis Protocol  : {result.tier_info['crisis_protocol']}")
    print(f"Override Flags   :")
    for f in result.override_flags:
        print(f"  ⚠  {f}")
    print(f"\nRAG Query:")
    print(f"  {result.rag_query}")