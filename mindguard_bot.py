# mindguard_bot.py
# ─────────────────────────────────────────────────────────────
# MindGuard Telegram Bot — Consent-Based Risk Monitoring
# Connects to existing main.py FastAPI backend
# ─────────────────────────────────────────────────────────────

import os
import random
import logging
import datetime
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)
from monitor_storage import MonitorStorage
from crisis_engine import crisis_engine

load_dotenv()

# ─────────────────────────────────────────────────────────────
# Configuration — all from .env (no hardcoded secrets)
# ─────────────────────────────────────────────────────────────

BOT_TOKEN       = os.getenv("TELEGRAM_BOT_TOKEN", "")
BACKEND_URL     = os.getenv("BACKEND_URL",         "http://localhost:8000")
API_KEY         = os.getenv("DESKTOP_APP_API_KEY", "dev-secret-key-change-in-prod")

if not BOT_TOKEN:
    raise EnvironmentError(
        "TELEGRAM_BOT_TOKEN is not set. "
        "Add it to your .env file: TELEGRAM_BOT_TOKEN=<your_token>"
    )

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Persistent Storage  (replaces in-memory dicts)
# ─────────────────────────────────────────────────────────────

db = MonitorStorage(db_path="monitor_history.db")

# ─────────────────────────────────────────────────────────────
# Phrase Detection Lists
# ─────────────────────────────────────────────────────────────

SELF_HARM_PHRASES = [
    "harm myself", "hurt myself", "kill myself",
    "want to die", "end my life", "end it all",
    "self harm", "self-harm", "cut myself", "cutting myself",
    "overdose", "take all my pills",
    "suicide", "suicidal",
    "unalive", "unaliving myself",
    "no reason to live", "nothing to live for",
    "dont want to be here", "don't want to be here",
    "dont want to live", "don't want to live",
    "better off dead", "better off without me",
    "wish i was dead", "rather be dead",
    "injure myself", "injuring myself",
    "cant go on", "can't go on",
    "cant go on any longer", "can't go on any longer",
    "no point in living", "no point anymore",
    "tired of living", "tired of life",
    "want to disappear forever",
    "decided i cant go on", "decided i can't go on",
]

AGGRESSION_PHRASES = [
    "want to harm someone", "want to hurt someone",
    "want to kill someone", "want to harm others",
    "want to hurt others", "going to hurt someone",
    "going to harm someone", "want to attack someone",
    "so angry i could", "i could kill",
    "im so angry i", "i'm so angry i",
    "want to hit someone", "feeling violent",
    "i could hurt someone", "going to lose control",
    "out of control anger", "i want to fight",
]

AMBIGUOUS_HARM_PHRASES = [
    "want to harm", "want to hurt",
    "going to hurt", "going to harm",
    "need to hurt", "need to harm",
]

EMOTIONAL_WORDS = [
    "harm", "hurt", "die", "dead", "kill", "pain",
    "suffer", "hopeless", "worthless", "empty", "numb",
    "alone", "cry", "scared", "afraid", "angry",
    "rage", "violent", "attack", "fight", "miserable",
    "desperate", "broken", "lost", "helpless",
]

# ─────────────────────────────────────────────────────────────
# Response Messages
# ─────────────────────────────────────────────────────────────

HIGH_RISK_RESPONSE = """
🚨 *I want to check in with you.*

What you shared tells me things might be really \
difficult right now. That takes a lot of courage to express.

*You don't have to face this alone.*

📞 *988* — Call or text (Crisis Lifeline)
💬 Text *HOME* to *741741* (Crisis Text Line)
🌍 findahelpline.com (International)
🇳🇬 MANI Nigeria: *08091110891*

A trained clinician has been notified and may reach out to you.

Would you like to talk about what you are going through?
"""

