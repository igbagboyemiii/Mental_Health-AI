import sys
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

import os
import re
import json
import uuid
import asyncio
import numpy as np
import nest_asyncio
import uvicorn
import faiss

from fastapi import FastAPI, HTTPException, status, Query, WebSocket, WebSocketDisconnect, Depends, Security
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date as DateType
from scoring.indicators import compute_scores, INDICATORS
from risk.classifier import classify, RISK_TIERS
from monitor_storage import MonitorStorage
from crisis_engine import crisis_engine
import requests
import time

try:
    nest_asyncio.apply()
except ValueError:
    pass  # uvloop (used on Render Linux) cannot be patched by nest_asyncio, but nesting is not required there.

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM        = 384
HOST                 = "0.0.0.0"
PORT                 = 8000

# ── API Key Security ──────────────────────────────────────────
DESKTOP_APP_API_KEY = os.getenv("DESKTOP_APP_API_KEY", "dev-secret-key-change-in-prod")
API_KEY_NAME        = "X-API-Key"
api_key_header      = APIKeyHeader(name=API_KEY_NAME, auto_error=True)


async def verify_api_key(key: str = Security(api_key_header)):
    if key != DESKTOP_APP_API_KEY:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "Invalid or missing API key",
        )
    return key


# ─────────────────────────────────────────────────────────────
# WebSocket Connection Manager
# ─────────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        # accept() is called in the endpoint before this — do NOT call again
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def send_json(self, ws: WebSocket, data: dict):
        await ws.send_text(json.dumps(data))


manager = ConnectionManager()

# ─────────────────────────────────────────────────────────────
# Keyword Dictionaries
# ─────────────────────────────────────────────────────────────

HIGH_RISK_KEYWORDS = [
    # Self harm variations
    "suicide", "suicidal",
    "kill myself", "killing myself",
    "end my life", "ending my life",
    "want to die", "wanted to die",
    "no reason to live", "nothing to live for",
    "can't go on", "cant go on",
    "can't go on any longer", "cant go on any longer",
    "self-harm", "self harm",
    "harm myself",           # ← MISSING — now added
    "hurt myself",           # ← MISSING — now added
    "want to hurt myself",   # ← MISSING — now added
    "want to harm myself",   # ← MISSING — now added
    "injure myself",         # ← MISSING — now added
    "cut myself", "cutting myself",
    "overdose", "take all my pills",
    "hopeless", "completely hopeless",
    "worthless", "feel worthless",
    "better off dead", "better off without me",
    "nobody cares", "no one cares",
    "can't take it anymore", "cant take it anymore",
    "nothing matters", "none of it matters",
    "no point", "no point anymore", "no point in life",
    "give up on life", "giving up",
    "don't want to be here", "dont want to be here",
    "don't want to live", "dont want to live",
    "tired of living", "tired of life",
    "end it all", "end everything",
    "unalive", "unaliving myself",
    "disappear forever", "wish i was dead",
    "rather be dead", "rather not exist",
]

MEDIUM_RISK_KEYWORDS = [
    "depressed", "anxious", "overwhelmed", "exhausted", "alone", "empty",
    "numb", "scared", "panic", "crying", "grief", "trauma", "struggling",
    "lost", "broken", "hurting", "suffering", "desperate", "helpless"
]

LOW_RISK_KEYWORDS = [
    "sad", "worried", "stressed", "tired", "frustrated", "upset", "lonely",
    "confused", "nervous", "unhappy", "down", "low", "bad day", "difficult"
]

NEGATION_WORDS   = {"not", "no", "never", "without", "don't", "doesn't", "didn't", "won't", "can't"}
INTENSIFIER_WORDS = {"very", "extremely", "really", "so", "completely", "absolutely", "utterly", "deeply"}

# ─────────────────────────────────────────────────────────────
# Sample RAG corpus (replace with real data in production)
# ─────────────────────────────────────────────────────────────

SAMPLE_CORPUS = [
    {"id": 0, "text": "Feeling hopeless and overwhelmed every single day",          "label": 1},
    {"id": 1, "text": "I can't stop thinking about ending everything",              "label": 2},
    {"id": 2, "text": "Anxiety is ruining my relationships and work life",          "label": 1},
    {"id": 3, "text": "Just a rough week, feeling a bit down but managing",        "label": 0},
    {"id": 4, "text": "I don't see any point in continuing anymore",                "label": 2},
    {"id": 5, "text": "Struggling with depression for months now",                  "label": 1},
    {"id": 6, "text": "Stressed about exams but otherwise okay",                    "label": 0},
    {"id": 7, "text": "Everything feels empty and meaningless",                     "label": 1},
    {"id": 8, "text": "Having panic attacks and can't leave the house",             "label": 1},
    {"id": 9, "text": "I tried to hurt myself last night",                          "label": 2},
]

RAG_RESPONSES = {
    "high":   "This text shows significant distress indicators. Immediate professional support is strongly recommended. Crisis resources: 988 Suicide & Crisis Lifeline (call/text 988), Crisis Text Line (text HOME to 741741).",
    "medium": "Moderate emotional distress detected. Consider speaking with a mental health professional, trusted person, or counselor. Self-care strategies and professional support can help.",
    "low":    "Mild stress or emotional difficulty noted. Regular self-care, social connection, and monitoring of mood are encouraged. Reach out if things worsen.",
}

# ─────────────────────────────────────────────────────────────
# Global State  (loaded once at startup)
# ─────────────────────────────────────────────────────────────

