# crisis_engine.py
# ─────────────────────────────────────────────────────────────
# Crisis Intervention Engine
# Triggered whenever risk tier == "CRISIS"
#
# Responsibilities:
#   1. Return localized crisis hotline resources
#   2. Send HTML alert to the assigned clinician
#   3. Send warm, personal HTML alert to each registered guardian
#   4. Log the CRISIS event (with notification status) to crisis_events table
#   5. Build a structured crisis event payload for audit logging
#
# Usage:
#   from crisis_engine import CrisisEngine
#   engine = CrisisEngine()
#   await engine.handle_crisis(user_id="tg:12345", text="...", score=0.91,
#                              source="telegram", db_store=storage_instance)
# ─────────────────────────────────────────────────────────────

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Configuration (all from .env)
# ─────────────────────────────────────────────────────────────

SMTP_HOST       = os.getenv("SMTP_HOST",       "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT",   "587"))
SMTP_USER       = os.getenv("SMTP_USER",       "")          # sender email
SMTP_PASSWORD   = os.getenv("SMTP_PASSWORD",   "")          # app password
CLINICIAN_EMAIL = os.getenv("CLINICIAN_EMAIL", "clinician@hospital.com")
SYSTEM_NAME     = os.getenv("SYSTEM_NAME",     "MindGuard")

# ─────────────────────────────────────────────────────────────
# Localized Crisis Resources
# ─────────────────────────────────────────────────────────────

CRISIS_RESOURCES: dict[str, list[str]] = {
    "NG": [  # Nigeria
        "Mentally Aware Nigeria Initiative (MANI): 08091110891",
        "Nigeria Suicide Prevention Initiative: support@nsp-initiative.org",
        "Substance Abuse & Mental Health Nigeria: samnhq@gmail.com",
    ],
    "US": [
        "988 Suicide & Crisis Lifeline: Call or text 988",
        "Crisis Text Line: text HOME to 741741",
        "SAMHSA National Helpline: 1-800-662-4357",
    ],
    "GB": [
        "Samaritans: 116 123 (free, 24/7)",
        "Crisis Text Line UK: text SHOUT to 85258",
        "Mind Infoline: 0300 123 3393",
    ],
    "GLOBAL": [
        "findahelpline.com — localized crisis lines worldwide",
        "befrienders.org — worldwide volunteer support",
        "988 Suicide & Crisis Lifeline (US): Call or text 988",
        "Crisis Text Line: text HOME to 741741",
    ],
}

# Adolescent-specific crisis resources (age 10–24)
ADOLESCENT_RESOURCES: dict[str, list[str]] = {
    "NG": [
        "Childline Nigeria: 116 (free, 24/7 for children)",
        "MANI — Mentally Aware Nigeria Initiative: 08091110891",
        "Nigeria Adolescent Health: nahip.fmoh.gov.ng",
        "Nigeria Suicide Prevention Initiative: support@nsp-initiative.org",
    ],
    "US": [
        "Crisis Text Line (Youth): text HOME to 741741",
        "Teen Line: 800-852-8336 (6pm–10pm PT, teens for teens)",
        "988 Suicide & Crisis Lifeline: call or text 988",
        "The Trevor Project (LGBTQ+): 1-866-488-7386",
        "Youth Crisis Text Line: text START to 678-678",
    ],
    "GB": [
        "Childline: 0800 1111 (free, 24/7 for under-19s)",
        "YoungMinds Crisis Messenger: text YM to 85258",
        "Samaritans: 116 123 (free, 24/7)",
        "Kooth — free online mental health support for young people: kooth.com",
    ],
    "GLOBAL": [
        "Crisis Text Line: text HOME to 741741",
        "findahelpline.com — worldwide localized crisis lines",
        "befrienders.org — worldwide volunteer support",
        "Childline International: childhelplineinternational.org",
    ],
}


