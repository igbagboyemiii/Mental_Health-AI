# evaluate_model.py
# ─────────────────────────────────────────────────────────────
# Calculates full performance metrics for the risk model
# Run: python evaluate_model.py
# Requires: main.py backend running on localhost:8000
# ─────────────────────────────────────────────────────────────

import requests
import numpy as np
from test_data import TEST_DATA
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

BACKEND_URL = "http://localhost:8000/analyze"
API_KEY     = "dev-secret-key-change-in-prod"

LABEL_MAP = {
    "high"  : 2,
    "medium": 1,
    "low"   : 0,
}

CLASS_NAMES = ["Low Risk", "Moderate Risk", "High Risk"]


# ─────────────────────────────────────────────────────────────
# Run Predictions
# ─────────────────────────────────────────────────────────────

def get_prediction(text: str) -> int:
    """Send text to backend and return predicted label."""
    try:
        response = requests.post(
            BACKEND_URL,
            json    = {"text": text},
            headers = {"X-API-Key": API_KEY},
            timeout = 10,
        )
        result = response.json()
        level  = result.get("risk_level", "low")
        return LABEL_MAP.get(level, 0)
    except Exception as e:
        print(f"Error predicting: {text[:40]}... → {e}")
        return 0


def run_evaluation():
    print("=" * 60)
    print("  MindGuard Model Evaluation")
    print("=" * 60)
    print(f"  Total test samples: {len(TEST_DATA)}")
    print("  Running predictions...\n")

    true_labels = []
    pred_labels = []
    errors      = []

    for i, (text, true_label) in enumerate(TEST_DATA):
        pred_label = get_prediction(text)
        true_labels.append(true_label)
        pred_labels.append(pred_label)

        status = "✅" if pred_label == true_label else "❌"

        # Track wrong predictions for review
        if pred_label != true_label:
            errors.append({
                "text"      : text,
                "expected"  : CLASS_NAMES[true_label],
                "predicted" : CLASS_NAMES[pred_label],
            })

        print(
            f"  {status} [{i+1:02d}] "
            f"Expected: {CLASS_NAMES[true_label]:15s} | "
            f"Got: {CLASS_NAMES[pred_label]:15s} | "
            f"{text[:45]}..."
        )

    # ── Calculate Metrics ─────────────────────────────────────
    accuracy  = accuracy_score(true_labels, pred_labels)
    precision = precision_score(
        true_labels, pred_labels,
        average = "weighted", zero_division = 0
    )
    recall = recall_score(
        true_labels, pred_labels,
        average = "weighted", zero_division = 0
    )
    f1 = f1_score(
        true_labels, pred_labels,
        average = "weighted", zero_division = 0
    )
    cm = confusion_matrix(true_labels, pred_labels)

    # ── Per-class metrics (most important for clinical use) ───
    precision_per_class = precision_score(
        true_labels, pred_labels,
        average = None, zero_division = 0
    )
    recall_per_class = recall_score(
        true_labels, pred_labels,
        average = None, zero_division = 0
    )
    f1_per_class = f1_score(
        true_labels, pred_labels,
        average = None, zero_division = 0
    )

    # ── Print Results ─────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  OVERALL METRICS")
    print("=" * 60)
    print(f"  Accuracy  : {accuracy  * 100:.1f}%")
    print(f"  Precision : {precision * 100:.1f}%")
    print(f"  Recall    : {recall    * 100:.1f}%")
    print(f"  F1 Score  : {f1        * 100:.1f}%")

    print("\n" + "=" * 60)
    print("  PER-CLASS METRICS")
    print("=" * 60)
    print(f"  {'Class':<18} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print(f"  {'-'*50}")
    for i, name in enumerate(CLASS_NAMES):
        p = precision_per_class[i] * 100 if i < len(precision_per_class) else 0
        r = recall_per_class[i]    * 100 if i < len(recall_per_class)    else 0
        f = f1_per_class[i]        * 100 if i < len(f1_per_class)        else 0
        print(f"  {name:<18} {p:>9.1f}% {r:>9.1f}% {f:>9.1f}%")

    print("\n" + "=" * 60)
    print("  CONFUSION MATRIX")
    print("=" * 60)
    print(f"  {'':20} {'Predicted Low':>14} {'Predicted Med':>14} {'Predicted High':>15}")
    row_names = ["Actual Low    ", "Actual Medium ", "Actual High   "]
    for i, row in enumerate(cm):
        if i < len(row_names):
            values = "  ".join(f"{v:>8}" for v in row)
            print(f"  {row_names[i]}   {values}")

    print("\n" + "=" * 60)
    print("  CLINICAL SAFETY CHECK")
    print("=" * 60)

    # Most critical — High Risk Recall
    high_recall = recall_per_class[2] * 100 if len(recall_per_class) > 2 else 0
    high_status = "✅ PASS" if high_recall >= 90 else "❌ FAIL — needs improvement"
    print(f"  High Risk Recall : {high_recall:.1f}%  {high_status}")
    print(f"  (Target: ≥ 90% — missing a high risk user is dangerous)")

    # False Negatives on High Risk
    if len(cm) > 2:
        high_risk_row     = cm[2]
        false_negatives   = sum(high_risk_row) - high_risk_row[2]
        print(f"\n  High Risk False Negatives : {false_negatives}")
        print(f"  (These are real people flagged as Low/Medium when they are High Risk)")

    # ── Print Wrong Predictions ───────────────────────────────
    if errors:
        print("\n" + "=" * 60)
        print(f"  WRONG PREDICTIONS ({len(errors)} total)")
        print("=" * 60)
        for err in errors:
            print(f"\n  Text      : {err['text']}")
            print(f"  Expected  : {err['expected']}")
            print(f"  Predicted : {err['predicted']}")

    print("\n" + "=" * 60)
    print("  EVALUATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    run_evaluation()