class HFEmbeddingClient:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        if "/" not in model_name:
            self.model_name = f"sentence-transformers/{model_name}"
        else:
            self.model_name = model_name
        self.api_url = f"https://api-inference.huggingface.co/models/{self.model_name}"
        # Fallback to a default public token if needed, or let user set HF_TOKEN in Render environment
        self.hf_token = os.getenv("HF_TOKEN")

    def encode(self, texts: list[str], convert_to_numpy: bool = True) -> np.ndarray:
        headers = {}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"
        
        # Hugging Face API can return 503 if model is loading, so we handle retries
        for attempt in range(5):
            try:
                response = requests.post(self.api_url, headers=headers, json={"inputs": texts}, timeout=15)
                data = response.json()
                if response.status_code == 200:
                    if isinstance(data, list):
                        arr = np.array(data, dtype=np.float32)
                        # If the Hugging Face API returns a 3D array (token embeddings), mean-pool it to 2D
                        if len(arr.shape) == 3:
                            arr = np.mean(arr, axis=1)
                        return arr
                    raise ValueError(f"Unexpected response format: {data}")
                elif response.status_code == 503 and isinstance(data, dict) and "estimated_time" in data:
                    wait_time = min(data.get("estimated_time", 5), 10)
                    print(f"⏳ Hugging Face model loading, waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"HF API Error ({response.status_code}): {data}")
            except Exception as e:
                if attempt == 4:
                    raise e
                time.sleep(2)
        raise RuntimeError("Failed to generate embeddings from HF API.")


embedding_model: HFEmbeddingClient = None
faiss_index:     faiss.IndexFlatL2   = None
embeddings:      np.ndarray          = None
corpus_texts:    list[dict]          = []
db_store:        MonitorStorage      = None   # shared storage instance


async def load_resources_async():
    """Load embedding model, build FAISS index from corpus asynchronously in background."""
    global embedding_model, faiss_index, embeddings, corpus_texts

    # Wait 2 seconds for server to bind and DNS network to come fully online
    await asyncio.sleep(2)

    try:
        print("⏳ Background: Initializing HF API Embedding client...")
        embedding_model = HFEmbeddingClient(EMBEDDING_MODEL_NAME)

        corpus_texts = SAMPLE_CORPUS
        texts        = [item["text"] for item in corpus_texts]

        print("⏳ Background: Building FAISS index via HF API embeddings...")
        
        # Perform network call in a separate thread to keep server completely responsive
        loop = asyncio.get_running_loop()
        embeddings_numpy = await loop.run_in_executor(
            None, lambda: embedding_model.encode(texts, convert_to_numpy=True)
        )
        
        embeddings = embeddings_numpy.astype("float32")
        faiss_index = faiss.IndexFlatL2(embeddings.shape[1])  # dynamically use dimensions
        faiss_index.add(embeddings)

        print(f"✅ Background: FAISS index ready — {faiss_index.ntotal} vectors (dim: {embeddings.shape[1]})")
    except Exception as e:
        print(f"❌ Background: Error during resource loading: {str(e)}")
        print("⚠️ Falling back to local mock embeddings to initialize FAISS index...")
        import traceback
        traceback.print_exc()
        try:
            # Generate random mock embeddings of dimension 384 for the SAMPLE_CORPUS items
            mock_dim = 384
            embeddings = np.random.rand(len(corpus_texts), mock_dim).astype("float32")
            faiss_index = faiss.IndexFlatL2(mock_dim)
            faiss_index.add(embeddings)
            print(f"✅ Background: Fallback FAISS index initialized with {faiss_index.ntotal} mock vectors.")
        except Exception as fallback_err:
            print(f"❌ Critical: Fallback FAISS initialization failed: {str(fallback_err)}")


# ─────────────────────────────────────────────────────────────
# NLP / Risk Assessment Helpers
# ─────────────────────────────────────────────────────────────

def keyword_analysis(text: str) -> dict:
    """Return matched keywords per tier and weighted counts."""
    lower  = text.lower()
    tokens = set(re.findall(r"\b\w+\b", lower))

    matched_high   = [k for k in HIGH_RISK_KEYWORDS   if k in lower]
    matched_medium = [k for k in MEDIUM_RISK_KEYWORDS if k in lower]
    matched_low    = [k for k in LOW_RISK_KEYWORDS    if k in lower]

    match_counts = {
        "high":   len(matched_high),
        "medium": len(matched_medium),
        "low":    len(matched_low),
    }

    # Weighted score  (0–10 range)
    # Fix 1: increased per-keyword weights so even one high-risk keyword
    # produces a strong signal (was 3.0 / 1.5 / 0.5 — far too low)
    raw   = match_counts["high"] * 5.0 + match_counts["medium"] * 2.0 + match_counts["low"] * 0.5
    score = min(raw, 10.0)

    return {
        "matched_high":   matched_high,
        "matched_medium": matched_medium,
        "matched_low":    matched_low,
        "match_counts":   match_counts,
        "keyword_score":  round(score, 2),
    }


def sentiment_analysis(text: str, external_sentiment: float = 0.0) -> dict:
    """
    Lightweight rule-based sentiment scoring.
    Returns an adjusted score in [-1, 1] plus metadata.
    """
    lower  = text.lower()
    tokens = re.findall(r"\b\w+\b", lower)

    negation_detected = any(w in NEGATION_WORDS   for w in tokens)
    intensifier_boost = 0.15 if any(w in INTENSIFIER_WORDS for w in tokens) else 0.0

    # Fix 2: high-risk words now pull sentiment much harder than medium-risk words
    # (was treating both equally at -0.1 per hit — high-risk words were being diluted)
    medium_hits    = sum(1 for w in MEDIUM_RISK_KEYWORDS if w in lower)
    high_hits      = sum(1 for w in HIGH_RISK_KEYWORDS   if w in lower)
    base_sentiment = external_sentiment if external_sentiment != 0.0 else max(
        -1.0, -(0.1 * medium_hits + 0.35 * high_hits)
    )

    adjusted = base_sentiment - intensifier_boost
    if negation_detected:
        adjusted *= 0.5            # negation softens the signal
    adjusted = max(-1.0, min(1.0, adjusted))

    polarity = "negative" if adjusted < -0.2 else ("positive" if adjusted > 0.2 else "neutral")

    return {
        "base_sentiment":     round(base_sentiment,  4),
        "adjusted_sentiment": round(adjusted,         4),
        "negation_detected":  negation_detected,
        "intensifier_boost":  intensifier_boost,
        "polarity":           polarity,
        "sentiment_score":    round(min(abs(adjusted) * 10, 10.0), 2),
    }


def full_risk_assessment(text: str, sentiment: float = 0.0, label: int = 0) -> dict:
    """Combine keyword, sentiment, and label signals into a composite score."""
    kw   = keyword_analysis(text)
    sent = sentiment_analysis(text, sentiment)

    label_score = {0: 0.0, 1: 5.0, 2: 9.0}.get(label, 0.0)

    # Fix 3a: keywords now carry 60% weight — they are the most reliable signal.
    # Sentiment carries 25%, label 15%. Previously keywords were only 45% and
    # label was hardcoded 0 everywhere, permanently wasting 20% of the score.
    composite = round(
        kw["keyword_score"]       * 0.60
        + sent["sentiment_score"] * 0.25
        + label_score             * 0.15,
        2,
    )
    composite = min(composite, 10.0)

    # Fix 3b: hard overrides — the composite math alone is not enough when
    # label is always 0. These rules guarantee correct tier classification
    # regardless of weighting arithmetic.
    #
    # Rule 1: ANY single high-risk keyword  → composite must be at least 7.5
    if kw["match_counts"]["high"] >= 1:
        composite = max(composite, 7.5)

    # Rule 2: 2+ medium-risk keywords       → composite must be at least 4.0
    if kw["match_counts"]["medium"] >= 2 and composite < 4.0:
        composite = max(composite, 4.0)

    # Rule 3: 1 high-risk + 1 medium-risk   → push to critical range
    if kw["match_counts"]["high"] >= 1 and kw["match_counts"]["medium"] >= 1:
        composite = max(composite, 8.5)

    if composite >= 7.0:
        risk_level, risk_label = "high",   "High Risk"
    elif composite >= 4.0:
        risk_level, risk_label = "medium", "Moderate Risk"
    else:
        risk_level, risk_label = "low",    "Low Risk"

    return {
        "keyword_score":    kw["keyword_score"],
        "sentiment_score":  sent["sentiment_score"],
        "label_score":      label_score,
        "composite_score":  composite,
        "risk_level":       risk_level,
        "risk_label":       risk_label,
        "keyword_detail":   {
            "matched_high":   kw["matched_high"],
            "matched_medium": kw["matched_medium"],
            "matched_low":    kw["matched_low"],
            "match_counts":   kw["match_counts"],
        },
        "sentiment_detail": {
            "base_sentiment":     sent["base_sentiment"],
            "adjusted_sentiment": sent["adjusted_sentiment"],
            "negation_detected":  sent["negation_detected"],
            "intensifier_boost":  sent["intensifier_boost"],
            "polarity":           sent["polarity"],
        },
    }


# ─────────────────────────────────────────────────────────────
# FAISS Retrieval
# ─────────────────────────────────────────────────────────────

def retrieve_similar(query: str, top_k: int = 5) -> list[dict]:
    """Return top-k similar corpus entries via FAISS L2 search."""
    global embedding_model, faiss_index
    if embedding_model is None or faiss_index is None:
        print("⚠️ Warning: FAISS index or embedding model not yet loaded. Returning empty similarity results.")
        return []

    q_vec      = embedding_model.encode([query], convert_to_numpy=True).astype("float32")
    distances, indices = faiss_index.search(q_vec, min(top_k, faiss_index.ntotal))

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx == -1:
            continue
        entry = corpus_texts[idx].copy()
        entry["similarity_score"] = round(float(1 / (1 + dist)), 4)
        results.append(entry)
    return results


def generate_rag_response(query: str, top_k: int = 5) -> tuple[str, list[dict]]:
    """Retrieve similar posts and return a risk-aware RAG response."""
    similar    = retrieve_similar(query, top_k)
    assessment = full_risk_assessment(query)
    response   = RAG_RESPONSES.get(assessment["risk_level"], RAG_RESPONSES["low"])
    return response, similar


# ─────────────────────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────────────────────

class TextAnalysisRequest(BaseModel):
    text        : str            = Field(..., min_length=10)
    sentiment   : Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    include_rag : bool           = Field(default=False)
    top_k       : int            = Field(default=5, ge=1, le=20)

    model_config = {
        "json_schema_extra": {
            "example": {
                "text"       : "I feel completely hopeless and can't stop worrying",
                "sentiment"  : -0.75,
                "include_rag": True,
                "top_k"      : 5,
            }
        }
    }


class BatchAnalysisRequest(BaseModel):
    texts       : list[str] = Field(..., min_length=1)
    include_rag : bool      = Field(default=False)


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
    text            : str
    composite_score : float
    risk_level      : str
    risk_label      : str
    scores          : RiskScores
    keyword_detail  : KeywordDetail
    sentiment_detail: SentimentDetail
    rag_response    : Optional[str]        = None
    similar_posts   : Optional[list[dict]] = None


class BatchAnalysisResponse(BaseModel):
    total_analyzed: int
    results       : list[RiskAnalysisResponse]
    summary       : dict


class HealthResponse(BaseModel):
    status       : str
    model_loaded : bool
    index_loaded : bool
    total_vectors: int


# ─────────────────────────────────────────────────────────────
# Response Builder
# ─────────────────────────────────────────────────────────────

def build_response(
    text      : str,
    assessment: dict,
    rag_resp  : str        = None,
    similar   : list[dict] = None,
) -> RiskAnalysisResponse:
    return RiskAnalysisResponse(
        text             = text,
        composite_score  = assessment["composite_score"],
        risk_level       = assessment["risk_level"],
        risk_label       = assessment["risk_label"],
        scores           = RiskScores(
            keyword_score   = assessment["keyword_score"],
            sentiment_score = assessment["sentiment_score"],
            label_score     = assessment["label_score"],
            composite_score = assessment["composite_score"],
        ),
        keyword_detail   = KeywordDetail(**assessment["keyword_detail"]),
        sentiment_detail = SentimentDetail(**assessment["sentiment_detail"]),
        rag_response     = rag_resp,
        similar_posts    = similar,
    )


# ─────────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_store
    db_store = MonitorStorage()
    db_store.migrate()   # non-destructive: adds new columns to existing DBs
    
    # Run the internet-dependent embedding load in background so server binds to port immediately
    asyncio.create_task(load_resources_async())
    
    print("🚀 API starting in background resource-loading mode...")
    yield
    if db_store:
        db_store.close()
    print("🛑 API shutting down...")


# ─────────────────────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "Emotional Risk Analysis API",
    description = "Analyze text for emotional distress risk using NLP, FAISS retrieval, and rule-based insights.",
    version     = "1.0.0",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = False,   # Must be False when allow_origins is "*"
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ─────────────────────────────────────────────────────────────
# ENDPOINT 1 — Health Check
# ─────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    return HealthResponse(
        status        = "healthy",
        model_loaded  = embedding_model is not None,
        index_loaded  = faiss_index is not None and faiss_index.ntotal > 0,
        total_vectors = faiss_index.ntotal if faiss_index is not None else 0,
    )


