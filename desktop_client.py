# desktop_client.py
# ─────────────────────────────────────────────────────────────
# PyQt6 Desktop Client — Emotional Risk Analysis
# Enhanced UI + user-friendly labels
# ─────────────────────────────────────────────────────────────

import sys
import json
import asyncio
import os
import requests
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QProgressBar, QFrame,
    QStatusBar, QMessageBox, QCheckBox, QGraphicsDropShadowEffect,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import websockets


# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

API_BASE_URL    = os.getenv("API_BASE_URL",        "http://localhost:8000")
WS_URL          = os.getenv("WS_URL",              "ws://localhost:8000/ws/analyze")
DESKTOP_API_KEY = os.getenv("DESKTOP_APP_API_KEY", "dev-secret-key-change-in-prod")

RISK_COLOURS = {
    "high"  : "#E53935",
    "medium": "#FB8C00",
    "low"   : "#43A047",
}

RISK_BG_COLOURS = {
    "high"  : "#FFEBEE",
    "medium": "#FFF3E0",
    "low"   : "#E8F5E9",
}

# ── Friendly user-facing label maps (suggested fix) ──────────
FRIENDLY_SCORE = {
    "high"  : "⚠️ Significant Distress",
    "medium": "😟 Moderate Difficulty",
    "low"   : "🙂 Mild or No Distress",
}

FRIENDLY_SENTIMENT = {
    "negative": "😔 Difficult Tone",
    "neutral" : "😐 Balanced Tone",
    "positive": "🙂 Positive Tone",
}

FRIENDLY_POLARITY = {
    "negative": "Difficult",
    "neutral" : "Balanced",
    "positive": "Positive",
}

SUPPORT_MESSAGES = {
    "high": (
        "We noticed signs of significant distress in your message. "
        "You don't have to face this alone.\n\n"
        "🆘  Call or text 988 (Suicide & Crisis Lifeline)\n"
        "💬  Text HOME to 741741 (Crisis Text Line)\n"
        "🏥  Visit your nearest emergency room if you feel unsafe"
    ),
    "medium": (
        "We detected some signs of emotional difficulty. "
        "It's okay to ask for help.\n\n"
        "💙  Consider speaking with a counsellor or trusted person\n"
        "📱  Try the Woebot or Sanvello app for guided support\n"
        "🤝  7 Cups offers free peer support at 7cups.com"
    ),
    "low": (
        "You seem to be managing, but it's always good to check in with yourself.\n\n"
        "🧘  Try 5–10 minutes of mindfulness or breathing exercises\n"
        "🚶  A short walk outside can lift your mood\n"
        "💬  Reach out to a friend or family member today"
    ),
}


# ─────────────────────────────────────────────────────────────
# Global Stylesheet
# ─────────────────────────────────────────────────────────────

APP_STYLE = """
QMainWindow { background-color: #F0F4F8; }
QWidget { background-color: #F0F4F8; }
QTextEdit#text_input {
    background-color: #FFFFFF;
    border: 2px solid #C5CAE9;
    border-radius: 10px;
    padding: 10px;
    font-size: 13px;
    color: #263238;
}
QTextEdit#text_input:focus { border: 2px solid #3F51B5; }
QTextEdit#detail_output {
    background-color: #FAFAFA;
    border: 1px solid #E0E0E0;
    border-radius: 8px;
    padding: 10px;
    font-family: 'Courier New', monospace;
    font-size: 11px;
    color: #37474F;
}
QPushButton#analyse_btn {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #3F51B5, stop:1 #5C6BC0);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 12px 24px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton#analyse_btn:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #303F9F, stop:1 #3F51B5);
}
QPushButton#analyse_btn:disabled { background: #B0BEC5; color: #ECEFF1; }
QPushButton#clear_btn {
    background-color: #FFFFFF;
    color: #546E7A;
    border: 2px solid #CFD8DC;
    border-radius: 10px;
    padding: 12px 24px;
    font-size: 13px;
}
QPushButton#clear_btn:hover { background-color: #ECEFF1; border-color: #90A4AE; }
QPushButton#clear_btn:disabled { color: #B0BEC5; }
QCheckBox { color: #546E7A; font-size: 12px; spacing: 6px; }
QCheckBox::indicator {
    width: 18px; height: 18px;
    border-radius: 4px; border: 2px solid #9FA8DA; background: white;
}
QCheckBox::indicator:checked { background-color: #3F51B5; border-color: #3F51B5; }
QProgressBar {
    border: none; border-radius: 3px;
    background-color: #E8EAF6; height: 6px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #3F51B5, stop:1 #7986CB);
    border-radius: 3px;
}
QStatusBar {
    background-color: #E8EAF6; color: #3F51B5;
    font-size: 11px; border-top: 1px solid #C5CAE9;
}
QScrollArea { border: none; background: transparent; }
"""


