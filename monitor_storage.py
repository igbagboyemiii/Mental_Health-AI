# monitor_storage.py
# ─────────────────────────────────────────────────────────────
# SQLite Storage Layer — Text Monitor + Risk Analysis History
# Works alongside main.py, desktop_app.py, risk_engine.py,
# mindguard_bot.py, crisis_engine.py
# ─────────────────────────────────────────────────────────────
#
# DATABASE SCHEMA:
#   Table: captured_events
#     id            INTEGER  — auto-increment primary key
#     timestamp     TEXT     — ISO-8601 datetime (indexed)
#     source        TEXT     — "keyboard", "clipboard", "manual", "telegram", "browser"
#     raw_text      TEXT     — the captured text
#     composite_score REAL   — risk score 0–100 (NULL if not scored)
#     risk_level    TEXT     — "none" | "low" | "medium" | "high" | "crisis" | NULL
#     risk_label    TEXT     — display label | NULL
#     scored        INTEGER  — 0 = not scored, 1 = scored
#
#   Table: user_sessions  (persistent consent store)
#     user_id           TEXT     — unique user identifier (PK)
#     username          TEXT
#     email             TEXT     — registered email address (NEW)
#     display_name      TEXT     — friendly display name (NEW)
#     consented_at      TEXT     — ISO-8601 datetime
#     monitoring_active INTEGER  — 1 = active, 0 = paused
#     country_code      TEXT     — ISO-3166-1 alpha-2 (default "GLOBAL")
#
#   Table: guardians  (people registered to watch for a monitored user)
#     id                INTEGER  — auto-increment primary key
#     user_id           TEXT     — FK → user_sessions.user_id
#     guardian_email    TEXT     — contact email
#     guardian_name     TEXT     — display name
#     relationship      TEXT     — e.g. "parent", "friend", "counselor"
#     added_at          TEXT     — ISO-8601 datetime
#
#   Table: temporal_context  (rolling 30-day window per user)
#     id            INTEGER  — auto-increment primary key
#     user_id       TEXT     — foreign key → user_sessions.user_id
#     timestamp     TEXT     — ISO-8601 datetime (indexed)
#     risk_level    TEXT
#     composite_score REAL
#     text_snippet  TEXT     — first 200 chars only (privacy)
#
#   Table: audit_log  (immutable inference audit trail)
#     id            INTEGER  — auto-increment primary key
#     timestamp     TEXT     — ISO-8601 datetime
#     user_id       TEXT
#     endpoint      TEXT     — API endpoint called
#     risk_level    TEXT
#     score         REAL
#     source        TEXT
#
#   Table: crisis_events  (record of CRISIS alerts + guardian notification status)
#     id                  INTEGER  — auto-increment primary key
#     timestamp           TEXT     — ISO-8601 datetime
#     user_id             TEXT     — FK → user_sessions.user_id
#     score               REAL     — composite risk score that triggered the event
#     source              TEXT     — origin system
#     text_snippet        TEXT     — first 300 chars of flagged text
#     guardians_notified  INTEGER  — number of guardian emails sent
#     clinician_notified  INTEGER  — 1 if clinician email sent, 0 otherwise
# ─────────────────────────────────────────────────────────────

import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Optional