# ─────────────────────────────────────────────────────────────
# ENDPOINT 2 — Analyze Single Text
# ─────────────────────────────────────────────────────────────

@app.post("/analyze", response_model=RiskAnalysisResponse, tags=["Analysis"])
async def analyze_text(request: TextAnalysisRequest,
                       user_id: str = Query(default="anonymous", description="User identifier for audit")):
    try:
        sentiment  = request.sentiment if request.sentiment is not None else 0.0
        assessment = full_risk_assessment(text=request.text, sentiment=sentiment, label=0)

        rag_resp, similar = None, None
        if request.include_rag:
            rag_resp, similar = generate_rag_response(request.text, top_k=request.top_k)

        # ── Audit log every inference ──────────────────────────────────────────
        if db_store:
            db_store.log_audit(
                user_id    = user_id,
                endpoint   = "/analyze",
                risk_level = assessment["risk_level"],
                score      = assessment["composite_score"],
                source     = "api",
            )
            db_store.insert_with_score("api", request.text, assessment)
            # Store in temporal context if user_id is provided
            if user_id != "anonymous":
                db_store.add_temporal_event(
                    user_id         = user_id,
                    risk_level      = assessment["risk_level"],
                    composite_score = assessment["composite_score"] / 10,
                    text            = request.text,
                )

        # ── Trigger crisis protocol if needed ────────────────────────────────
        if assessment["risk_level"] in ("high", "crisis"):
            crisis_engine.handle_crisis(
                user_id      = user_id,
                text         = request.text,
                score        = assessment["composite_score"] / 10,
                source       = "api",
                db_store     = db_store,
                watched_name = user_id,
            )

        return build_response(request.text, assessment, rag_resp, similar)

    except Exception as e:
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail      = f"Analysis failed: {str(e)}",
        )


