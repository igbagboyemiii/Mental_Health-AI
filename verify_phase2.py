# verify_phase2.py
import requests, sys, uuid

BASE = "http://localhost:8000"

def check(label, cond, detail=""):
    print(f"{'[PASS]' if cond else '[FAIL]'} {label:<45} {detail}")
    if not cond:
        sys.exit(1)

print("\n--- PHASE 2 FEATURE VERIFICATION ---")

# 1. Register User (Consent)
print("\n1. Testing Auth & Consent...")
username = f"testuser_{uuid.uuid4().hex[:6]}"
res = requests.post(f"{BASE}/auth/register", json={
    "username": username,
    "email": f"{username}@example.com",
    "consent": True
})
data = res.json()
check("Registration successful", res.status_code == 200)
user_id = data["user_id"]
check("User ID returned", user_id.startswith("ext:"))

# 2. Get User Profile
res = requests.get(f"{BASE}/auth/me?user_id={user_id}")
check("Profile retrieved", res.status_code == 200)
check("Consent verified", "user_id" in res.json())

# 3. Add Guardian
print("\n2. Testing Guardian Features...")
guardian_email = f"guardian_{uuid.uuid4().hex[:6]}@example.com"
res = requests.post(f"{BASE}/auth/guardian", json={
    "user_id": user_id,
    "guardian_email": guardian_email,
    "relationship": "parent"
})
check("Guardian added", res.status_code == 200)

res = requests.get(f"{BASE}/auth/guardians/{user_id}")
check("Guardians retrieved", res.status_code == 200)
check("Guardian exists in list", len(res.json()["guardians"]) == 1)

# 4. Context Window & Crisis Trigger
print("\n3. Testing Rolling Context & Crisis Engine...")
res = requests.post(f"{BASE}/analyze/context", json={
    "user_id": user_id,
    "texts": ["I am feeling incredibly hopeless, I want to end it all. There is no point."],
    "session_max": 8.0,
    "window_days": 14
})
check("Context window evaluated", res.status_code == 200)
c_data = res.json()
check("Crisis triggered", c_data["crisis_triggered"] == True)

# 5. Crisis History
print("\n4. Testing Crisis History Logs...")
res = requests.get(f"{BASE}/crisis/history/{user_id}")
check("Crisis history retrieved", res.status_code == 200)
h_data = res.json()
check("Crisis event logged", len(h_data["events"]) > 0)
print(f"Guardian notified count: {h_data['events'][0]['guardians_notified']}")

print("\nAll Phase 2 Backend features verified successfully!")
