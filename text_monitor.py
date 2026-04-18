# text_monitor.py
# ─────────────────────────────────────────────────────────────
# Real-Time Text Capture Module — App-Restricted Version
# Only captures text when a specific target app is active
# ─────────────────────────────────────────────────────────────
#
# SUPPORTED TARGET APPS (set TARGET_APP below):
#   "instagram"  → captures when browser tab title contains "Instagram"
#   "telegram"   → captures when Telegram desktop window is active
#   "whatsapp"   → captures when WhatsApp window is active
#   "chrome"     → captures when any Chrome window is active
#   ""           → empty string = monitor ALL apps (no restriction)
#
# INSTALL:
#   pip install pynput pyperclip pygetwindow
# ─────────────────────────────────────────────────────────────

import time
import threading
from datetime import datetime

import pyperclip
from pynput import keyboard

from risk_engine     import full_risk_assessment
from monitor_storage import MonitorStorage


# ─────────────────────────────────────────────────────────────
# ★ CONFIGURATION — Edit these to change behaviour
# ─────────────────────────────────────────────────────────────

# Set the app you want to monitor.
# Matched against the active window title (case-insensitive).
# Examples:
#   "instagram"  → matches browser tab "Instagram • Direct · Firefox"
#   "telegram"   → matches "Telegram (12)"
#   "whatsapp"   → matches "WhatsApp"
#   ""           → no restriction, monitors everything

TARGET_APP = "telegram"          # ← CHANGE THIS to "instagram", "whatsapp", etc.

MIN_TEXT_LENGTH          = 30    # minimum chars before scoring
CLIPBOARD_POLL_INTERVAL  = 1.5   # seconds between clipboard checks
KEYBOARD_FLUSH_WORD_COUNT = 8    # words buffered before scoring
ALERT_THRESHOLD          = 65.0  # risk score that triggers an alert
DB_PATH                  = "monitor_history.db"


# ─────────────────────────────────────────────────────────────
# Window Detection
# ─────────────────────────────────────────────────────────────

def get_active_window_title() -> str:
    """Returns the title of the currently focused window."""
    try:
        import pygetwindow as gw
        win = gw.getActiveWindow()
        return win.title if win else ""
    except Exception:
        return ""


def is_target_app_active() -> bool:
    """
    Returns True if the currently focused window matches TARGET_APP.
    If TARGET_APP is empty, always returns True (no restriction).
    """
    if not TARGET_APP:
        return True
    return TARGET_APP.lower() in get_active_window_title().lower()


def get_active_app_label() -> str:
    title = get_active_window_title()
    return (title[:40] + "…") if len(title) > 40 else title


# ─────────────────────────────────────────────────────────────
# Shared Utilities
# ─────────────────────────────────────────────────────────────

def _timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _score_and_store(source: str, text: str,
                     db: MonitorStorage, window: str = "") -> dict:
    """Score text with risk_engine and save to SQLite."""
    text = text.strip()
    if len(text) < MIN_TEXT_LENGTH:
        return {}

    assessment = full_risk_assessment(text=text, sentiment=0.0, label=0)
    db.insert_with_score(source, text, assessment)

    score = assessment["composite_score"]
    label = assessment["risk_label"]
    print(f"[{_timestamp()}] [{source.upper()}] {label} ({score:.1f})  "
          f"→  {text[:55]}{'…' if len(text) > 55 else ''}")

    if score >= ALERT_THRESHOLD:
        print(f"\n  ⚠️  ALERT  score={score:.1f}  app={window}")
        print(f"  Keywords: {assessment.get('high_keywords', [])}\n")

    return assessment


# ─────────────────────────────────────────────────────────────
# Clipboard Monitor
# ─────────────────────────────────────────────────────────────

class ClipboardMonitor:
    def __init__(self, db: MonitorStorage):
        self.db            = db
        self.running       = False
        self._last_content = ""
        self._thread       = None

    def start(self):
        self.running       = True
        self._last_content = pyperclip.paste()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="ClipboardMonitor"
        )
        self._thread.start()
        target = f'"{TARGET_APP}"' if TARGET_APP else "ALL apps"
        print(f"📋 Clipboard monitor  → running  (watching: {target})")

    def stop(self):
        self.running = False

    def _loop(self):
        while self.running:
            try:
                current = pyperclip.paste()
                if current and current != self._last_content:
                    self._last_content = current
                    # Only save if target app is currently active
                    if is_target_app_active():
                        _score_and_store("clipboard", current,
                                         self.db, get_active_app_label())
            except Exception as exc:
                print(f"[ClipboardMonitor] error: {exc}")
            time.sleep(CLIPBOARD_POLL_INTERVAL)