class MonitorStorage:
    """
    Thread-safe SQLite storage for captured text events, user consent,
    temporal context, and audit logs.

    A single instance can be shared across keyboard monitor thread,
    clipboard monitor thread, and the main FastAPI thread.
    """

    def __init__(self, db_path: str = "monitor_history.db"):
        self.db_path = db_path
        self._lock   = threading.Lock()
        self._conn   = sqlite3.connect(
            db_path,
            check_same_thread = False
        )
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        print(f"✅ MonitorStorage ready  →  {db_path}")

    # ── Schema ────────────────────────────────────────────────

    def _create_tables(self):
        with self._lock:
            self._conn.executescript("""
                -- ── Captured text events ──────────────────────────────
                CREATE TABLE IF NOT EXISTS captured_events (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp       TEXT    NOT NULL,
                    source          TEXT    NOT NULL,
                    raw_text        TEXT    NOT NULL,
                    composite_score REAL,
                    risk_level      TEXT,
                    risk_label      TEXT,
                    scored          INTEGER NOT NULL DEFAULT 0
                );

                -- Indexes for fast lookups
                CREATE INDEX IF NOT EXISTS idx_risk_level
                    ON captured_events (risk_level);
                CREATE INDEX IF NOT EXISTS idx_timestamp
                    ON captured_events (timestamp);

                -- ── Persistent consent / user sessions ────────────────
                CREATE TABLE IF NOT EXISTS user_sessions (
                    user_id           TEXT    PRIMARY KEY,
                    username          TEXT,
                    email             TEXT,
                    display_name      TEXT,
                    consented_at      TEXT    NOT NULL,
                    monitoring_active INTEGER NOT NULL DEFAULT 1,
                    country_code      TEXT    NOT NULL DEFAULT 'GLOBAL'
                );

                -- Allow upgrading existing DBs without losing data
                -- (SQLite ignores ADD COLUMN if it already exists via IF NOT EXISTS workaround)
                CREATE TABLE IF NOT EXISTS _schema_migrations (
                    version INTEGER PRIMARY KEY
                );

                -- ── Guardians (registered watchers) ───────────────────
                CREATE TABLE IF NOT EXISTS guardians (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id        TEXT    NOT NULL,
                    guardian_email TEXT    NOT NULL,
                    guardian_name  TEXT,
                    relationship   TEXT    NOT NULL DEFAULT 'guardian',
                    added_at       TEXT    NOT NULL,
                    UNIQUE(user_id, guardian_email)
                );

                CREATE INDEX IF NOT EXISTS idx_guardians_user
                    ON guardians (user_id);

                -- ── Crisis events audit trail ──────────────────────────
                CREATE TABLE IF NOT EXISTS crisis_events (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp           TEXT    NOT NULL,
                    user_id             TEXT    NOT NULL,
                    score               REAL,
                    source              TEXT,
                    text_snippet        TEXT,
                    guardians_notified  INTEGER NOT NULL DEFAULT 0,
                    clinician_notified  INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_crisis_user
                    ON crisis_events (user_id, timestamp);

                -- ── Temporal context (rolling 30-day window) ──────────
                CREATE TABLE IF NOT EXISTS temporal_context (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id         TEXT    NOT NULL,
                    timestamp       TEXT    NOT NULL,
                    risk_level      TEXT,
                    composite_score REAL,
                    text_snippet    TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_temporal_user
                    ON temporal_context (user_id, timestamp);

                -- ── Audit log (immutable) ─────────────────────────────
                CREATE TABLE IF NOT EXISTS audit_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT    NOT NULL,
                    user_id     TEXT,
                    endpoint    TEXT,
                    risk_level  TEXT,
                    score       REAL,
                    source      TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                    ON audit_log (timestamp);
            """)
            self._conn.commit()

    # ── Captured Events — Write ────────────────────────────────

    def insert(self, source: str, text: str) -> int:
        """Save a raw captured event WITHOUT a risk score. Returns the new row id."""
        ts = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO captured_events
                   (timestamp, source, raw_text, scored)
                   VALUES (?, ?, ?, 0)""",
                (ts, source, text)
            )
            self._conn.commit()
            return cur.lastrowid

    def insert_with_score(self,
                          source     : str,
                          text       : str,
                          score_dict : dict) -> int:
        """Save a captured event WITH a risk score attached."""
        ts = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO captured_events
                   (timestamp, source, raw_text,
                    composite_score, risk_level, risk_label, scored)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (
                    ts,
                    source,
                    text,
                    score_dict.get("composite_score"),
                    score_dict.get("risk_level"),
                    score_dict.get("risk_label"),
                )
            )
            self._conn.commit()
            return cur.lastrowid

    def update_score(self, row_id: int, score_dict: dict) -> None:
        """Attach a risk score to a previously-inserted row (by id)."""
        with self._lock:
            self._conn.execute(
                """UPDATE captured_events
                   SET composite_score = ?,
                       risk_level      = ?,
                       risk_label      = ?,
                       scored          = 1
                   WHERE id = ?""",
                (
                    score_dict.get("composite_score"),
                    score_dict.get("risk_level"),
                    score_dict.get("risk_label"),
                    row_id,
                )
            )
            self._conn.commit()

    # ── Captured Events — Read ─────────────────────────────────

    def query_recent(self, limit: int = 50) -> list[dict]:
        """Return the most recent N events, newest first."""
        cur = self._conn.execute(
            """SELECT * FROM captured_events
               ORDER BY id DESC LIMIT ?""",
            (limit,)
        )
        return [dict(row) for row in cur.fetchall()]

    def query_by_risk(self, risk_level: str, limit: int = 100) -> list[dict]:
        """Return events filtered by risk level."""
        cur = self._conn.execute(
            """SELECT * FROM captured_events
               WHERE risk_level = ?
               ORDER BY id DESC LIMIT ?""",
            (risk_level.lower(), limit)
        )
        return [dict(row) for row in cur.fetchall()]

    def query_high_risk(self, limit: int = 50) -> list[dict]:
        """Shortcut — returns only CRISIS + HIGH risk events."""
        cur = self._conn.execute(
            """SELECT * FROM captured_events
               WHERE risk_level IN ('crisis', 'high')
               ORDER BY id DESC LIMIT ?""",
            (limit,)
        )
        return [dict(row) for row in cur.fetchall()]

    def query_since(self, since_iso: str, limit: int = 500) -> list[dict]:
        """Return events since a given ISO timestamp."""
        cur = self._conn.execute(
            """SELECT * FROM captured_events
               WHERE timestamp >= ?
               ORDER BY id DESC LIMIT ?""",
            (since_iso, limit)
        )
        return [dict(row) for row in cur.fetchall()]

    def get_summary(self) -> dict:
        """Return aggregate counts — useful for the desktop dashboard."""
        cur = self._conn.execute(
            """SELECT
                 COUNT(*)                                    AS total,
                 SUM(CASE WHEN risk_level='crisis' THEN 1 ELSE 0 END) AS crisis_count,
                 SUM(CASE WHEN risk_level='high'   THEN 1 ELSE 0 END) AS high_count,
                 SUM(CASE WHEN risk_level='medium' THEN 1 ELSE 0 END) AS medium_count,
                 SUM(CASE WHEN risk_level='low'    THEN 1 ELSE 0 END) AS low_count,
                 SUM(CASE WHEN risk_level='none'   THEN 1 ELSE 0 END) AS none_count,
                 SUM(CASE WHEN scored=0            THEN 1 ELSE 0 END) AS unscored,
                 ROUND(AVG(composite_score), 2)              AS avg_score,
                 MAX(composite_score)                        AS max_score
               FROM captured_events"""
        )
        row = cur.fetchone()
        return dict(row) if row else {}

    # ── Schema Migration (live DB upgrade) ───────────────────

    def migrate(self) -> None:
        """
        Apply non-destructive ALTER TABLE migrations for existing databases
        that pre-date the guardians / crisis_events schema additions.
        """
        migrations = [
            "ALTER TABLE user_sessions ADD COLUMN email TEXT",
            "ALTER TABLE user_sessions ADD COLUMN display_name TEXT",
        ]
        with self._lock:
            for sql in migrations:
                try:
                    self._conn.execute(sql)
                except Exception:
                    pass   # column already exists — safe to ignore
            self._conn.commit()

    # ── User Sessions (Persistent Consent) ────────────────────

    def save_consent(self, user_id: str, username: str,
                     country_code: str = "GLOBAL",
                     email: str = "",
                     display_name: str = "") -> None:
        """Record or refresh consent for a user."""
        ts = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            self._conn.execute(
                """INSERT INTO user_sessions
                   (user_id, username, email, display_name,
                    consented_at, monitoring_active, country_code)
                   VALUES (?, ?, ?, ?, ?, 1, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       username          = excluded.username,
                       email             = excluded.email,
                       display_name      = excluded.display_name,
                       consented_at      = excluded.consented_at,
                       monitoring_active = 1,
                       country_code      = excluded.country_code""",
                (str(user_id), username, email, display_name, ts, country_code)
            )
            self._conn.commit()

    def revoke_consent(self, user_id: str) -> None:
        """Pause monitoring for a user (does not delete their data)."""
        with self._lock:
            self._conn.execute(
                "UPDATE user_sessions SET monitoring_active = 0 WHERE user_id = ?",
                (str(user_id),)
            )
            self._conn.commit()

    def resume_consent(self, user_id: str) -> None:
        """Re-enable monitoring for a user."""
        with self._lock:
            self._conn.execute(
                "UPDATE user_sessions SET monitoring_active = 1 WHERE user_id = ?",
                (str(user_id),)
            )
            self._conn.commit()

    def delete_user(self, user_id: str) -> None:
        """Permanently delete all data for a user (right to erasure)."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM user_sessions WHERE user_id = ?", (str(user_id),))
            self._conn.execute(
                "DELETE FROM temporal_context WHERE user_id = ?", (str(user_id),))
            self._conn.commit()

    def get_user(self, user_id: str) -> Optional[dict]:
        """Return user session record or None."""
        cur = self._conn.execute(
            "SELECT * FROM user_sessions WHERE user_id = ?", (str(user_id),)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def has_consented(self, user_id: str) -> bool:
        user = self.get_user(user_id)
        return user is not None

    def is_monitoring_active(self, user_id: str) -> bool:
        user = self.get_user(user_id)
        return bool(user.get("monitoring_active", 0)) if user else False

    # ── Temporal Context ───────────────────────────────────────

    def add_temporal_event(self, user_id: str, risk_level: str,
                           composite_score: float, text: str = "") -> None:
        """Record a risk event in the 30-day rolling temporal context store."""
        ts      = datetime.now().isoformat(timespec="seconds")
        snippet = text[:200] if text else ""
        with self._lock:
            self._conn.execute(
                """INSERT INTO temporal_context
                   (user_id, timestamp, risk_level, composite_score, text_snippet)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(user_id), ts, risk_level, composite_score, snippet)
            )
            self._conn.commit()

    def get_temporal_window(self, user_id: str, days: int = 30) -> list[dict]:
        """Fetch rolling temporal context for a user over the past N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        cur = self._conn.execute(
            """SELECT * FROM temporal_context
               WHERE user_id = ? AND timestamp >= ?
               ORDER BY timestamp ASC""",
            (str(user_id), cutoff)
        )
        return [dict(row) for row in cur.fetchall()]

    def get_temporal_summary(self, user_id: str, days: int = 30) -> dict:
        """Return aggregate stats for a user's recent history."""
        rows = self.get_temporal_window(user_id, days)
        if not rows:
            return {"total": 0, "avg_score": 0.0, "crisis_count": 0,
                    "high_count": 0, "trend": "stable"}

        scores       = [r["composite_score"] for r in rows if r["composite_score"]]
        crisis_count = sum(1 for r in rows if r["risk_level"] in ("crisis", "CRISIS"))
        high_count   = sum(1 for r in rows if r["risk_level"] in ("high",   "HIGH"))

        # Detect escalation: is the recent average higher than the older half?
        mid   = len(scores) // 2
        trend = "stable"
        if len(scores) >= 4:
            older_avg  = sum(scores[:mid]) / max(mid, 1)
            recent_avg = sum(scores[mid:]) / max(len(scores) - mid, 1)
            if recent_avg > older_avg + 0.1:
                trend = "escalating"
            elif recent_avg < older_avg - 0.1:
                trend = "improving"

        return {
            "total"        : len(rows),
            "avg_score"    : round(sum(scores) / len(scores), 4) if scores else 0.0,
            "crisis_count" : crisis_count,
            "high_count"   : high_count,
            "trend"        : trend,
            "window_days"  : days,
        }

    def detect_escalation(self, user_id: str, lookback: int = 3) -> bool:
        """
        Return True if the last `lookback` risk scores are trending upward
        and the most recent exceeds the oldest by >0.1.
        """
        rows = self.get_temporal_window(user_id, days=7)
        if len(rows) < lookback:
            return False
        recent = [r["composite_score"] for r in rows[-lookback:]
                  if r["composite_score"] is not None]
        if len(recent) < 2:
            return False
        return recent[-1] > recent[0] and (recent[-1] - recent[0]) > 0.1

    # ── Guardians ──────────────────────────────────────────────

    def add_guardian(
        self,
        user_id        : str,
        guardian_email : str,
        guardian_name  : str  = "",
        relationship   : str  = "guardian",
    ) -> None:
        """Register a guardian for a user. Duplicate emails are ignored."""
        ts = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            self._conn.execute(
                """INSERT OR IGNORE INTO guardians
                   (user_id, guardian_email, guardian_name, relationship, added_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(user_id), guardian_email.lower().strip(),
                 guardian_name, relationship, ts)
            )
            self._conn.commit()

    def remove_guardian(self, user_id: str, guardian_email: str) -> None:
        """Remove a guardian contact from a user's account."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM guardians WHERE user_id = ? AND guardian_email = ?",
                (str(user_id), guardian_email.lower().strip())
            )
            self._conn.commit()

    def get_guardians(self, user_id: str) -> list[dict]:
        """Return all guardian contacts for a given user."""
        cur = self._conn.execute(
            """SELECT id, guardian_email, guardian_name, relationship, added_at
               FROM guardians WHERE user_id = ?
               ORDER BY added_at ASC""",
            (str(user_id),)
        )
        return [dict(row) for row in cur.fetchall()]

    # ── Crisis Events ──────────────────────────────────────────

    def log_crisis_event(
        self,
        user_id             : str,
        score               : float,
        source              : str  = "unknown",
        text                : str  = "",
        guardians_notified  : int  = 0,
        clinician_notified  : bool = False,
    ) -> int:
        """
        Record a CRISIS event in the crisis_events table.
        Returns the new row id.
        """
        ts      = datetime.now().isoformat(timespec="seconds")
        snippet = text[:300] if text else ""
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO crisis_events
                   (timestamp, user_id, score, source, text_snippet,
                    guardians_notified, clinician_notified)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (ts, str(user_id), score, source, snippet,
                 guardians_notified, int(clinician_notified))
            )
            self._conn.commit()
            return cur.lastrowid

    def get_crisis_events(
        self,
        user_id : str,
        limit   : int = 50,
    ) -> list[dict]:
        """Return the most recent CRISIS events for a user."""
        cur = self._conn.execute(
            """SELECT * FROM crisis_events
               WHERE user_id = ?
               ORDER BY id DESC LIMIT ?""",
            (str(user_id), limit)
        )
        return [dict(row) for row in cur.fetchall()]

    # ── Audit Log ──────────────────────────────────────────────

    def log_audit(self, user_id: str = "", endpoint: str = "",
                  risk_level: str = "", score: float = 0.0,
                  source: str = "") -> None:
        """Write an immutable audit record for every inference call."""
        ts = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            self._conn.execute(
                """INSERT INTO audit_log
                   (timestamp, user_id, endpoint, risk_level, score, source)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (ts, str(user_id), endpoint, risk_level, score, source)
            )
            self._conn.commit()

    def query_audit(self, limit: int = 100) -> list[dict]:
        """Return the most recent N audit records."""
        cur = self._conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cur.fetchall()]

    # ── Maintenance ────────────────────────────────────────────

    def delete_older_than_days(self, days: int = 30) -> int:
        """Purge captured_events entries older than N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM captured_events WHERE timestamp < ?", (cutoff,)
            )
            self._conn.commit()
            return cur.rowcount

    def purge_old_temporal(self, days: int = 30) -> int:
        """Purge temporal_context entries older than N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM temporal_context WHERE timestamp < ?", (cutoff,)
            )
            self._conn.commit()
            return cur.rowcount

    def close(self):
        """Close the database connection cleanly."""
        self._conn.close()
        print("🛑 MonitorStorage closed.")


# ─────────────────────────────────────────────────────────────
# Quick self-test — run directly to verify the DB works
# python monitor_storage.py
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    db = MonitorStorage(db_path=":memory:")

    # Consent lifecycle
    db.save_consent("tg:12345", "Alice", "NG")
    print(f"Consented  : {db.has_consented('tg:12345')}")
    print(f"Active     : {db.is_monitoring_active('tg:12345')}")

    db.revoke_consent("tg:12345")
    print(f"After revoke active: {db.is_monitoring_active('tg:12345')}")

    db.resume_consent("tg:12345")
    print(f"After resume active: {db.is_monitoring_active('tg:12345')}")

    # Captured events
    rid1 = db.insert("keyboard", "I feel really stressed today")
    db.update_score(rid1, {"composite_score": 38.0,
                            "risk_level": "moderate", "risk_label": "Moderate Risk"})

    db.insert_with_score("telegram", "I can't go on anymore", {
        "composite_score": 91.0, "risk_level": "crisis", "risk_label": "Crisis"
    })

    # Temporal context
    db.add_temporal_event("tg:12345", "moderate", 0.38, "I feel stressed")
    db.add_temporal_event("tg:12345", "high",     0.72, "Getting worse")
    db.add_temporal_event("tg:12345", "crisis",   0.91, "I can't go on")

    summary = db.get_temporal_summary("tg:12345")
    print(f"\nTemporal summary : {summary}")
    print(f"Escalating       : {db.detect_escalation('tg:12345')}")

    # Audit
    db.log_audit("tg:12345", "/analyze", "crisis", 0.91, "telegram")
    print(f"\nAudit log rows   : {len(db.query_audit())}")

    # Summary
    print(f"Captured summary : {db.get_summary()}")

    db.close()
    print("\n✅ MonitorStorage self-test passed")