import httpx

BASE_URL = "http://localhost:8000"

resp = httpx.get(f"{BASE_URL}/health", timeout=10)
print("✅ HEALTH:", resp.json())

resp = httpx.post(f"{BASE_URL}/analyze", json={
    "text"      : "I feel hopeless and can't stop having panic attacks",
    "sentiment" : -0.75,
    "include_rag": False
}, timeout=30)
print("✅ ANALYZE:", resp.json()["risk_label"], "|", resp.json()["composite_score"])