AGGRESSION_RESPONSE = """
💛 *I can hear that you are feeling really angry right now.*

Those feelings are valid — but I want to make sure \
you and everyone around you stays safe.

*When anger feels overwhelming try:*
• Step away from the situation immediately
• Take 10 slow deep breaths before reacting
• Go for a fast walk to release the tension
• Call someone you trust right now

*If you feel like you may lose control:*
📞 Call *988* — they help with crisis anger too
💬 Text HOME to *741741*
🚨 Call *999* or *911* if someone is in immediate danger

Would you like to talk about what made you feel this way? 💙
"""

AMBIGUOUS_HARM_RESPONSE = """
💙 *I noticed something in what you shared.*

When you say you want to harm — can you tell me \
a little more about what you mean?

Are you feeling like hurting *yourself*, or are \
you feeling angry toward *someone else*?

Either way I am here and I want to help you through this. \
You don't have to face it alone.

📞 *988* — Crisis support for any kind of distress
💬 Text HOME to *741741*
"""

MEDIUM_RISK_RESPONSE = """
💛 *Thank you for sharing that.*

It sounds like things have been tough lately. \
What you are feeling is valid.

*A few things that might help right now:*
• Talk to someone you trust today
• Try 5 minutes of slow deep breathing
• Step outside for a short walk if you can

I am here if you want to keep talking 💙
"""

ESCALATION_RESPONSE = """
💙 *I have noticed things have been getting harder \
for you over the past few days.*

That is a lot to carry and you deserve support.

*Please reach out to someone:*
📞 *988* — Call or text
💬 Text *HOME* to *741741*
🇳🇬 MANI Nigeria: *08091110891*

A clinician has been notified about your recent \
messages and may contact you.

You matter and you are not alone 💙
"""

LOW_RISK_RESPONSE_OPTIONS = [
    "Thanks for sharing 😊 Hope the rest of your day goes well 💙",
    "I hear you. Take care of yourself today 🌱",
    "Thanks for checking in. You are doing well 💙",
    "Good to hear from you. Remember small steps matter 😊",
]

# ─────────────────────────────────────────────────────────────
# Backend Analysis Call
# ─────────────────────────────────────────────────────────────

