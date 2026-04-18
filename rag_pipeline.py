# rag_pipeline.py contents — paste this entire cell
# ─────────────────────────────────────────────────────────────
# STEP 4: RAG Pipeline
# ─────────────────────────────────────────────────────────────

import os
import numpy as np
import pandas as pd
import faiss
import tiktoken
from dotenv                import load_dotenv
from openai                import OpenAI
from sentence_transformers import SentenceTransformer

# ── Load .env ─────────────────────────────────────────────────
load_dotenv()

# ── Inline constants (replaces config import) ─────────────────
EMBED_MODEL     = "all-MiniLM-L6-v2"
LLM_MODEL       = "llama-3.3-70b-versatile"
MAX_CTX_TOKENS  = 6000
TOP_K           = 5
GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
EMBEDDINGS_PATH = "dreaddit_embeddings.npy"
INDEX_PATH      = "dreaddit_embedding_index.csv"

# ── Load assets once ──────────────────────────────────────────
print("⚙️  Loading RAG pipeline assets...")

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

print(f"✅ Embedder loaded   : {EMBED_MODEL}")
print(f"✅ FAISS index ready : {faiss_index.ntotal} vectors")
print(f"✅ LLM model         : {LLM_MODEL}")
print(f"✅ Groq API key      : {GROQ_API_KEY[:8]}...{GROQ_API_KEY[-4:]}")


# ── Helper functions ──────────────────────────────────────────

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
    """
    Full RAG: retrieve → build context → call LLM.
    Returns (llm_response, similar_posts)
    """
    docs    = retrieve_similar(query, top_k)
    context = build_context(docs)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": (
            f'Query: """{query}"""\n\n'
            f"Context:\n---\n{context}\n---\n\n"
            f"Provide an empathetic, grounded response based on the context."
        )}
    ]

    response = client.chat.completions.create(
        model       = LLM_MODEL,
        messages    = messages,
        temperature = 0.3,
        max_tokens  = 512
    )

    return response.choices[0].message.content.strip(), docs


# ── Quick test (only runs when executed directly) ────────────────────────
if __name__ == "__main__":
    print("\n⚙️  Testing RAG pipeline...")
    test_response, test_docs = generate_rag_response(
        "I feel overwhelmed and can't stop worrying", top_k=3
    )
    print(f"\n✅ RAG test successful")
    print(f"   Retrieved : {len(test_docs)} posts")
    print(f"   Response  : {test_response[:150]}...")