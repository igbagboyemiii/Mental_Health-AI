# =============================================================================
# COMPLETE API — Single Cell, No External Imports
# =============================================================================

import os
import re
import time
import socket
import threading
import numpy as np
import pandas as pd
import faiss
import tiktoken
import uvicorn
import nest_asyncio
from dotenv                  import load_dotenv
from openai                  import OpenAI
from sentence_transformers   import SentenceTransformer
from pydantic                import BaseModel, Field
from typing                  import Optional
from fastapi                 import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib              import asynccontextmanager
from collections             import defaultdict

load_dotenv()
nest_asyncio.apply()

print("✅ Step 1/7 — Imports done")

# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────

GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
EMBED_MODEL     = "all-MiniLM-L6-v2"
LLM_MODEL       = "llama-3.3-70b-versatile"
MAX_CTX_TOKENS  = 6000
TOP_K           = 5
EMBEDDINGS_PATH = "dreaddit_embeddings.npy"
INDEX_PATH      = "dreaddit_embedding_index.csv"
RISK_THRESHOLDS = {"high": 65,  "medium": 35}
RISK_WEIGHTS    = {"high": 3.0, "medium": 2.0, "low": 1.0}
SCORE_WEIGHTS   = {"keyword": 0.50, "sentiment": 0.30, "label": 0.20}
RISK_LABELS     = {"high": "🔴 HIGH", "medium": "🟡 MEDIUM", "low": "🟢 LOW"}

print("✅ Step 2/7 — Constants defined")

# ─────────────────────────────────────────────────────────────
# RISK ENGINE
# ─────────────────────────────────────────────────────────────

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
    kw          = keyword_risk_score(text)
    kw_score    = min(kw["normalized_score"] * 10, 100)
    sent        = sentiment_risk_score(text, sentiment)
    sent_score  = ((1.0 - sent["adjusted_sentiment"]) / 2.0) * 100
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

print("✅ Step 3/7 — Risk engine ready")

# ─────────────────────────────────────────────────────────────
# RAG PIPELINE
# ─────────────────────────────────────────────────────────────

embedder    = SentenceTransformer(EMBED_MODEL)
embeddings  = np.load(EMBEDDINGS_PATH).astype("float32")
df_index    = pd.read_csv(INDEX_PATH, index_col=0)
encoding    = tiktoken.get_encoding("cl100k_base")
EMB_DIM     = embeddings.shape[1]
faiss_index = faiss.IndexFlatIP(EMB_DIM)
faiss_index.add(embeddings)

