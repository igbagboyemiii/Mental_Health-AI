# verify.py  --  MindGuard System Verification Script
# Run AFTER starting main.py:   python verify.py
import sys
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

import argparse, requests

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://localhost:8000")
parser.add_argument("--key", default="dev-secret-key-change-in-prod")
args   = parser.parse_args()

BASE    = args.url.rstrip("/")
HEADERS = {"X-API-Key": args.key, "Content-Type": "application/json"}

results = []

def section(title):
    print(f"\n{'-'*62}\n  {title}\n{'-'*62}")

def check(label, ok, detail=""):
    sym = "[PASS]" if ok else "[FAIL]"
    print(f"  {sym}  {label:<46} {detail}")
    results.append(ok)

# ── 1. Health ─────────────────────────────────────────────────
section("1 - BACKEND HEALTH")
try:
    r    = requests.get(f"{BASE}/health", timeout=6)
    data = r.json()
    check("API reachable",           r.status_code == 200)
    check("Embedding model loaded",  data.get("model_loaded", False))
    check("FAISS index loaded",      data.get("index_loaded", False))
    check("FAISS has vectors",       data.get("total_vectors", 0) > 0,
          f"({data.get('total_vectors',0)} vectors)")
except requests.ConnectionError:
    print(f"\n  [FAIL]  Cannot reach {BASE}")
    print("          Start the server first:  python main.py\n")
    sys.exit(1)
except Exception as e:
    check("Health check", False, str(e))

# ── 2. Low-risk analysis ──────────────────────────────────────
section("2 - TEXT ANALYSIS  (low risk)")
try:
    r = requests.post(f"{BASE}/analyze?user_id=verify",
        headers=HEADERS,
        json={"text": "Had a bit of a stressful week at work, feeling tired but okay overall.", "include_rag": False},
        timeout=12)
    d = r.json()
    check("Status 200",              r.status_code == 200)
    check("Has composite_score",     "composite_score" in d)
    check("Has risk_level",          "risk_level" in d)
    check("Risk level low/none",     d.get("risk_level","") in ("low","none"),
          f"(got: {d.get('risk_level')})")
    check("Has keyword_detail",      "keyword_detail" in d)
except Exception as e:
    check("Low-risk analysis", False, str(e))

# ── 3. High-risk analysis ─────────────────────────────────────
section("3 - TEXT ANALYSIS  (high risk)")
try:
    r = requests.post(f"{BASE}/analyze?user_id=verify",
        headers=HEADERS,
        json={"text": "I feel completely hopeless and worthless. I can't go on anymore and just want to end it all.", "include_rag": False},
        timeout=12)
    d = r.json()
    check("Status 200",              r.status_code == 200)
    check("Risk level high/crisis",  d.get("risk_level","") in ("high","crisis"),
          f"(got: {d.get('risk_level')})")
    check("Score above 5.0",         float(d.get("composite_score",0)) >= 5.0,
          f"(got: {d.get('composite_score')})")
    check("High keywords detected",  len(d.get("keyword_detail",{}).get("matched_high",[])) > 0)
except Exception as e:
    check("High-risk analysis", False, str(e))

# ── 4. RAG ───────────────────────────────────────────────────
section("4 - RAG RETRIEVAL")
try:
    r = requests.post(f"{BASE}/analyze?user_id=verify",
        headers=HEADERS,
        json={"text": "I feel overwhelmed and can't stop worrying about everything.", "include_rag": True, "top_k": 3},
        timeout=25)
    d = r.json()
    check("Status 200",              r.status_code == 200)
    check("RAG response present",    bool(d.get("rag_response")))
    check("Similar posts returned",  len(d.get("similar_posts") or []) > 0,
          f"({len(d.get('similar_posts') or [])} posts)")
except Exception as e:
    check("RAG pipeline", False, str(e))

# ── 5. Assessment (sliders) ───────────────────────────────────
section("5 - ASSESSMENT ENDPOINT  (/assess)")
try:
    r = requests.post(f"{BASE}/assess", headers=HEADERS,
        json={"stress":8,"mood":3,"social":2,"sleep":4.0,
              "appetite":3,"concentration":3,"activity":1,"substance":2},
        timeout=15)
    d = r.json()
    check("Status 200",              r.status_code == 200)
    check("Has tier",                "tier" in d, f"(tier: {d.get('tier')})")
    check("Tier is valid",           d.get("tier") in ("NONE","LOW","MODERATE","HIGH","CRISIS"),
          f"(got: {d.get('tier')})")
    check("Has suggestion_summary",  bool(d.get("suggestion_summary")))
    check("Has suggested_actions",   len(d.get("suggested_actions",[])) > 0)
except Exception as e:
    check("Assessment endpoint", False, str(e))

# ── 6. History endpoints ─────────────────────────────────────
section("6 - HISTORY & AUDIT ENDPOINTS")
try:
    r = requests.get(f"{BASE}/history?limit=5", headers=HEADERS, timeout=6)
    d = r.json()
    check("GET /history  200",       r.status_code == 200)
    check("Has total + rows",        "total" in d and "rows" in d)

    r = requests.get(f"{BASE}/history/summary", headers=HEADERS, timeout=6)
    check("GET /history/summary 200", r.status_code == 200)

    r = requests.get(f"{BASE}/temporal/verify?days=7", headers=HEADERS, timeout=6)
    d = r.json()
    check("GET /temporal/{id} 200",  r.status_code == 200)
    check("Has summary + events",    "summary" in d and "events" in d)
except Exception as e:
    check("History endpoints", False, str(e))

# ── 7. Batch ─────────────────────────────────────────────────
section("7 - BATCH ANALYSIS")
try:
    r = requests.post(f"{BASE}/analyze/batch", headers=HEADERS,
        json={"texts":["Feeling a bit down today.",
                       "I can't stop crying and feel completely hopeless.",
                       "Just a rough morning but managing fine."],
              "include_rag": False},
        timeout=18)
    d = r.json()
    check("Status 200",              r.status_code == 200)
    check("total_analyzed == 3",     d.get("total_analyzed") == 3,
          f"(got: {d.get('total_analyzed')})")
    check("Has summary stats",       "summary" in d)
except Exception as e:
    check("Batch analysis", False, str(e))

# ── 8. Auth ──────────────────────────────────────────────────
section("8 - SECURITY  (invalid key rejected)")
try:
    r = requests.get(f"{BASE}/audit",
        headers={"X-API-Key": "wrong-key"}, timeout=5)
    check("Invalid key returns 401", r.status_code == 401,
          f"(got: {r.status_code})")
except Exception as e:
    check("Auth check", False, str(e))

# ── Summary ──────────────────────────────────────────────────
passed = sum(results)
total  = len(results)
print(f"\n{'='*62}")
print(f"  RESULT: {passed}/{total} checks passed  ", end="")
if passed == total:
    print("All systems go!")
elif passed >= total * 0.8:
    print("Minor issues -- check failures above.")
else:
    print("Significant failures -- review output above.")
print(f"{'='*62}\n")
sys.exit(0 if passed == total else 1)