def get_crisis_resources(
    country_code  : str  = "GLOBAL",
    is_adolescent : bool = True,
) -> list[str]:
    """
    Return localized crisis hotline resources.
    Prefers adolescent-specific lines when is_adolescent=True.
    Falls back to GLOBAL if country_code is not found.
    """
    pool = ADOLESCENT_RESOURCES if is_adolescent else CRISIS_RESOURCES
    return pool.get(country_code.upper(), pool["GLOBAL"])


# ─────────────────────────────────────────────────────────────
# Email Alert
# ─────────────────────────────────────────────────────────────

def _build_email_html(user_id: str, text: str, score: float,
                      source: str, timestamp: str,
                      resources: list[str]) -> str:
    resource_html = "".join(f"<li>{r}</li>" for r in resources)
    safe_text = text.replace("<", "&lt;").replace(">", "&gt;")
    return f"""
    <html><body style="font-family: Arial, sans-serif; background:#f4f4f4; padding:20px;">
    <div style="max-width:600px; margin:auto; background:#fff; border-radius:8px;
                border-left:6px solid #ef4444; padding:24px;">
        <h2 style="color:#ef4444; margin-top:0;">
            🚨 CRISIS ALERT — {SYSTEM_NAME}
        </h2>
        <p style="color:#555; font-size:14px;">
            A user has been classified at <strong>CRISIS</strong> risk tier.
            Immediate review is recommended.
        </p>

        <table style="width:100%; border-collapse:collapse; font-size:13px; color:#333;">
          <tr><td style="padding:6px 0; font-weight:bold; width:140px;">User ID</td>
              <td>{user_id}</td></tr>
          <tr><td style="padding:6px 0; font-weight:bold;">Source</td>
              <td>{source}</td></tr>
          <tr><td style="padding:6px 0; font-weight:bold;">Risk Score</td>
              <td><span style="color:#ef4444; font-weight:bold;">{score:.2f} / 1.00</span></td></tr>
          <tr><td style="padding:6px 0; font-weight:bold;">Timestamp</td>
              <td>{timestamp}</td></tr>
        </table>

        <div style="margin:16px 0; padding:14px; background:#fff5f5;
                    border:1px solid #fecaca; border-radius:6px;">
            <strong style="color:#991b1b;">Flagged Text:</strong>
            <p style="color:#333; margin:8px 0 0 0; font-style:italic;">
                &ldquo;{safe_text}&rdquo;
            </p>
        </div>

        <div style="margin:16px 0;">
            <strong style="color:#333;">Crisis Resources Provided to User:</strong>
            <ul style="color:#555; font-size:13px; margin-top:8px;">
                {resource_html}
            </ul>
        </div>

        <hr style="border:none; border-top:1px solid #e5e7eb; margin:20px 0;">
        <p style="color:#9ca3af; font-size:11px;">
            This alert was automatically generated by {SYSTEM_NAME}.<br>
            Do not reply to this email. Contact the user via your clinical platform.
        </p>
    </div>
    </body></html>
    """