client = OpenAI(
    api_key  = GROQ_API_KEY,
    base_url = "https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = """You are an empathetic mental health assistant analyzing
emotional distress in Reddit posts. Base your response strictly on the
retrieved context. Always recommend professional help when appropriate.
You are an AI — be transparent about this."""

def count_tokens(text: str) -> int:
    return len(encoding.encode(text))

def retrieve_similar(query: str, top_k: int = TOP_K) -> list[dict]:
    q_emb = embedder.encode(
        [query], convert_to_numpy=True, normalize_embeddings=True
    ).astype("float32")
    scores, indices = faiss_index.search(q_emb, top_k)
    return [
        {
            "rank"      : rank,
            "text"      : df_index["text"].iloc[idx],
            "similarity": round(float(score), 4)
        }
        for rank, (idx, score) in enumerate(
            zip(indices[0], scores[0]), start=1
        )
    ]

def build_context(docs: list[dict]) -> str:
    parts        = []
    total_tokens = 0
    for doc in docs:
        snippet     = (f"[Post {doc['rank']} | "
                       f"Sim: {doc['similarity']}]\n{doc['text'].strip()}")
        token_count = count_tokens(snippet)
        if total_tokens + token_count > MAX_CTX_TOKENS:
            break
        parts.append(snippet)
        total_tokens += token_count
    return "\n\n---\n\n".join(parts)

def generate_rag_response(query: str,
                          top_k: int = TOP_K) -> tuple[str, list[dict]]:
    docs     = retrieve_similar(query, top_k)
    context  = build_context(docs)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": (
            f'Query: """{query}"""\n\n'
            f"Context:\n---\n{context}\n---\n\n"
            f"Provide an empathetic, grounded response."
        )}
    ]
    response = client.chat.completions.create(
        model       = LLM_MODEL,
        messages    = messages,
        temperature = 0.3,
        max_tokens  = 512
    )
    return response.choices[0].message.content.strip(), docs

print("✅ Step 4/7 — RAG pipeline ready")
print(f"   FAISS vectors : {faiss_index.ntotal}")
print(f"   Embeddings    : {embeddings.shape}")

# ─────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────────────────────

class TextAnalysisRequest(BaseModel):
    text        : str             = Field(..., min_length=10)
    sentiment   : Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    include_rag : bool            = Field(default=False)
    top_k       : int             = Field(default=5, ge=1, le=20)

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
    status        : str
    model_loaded  : bool
    index_loaded  : bool
    total_vectors : int

print("✅ Step 5/7 — Schemas defined")

# ─────────────────────────────────────────────────────────────
# FASTAPI APP + ENDPOINTS
# ─────────────────────────────────────────────────────────────

def build_response(text      : str,
                   assessment: dict,
                   rag_resp  : str        = None,
                   similar   : list[dict] = None) -> RiskAnalysisResponse:
    return RiskAnalysisResponse(
        text             = text,
        composite_score  = assessment["composite_score"],
        risk_level       = assessment["risk_level"],
        risk_label       = assessment["risk_label"],
        scores           = RiskScores(
            keyword_score   = assessment["keyword_score"],
            sentiment_score = assessment["sentiment_score"],
            label_score     = assessment["label_score"],
            composite_score = assessment["composite_score"]
        ),
        keyword_detail   = KeywordDetail(**assessment["keyword_detail"]),
        sentiment_detail = SentimentDetail(**assessment["sentiment_detail"]),
        rag_response     = rag_resp,
        similar_posts    = similar
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 API starting up...")
    yield
    print("🛑 API shutting down...")

app = FastAPI(
    title       = "Emotional Risk Analysis API",
    description = "Analyze text for emotional distress using NLP + LLM",
    version     = "1.0.0",
    lifespan    = lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"]
)

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    return HealthResponse(
        status        = "healthy",
        model_loaded  = True,
        index_loaded  = faiss_index.ntotal > 0,
        total_vectors = faiss_index.ntotal
    )

@app.post("/analyze", response_model=RiskAnalysisResponse, tags=["Analysis"])
async def analyze_text(request: TextAnalysisRequest):
    try:
        sentiment  = request.sentiment if request.sentiment is not None else 0.0
        assessment = full_risk_assessment(
            text=request.text, sentiment=sentiment, label=0
        )
        rag_resp, similar = None, None
        if request.include_rag:
            rag_resp, similar = generate_rag_response(
                request.text, top_k=request.top_k
            )
        return build_response(request.text, assessment, rag_resp, similar)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/analyze/batch", response_model=BatchAnalysisResponse, tags=["Analysis"])
async def analyze_batch(request: BatchAnalysisRequest):
    if len(request.texts) > 50:
        raise HTTPException(status_code=400, detail="Batch limit is 50 texts")
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
    scores      = [r.composite_score for r in results]
    risk_counts = {"high": 0, "medium": 0, "low": 0}
    for r in results:
        risk_counts[r.risk_level] += 1
    summary = {
        "total"      : len(results),
        "avg_score"  : round(float(np.mean(scores)), 2) if scores else 0,
        "max_score"  : round(float(np.max(scores)),  2) if scores else 0,
        "min_score"  : round(float(np.min(scores)),  2) if scores else 0,
        "risk_counts": risk_counts
    }
    return BatchAnalysisResponse(
        total_analyzed=len(results), results=results, summary=summary
    )

@app.post("/similar", tags=["Retrieval"])
async def get_similar_posts(query: str, top_k: int = 5):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    return {"query": query, "top_k": top_k,
            "results": retrieve_similar(query, top_k=top_k)}

@app.post("/rag", tags=["RAG"])
async def rag_query(query: str, top_k: int = 5):
    try:
        response, similar = generate_rag_response(query, top_k=top_k)
        return {"query": query, "rag_response": response, "similar_posts": similar}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG failed: {str(e)}")

print("✅ Step 6/7 — FastAPI app + endpoints defined")

# ─────────────────────────────────────────────────────────────
# START SERVER
# ─────────────────────────────────────────────────────────────

config = uvicorn.Config(
    app       = app,
    host      = "0.0.0.0",
    port      = 8000,
    loop      = "asyncio",
    log_level = "info"
)

server = uvicorn.Server(config)
thread = threading.Thread(target=server.run, daemon=True)
thread.start()

# Wait for server to start
for i in range(10):
    time.sleep(1)
    sock   = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("localhost", 8000))
    sock.close()
    if result == 0:
        print(f"✅ Step 7/7 — Server started after {i+1}s")
        print("📖 Swagger UI   → http://localhost:8000/docs")
        print("🔍 Health check → http://localhost:8000/health")
        break
    print(f"   Waiting for server... ({i+1}s)")
else:
    print("❌ Server failed to start — check errors above")