# ─────────────────────────────────────────────────────────────
# WebSocket Worker Thread
# ─────────────────────────────────────────────────────────────

class WebSocketWorker(QThread):
    progress_update = pyqtSignal(str)
    result_received = pyqtSignal(dict)
    error_occurred  = pyqtSignal(str)
    analysis_done   = pyqtSignal()

    def __init__(self, text: str, include_rag: bool = False, top_k: int = 5):
        super().__init__()
        self.text        = text
        self.include_rag = include_rag
        self.top_k       = top_k
        self._running    = True

    def run(self):
        asyncio.run(self._connect_and_stream())

    async def _connect_and_stream(self):
        try:
            async with websockets.connect(WS_URL) as ws:
                payload = json.dumps({
                    "text"       : self.text,
                    "include_rag": self.include_rag,
                    "top_k"      : self.top_k,
                    "api_key"    : DESKTOP_API_KEY,
                })
                await ws.send(payload)

                async for raw in ws:
                    if not self._running:
                        break
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    event = msg.get("event")
                    if event == "progress":
                        self.progress_update.emit(msg.get("stage", "processing"))
                    elif event == "result":
                        self.result_received.emit(msg.get("data", {}))
                    elif event == "done":
                        self.analysis_done.emit()
                        break
                    elif event == "error":
                        self.error_occurred.emit(msg.get("detail", "Unknown error"))
                        break

        except ConnectionRefusedError:
            self.error_occurred.emit(
                f"Cannot connect to backend server.\n"
                f"Make sure main.py is running on {API_BASE_URL}"
            )
        except Exception as e:
            self.error_occurred.emit(f"WebSocket error: {str(e)}")

    def stop(self):
        self._running = False


# ─────────────────────────────────────────────────────────────
# HTTP Health Check Worker
# ─────────────────────────────────────────────────────────────

class HealthCheckWorker(QThread):
    health_result = pyqtSignal(bool, str)

    def run(self):
        try:
            resp = requests.get(f"{API_BASE_URL}/health", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                msg  = (
                    f"✅ Backend online  |  "
                    f"Model: {'✓' if data.get('model_loaded') else '✗'}  |  "
                    f"Index: {data.get('total_vectors', 0)} vectors"
                )
                self.health_result.emit(True, msg)
            else:
                self.health_result.emit(False, f"Backend returned HTTP {resp.status_code}")
        except requests.exceptions.ConnectionError:
            self.health_result.emit(False, "❌ Backend unreachable — is main.py running?")
        except Exception as e:
            self.health_result.emit(False, f"Health check failed: {str(e)}")


# ─────────────────────────────────────────────────────────────
# Enhanced Metric Card Widget
# ─────────────────────────────────────────────────────────────

class MetricCard(QFrame):
    """Rounded card displaying a single metric."""

    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("metric_card")
        self.setMinimumHeight(110)
        self._apply_default_style()

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        icon_lbl = QLabel(icon)
        icon_lbl.setFont(QFont("Arial", 15))
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #78909C; font-size: 10px; font-weight: bold;")
        top_row.addWidget(icon_lbl)
        top_row.addWidget(lbl)
        top_row.addStretch()
        layout.addLayout(top_row)

        self.value_lbl = QLabel("—")
        self.value_lbl.setWordWrap(True)
        self.value_lbl.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.value_lbl.setStyleSheet("color: #263238;")
        layout.addWidget(self.value_lbl)
        layout.addStretch()

    def _apply_default_style(self):
        self.setStyleSheet("""
            QFrame#metric_card {
                background-color: #FFFFFF;
                border-radius: 12px;
                border: 1px solid #E8EAF6;
            }
        """)

    def set_value(self, text: str, colour: str = None, bg_colour: str = None):
        self.value_lbl.setText(text)
        fg = colour or "#263238"
        bg = bg_colour or "#FFFFFF"
        border = colour or "#E8EAF6"
        self.value_lbl.setStyleSheet(
            f"color: {fg}; font-size: 12px; font-weight: bold;"
        )
        self.setStyleSheet(f"""
            QFrame#metric_card {{
                background-color: {bg};
                border-radius: 12px;
                border: 1px solid {border};
            }}
        """)

    def reset(self):
        self.value_lbl.setText("—")
        self.value_lbl.setStyleSheet("color: #263238; font-size: 12px; font-weight: bold;")
        self._apply_default_style()


# ─────────────────────────────────────────────────────────────
# Support Message Banner
# ─────────────────────────────────────────────────────────────

class SupportBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("support_banner")
        self.setVisible(False)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 25))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)

        self.message_lbl = QLabel()
        self.message_lbl.setWordWrap(True)
        self.message_lbl.setFont(QFont("Arial", 11))
        self.message_lbl.setStyleSheet("color: #263238;")
        layout.addWidget(self.message_lbl)

    def show_message(self, level: str, message: str):
        bg     = RISK_BG_COLOURS.get(level, "#F5F5F5")
        border = RISK_COLOURS.get(level, "#90A4AE")
        self.setStyleSheet(f"""
            QFrame#support_banner {{
                background-color: {bg};
                border-radius: 10px;
                border-left: 4px solid {border};
            }}
        """)
        self.message_lbl.setText(message)
        self.setVisible(True)

    def hide_message(self):
        self.setVisible(False)


