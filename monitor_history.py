# check_history.py  — run this anytime to see saved data
from monitor_storage import MonitorStorage

db = MonitorStorage()

print("=== RECENT CAPTURES ===")
for row in db.query_recent(limit=10):
    print(f"[{row['timestamp']}] {row['source']} | "
          f"{row['risk_label']} ({row['composite_score']}) | "
          f"{row['raw_text'][:60]}")

print("\n=== HIGH RISK ONLY ===")
for row in db.query_high_risk():
    print(f"[{row['timestamp']}] {row['raw_text'][:80]}")

print("\n=== SUMMARY ===")
print(db.get_summary())

db.close()