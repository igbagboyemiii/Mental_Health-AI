"""
Mental Health Suggestion Engine
================================
Module 1: Input Indicators & Normalization
Target Constructs: Anxiety Severity + Burnout Likelihood
Method A: Literature-Based Weights (PHQ-9, GAD-7, MBI, PSS)
"""
import sys
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

from dataclasses import dataclass, field
from typing import Optional
import math


# ─────────────────────────────────────────────
# 1. INDICATOR DEFINITIONS
# ─────────────────────────────────────────────

@dataclass
class Indicator:
    key: str
    label: str
    construct: list[str]       # which constructs this feeds
    weight: float              # Method A literature weight
    scale_min: float
    scale_max: float
    norm_type: str             # "inverse" | "linear" | "ushaped" | "threshold"
    optimal: Optional[float] = None   # for u-shaped only
    clinical_ref: str = ""


INDICATORS: dict[str, Indicator] = {

    # ── ANXIETY / STRESS ──────────────────────────────────────────────
    "stress": Indicator(
        key="stress",
        label="Perceived Stress Level",
        construct=["anxiety_severity"],
        weight=0.20,
        scale_min=1, scale_max=10,
        norm_type="linear",                    # higher = more risk
        clinical_ref="PSS (Cohen, 1983); GAD-7 item 1"
    ),

    # ── DEPRESSION / MANIA ───────────────────────────────────────────
    "mood": Indicator(
        key="mood",
        label="Mood / Affect Quality",
        construct=["anxiety_severity", "burnout_likelihood"],
        weight=0.18,
        scale_min=1, scale_max=10,
        norm_type="inverse",                   # lower = more risk
        clinical_ref="PHQ-9 item 1; PANAS Negative Affect"
    ),

    # ── LONELINESS RISK ───────────────────────────────────────────────
    "social": Indicator(
        key="social",
        label="Social Connection & Support",
        construct=["anxiety_severity", "burnout_likelihood"],
        weight=0.12,
        scale_min=1, scale_max=10,
        norm_type="inverse",                   # lower connection = more risk
        clinical_ref="UCLA Loneliness Scale; Cacioppo 2008"
    ),

    # ── SOMATIC SYMPTOMS ─────────────────────────────────────────────
    "sleep": Indicator(
        key="sleep",
        label="Sleep Quality (hours last night)",
        construct=["anxiety_severity", "burnout_likelihood"],
        weight=0.16,
        scale_min=0, scale_max=12,
        norm_type="ushaped",
        optimal=7.5,                           # deviation from 7.5h = risk
        clinical_ref="PSQI; Walker 2017; DSM-5 insomnia criterion"
    ),

    "appetite": Indicator(
        key="appetite",
        label="Appetite & Physical Energy",
        construct=["burnout_likelihood"],
        weight=0.10,
        scale_min=1, scale_max=10,
        norm_type="inverse",
        clinical_ref="PHQ-9 items 3,4; MBI exhaustion subscale"
    ),

    # ── COGNITIVE SYMPTOM ────────────────────────────────────────────
    "concentration": Indicator(
        key="concentration",
        label="Concentration & Focus",
        construct=["anxiety_severity", "burnout_likelihood"],
        weight=0.12,
        scale_min=1, scale_max=10,
        norm_type="inverse",                   # lower = more risk
        clinical_ref="PHQ-9 item 7; MBI cynicism; GAD-7 item 3"
    ),

    # ── BEHAVIORAL ACTIVATION PROXY ──────────────────────────────────
    "activity": Indicator(
        key="activity",
        label="Physical Activity Level (days active this week)",
        construct=["burnout_likelihood"],
        weight=0.08,
        scale_min=0, scale_max=7,
        norm_type="inverse",                   # less activity = more burnout risk
        clinical_ref="IPAQ; Stubbs et al. 2017 (exercise as antidepressant)"
    ),

    # ── SUBSTANCE USE (COMORBIDITY) ───────────────────────────────────
    "substance": Indicator(
        key="substance",
        label="Substance Use Frequency (0=never, 10=daily)",
        construct=["anxiety_severity", "burnout_likelihood"],
        weight=0.04,
        scale_min=0, scale_max=10,
        norm_type="threshold",                 # any use above 3 escalates risk
        clinical_ref="AUDIT-C; DAST-10; NIAAA comorbidity guidelines"
    ),
}

# Validate weights sum to ~1.0
assert abs(sum(i.weight for i in INDICATORS.values()) - 1.0) < 0.001, \
    f"Weights must sum to 1.0, got {sum(i.weight for i in INDICATORS.values())}"