# ─────────────────────────────────────────────────────────────
# ENDPOINT 3 — Batch Analysis
# ─────────────────────────────────────────────────────────────

@app.post("/analyze/batch", response_model=BatchAnalysisResponse, tags=["Analysis"])
async def analyze_batch(request: BatchAnalysisRequest):
    if len(request.texts) > 50:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail      = "Batch limit is 50 texts per request",
        )

    results = []
    for text in request.texts:
        try:
            assessment        = full_risk_assessment(text=text, sentiment=0.0)
            rag_resp, similar = None, None
            if request.include_rag:
                rag_resp, similar = generate_rag_response(text)
            results.append(build_response(text, assessment, rag_resp, similar))
        except Exception:
            continue

    scores = [r.composite_score for r in results]

    # Safe risk_counts — handles any risk_level value returned
    risk_counts: dict[str, int] = {}
    for r in results:
        risk_counts[r.risk_level] = risk_counts.get(r.risk_level, 0) + 1

    summary = {
        "total"      : len(results),
        "avg_score"  : round(float(np.mean(scores)), 2) if scores else 0.0,
        "max_score"  : round(float(np.max(scores)),  2) if scores else 0.0,
        "min_score"  : round(float(np.min(scores)),  2) if scores else 0.0,
        "risk_counts": risk_counts,
    }

    return BatchAnalysisResponse(
        total_analyzed = len(results),
        results        = results,
        summary        = summary,
    )


# ─────────────────────────────────────────────────────────────
# ENDPOINT 4 — Similar Posts
# ─────────────────────────────────────────────────────────────

@app.post("/similar", tags=["Retrieval"])
async def get_similar_posts(
    query: str = Query(..., min_length=1, description="Text to find similar posts for"),
    top_k: int = Query(default=5, ge=1, le=20),
):
    similar = retrieve_similar(query, top_k=top_k)
    return {"query": query, "top_k": top_k, "results": similar}


# ─────────────────────────────────────────────────────────────
# ENDPOINT 5 — RAG Query
# ─────────────────────────────────────────────────────────────

@app.post("/rag", tags=["RAG"])
async def rag_query(
    query: str = Query(..., min_length=1, description="Query for RAG retrieval"),
    top_k: int = Query(default=5, ge=1, le=20),
):
    try:
        response, similar = generate_rag_response(query, top_k=top_k)
        return {"query": query, "rag_response": response, "similar_posts": similar}
    except Exception as e:
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail      = f"RAG query failed: {str(e)}",
        )
    
    # ─────────────────────────────────────────────
# ENDPOINT 6 — Structured Assessment (new)
# ─────────────────────────────────────────────

class AssessmentInput(BaseModel):
    stress        : float = Field(5.0, ge=1, le=10)
    mood          : float = Field(5.0, ge=1, le=10)
    social        : float = Field(5.0, ge=1, le=10)
    sleep         : float = Field(7.0, ge=0, le=12)
    appetite      : float = Field(5.0, ge=1, le=10)
    concentration : float = Field(5.0, ge=1, le=10)
    activity      : float = Field(3.0, ge=0, le=7)
    substance     : float = Field(0.0, ge=0, le=10)