# ─────────────────────────────────────────────────────────────
# Keyboard Monitor
# ─────────────────────────────────────────────────────────────

class KeyboardMonitor:
    def __init__(self, db: MonitorStorage, stop_callback=None):
        self.db            = db
        self.stop_callback = stop_callback
        self._word_buffer  = []
        self._char_buffer  = []
        self._listener     = None

    def start(self):
        target = f'"{TARGET_APP}"' if TARGET_APP else "ALL apps"
        print(f"⌨️  Keyboard monitor   → running  (watching: {target})  |  ESC to stop")
        self._listener = keyboard.Listener(
            on_press   = self._on_press,
            on_release = self._on_release,
        )
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()

    def join(self):
        if self._listener:
            self._listener.join()

    def _on_press(self, key):
        # ESC always stops regardless of active window
        try:
            if key == keyboard.Key.esc:
                self._flush_current_word()
                self._flush_sentence(force=True)
                self.stop()
                if self.stop_callback:
                    self.stop_callback()
                return False
        except Exception:
            pass

        # Skip if target app is not the focused window
        if not is_target_app_active():
            return

        try:
            char = key.char
            if char:
                self._char_buffer.append(char)
        except AttributeError:
            if key == keyboard.Key.space:
                self._flush_current_word()
            elif key == keyboard.Key.enter:
                self._flush_current_word()
                self._flush_sentence(force=True)
            elif key == keyboard.Key.backspace:
                if self._char_buffer:
                    self._char_buffer.pop()

    def _on_release(self, _key):
        pass

    def _flush_current_word(self):
        word = "".join(self._char_buffer).strip()
        if word:
            self._word_buffer.append(word)
        self._char_buffer.clear()
        if len(self._word_buffer) >= KEYBOARD_FLUSH_WORD_COUNT:
            self._flush_sentence()

    def _flush_sentence(self, force: bool = False):
        if not self._word_buffer:
            return
        sentence = " ".join(self._word_buffer)
        self._word_buffer.clear()
        if force or len(sentence) >= MIN_TEXT_LENGTH:
            _score_and_store("keyboard", sentence,
                             self.db, get_active_app_label())


# ─────────────────────────────────────────────────────────────
# Combined Text Monitor
# ─────────────────────────────────────────────────────────────

class TextMonitor:
    def __init__(self, db_path: str = DB_PATH):
        self.db         = MonitorStorage(db_path=db_path)
        self._clipboard = ClipboardMonitor(db=self.db)
        self._keyboard  = KeyboardMonitor(
            db=self.db, stop_callback=self._on_stop
        )

    def start(self):
        target = f'"{TARGET_APP}"' if TARGET_APP else "ALL APPLICATIONS"
        print("\n" + "═" * 62)
        print("  🧠 MindGuard Text Monitor")
        print(f"  Target app      : {target}")
        print(f"  Min text length : {MIN_TEXT_LENGTH} chars")
        print(f"  Flush every     : {KEYBOARD_FLUSH_WORD_COUNT} words")
        print(f"  Alert threshold : {ALERT_THRESHOLD}/100")
        print(f"  Database        : {DB_PATH}")
        print("  Press ESC to stop")
        print("═" * 62 + "\n")

        self._clipboard.start()
        self._keyboard.start()
        self._keyboard.join()

    def _on_stop(self):
        self._clipboard.stop()
        summary = self.db.get_summary()
        print("\n" + "─" * 50)
        print(f"  Session Summary  (app: {TARGET_APP or 'ALL'})")
        print(f"  Total captured  : {summary.get('total', 0)}")
        print(f"  🔴 High risk    : {summary.get('high_count', 0)}")
        print(f"  🟡 Medium risk  : {summary.get('medium_count', 0)}")
        print(f"  🟢 Low risk     : {summary.get('low_count', 0)}")
        print(f"  Avg score       : {summary.get('avg_score', 0)}")
        print("─" * 50)
        self.db.close()
        print("✅ Text monitor stopped.\n")


if __name__ == "__main__":
    monitor = TextMonitor(db_path=DB_PATH)
    monitor.start()