# ─────────────────────────────────────────────
# 2. NORMALIZATION FUNCTIONS
# ─────────────────────────────────────────────

def normalize(indicator: Indicator, raw_value: float) -> float:
    """
    Convert raw input → 0.0–1.0 risk contribution.
    0.0 = no risk, 1.0 = maximum risk.
    """
    v = max(indicator.scale_min, min(indicator.scale_max, raw_value))
    span = indicator.scale_max - indicator.scale_min

    nt = indicator.norm_type
    if nt == "linear":
        # Higher value = higher risk (e.g. stress)
        return (v - indicator.scale_min) / span

    elif nt == "inverse":
        # Lower value = higher risk (e.g. mood, social, concentration)
        return (indicator.scale_max - v) / span

    elif nt == "ushaped":
        # Deviation from optimal = risk (e.g. sleep)
        # Both too little AND too much carry risk
        opt = indicator.optimal or (span / 2 + indicator.scale_min)
        max_dev = max(opt - indicator.scale_min, indicator.scale_max - opt)
        return min(1.0, abs(v - opt) / max_dev)

    elif nt == "threshold":
        # Low use = 0 risk, crosses threshold sharply (e.g. substance)
        threshold = indicator.scale_min + span * 0.3   # 30% of scale
        if v <= threshold:
            return 0.0
        return min(1.0, (v - threshold) / (span * 0.7))

    else:
        raise ValueError(f"Unknown norm_type: {indicator.norm_type}")


# ─────────────────────────────────────────────
# 3. WEIGHTED SCORE COMPUTATION
# ─────────────────────────────────────────────

@dataclass
class ScoringResult:
    composite_score: float              # 0.0–1.0 overall risk
    anxiety_score: float                # 0.0–1.0 anxiety construct
    burnout_score: float                # 0.0–1.0 burnout construct
    factor_contributions: dict          # per-indicator breakdown
    dominant_factors: list[str]         # top 3 risk drivers
    raw_inputs: dict


def compute_scores(raw_inputs: dict[str, float]) -> ScoringResult:
    """
    Run all indicators and return construct-level + composite scores.
    """
    contributions = {}
    anxiety_num, anxiety_den = 0.0, 0.0
    burnout_num, burnout_den = 0.0, 0.0

    for key, indicator in INDICATORS.items():
        value = raw_inputs.get(key)
        if value is None:
            continue

        norm = normalize(indicator, value)
        weighted = norm * indicator.weight
        contributions[key] = {
            "raw": value,
            "normalized": round(norm, 3),
            "weighted": round(weighted, 4),
            "label": indicator.label,
            "weight": indicator.weight,
        }

        if "anxiety_severity" in indicator.construct:
            anxiety_num += weighted
            anxiety_den += indicator.weight
        if "burnout_likelihood" in indicator.construct:
            burnout_num += weighted
            burnout_den += indicator.weight

    # Normalize construct scores to 0-1 range relative to their weights
    anxiety_score = (anxiety_num / anxiety_den) if anxiety_den > 0 else 0.0
    burnout_score = (burnout_num / burnout_den) if burnout_den > 0 else 0.0

    # Composite = weighted blend of both constructs
    composite = (anxiety_score * 0.5) + (burnout_score * 0.5)

    # Find dominant risk factors (top 3 by normalized contribution)
    sorted_factors = sorted(
        contributions.items(),
        key=lambda x: x[1]["normalized"],
        reverse=True
    )
    dominant = [k for k, _ in sorted_factors[:3]]

    return ScoringResult(
        composite_score=round(composite, 4),
        anxiety_score=round(anxiety_score, 4),
        burnout_score=round(burnout_score, 4),
        factor_contributions=contributions,
        dominant_factors=dominant,
        raw_inputs=raw_inputs,
    )


# ─────────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────────
if __name__ == "__main__":
    sample = {
        "stress": 8,
        "mood": 3,
        "social": 4,
        "sleep": 4.5,
        "appetite": 4,
        "concentration": 3,
        "activity": 1,
        "substance": 5,
    }
    result = compute_scores(sample)
    print(f"\nComposite Risk Score : {result.composite_score:.2%}")
    print(f"Anxiety Severity     : {result.anxiety_score:.2%}")
    print(f"Burnout Likelihood   : {result.burnout_score:.2%}")
    print(f"Top Risk Drivers     : {result.dominant_factors}")
    print("\nFactor Breakdown:")
    for k, v in result.factor_contributions.items():
        bar = "█" * int(v["normalized"] * 20)
        print(f"  {k:<15} {bar:<20} {v['normalized']:.2f}  (raw={v['raw']})")