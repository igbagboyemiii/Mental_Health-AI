import os
from dotenv import load_dotenv

load_dotenv()

# ── Model settings ────────────────────────────────────────────
EMBED_MODEL    = "all-MiniLM-L6-v2"
LLM_MODEL      = "llama-3.3-70b-versatile"
MAX_CTX_TOKENS = 6000
TOP_K          = 5

# ── Risk thresholds ───────────────────────────────────────────
RISK_THRESHOLDS = {"high": 65, "medium": 35}

RISK_WEIGHTS = {"high": 3.0, "medium": 2.0, "low": 1.0}

SCORE_WEIGHTS = {"keyword": 0.50, "sentiment": 0.30, "label": 0.20}

# ── API keys ──────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ── File paths ────────────────────────────────────────────────
EMBEDDINGS_PATH = "dreaddit_embeddings.npy"
INDEX_PATH      = "dreaddit_embedding_index.csv"

print("✅ Config loaded")