@app.post("/assess", tags=["Suggestion Engine"])
async def assess_indicators(input_data: AssessmentInput):
    from risk.classifier import classify
    from scoring.indicators import compute_scores

    raw = input_data.model_dump()
    scoring = compute_scores(raw)
    classification = classify(scoring)

    # ── Build tier-aware suggestion directly ──────────────────
    # Don't use generate_rag_response() — it re-scores the query
    # as text and always returns "low". Use the tier we already
    # computed from the indicators instead.

    TIER_SUGGESTIONS = {
        "LOW": {
            "summary": "Subclinical stress levels detected. Focus on maintaining healthy habits.",
            "actions": [
                "Practice 5–10 min daily mindfulness or breathing exercises",
                "Schedule one enjoyable social activity this week",
                "Maintain consistent sleep and wake times",
                "Take a 20-minute walk in a green space",
            ],
            "resources": [],
        },
        "MODERATE": {
            "summary": "Moderate anxiety/burnout indicators present. Structured self-help recommended.",
            "actions": [
                "Try box breathing (inhale 4 — hold 4 — exhale 4 — hold 4) daily",
                "Start a thought record: write triggering situations + automatic thoughts",
                "Schedule one rewarding activity per day (behavioral activation)",
                "Reset sleep hygiene: no screens 60 min before bed, fixed wake time",
                "Reach out to a trusted person or peer support group",
            ],
            "resources": ["Woebot or Sanvello app", "7 Cups (peer support)"],
        },
        "HIGH": {
            "summary": "Significant distress indicators across multiple domains. Professional support strongly recommended.",
            "actions": [
                "Book an appointment with a GP or mental health professional this week",
                "Use DBT TIPP skill for acute distress: cold water on face, intense exercise",
                "Build a personal safety plan: warning signs, coping strategies, contacts",
                "Establish a structured daily routine to reduce decision fatigue",
                "Request a blood panel to rule out thyroid/vitamin D issues",
            ],
            "resources": [
                "Psychology Today therapist finder",
                "BetterHelp or Talkspace",
                "SAMHSA helpline: 1-800-662-4357",
            ],
        },
        "CRISIS": {
            "summary": "Severe risk indicators detected. Immediate professional support is strongly advised.",
            "actions": [
                "Contact a crisis line right now — you do not have to face this alone",
                "Tell someone you trust where you are and how you are feeling",
                "Use 5-4-3-2-1 grounding: name 5 things you see, 4 you can touch, 3 you hear",
                "Go to your nearest emergency room if you feel unsafe",
            ],
            "resources": [
                "US: Call or text 988 (Suicide & Crisis Lifeline)",
                "Crisis Text Line: text HOME to 741741",
                "UK: Samaritans 116 123",
                "International: findahelpline.com",
            ],
        },
    }

    tier = classification.tier
    suggestion = TIER_SUGGESTIONS.get(tier, TIER_SUGGESTIONS["LOW"])

    # Still use your FAISS retrieval for similar cases
    similar = retrieve_similar(classification.rag_query, top_k=3)

    # ── Audit + temporal context ───────────────────────────────────────
    if db_store:
        db_store.log_audit(
            user_id    = "desktop",
            endpoint   = "/assess",
            risk_level = tier.lower(),
            score      = scoring.composite_score,
            source     = "desktop",
        )

    # ── Crisis protocol ─────────────────────────────────────────────
    if tier == "CRISIS":
        crisis_engine.handle_crisis(
            user_id      = "desktop",
            text         = classification.rag_query,
            score        = scoring.composite_score,
            source       = "desktop_assessment",
            db_store     = db_store,
            watched_name = "desktop",
        )

    return {
        "composite_score"      : scoring.composite_score,
        "anxiety_score"        : scoring.anxiety_score,
        "burnout_score"        : scoring.burnout_score,
        "tier"                 : tier,
        "dominant_factors"     : scoring.dominant_factors,
        "override_flags"       : classification.override_flags,
        "professional_referral": classification.tier_info["professional_referral"],
        "crisis_protocol"      : classification.tier_info["crisis_protocol"],
        "suggestion_summary"   : suggestion["summary"],
        "suggested_actions"    : suggestion["actions"],
        "resources"            : suggestion["resources"],
        "similar_cases"        : similar,
    }

# ─────────────────────────────────────────────
# ENDPOINT 7 — Live Score (no RAG, fast)
# ─────────────────────────────────────────────

@app.post("/assess/score", tags=["Suggestion Engine"])
async def score_indicators(input_data: AssessmentInput):
    """Fast scoring for real-time slider feedback — no RAG call."""
    from risk.classifier import classify
    from scoring.indicators import compute_scores

    raw = input_data.model_dump()
    scoring = compute_scores(raw)
    classification = classify(scoring)

    return {
        "composite_score"  : scoring.composite_score,
        "anxiety_score"    : scoring.anxiety_score,
        "burnout_score"    : scoring.burnout_score,
        "tier"             : classification.tier,
        "dominant_factors" : scoring.dominant_factors,
        "override_flags"   : classification.override_flags,
    }


# ─────────────────────────────────────────────────────────────
# ENDPOINT 8 — History (paginated captured events)
# ─────────────────────────────────────────────────────────────

@app.get("/history", tags=["History"])
async def get_history(
    limit      : int = Query(default=50, ge=1,  le=200),
    risk_level : Optional[str] = Query(default=None,
        description="Filter by risk level: none | low | medium | high | crisis"),
):
    """Return recent captured events from the SQLite store."""
    if db_store is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    if risk_level:
        rows = db_store.query_by_risk(risk_level, limit=limit)
    else:
        rows = db_store.query_recent(limit=limit)
    return {"total": len(rows), "rows": rows}


@app.get("/history/summary", tags=["History"])
async def get_history_summary():
    """Return aggregate stats from the SQLite captured_events table."""
    if db_store is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    return db_store.get_summary()


@app.get("/temporal/{user_id}", tags=["History"])
async def get_temporal_context(
    user_id : str,
    days    : int = Query(default=30, ge=1, le=90),
):
    """Return the rolling temporal risk context for a specific user."""
    if db_store is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    summary = db_store.get_temporal_summary(user_id, days=days)
    events  = db_store.get_temporal_window(user_id, days=days)
    return {
        "user_id"     : user_id,
        "window_days" : days,
        "summary"     : summary,
        "events"      : events,
    }


@app.get("/audit", tags=["Audit"])
async def get_audit_log(
    limit: int = Query(default=100, ge=1, le=500),
    key  : str = Security(api_key_header),
):
    """Return the audit log (API-key protected)."""
    if key != DESKTOP_APP_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if db_store is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    return {"rows": db_store.query_audit(limit=limit)}

# ─────────────────────────────────────────────────────────────
# AUTH / CONSENT / GUARDIAN ENDPOINTS
# ─────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username     : str  = Field(..., min_length=2, max_length=60)
    email        : str  = Field(..., min_length=5, max_length=120)
    display_name : str  = Field(default="",  max_length=80)
    country_code : str  = Field(default="GLOBAL", max_length=2)
    consent      : bool = Field(..., description="User must explicitly consent to monitoring")

    model_config = {"json_schema_extra": {"example": {
        "username"    : "alice",
        "email"       : "alice@example.com",
        "display_name": "Alice",
        "country_code": "NG",
        "consent"     : True,
    }}}


class GuardianRequest(BaseModel):
    user_id        : str = Field(...)
    guardian_email : str = Field(..., min_length=5)
    guardian_name  : str = Field(default="")
    relationship   : str = Field(default="guardian",
                                  description="e.g. parent, friend, counselor, guardian")