# ─────────────────────────────────────────────────────────────
# Stage Progress Indicator
# ─────────────────────────────────────────────────────────────

class StageIndicator(QWidget):
    STAGES       = ["keyword", "sentiment", "scoring", "rag"]
    STAGE_LABELS = {
        "keyword"  : "Keywords",
        "sentiment": "Sentiment",
        "scoring"  : "Scoring",
        "rag"      : "RAG",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_stage = None
        self.setFixedHeight(38)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch()

        self.dots   = {}
        self.labels = {}

        for i, stage in enumerate(self.STAGES):
            col = QVBoxLayout()
            col.setSpacing(2)
            col.setAlignment(Qt.AlignmentFlag.AlignCenter)

            dot = QLabel("●")
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setStyleSheet("color: #CFD8DC; font-size: 14px; background: transparent;")

            lbl = QLabel(self.STAGE_LABELS[stage])
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #B0BEC5; font-size: 9px; background: transparent;")

            col.addWidget(dot)
            col.addWidget(lbl)
            self.dots[stage]   = dot
            self.labels[stage] = lbl
            layout.addLayout(col)

            if i < len(self.STAGES) - 1:
                line = QLabel("──")
                line.setStyleSheet("color: #CFD8DC; font-size: 10px; background: transparent;")
                line.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(line)

        layout.addStretch()

    def set_stage(self, stage: str):
        self.current_stage = stage
        idx = self.STAGES.index(stage) if stage in self.STAGES else -1
        for i, s in enumerate(self.STAGES):
            if i < idx:
                self.dots[s].setStyleSheet("color: #43A047; font-size:14px; background:transparent;")
                self.labels[s].setStyleSheet("color: #43A047; font-size:9px; background:transparent;")
            elif i == idx:
                self.dots[s].setStyleSheet("color: #3F51B5; font-size:14px; background:transparent;")
                self.labels[s].setStyleSheet("color: #3F51B5; font-size:9px; font-weight:bold; background:transparent;")
            else:
                self.dots[s].setStyleSheet("color: #CFD8DC; font-size:14px; background:transparent;")
                self.labels[s].setStyleSheet("color: #B0BEC5; font-size:9px; background:transparent;")

    def set_complete(self):
        self.current_stage = "done"
        for s in self.STAGES:
            self.dots[s].setStyleSheet("color: #43A047; font-size:14px; background:transparent;")
            self.labels[s].setStyleSheet("color: #43A047; font-size:9px; background:transparent;")

    def reset(self):
        self.current_stage = None
        for s in self.STAGES:
            self.dots[s].setStyleSheet("color: #CFD8DC; font-size:14px; background:transparent;")
            self.labels[s].setStyleSheet("color: #B0BEC5; font-size:9px; background:transparent;")


# ─────────────────────────────────────────────────────────────
# Main Window
# ─────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Emotional Risk Analyser")
        self.setMinimumSize(960, 820)
        self._worker: WebSocketWorker | None = None
        self._build_ui()
        self._run_health_check()

    def _build_ui(self):
        self.setStyleSheet(APP_STYLE)

        # Scrollable root
        container = QWidget()
        scroll    = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        scroll.setStyleSheet("QScrollArea { border: none; background: #F0F4F8; }")
        self.setCentralWidget(scroll)

        root = QVBoxLayout(container)
        root.setSpacing(14)
        root.setContentsMargins(24, 20, 24, 20)

        # ── Header card ────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #1A237E, stop:1 #3F51B5);
                border-radius: 14px;
            }
        """)
        hdr_shadow = QGraphicsDropShadowEffect()
        hdr_shadow.setBlurRadius(16)
        hdr_shadow.setOffset(0, 4)
        hdr_shadow.setColor(QColor(63, 81, 181, 80))
        header.setGraphicsEffect(hdr_shadow)

        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 16, 20, 16)

        brain = QLabel("🧠")
        brain.setFont(QFont("Arial", 32))
        brain.setStyleSheet("background: transparent;")
        h_layout.addWidget(brain)

        title_col = QVBoxLayout()
        t1 = QLabel("Emotional Risk Analysis")
        t1.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        t1.setStyleSheet("color: white; background: transparent;")
        t2 = QLabel("Real-time mental health text assessment powered by AI")
        t2.setStyleSheet("color: #9FA8DA; font-size: 11px; background: transparent;")
        title_col.addWidget(t1)
        title_col.addWidget(t2)
        h_layout.addLayout(title_col)
        h_layout.addStretch()

        self.conn_badge = QLabel("⬤  Connecting…")
        self.conn_badge.setStyleSheet(
            "color: #FFF9C4; font-size: 11px; font-weight: bold; background: transparent;"
        )
        h_layout.addWidget(self.conn_badge)
        root.addWidget(header)

        # ── Input card ─────────────────────────────────────────
        input_card = self._make_card()
        ic_layout  = QVBoxLayout(input_card)
        ic_layout.setContentsMargins(16, 14, 16, 14)
        ic_layout.setSpacing(10)

        ic_layout.addWidget(self._section_label("📝  Enter text to analyse"))

        self.text_input = QTextEdit()
        self.text_input.setObjectName("text_input")
        self.text_input.setPlaceholderText(
            "Type or paste text here…\n\n"
            "Example: 'I've been feeling really overwhelmed lately and can't sleep.'"
        )
        self.text_input.setMinimumHeight(110)
        self.text_input.setMaximumHeight(160)
        ic_layout.addWidget(self.text_input)

        bottom_row = QHBoxLayout()
        self.rag_checkbox = QCheckBox("Include similar case retrieval (RAG)")
        self.rag_checkbox.setToolTip("Fetch similar cases from the corpus for context")
        bottom_row.addWidget(self.rag_checkbox)
        bottom_row.addStretch()

        self.clear_btn = QPushButton("🗑  Clear")
        self.clear_btn.setObjectName("clear_btn")
        self.clear_btn.setMinimumHeight(42)
        self.clear_btn.setMinimumWidth(110)
        self.clear_btn.clicked.connect(self._clear_all)

        self.analyse_btn = QPushButton("▶   Analyse Now")
        self.analyse_btn.setObjectName("analyse_btn")
        self.analyse_btn.setMinimumHeight(42)
        self.analyse_btn.setMinimumWidth(160)
        self.analyse_btn.clicked.connect(self._start_analysis)

        bottom_row.addWidget(self.clear_btn)
        bottom_row.addWidget(self.analyse_btn)
        ic_layout.addLayout(bottom_row)
        root.addWidget(input_card)

        # ── Progress ───────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)
        root.addWidget(self.progress_bar)

        self.stage_indicator = StageIndicator()
        self.stage_indicator.setVisible(False)
        root.addWidget(self.stage_indicator)

        self.stage_label = QLabel("")
        self.stage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stage_label.setStyleSheet(
            "color: #5C6BC0; font-size: 11px; font-style: italic; background: transparent;"
        )
        root.addWidget(self.stage_label)

        # ── Support banner ─────────────────────────────────────
        self.support_banner = SupportBanner()
        root.addWidget(self.support_banner)

        # ── Metric cards ───────────────────────────────────────
        root.addWidget(self._section_label("📊  Analysis Results"))

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(12)
        self.score_card     = MetricCard("🎯", "OVERALL ASSESSMENT")
        self.risk_card      = MetricCard("🚦", "RISK LEVEL")
        self.sentiment_card = MetricCard("💬", "EMOTIONAL TONE")
        self.polarity_card  = MetricCard("🔀", "POLARITY")
        for card in (self.score_card, self.risk_card,
                     self.sentiment_card, self.polarity_card):
            metrics_row.addWidget(card)
        root.addLayout(metrics_row)

        # ── Detail card ────────────────────────────────────────
        detail_card = self._make_card()
        dc_layout   = QVBoxLayout(detail_card)
        dc_layout.setContentsMargins(16, 14, 16, 14)
        dc_layout.setSpacing(8)
        dc_layout.addWidget(self._section_label("🔍  Detailed Breakdown"))

        self.detail_output = QTextEdit()
        self.detail_output.setObjectName("detail_output")
        self.detail_output.setReadOnly(True)
        self.detail_output.setMinimumHeight(180)
        self.detail_output.setPlaceholderText(
            "Analysis details will appear here after you run an assessment…"
        )
        dc_layout.addWidget(self.detail_output)
        root.addWidget(detail_card)

        # ── Status bar ─────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Starting up…")

    # ── Helper: card frame ────────────────────────────────────

    def _make_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 12px;
                border: 1px solid #E8EAF6;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 20))
        card.setGraphicsEffect(shadow)
        return card

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #37474F; font-size: 12px; font-weight: bold; background: transparent;"
        )
        return lbl

    # ── Health Check ──────────────────────────────────────────

    def _run_health_check(self):
        self.health_worker = HealthCheckWorker()
        self.health_worker.health_result.connect(self._on_health_result)
        self.health_worker.start()

    def _on_health_result(self, healthy: bool, message: str):
        self.status_bar.showMessage(message)
        self.analyse_btn.setEnabled(healthy)
        if healthy:
            self.conn_badge.setText("⬤  Connected")
            self.conn_badge.setStyleSheet(
                "color: #A5D6A7; font-size: 11px; font-weight: bold; background: transparent;"
            )
        else:
            self.conn_badge.setText("⬤  Offline")
            self.conn_badge.setStyleSheet(
                "color: #EF9A9A; font-size: 11px; font-weight: bold; background: transparent;"
            )
            self.detail_output.setText(
                "⚠️  Backend server is not reachable.\n\n"
                "Start it with:\n"
                "    uvicorn main:app --host 0.0.0.0 --port 8000\n\n"
                f"Expected URL: {API_BASE_URL}"
            )

    # ── Analysis Flow ─────────────────────────────────────────

    def _start_analysis(self):
        text = self.text_input.toPlainText().strip()
        if len(text) < 10:
            QMessageBox.warning(
                self, "Input too short",
                "Please enter at least 10 characters to analyse."
            )
            return

        self._set_busy(True)
        self.detail_output.clear()
        self.support_banner.hide_message()
        self.stage_indicator.reset()
        self.stage_indicator.setVisible(True)

        self._worker = WebSocketWorker(
            text        = text,
            include_rag = self.rag_checkbox.isChecked(),
        )
        self._worker.progress_update.connect(self._on_progress)
        self._worker.result_received.connect(self._on_result)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.analysis_done.connect(self._on_done)
        self._worker.start()

    def _on_progress(self, stage: str):
        stage_labels = {
            "keyword"  : "🔍  Scanning for emotional keywords…",
            "sentiment": "💬  Analysing emotional tone…",
            "scoring"  : "📊  Calculating risk score…",
            "rag"      : "🗂️   Retrieving similar cases…",
        }
        self.stage_label.setText(stage_labels.get(stage, f"Processing: {stage}…"))
        self.stage_indicator.set_stage(stage)
        self.status_bar.showMessage(f"Analysing — stage: {stage}")

    def _on_result(self, data: dict):
        score  = data.get("composite_score", 0)
        level  = data.get("risk_level", "low")
        colour = RISK_COLOURS.get(level, "#888888")
        bg     = RISK_BG_COLOURS.get(level, "#FAFAFA")

        sent_detail = data.get("sentiment_detail", {})
        polarity    = sent_detail.get("polarity", "neutral").lower()

        # ── Friendly metric cards (suggested fix applied here) ─
        self.score_card.set_value(
            FRIENDLY_SCORE.get(level, "—"), colour, bg
        )
        self.risk_card.set_value(
            data.get("risk_label", "—"), colour, bg
        )
        self.sentiment_card.set_value(
            FRIENDLY_SENTIMENT.get(polarity, "—"),
            RISK_COLOURS.get(
                "high"   if polarity == "negative" else
                "low"    if polarity == "positive" else "medium",
                "#888"
            )
        )
        self.polarity_card.set_value(
            FRIENDLY_POLARITY.get(polarity, "—")
        )

        # ── Empathetic support banner ─────────────────────────
        self.support_banner.show_message(
            level, SUPPORT_MESSAGES.get(level, "")
        )

        # ── Detailed breakdown (internal reference) ───────────
        kw        = data.get("keyword_detail", {})
        high_kw   = kw.get("matched_high",   [])
        medium_kw = kw.get("matched_medium", [])
        low_kw    = kw.get("matched_low",    [])

        lines = [
            "━━━  KEYWORD ANALYSIS  ━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"  High-risk words   : {', '.join(high_kw)   if high_kw   else 'None detected'}",
            f"  Medium-risk words : {', '.join(medium_kw) if medium_kw else 'None detected'}",
            f"  Low-risk words    : {', '.join(low_kw)    if low_kw    else 'None detected'}",
            "",
            "━━━  INTERNAL SCORES  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"  Keyword score     : {data['scores']['keyword_score']}  / 10",
            f"  Sentiment score   : {data['scores']['sentiment_score']} / 10",
            f"  Composite score   : {data['scores']['composite_score']} / 10",
            f"  Adjusted sentiment: {sent_detail.get('adjusted_sentiment', '—')}",
            f"  Negation detected : {'Yes' if sent_detail.get('negation_detected') else 'No'}",
            f"  Intensifiers found: {'Yes' if sent_detail.get('intensifier_boost') else 'No'}",
        ]

        if data.get("rag_response"):
            lines += [
                "",
                "━━━  AI RESPONSE  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                f"  {data['rag_response']}",
            ]

        if data.get("similar_posts"):
            lines += ["", "━━━  SIMILAR CASES  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
            for post in data["similar_posts"][:3]:
                lines.append(
                    f"  [{post.get('similarity_score', 0):.3f}]  {post.get('text', '')}"
                )

        self.detail_output.setText("\n".join(lines))

    def _on_error(self, message: str):
        self._set_busy(False)
        self.stage_label.setText("")
        self.stage_indicator.reset()
        self.status_bar.showMessage("❌  Error during analysis")
        QMessageBox.critical(self, "Analysis Error", message)

    def _on_done(self):
        self._set_busy(False)
        self.stage_label.setText("")
        self.stage_indicator.set_complete()
        self.status_bar.showMessage("✅  Analysis complete")

    # ── Helpers ───────────────────────────────────────────────

    def _set_busy(self, busy: bool):
        self.analyse_btn.setEnabled(not busy)
        self.clear_btn.setEnabled(not busy)
        self.progress_bar.setVisible(busy)

    def _clear_all(self):
        self.text_input.clear()
        self.detail_output.clear()
        self.stage_label.setText("")
        self.stage_indicator.reset()
        self.stage_indicator.setVisible(False)
        self.support_banner.hide_message()
        for card in (self.score_card, self.risk_card,
                     self.sentiment_card, self.polarity_card):
            card.reset()
        self.status_bar.showMessage("Cleared — ready for new analysis")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)
        event.accept()


# ─────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
    