def send_clinician_alert(
    user_id    : str,
    text       : str,
    score      : float,
    source     : str        = "unknown",
    country    : str        = "GLOBAL",
    to_email   : Optional[str] = None,
) -> bool:
    """
    Send an HTML email alert to the clinician.

    Returns True on success, False on failure (never raises — callers
    should not crash because email failed).
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning(
            "Crisis alert not sent — SMTP_USER / SMTP_PASSWORD not set in .env"
        )
        return False

    recipient  = to_email or CLINICIAN_EMAIL
    timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resources  = get_crisis_resources(country)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{SYSTEM_NAME}] 🚨 CRISIS ALERT — User {user_id}"
    msg["From"]    = SMTP_USER
    msg["To"]      = recipient

    body_html = _build_email_html(user_id, text, score, source, timestamp, resources)
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, recipient, msg.as_string())
        logger.info(f"Crisis alert sent to {recipient} for user {user_id}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send crisis alert: {exc}")
        return False


# ─────────────────────────────────────────────────────────────
# Guardian Alert Email  (warm, personal — not clinical)
# ─────────────────────────────────────────────────────────────

def _build_guardian_email_html(
    guardian_name  : str,
    watched_name   : str,
    score          : float,
    timestamp      : str,
    resources      : list[str],
    relationship   : str = "guardian",
    ward_age       : int = 0,
) -> str:
    """
    Build a warm, human-centred HTML email for a guardian/parent.
    Adolescent-aware: references the child's name and the guardian relationship.
    """
    resource_html = "".join(f"<li>{r}</li>" for r in resources)
    salutation    = guardian_name.split()[0] if guardian_name else "there"
    pct           = min(int(score * 100), 100)
    bar_color     = "#ef4444" if pct >= 75 else ("#f97316" if pct >= 50 else "#f59e0b")
    age_note      = f" (age {ward_age})" if ward_age else ""
    minor_note    = (
        "<p style=\"font-size:13px; color:#7c3aed; background:#f5f3ff; "
        "border:1px solid #ddd6fe; border-radius:6px; padding:10px 14px; margin:16px 0;\">\n"
        "        <strong>Minor under your care</strong> — As "
        f"{watched_name}'s {relationship}, you have been registered to receive these alerts "
        "so you can provide timely support.\n      </p>"
    ) if ward_age < 18 else (
        "<p style=\"font-size:13px; color:#1d4ed8; background:#eff6ff; "
        "border:1px solid #bfdbfe; border-radius:6px; padding:10px 14px; margin:16px 0;\">\n"
        f"        <strong>Young adult (18+)</strong> — {watched_name} has agreed to allow you "
        "to receive these support alerts.\n      </p>"
    )

    return f"""
    <html><body style="font-family: 'Segoe UI', Arial, sans-serif;
                       background:#f8fafc; padding:24px; margin:0;">
    <div style="max-width:600px; margin:auto; background:#ffffff;
                border-radius:12px; overflow:hidden;
                box-shadow:0 4px 20px rgba(0,0,0,0.08);">

      <!-- Header -->
      <div style="background:linear-gradient(135deg,#1e3a5f,#2563eb);
                  padding:28px 32px; color:#fff;">
        <div style="font-size:22px; font-weight:700; letter-spacing:0.5px;">
          MindGuard &mdash; Support Alert
        </div>
        <div style="font-size:13px; opacity:0.8; margin-top:4px;">
          {watched_name}{age_note} may need your support right now
        </div>
      </div>

      <!-- Body -->
      <div style="padding:28px 32px; color:#374151;">
        <p style="font-size:16px; line-height:1.6; margin-top:0;">
          Hi <strong>{salutation}</strong>,
        </p>
        {minor_note}
        <p style="font-size:15px; line-height:1.7; color:#4b5563;">
          MindGuard has detected patterns in <strong>{watched_name}</strong>&apos;s
          recent online activity that suggest they may be going through a difficult
          time emotionally. <strong>This is not an emergency system call</strong>,
          but we wanted to reach out so you can check in with them.
        </p>

        <!-- Risk indicator bar -->
        <div style="background:#fff7ed; border:1px solid #fed7aa;
                    border-radius:8px; padding:16px 20px; margin:20px 0;">
          <div style="font-size:12px; color:#92400e; font-weight:600;
                      letter-spacing:0.5px; text-transform:uppercase;
                      margin-bottom:10px;">Distress Indicator</div>
          <div style="background:#e5e7eb; border-radius:100px; height:10px;">
            <div style="width:{pct}%; background:{bar_color};
                        height:10px; border-radius:100px;"></div>
          </div>
          <div style="font-size:12px; color:#6b7280; margin-top:6px;">
            Score: {pct}/100 &nbsp;&bull;&nbsp; Detected at {timestamp}
          </div>
        </div>

        <p style="font-size:15px; line-height:1.7; color:#4b5563;">
          <strong>What can you do?</strong> A simple, genuine check-in can make
          a real difference. You don&apos;t need to fix anything &mdash; just letting them
          know you&apos;re there matters enormously.
        </p>

        <ul style="color:#374151; font-size:14px; line-height:2; padding-left:20px;">
          <li>Send a text or call them today</li>
          <li>Ask open-ended questions: <em>&ldquo;How have you been feeling lately?&rdquo;</em></li>
          <li>Listen without judgement &mdash; resist the urge to immediately solve</li>
          <li>If you&apos;re worried about their immediate safety, call emergency services</li>
        </ul>

        <!-- Crisis resources -->
        <div style="background:#f0fdf4; border:1px solid #bbf7d0;
                    border-radius:8px; padding:16px 20px; margin:20px 0;">
          <div style="font-size:12px; color:#166534; font-weight:600;
                      letter-spacing:0.5px; text-transform:uppercase;
                      margin-bottom:8px;">Youth Crisis Resources (to share if needed)</div>
          <ul style="color:#374151; font-size:13px; line-height:1.9; padding-left:20px; margin:0;">
            {resource_html}
          </ul>
        </div>
      </div>

      <!-- Footer -->
      <div style="background:#f9fafb; padding:16px 32px;
                  border-top:1px solid #e5e7eb;">
        <p style="font-size:11px; color:#9ca3af; margin:0; line-height:1.6;">
          You are listed as <strong>{relationship}</strong> for {watched_name}{age_note}.
          This alert was sent automatically by {SYSTEM_NAME}.<br>
          To manage monitoring settings, visit your MindGuard Guardian Dashboard.
        </p>
      </div>

    </div>
    </body></html>
    """


def send_guardian_alert(
    guardian        : dict,
    watched_name    : str,
    score           : float,
    resources       : list[str],
    ward_age        : int = 0,
) -> bool:
    """
    Send a warm guardian alert email.
    `guardian` dict must have keys: guardian_email, guardian_name, relationship.
    Returns True on success.
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("Guardian alert not sent — SMTP_USER/SMTP_PASSWORD not configured")
        return False

    recipient     = guardian.get("guardian_email", "")
    guardian_name = guardian.get("guardian_name", "") or guardian.get("display_name", "") or recipient
    relationship  = guardian.get("relationship", "guardian")
    timestamp     = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not recipient:
        return False

    msg             = MIMEMultipart("alternative")
    msg["Subject"]  = f"[{SYSTEM_NAME}] 💙 Please check in on {watched_name}"
    msg["From"]     = SMTP_USER
    msg["To"]       = recipient

    body_html = _build_guardian_email_html(
        guardian_name = guardian_name,
        watched_name  = watched_name,
        score         = score,
        timestamp     = timestamp,
        resources     = resources,
        relationship  = relationship,
        ward_age      = ward_age,
    )
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, recipient, msg.as_string())
        logger.info(f"Guardian alert sent to {recipient} for {watched_name}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send guardian alert to {recipient}: {exc}")
        return False