@app.post("/auth/register", tags=["Auth"])
async def register_user(req: RegisterRequest):
    """
    Register a new user and record their monitoring consent.
    Returns a stable user_id to store in the browser extension.
    """
    if not req.consent:
        raise HTTPException(
            status_code=400,
            detail="Consent is required to use MindGuard monitoring."
        )
    if db_store is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")

    import random
    import string
    # Generate a 6-character alphanumeric code for easy device linking
    user_id = 'ext:' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    db_store.save_consent(
        user_id      = user_id,
        username     = req.username,
        country_code = req.country_code,
        email        = req.email,
        display_name = req.display_name or req.username,
    )
    db_store.log_audit(
        user_id    = user_id,
        endpoint   = "/auth/register",
        risk_level = "none",
        score      = 0.0,
        source     = "browser_extension",
    )
    return {
        "user_id"      : user_id,
        "username"     : req.username,
        "display_name" : req.display_name or req.username,
        "consented"    : True,
        "message"      : "Registration successful. Monitoring is now active.",
    }


@app.get("/auth/me", tags=["Auth"])
async def get_user_profile(
    user_id: str = Query(..., description="User ID returned at registration")
):
    """Return the registered user profile for a given user_id."""
    if db_store is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    user = db_store.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Strip sensitive fields before returning
    user.pop("email", None)
    return user


@app.post("/auth/guardian", tags=["Auth"])
async def add_guardian(req: GuardianRequest):
    """
    Register a guardian (parent / friend / counselor) for a monitored user.
    The guardian will be emailed when a CRISIS event is detected.
    """
    if db_store is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    if not db_store.has_consented(req.user_id):
        raise HTTPException(
            status_code=404,
            detail="User not found or has not completed registration."
        )
    db_store.add_guardian(
        user_id        = req.user_id,
        guardian_email = req.guardian_email,
        guardian_name  = req.guardian_name,
        relationship   = req.relationship,
    )
    db_store.log_audit(
        user_id    = req.user_id,
        endpoint   = "/auth/guardian",
        risk_level = "none",
        score      = 0.0,
        source     = "browser_extension",
    )
    return {
        "user_id"        : req.user_id,
        "guardian_email" : req.guardian_email,
        "relationship"   : req.relationship,
        "message"        : f"Guardian {req.guardian_email!r} added. They will be notified on CRISIS events.",
    }


@app.delete("/auth/guardian", tags=["Auth"])
async def remove_guardian(
    user_id        : str = Query(...),
    guardian_email : str = Query(...),
):
    """Remove a guardian contact from a user's account."""
    if db_store is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    db_store.remove_guardian(user_id, guardian_email)
    return {"message": f"Guardian {guardian_email!r} removed."}


@app.get("/auth/guardians/{user_id}", tags=["Auth"])
async def list_guardians(user_id: str):
    """Return all registered guardians for a given user."""
    if db_store is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    guardians = db_store.get_guardians(user_id)
    return {"user_id": user_id, "guardians": guardians, "total": len(guardians)}


# ─────────────────────────────────────────────────────────────
# ADOLESCENT-FIRST ENDPOINTS (Age 10–24 Guardian-Ward Flow)
# ─────────────────────────────────────────────────────────────

class GuardianRegistrationRequest(BaseModel):
    """
    Step 1 — Parent/guardian creates their own account.
    Returns guardian_id which is used in Step 2.
    """
    guardian_name : str  = Field(..., min_length=2, max_length=80)
    guardian_email: str  = Field(..., min_length=5, max_length=120)
    country_code  : str  = Field(default="GLOBAL", max_length=6)
    consent       : bool = Field(..., description="Guardian confirms responsibility for the monitored device")

    model_config = {"json_schema_extra": {"example": {
        "guardian_name" : "Mrs Adaeze Obi",
        "guardian_email": "adaeze@example.com",
        "country_code"  : "NG",
        "consent"       : True,
    }}}


class WardRegistrationRequest(BaseModel):
    """
    Step 2 — Guardian links a child (ward) account.
    ward_dob is used to verify age 10–24.
    For wards aged 18–24, adult_aware_consent must also be True.
    """
    guardian_id       : str  = Field(..., description="guardian_id from Step 1")
    ward_name         : str  = Field(..., min_length=1, max_length=60)
    ward_dob          : str  = Field(..., description="ISO date YYYY-MM-DD (used for age validation)")
    relationship      : str  = Field(default="parent",
                                     description="parent | guardian | counselor | sibling")
    guardian_consent  : bool = Field(..., description="Guardian gives consent on behalf of the ward")
    adult_aware_consent: bool = Field(
        default=False,
        description="For wards 18–24: confirms the young adult is aware of and agrees to monitoring"
    )

    model_config = {"json_schema_extra": {"example": {
        "guardian_id"        : "AB12CD",
        "ward_name"          : "Emeka",
        "ward_dob"           : "2010-06-15",
        "relationship"       : "parent",
        "guardian_consent"   : True,
        "adult_aware_consent": False,
    }}}


def _compute_age(dob_str: str) -> int:
    """Parse YYYY-MM-DD and return age in whole years."""
    try:
        dob   = DateType.fromisoformat(dob_str)
        today = DateType.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date_of_birth. Use YYYY-MM-DD format.")


@app.post("/auth/guardian/register", tags=["Adolescent Auth"])
async def register_guardian(req: GuardianRegistrationRequest):
    """
    Step 1 — Parent/guardian creates a MindGuard guardian account.
    Returns guardian_id to use in Step 2 (ward registration).
    """
    if not req.consent:
        raise HTTPException(
            status_code=400,
            detail="Consent is required. The guardian must agree to take responsibility for monitoring."
        )
    if db_store is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")

    import random, string
    guardian_id = "G-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

    db_store.save_guardian_account(
        guardian_id  = guardian_id,
        name         = req.guardian_name,
        email        = req.guardian_email,
        country_code = req.country_code,
    )
    db_store.log_audit(
        user_id    = guardian_id,
        endpoint   = "/auth/guardian/register",
        risk_level = "none",
        score      = 0.0,
        source     = "browser_extension",
    )
    return {
        "guardian_id"   : guardian_id,
        "guardian_name" : req.guardian_name,
        "guardian_email": req.guardian_email,
        "message"       : "Guardian account created. Proceed to Step 2 to link your child's account.",
    }


