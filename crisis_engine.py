# crisis_engine.py
# ─────────────────────────────────────────────────────────────
# Crisis Intervention Engine
# Triggered whenever risk tier == "CRISIS"
#
# Responsibilities:
#   1. Return localized crisis hotline resources
#   2. Send email alert to the assigned clinician
#   3. Build a structured crisis event payload for audit logging
#
# Usage:
#   from crisis_engine import CrisisEngine
#   engine = CrisisEngine()
#   await engine.handle_crisis(user_id="tg:12345", text="...", score=0.91, source="telegram")
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


def get_crisis_resources(country_code: str = "GLOBAL") -> list[str]:
    """
    Return localized crisis hotline resources.
    Falls back to GLOBAL if country_code is not found.
    """
    return CRISIS_RESOURCES.get(country_code.upper(), CRISIS_RESOURCES["GLOBAL"])


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
# Main Crisis Handler
# ─────────────────────────────────────────────────────────────

class CrisisEngine:
    """
    Orchestrates the full crisis response workflow:
      1. Fetch localized resources
      2. Email the clinician
      3. Return a structured event dict for audit logging

    Usage:
        engine = CrisisEngine()
        event  = engine.handle_crisis(
            user_id="tg:12345",
            text="I want to end my life",
            score=0.92,
            source="telegram",
            country="NG",
        )
    """

    def __init__(self, default_country: str = "GLOBAL"):
        self.default_country = default_country

    def handle_crisis(
        self,
        user_id  : str,
        text     : str,
        score    : float,
        source   : str  = "unknown",
        country  : str  = "",
        to_email : Optional[str] = None,
    ) -> dict:
        """
        Run full crisis protocol. Returns a structured event payload.

        Args:
            user_id  : unique identifier (e.g. "tg:12345", "browser:session_abc")
            text     : the flagged text
            score    : composite risk score (0.0–1.0)
            source   : "telegram" | "browser_extension" | "text_monitor" | "api"
            country  : ISO-3166-1 alpha-2 code, e.g. "NG", "US", "GB"
            to_email : override clinician email (optional)

        Returns:
            dict with keys: user_id, text, score, source, timestamp,
                            resources, alert_sent
        """
        country    = country or self.default_country
        timestamp  = datetime.now().isoformat()
        resources  = get_crisis_resources(country)

        alert_sent = send_clinician_alert(
            user_id  = user_id,
            text     = text,
            score    = score,
            source   = source,
            country  = country,
            to_email = to_email,
        )

        event = {
            "event_type" : "CRISIS",
            "user_id"    : user_id,
            "text"       : text,
            "score"      : score,
            "source"     : source,
            "country"    : country,
            "timestamp"  : timestamp,
            "resources"  : resources,
            "alert_sent" : alert_sent,
        }

        logger.warning(
            f"CRISIS event — user={user_id} score={score:.2f} "
            f"source={source} alert_sent={alert_sent}"
        )
        return event


# ─────────────────────────────────────────────────────────────
# Singleton — import and reuse across the app
# ─────────────────────────────────────────────────────────────

crisis_engine = CrisisEngine()