def analyse_text(text: str, user_id: str) -> dict:
    """Calls the main.py /analyze endpoint, passing user_id for audit."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/analyze",
            json    = {"text": text, "include_rag": False},
            headers = {"X-API-Key": API_KEY},
            params  = {"user_id": f"tg:{user_id}"},
            timeout = 10,
        )
        return response.json()
    except Exception as e:
        logger.error(f"Backend error: {e}")
        return {"risk_level": "low", "composite_score": 0}

# ─────────────────────────────────────────────────────────────
# /start — Welcome + Consent Screen
# ─────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    username = update.effective_user.first_name or "there"

    if db.has_consented(str(user_id)) and db.is_monitoring_active(str(user_id)):
        await update.message.reply_text(
            f"👋 Welcome back {username}!\n\n"
            "Monitoring is already active for your account.\n"
            "Just chat normally — I am here if you need support.\n\n"
            "Type /status to see your current settings.\n"
            "Type /stop to pause monitoring at any time."
        )
        return

    consent_text = (
        f"👋 Hello {username}, welcome to *MindGuard*\n\n"
        "MindGuard is an AI-powered emotional support bot "
        "that monitors your messages for signs of distress "
        "and connects you with help when you need it most.\n\n"

        "📋 *WHAT YOU ARE AGREEING TO:*\n"
        "✅ Every message you send will be privately analysed "
        "for emotional distress signals\n"
        "✅ You will receive supportive responses if distress "
        "is detected\n"
        "✅ A clinician may be alerted if your risk level is "
        "critically high\n"
        "✅ Your emotional patterns are tracked over time\n\n"

        "🔒 *YOUR PRIVACY:*\n"
        "❌ Your messages are never stored permanently\n"
        "❌ Your data is never sold or shared commercially\n"
        "❌ Only your assigned clinician can see alerts\n\n"

        "⚖️ *YOUR RIGHTS:*\n"
        "• Withdraw consent anytime with /stop\n"
        "• Delete your data anytime with /delete\n"
        "• Pause monitoring anytime with /pause\n\n"

        "This is a support tool — not a replacement "
        "for professional care.\n\n"
        "*Do you agree to these terms?*"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅  Yes, I Agree", callback_data="consent_yes"),
            InlineKeyboardButton("❌  No Thanks",    callback_data="consent_no"),
        ]
    ])

    await update.message.reply_text(
        consent_text,
        parse_mode   = "Markdown",
        reply_markup = keyboard,
    )

# ─────────────────────────────────────────────────────────────
# Consent Button Handler
# ─────────────────────────────────────────────────────────────

async def handle_consent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    user_id  = query.from_user.id
    username = query.from_user.first_name or "there"

    await query.answer()

    if query.data == "consent_yes":
        db.save_consent(str(user_id), username, country_code="GLOBAL")
        await query.edit_message_text(
            f"✅ *Thank you {username} — you are now registered.*\n\n"
            "From this moment MindGuard will:\n"
            "• Analyse every message you send here\n"
            "• Respond with support if distress is detected\n"
            "• Alert a clinician if your risk is critically high\n\n"
            "You can chat naturally — just talk to me like you "
            "would talk to a trusted friend.\n\n"
            "How are you feeling today? 💙",
            parse_mode = "Markdown",
        )

    elif query.data == "consent_no":
        await query.edit_message_text(
            "That is completely okay 💙\n\n"
            "MindGuard requires consent to work safely and "
            "ethically, so we are unable to proceed without it.\n\n"
            "If you ever change your mind, just type /start "
            "and we will walk you through it again.\n\n"
            "If you need immediate support right now:\n"
            "📞 Call or text *988*\n"
            "💬 Text HOME to *741741*",
            parse_mode = "Markdown",
        )

# ─────────────────────────────────────────────────────────────
# Main Message Handler — 5-layer detection pipeline
# ─────────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text    = update.message.text

    if not text or len(text) < 5:
        return

    # ── Not consented yet ─────────────────────────────────────
    if not db.has_consented(str(user_id)):
        await update.message.reply_text(
            "👋 Hi! To use MindGuard please type /start "
            "to read and agree to our terms first."
        )
        return

    # ── Monitoring paused ─────────────────────────────────────
    if not db.is_monitoring_active(str(user_id)):
        await update.message.reply_text(
            "Your monitoring is currently paused.\n"
            "Type /resume to reactivate it."
        )
        return

    lower_text = (
        text.lower()
            .replace("'", "")
            .replace("'", "")
            .replace("`", "")
    )

    # ── LAYER 1: Self-harm / suicidal phrases → CRISIS ────────
    if any(phrase in lower_text for phrase in SELF_HARM_PHRASES):
        db.add_temporal_event(str(user_id), "crisis", 1.0, text)
        crisis_engine.handle_crisis(
            user_id = f"tg:{user_id}",
            text    = text,
            score   = 1.0,
            source  = "telegram",
        )
        await update.message.reply_text(HIGH_RISK_RESPONSE, parse_mode="Markdown")
        return

    # ── LAYER 2: Outward aggression ────────────────────────────
    if any(phrase in lower_text for phrase in AGGRESSION_PHRASES):
        db.add_temporal_event(str(user_id), "high", 0.75, text)
        await update.message.reply_text(AGGRESSION_RESPONSE, parse_mode="Markdown")
        return

    # ── LAYER 3: Ambiguous harm ────────────────────────────────
    if any(phrase in lower_text for phrase in AMBIGUOUS_HARM_PHRASES):
        db.add_temporal_event(str(user_id), "high", 0.80, text)
        await update.message.reply_text(AMBIGUOUS_HARM_RESPONSE, parse_mode="Markdown")
        return

    # ── LAYER 4: AI scoring via main.py backend ────────────────
    result = analyse_text(text, user_id)
    score  = result.get("composite_score", 0)
    level  = result.get("risk_level", "low")

    # Normalise score to 0-1 range (API returns 0-10)
    norm_score = score / 10.0 if score > 1 else score
    db.add_temporal_event(str(user_id), level, norm_score, text)

    if level in ("high", "crisis"):
        crisis_engine.handle_crisis(
            user_id = f"tg:{user_id}",
            text    = text,
            score   = norm_score,
            source  = "telegram",
        )
        await update.message.reply_text(HIGH_RISK_RESPONSE, parse_mode="Markdown")

    elif db.detect_escalation(str(user_id)):
        await update.message.reply_text(ESCALATION_RESPONSE, parse_mode="Markdown")

    elif level == "medium":
        await update.message.reply_text(MEDIUM_RISK_RESPONSE, parse_mode="Markdown")

    else:
        # ── LAYER 5: Emotional word safety net ────────────────
        if any(word in lower_text for word in EMOTIONAL_WORDS):
            await update.message.reply_text(
                "💙 It sounds like things might be a little tough "
                "right now.\n\n"
                "I am here if you want to talk about how you are "
                "feeling. You are not alone."
            )
        else:
            await update.message.reply_text(random.choice(LOW_RISK_RESPONSE_OPTIONS))

# ─────────────────────────────────────────────────────────────
# Control Commands
# ─────────────────────────────────────────────────────────────

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.revoke_consent(str(user_id))
    await update.message.reply_text(
        "⏸️ Monitoring has been paused.\n\n"
        "Your data has not been deleted — "
        "type /resume to reactivate anytime.\n"
        "Type /delete to permanently remove your data."
    )

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.has_consented(str(user_id)):
        db.resume_consent(str(user_id))
        await update.message.reply_text(
            "✅ Monitoring resumed. I am here if you need me 💙"
        )
    else:
        await update.message.reply_text("Please type /start to register first.")

async def delete_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.delete_user(str(user_id))
    await update.message.reply_text(
        "🗑️ All your data has been permanently deleted.\n\n"
        "Type /start if you would like to register again."
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user    = db.get_user(str(user_id))
    if not user:
        await update.message.reply_text(
            "You are not currently registered.\nType /start to sign up."
        )
        return

    summary = db.get_temporal_summary(str(user_id), days=7)
    trend   = summary.get("trend", "stable")

    await update.message.reply_text(
        f"📊 *Your MindGuard Status*\n\n"
        f"Monitoring  : {'Active ✅' if user['monitoring_active'] else 'Paused ⏸️'}\n"
        f"Registered  : {user['consented_at'][:10]}\n"
        f"Messages (7d): {summary.get('total', 0)}\n"
        f"Risk trend  : {trend.capitalize()}\n"
        f"Crisis events (7d): {summary.get('crisis_count', 0)}\n\n"
        f"Commands:\n"
        f"/stop    — pause monitoring\n"
        f"/resume  — reactivate monitoring\n"
        f"/delete  — remove all your data\n"
        f"/privacy — read privacy policy",
        parse_mode = "Markdown"
    )

async def privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔒 *MindGuard Privacy Policy*\n\n"
        "• You consented to analysis at signup\n"
        "• Messages are analysed in real time\n"
        "• Text snippets kept ≤200 chars for 30-day trend analysis\n"
        "• Risk scores kept for 30 days for trend tracking\n"
        "• Only your clinician sees crisis alerts\n"
        "• Your data is never sold or shared commercially\n"
        "• You can delete everything with /delete at any time\n\n"
        "For questions contact: support@mindguard.com",
        parse_mode = "Markdown"
    )

# ─────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("stop",    stop))
    app.add_handler(CommandHandler("resume",  resume))
    app.add_handler(CommandHandler("delete",  delete_data))
    app.add_handler(CommandHandler("status",  status))
    app.add_handler(CommandHandler("privacy", privacy))
    app.add_handler(CallbackQueryHandler(handle_consent))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_message
    ))

    print("🤖 MindGuard Bot is running...")
    app.run_polling()