@app.post("/auth/ward/register", tags=["Adolescent Auth"])
async def register_ward(req: WardRegistrationRequest):
    """
    Step 2 — Guardian links a ward (child aged 10–24).
    Validates age, enforces two-step consent for 18–24-year-olds,
    and returns the ward_id to store in the extension on the child's device.
    """
    if db_store is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")

    # Validate guardian exists
    guardian = db_store.get_guardian_account(req.guardian_id)
    if not guardian:
        raise HTTPException(
            status_code=404,
            detail="Guardian account not found. Complete Step 1 first (/auth/guardian/register)."
        )

    # Validate ward age 10–24
    age = _compute_age(req.ward_dob)
    if age < 10 or age > 24:
        raise HTTPException(
            status_code=400,
            detail=f"Ward age must be between 10 and 24. Computed age: {age} years."
        )

    # For 18–24: require the adult_aware_consent flag
    if age >= 18 and not req.adult_aware_consent:
        raise HTTPException(
            status_code=400,
            detail=(
                "The ward is 18 or older. adult_aware_consent must be True, confirming that "
                "the young adult is informed about and agrees to monitoring."
            )
        )

    if not req.guardian_consent:
        raise HTTPException(status_code=400, detail="Guardian consent is required to register a ward.")

    import random, string
    ward_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

    # Get guardian's country for localized crisis resources
    country = guardian.get("country_code", "GLOBAL")

    # Create the ward user session
    db_store.save_consent(
        user_id          = ward_id,
        username         = req.ward_name,
        display_name     = req.ward_name,
        country_code     = country,
        role             = "ward",
        date_of_birth    = req.ward_dob,
        guardian_user_id = req.guardian_id,
    )

    # Create the guardian ↔ ward link
    db_store.link_ward_to_guardian(
        guardian_id  = req.guardian_id,
        ward_id      = ward_id,
        ward_name    = req.ward_name,
        ward_dob     = req.ward_dob,
        relationship = req.relationship,
    )

    # Also add legacy guardian contact so crisis_engine still works
    guardian_email = guardian.get("email", "")
    if guardian_email:
        db_store.add_guardian(
            user_id        = ward_id,
            guardian_email = guardian_email,
            guardian_name  = guardian.get("display_name", ""),
            relationship   = req.relationship,
        )

    db_store.log_audit(
        user_id    = ward_id,
        endpoint   = "/auth/ward/register",
        risk_level = "none",
        score      = 0.0,
        source     = "browser_extension",
    )
    return {
        "ward_id"          : ward_id,
        "ward_name"        : req.ward_name,
        "ward_age"         : age,
        "guardian_id"      : req.guardian_id,
        "link_code"        : ward_id,
        "message"          : (
            f"{req.ward_name}'s monitoring account is active. "
            f"Install the extension on their device and enter Link Code: {ward_id}"
        ),
    }


@app.get("/auth/guardian/{guardian_id}/wards", tags=["Adolescent Auth"])
async def list_guardian_wards(guardian_id: str):
    """Return all wards linked to a guardian account."""
    if db_store is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    wards = db_store.get_linked_wards(guardian_id)
    return {"guardian_id": guardian_id, "wards": wards, "total": len(wards)}


@app.delete("/auth/ward/unlink", tags=["Adolescent Auth"])
async def unlink_ward(
    guardian_id : str = Query(...),
    ward_id     : str = Query(...),
):
    """Remove a guardian ↔ ward monitoring link."""
    if db_store is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    db_store.unlink_ward(guardian_id, ward_id)
    return {"message": f"Ward {ward_id!r} unlinked from guardian {guardian_id!r}."}


@app.get("/guardian/dashboard/{guardian_id}", tags=["Adolescent Auth"])
async def guardian_dashboard_data(guardian_id: str):
    """
    Returns aggregated monitoring data for all wards linked to a guardian.
    Used by the standalone guardian web dashboard.
    """
    if db_store is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")

    guardian = db_store.get_guardian_account(guardian_id)
    if not guardian:
        raise HTTPException(status_code=404, detail="Guardian account not found.")

    wards = db_store.get_linked_wards(guardian_id)
    ward_data = []
    for w in wards:
        wid    = w["ward_id"]
        temporal  = db_store.get_temporal_summary(wid, days=14)
        crises    = db_store.get_crisis_events(wid, limit=5)
        escalating = db_store.detect_escalation(wid)
        ward_data.append({
            "ward_id"         : wid,
            "ward_name"       : w["ward_name"],
            "ward_dob"        : w["ward_dob"],
            "relationship"    : w["relationship"],
            "linked_at"       : w["linked_at"],
            "monitoring_active": w.get("monitoring_active", 1),
            "temporal_summary": temporal,
            "recent_crises"   : crises,
            "escalating"      : escalating,
        })

    return {
        "guardian_id"   : guardian_id,
        "guardian_name" : guardian.get("display_name", ""),
        "guardian_email": guardian.get("email", ""),
        "total_wards"   : len(wards),
        "wards"         : ward_data,
    }