# ─────────────────────────────────────────────────────────────
# Main Crisis Handler
# ─────────────────────────────────────────────────────────────

class CrisisEngine:
    """
    Orchestrates the full crisis response workflow:
      1. Fetch localized resources
      2. Email the clinician
      3. Email every registered guardian (warm, personal tone)
      4. Log the event to crisis_events table (with notification counts)
      5. Return a structured event dict for audit logging

    Usage:
        engine = CrisisEngine()
        event  = engine.handle_crisis(
            user_id    = "tg:12345",
            text       = "I want to end my life",
            score      = 0.92,
            source     = "telegram",
            country    = "NG",
            db_store   = storage_instance,   # optional — enables guardian lookup
            watched_name = "Alice",           # optional friendly name
        )
    """

    def __init__(self, default_country: str = "GLOBAL"):
        self.default_country = default_country

    def handle_crisis(
        self,
        user_id      : str,
        text         : str,
        score        : float,
        source       : str  = "unknown",
        country      : str  = "",
        to_email     : Optional[str] = None,
        db_store     = None,          # MonitorStorage instance (optional)
        watched_name : str = "",      # friendly name for guardian email
    ) -> dict:
        """
        Run full crisis protocol. Returns a structured event payload.

        Args:
            user_id      : unique identifier (e.g. "tg:12345", "browser:session_abc")
            text         : the flagged text
            score        : composite risk score (0.0–1.0)
            source       : "telegram" | "browser_extension" | "text_monitor" | "api"
            country      : ISO-3166-1 alpha-2 code, e.g. "NG", "US", "GB"
            to_email     : override clinician email (optional)
            db_store     : MonitorStorage instance for guardian lookup & event logging
            watched_name : friendly display name for guardian emails

        Returns:
            dict with keys: user_id, text, score, source, timestamp,
                            resources, alert_sent, guardians_notified
        """
        country   = country or self.default_country
        timestamp = datetime.now().isoformat()
        resources = get_crisis_resources(country)
        name      = watched_name or user_id

        # 1. Notify clinician
        alert_sent = send_clinician_alert(
            user_id  = user_id,
            text     = text,
            score    = score,
            source   = source,
            country  = country,
            to_email = to_email,
        )

        # 2. Notify guardians (legacy contacts from guardians table)
        guardians_notified = 0
        ward_age = 0

        if db_store is not None:
            # Compute ward age from DOB if available
            try:
                ward_rec = db_store.get_user(user_id)
                dob_str  = (ward_rec or {}).get("date_of_birth", "")
                if dob_str:
                    from datetime import date as _Date
                    dob = _Date.fromisoformat(dob_str)
                    today = _Date.today()
                    ward_age = today.year - dob.year - (
                        (today.month, today.day) < (dob.month, dob.day)
                    )
            except Exception:
                ward_age = 0

            is_adolescent = 10 <= ward_age <= 24 if ward_age else True
            resources = get_crisis_resources(country, is_adolescent=is_adolescent)

            try:
                guardians = db_store.get_guardians(user_id)
                for g in guardians:
                    ok = send_guardian_alert(
                        guardian     = g,
                        watched_name = name,
                        score        = score,
                        resources    = resources,
                        ward_age     = ward_age,
                    )
                    if ok:
                        guardians_notified += 1
            except Exception as exc:
                logger.error(f"Guardian notification loop failed: {exc}")

            # 2b. Also notify via guardian_ward_links (guardian account email)
            try:
                guardian_account = db_store.get_ward_guardian(user_id)
                if guardian_account:
                    ga_email = guardian_account.get("email", "")
                    already_notified = any(
                        g.get("guardian_email", "").lower() == ga_email.lower()
                        for g in db_store.get_guardians(user_id)
                    )
                    if ga_email and not already_notified:
                        ok = send_guardian_alert(
                            guardian     = {
                                "guardian_email": ga_email,
                                "guardian_name" : guardian_account.get("display_name", ""),
                                "relationship"  : guardian_account.get("relationship", "guardian"),
                            },
                            watched_name = guardian_account.get("ward_name", name),
                            score        = score,
                            resources    = resources,
                            ward_age     = ward_age,
                        )
                        if ok:
                            guardians_notified += 1
            except Exception as exc:
                logger.error(f"Guardian account notification failed: {exc}")

        # 3. Log to crisis_events table
        if db_store is not None:
            try:
                db_store.log_crisis_event(
                    user_id            = user_id,
                    score              = score,
                    source             = source,
                    text               = text,
                    guardians_notified = guardians_notified,
                    clinician_notified = alert_sent,
                )
            except Exception as exc:
                logger.error(f"Crisis event logging failed: {exc}")

        event = {
            "event_type"         : "CRISIS",
            "user_id"            : user_id,
            "text"               : text,
            "score"              : score,
            "source"             : source,
            "country"            : country,
            "timestamp"          : timestamp,
            "resources"          : resources,
            "alert_sent"         : alert_sent,
            "guardians_notified" : guardians_notified,
        }

        logger.warning(
            f"CRISIS event — user={user_id} score={score:.2f} "
            f"source={source} clinician={alert_sent} "
            f"guardians_notified={guardians_notified}"
        )
        return event


# ─────────────────────────────────────────────────────────────
# Singleton — import and reuse across the app
# ─────────────────────────────────────────────────────────────

crisis_engine = CrisisEngine()