@app.get("/dashboard", response_class=HTMLResponse, tags=["Guardian Dashboard"])
async def serve_guardian_dashboard():
    """Serve the standalone guardian web dashboard HTML page."""
    import os
    dashboard_path = os.path.join(os.path.dirname(__file__), "guardian_dashboard.html")
    if not os.path.exists(dashboard_path):
        raise HTTPException(status_code=404, detail="Dashboard file not found.")
    with open(dashboard_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ─────────────────────────────────────────────────────────────
# ANALYZE/CONTEXT — Rolling Context Window
# ─────────────────────────────────────────────────────────────

class ContextWindowRequest(BaseModel):
    user_id       : str             = Field(...)
    texts         : list[str]       = Field(..., min_length=1,
                                            description="Last N text flushes (newest last)")
    session_avg   : Optional[float] = Field(default=None, ge=0.0, le=10.0,
                                            description="Pre-computed avg score from extension")
    session_max   : Optional[float] = Field(default=None, ge=0.0, le=10.0)
    session_count : Optional[int]   = Field(default=None, ge=0)
    window_days   : int             = Field(default=14, ge=1, le=30)


@app.post("/analyze/context", tags=["Analysis"])
async def analyze_context_window(req: ContextWindowRequest):
    """
    Evaluate a rolling context window of text flushes.

    Accepts the last N flushed texts from the browser extension (the extension
    pre-filters to the last 5 raw texts to keep payload small) plus optional
    pre-aggregated session statistics covering up to 14 days.

    Returns:
      - Per-text risk scores
      - Window aggregate (avg, max, trend)
      - Backend temporal summary (if user is registered)
      - Whether escalation is detected
    """
    if db_store is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")

    results = []
    for text in req.texts[-5:]:   # cap at last 5 to bound payload
        if text and len(text.strip()) >= 10:
            assessment = full_risk_assessment(text=text, sentiment=0.0)
            results.append({
                "text"           : text[:200],
                "composite_score": assessment["composite_score"],
                "risk_level"     : assessment["risk_level"],
            })
            # Store each text in temporal context
            db_store.add_temporal_event(
                user_id         = req.user_id,
                risk_level      = assessment["risk_level"],
                composite_score = assessment["composite_score"] / 10,
                text            = text,
            )

    # Merge extension-side aggregates with fresh scores
    scores    = [r["composite_score"] for r in results]
    live_avg  = round(sum(scores) / len(scores), 2) if scores else 0.0
    live_max  = round(max(scores), 2) if scores else 0.0

    # Backend temporal summary (up to window_days)
    temporal  = db_store.get_temporal_summary(req.user_id, days=req.window_days)
    escalating = db_store.detect_escalation(req.user_id)

    # Merged aggregate (extension stats + live scores)
    merged_avg = live_avg
    merged_max = live_max
    if req.session_avg is not None:
        merged_avg = round((live_avg + req.session_avg) / 2, 2)
    if req.session_max is not None:
        merged_max = round(max(live_max, req.session_max), 2)

    # Trigger crisis if merged_max is critical and user is registered
    if merged_max >= 7.5:
        user_rec = db_store.get_user(req.user_id)
        name     = (user_rec or {}).get("display_name", req.user_id)
        crisis_engine.handle_crisis(
            user_id      = req.user_id,
            text         = req.texts[-1] if req.texts else "",
            score        = merged_max / 10,
            source       = "browser_extension_context",
            db_store     = db_store,
            watched_name = name,
        )

    db_store.log_audit(
        user_id    = req.user_id,
        endpoint   = "/analyze/context",
        risk_level = "high" if merged_max >= 7.0 else "medium" if merged_max >= 4.0 else "low",
        score      = merged_max,
        source     = "browser_extension",
    )

    return {
        "user_id"         : req.user_id,
        "live_results"    : results,
        "live_avg"        : live_avg,
        "live_max"        : live_max,
        "merged_avg"      : merged_avg,
        "merged_max"      : merged_max,
        "session_count"   : req.session_count,
        "temporal_summary": temporal,
        "escalating"      : escalating,
        "crisis_triggered": merged_max >= 7.5,
    }


# ─────────────────────────────────────────────────────────────
# CRISIS HISTORY — Guardian-facing event log
# ─────────────────────────────────────────────────────────────

@app.get("/crisis/history/{user_id}", tags=["Crisis"])
async def get_crisis_history(
    user_id : str,
    limit   : int = Query(default=20, ge=1, le=100),
):
    """
    Return the stored CRISIS events for a user.
    Intended for guardian dashboards to review past alerts.
    """
    if db_store is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    events = db_store.get_crisis_events(user_id, limit=limit)
    return {
        "user_id" : user_id,
        "total"   : len(events),
        "events"  : events,
    }


#
# Flow:
#   1. Desktop app connects to ws://localhost:8000/ws/analyze
#   2. Client sends JSON matching WSAnalysisPayload schema
#   3. Server validates the API key embedded in the message
#   4. Server streams back JSON progress events then final result
#   5. On error: {"event": "error", "detail": "..."}
#
# WHY accept() is called manually here:
#   PyQt6 desktop apps send no Origin header. FastAPI's CORS
#   middleware sees Origin=None and returns 403 Forbidden before
#   the handler runs. Calling websocket.accept() first bypasses
#   that check and lets the connection through.
# ─────────────────────────────────────────────────────────────

class WSAnalysisPayload(BaseModel):
    """Schema for messages received over the WebSocket connection."""
    text        : str             = Field(..., min_length=1)
    sentiment   : Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    include_rag : bool            = Field(default=False)
    top_k       : int             = Field(default=5, ge=1, le=20)
    api_key     : str             = Field(..., description="Desktop app API key for WS auth")


@app.websocket("/ws/analyze")
async def ws_analyze(websocket: WebSocket):
    # ── Manually accept BEFORE middleware origin check ────────
    # This is the fix for the 403 Forbidden error. PyQt6 desktop
    # clients send no Origin header so CORS blocks them. Accepting
    # manually here lets the connection through before that check.
    await websocket.accept()
    await manager.connect(websocket)

    try:
        while True:
            raw_message = await websocket.receive_text()

            # ── Parse & validate payload ──────────────────────
            try:
                payload = WSAnalysisPayload(**json.loads(raw_message))
            except Exception:
                await manager.send_json(websocket, {
                    "event" : "error",
                    "detail": "Invalid payload. Expected JSON matching WSAnalysisPayload schema.",
                })
                continue

            # ── Authenticate via key inside message ───────────
            if payload.api_key != DESKTOP_APP_API_KEY:
                await manager.send_json(websocket, {
                    "event" : "error",
                    "detail": "Unauthorized — invalid API key.",
                })
                continue

            # ── Stage 1: Keyword analysis ─────────────────────
            await manager.send_json(websocket, {"event": "progress", "stage": "keyword"})
            await asyncio.sleep(0)

            sentiment = payload.sentiment if payload.sentiment is not None else 0.0
            kw_result = keyword_analysis(payload.text)

            # ── Stage 2: Sentiment analysis ───────────────────
            await manager.send_json(websocket, {"event": "progress", "stage": "sentiment"})
            await asyncio.sleep(0)

            sent_result = sentiment_analysis(payload.text, sentiment)

            # ── Stage 3: Composite risk score ─────────────────
            await manager.send_json(websocket, {"event": "progress", "stage": "scoring"})
            await asyncio.sleep(0)

            assessment = full_risk_assessment(payload.text, sentiment)

            # ── Stage 4: Optional RAG retrieval ───────────────
            rag_resp, similar = None, None
            if payload.include_rag:
                await manager.send_json(websocket, {"event": "progress", "stage": "rag"})
                await asyncio.sleep(0)
                rag_resp, similar = generate_rag_response(payload.text, top_k=payload.top_k)

            # ── Stage 5: Build & stream final result ──────────
            response = build_response(payload.text, assessment, rag_resp, similar)

            await manager.send_json(websocket, {
                "event": "result",
                "data" : response.model_dump(),
            })

            await manager.send_json(websocket, {"event": "done"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("WebSocket client disconnected")

    except Exception as e:
        try:
            await manager.send_json(websocket, {"event": "error", "detail": str(e)})
        except Exception:
            pass
        manager.disconnect(websocket)


# ─────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)