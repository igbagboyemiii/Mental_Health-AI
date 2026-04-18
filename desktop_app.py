# desktop_app.py
# ─────────────────────────────────────────────────────────────
# Mental Health Monitoring Assistant — Desktop Interface
# Connects to your existing FastAPI backend on localhost:8000
# ─────────────────────────────────────────────────────────────

import sys
import json
import httpx
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QSlider, QFrame,
    QScrollArea, QSplitter, QProgressBar, QTextEdit,
    QGroupBox, QGridLayout, QStatusBar
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation,
    QEasingCurve
)
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon

BASE_URL = "http://localhost:8000"

# ─────────────────────────────────────────────────────────────
# COLORS & STYLES
# ─────────────────────────────────────────────────────────────

COLORS = {
    "bg_dark"    : "#080c14",
    "bg_panel"   : "#0d1220",
    "bg_card"    : "#111827",
    "bg_card2"   : "#0f1729",
    "border"     : "#1e2d45",
    "border_hi"  : "#2a4a7f",
    "text_main"  : "#cdd9f0",
    "text_dim"   : "#4a6080",
    "text_bright": "#e8f0ff",
    "accent"     : "#3b82f6",
    "accent_glow": "#1d4ed8",
    "NONE"       : "#6b7280",
    "LOW"        : "#10b981",
    "MODERATE"   : "#f59e0b",
    "HIGH"       : "#f97316",
    "CRISIS"     : "#ef4444",
    "healthy"    : "#10b981",
    "unhealthy"  : "#ef4444",
    "teal"       : "#06b6d4",
    "purple"     : "#8b5cf6",
}

TIER_COLORS = {
    "NONE"    : "#6b7280",
    "LOW"     : "#10b981",
    "MODERATE": "#f59e0b",
    "HIGH"    : "#f97316",
    "CRISIS"  : "#ef4444",
}

APP_STYLE = f"""
    QMainWindow, QWidget {{
        background-color: {COLORS['bg_dark']};
        color: {COLORS['text_main']};
        font-family: 'Trebuchet MS', 'Segoe UI', sans-serif;
    }}
    QGroupBox {{
        border: 1px solid {COLORS['border']};
        border-top: 2px solid {COLORS['border_hi']};
        border-radius: 10px;
        margin-top: 14px;
        padding: 12px 10px 10px 10px;
        font-weight: bold;
        color: {COLORS['teal']};
        font-size: 10px;
        letter-spacing: 2px;
        background-color: {COLORS['bg_panel']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 14px;
        padding: 0 8px;
        background-color: {COLORS['bg_panel']};
    }}
    QPushButton {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {COLORS['accent']}, stop:1 {COLORS['accent_glow']});
        color: {COLORS['text_bright']};
        border: 1px solid {COLORS['border_hi']};
        border-radius: 8px;
        padding: 9px 20px;
        font-size: 12px;
        font-weight: bold;
        letter-spacing: 0.5px;
    }}
    QPushButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #60a5fa, stop:1 {COLORS['accent']});
        border-color: #60a5fa;
    }}
    QPushButton:pressed {{
        background: {COLORS['accent_glow']};
        padding-top: 10px;
    }}
    QPushButton:disabled {{
        background: {COLORS['bg_card']};
        color: {COLORS['text_dim']};
        border-color: {COLORS['border']};
    }}
    QPushButton#secondary {{
        background: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        color: {COLORS['text_dim']};
    }}
    QPushButton#secondary:hover {{
        border-color: {COLORS['teal']};
        color: {COLORS['teal']};
        background: {COLORS['bg_card2']};
    }}
    QSlider::groove:horizontal {{
        height: 5px;
        background: {COLORS['border']};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {COLORS['accent']};
        border: 2px solid {COLORS['text_bright']};
        width: 14px; height: 14px;
        margin: -5px 0;
        border-radius: 8px;
    }}
    QSlider::handle:horizontal:hover {{
        background: #60a5fa;
        width: 16px; height: 16px;
        margin: -6px 0;
    }}
    QSlider::sub-page:horizontal {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {COLORS['teal']}, stop:1 {COLORS['accent']});
        border-radius: 3px;
    }}
    QTextEdit {{
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        border-radius: 8px;
        padding: 10px;
        color: {COLORS['text_main']};
        font-size: 12px;
        selection-background-color: {COLORS['accent']};
    }}
    QScrollBar:vertical {{
        background: {COLORS['bg_panel']};
        width: 5px;
        border-radius: 3px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {COLORS['border_hi']};
        border-radius: 3px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {COLORS['accent']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QSplitter::handle {{
        background: {COLORS['border']};
        width: 1px;
    }}
    QStatusBar {{
        background: {COLORS['bg_panel']};
        color: {COLORS['text_dim']};
        font-size: 11px;
        border-top: 1px solid {COLORS['border']};
        padding: 0 8px;
    }}
"""


# ─────────────────────────────────────────────────────────────
# BACKGROUND WORKER — non-blocking API calls
# ─────────────────────────────────────────────────────────────

class ApiWorker(QThread):
    result  = pyqtSignal(dict)
    error   = pyqtSignal(str)

    def __init__(self, endpoint, payload=None):
        super().__init__()
        self.endpoint = endpoint
        self.payload  = payload

    def run(self):
        try:
            if self.payload:
                resp = httpx.post(
                    f"{BASE_URL}{self.endpoint}",
                    json=self.payload, timeout=15
                )
            else:
                resp = httpx.get(
                    f"{BASE_URL}{self.endpoint}",
                    timeout=10
                )
            resp.raise_for_status()
            self.result.emit(resp.json())
        except httpx.ConnectError:
            self.error.emit("Cannot connect — is the server running?")
        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────────────────────────────────────────────
# REUSABLE WIDGETS
# ─────────────────────────────────────────────────────────────

class ScoreBar(QWidget):
    """Sleek labeled progress bar with glowing fill."""
    def __init__(self, label, color=None):
        super().__init__()
        self._color = color or COLORS["accent"]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        self.label_w = QLabel(label)
        self.label_w.setFixedWidth(130)
        self.label_w.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 11px; letter-spacing: 0.5px;"
        )

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setFixedHeight(6)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet(f"""
            QProgressBar {{
                background: {COLORS['border']};
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self._color}88, stop:1 {self._color});
                border-radius: 3px;
            }}
        """)

        self.value_w = QLabel("—")
        self.value_w.setFixedWidth(42)
        self.value_w.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value_w.setStyleSheet(
            f"color: {self._color}; font-size: 13px; font-weight: bold; font-family: 'Consolas', monospace;"
        )

        layout.addWidget(self.label_w)
        layout.addWidget(self.bar)
        layout.addWidget(self.value_w)

    def set_value(self, v):
        self.bar.setValue(int(v * 100))
        self.value_w.setText(f"{v:.2f}")


class IndicatorSlider(QWidget):
    """A labeled slider with live value pill."""
    def __init__(self, key, label, min_v, max_v, default, step=1):
        super().__init__()
        self.key   = key
        self.step  = step
        self.min_v = min_v
        self.max_v = max_v

        self.setFixedHeight(36)
        layout = QGridLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setColumnStretch(1, 1)
        layout.setSpacing(8)

        name = QLabel(label)
        name.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 11px; letter-spacing: 0.3px;"
        )
        name.setFixedWidth(128)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        int_max     = int((max_v - min_v) / step)
        int_def     = int((default - min_v) / step)
        self.slider.setRange(0, int_max)
        self.slider.setValue(int_def)
        self.slider.valueChanged.connect(self._update_label)

        self.val_label = QLabel(str(default))
        self.val_label.setFixedWidth(36)
        self.val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.val_label.setStyleSheet(f"""
            color: {COLORS['text_bright']};
            font-weight: bold;
            font-size: 11px;
            font-family: 'Consolas', monospace;
            background: {COLORS['bg_card']};
            border: 1px solid {COLORS['border_hi']};
            border-radius: 4px;
            padding: 1px 3px;
        """)

        layout.addWidget(name,           0, 0)
        layout.addWidget(self.slider,    0, 1)
        layout.addWidget(self.val_label, 0, 2)

    def _update_label(self, v):
        real = self.min_v + v * self.step
        self.val_label.setText(
            str(int(real)) if self.step == 1 else f"{real:.1f}"
        )

    def get_value(self):
        return self.min_v + self.slider.value() * self.step


# ─────────────────────────────────────────────────────────────
# MAIN WINDOW
# ─────────────────────────────────────────────────────────────

class MonitoringApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MindGuard · Mental Health Monitor")
        self.setMinimumSize(1200, 780)
        self.history = []
        self._build_ui()
        self._start_health_poll()

    # ── UI CONSTRUCTION ───────────────────────────────────────

    def _build_ui(self):
        self.setStyleSheet(APP_STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header bar ────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['bg_panel']}, stop:1 #0a1628);
                border-bottom: 1px solid {COLORS['border_hi']};
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        # Logo area
        logo_dot = QLabel("◆")
        logo_dot.setStyleSheet(f"color: {COLORS['teal']}; font-size: 16px; border: none; background: transparent;")
        title = QLabel("MindGuard")
        title.setFont(QFont("Trebuchet MS", 15, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['text_bright']}; letter-spacing: 1px; border: none; background: transparent;")

        subtitle = QLabel("Mental Health Monitoring Assistant")
        subtitle.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px; border: none; background: transparent;")

        divider = QLabel("|")
        divider.setStyleSheet(f"color: {COLORS['border_hi']}; font-size: 18px; margin: 0 8px; border: none; background: transparent;")

        # API status
        self.api_dot = QLabel("●")
        self.api_dot.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 14px; border: none; background: transparent;")
        self.api_lbl = QLabel("Connecting...")
        self.api_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px; border: none; background: transparent;")

        header_layout.addWidget(logo_dot)
        header_layout.addWidget(title)
        header_layout.addWidget(divider)
        header_layout.addWidget(subtitle)
        header_layout.addStretch()
        header_layout.addWidget(self.api_dot)
        header_layout.addWidget(self.api_lbl)
        root.addWidget(header)

        # ── Body ──────────────────────────────────────────────
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(16, 14, 16, 8)
        body_layout.setSpacing(14)

        # Left sidebar
        left = QWidget()
        left.setFixedWidth(330)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        left_layout.addWidget(self._build_input_panel())
        left_layout.addStretch()
        body_layout.addWidget(left)

        # Right panel
        right        = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        right_layout.addWidget(self._build_score_panel())
        right_layout.addWidget(self._build_suggestion_panel())
        right_layout.addWidget(self._build_history_panel())
        right_layout.addWidget(self._build_monitor_panel())
        body_layout.addWidget(right, stretch=1)

        root.addWidget(body, stretch=1)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready  ·  server must be running on localhost:8000")

    def _build_input_panel(self):
        group = QGroupBox("Assessment Input")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        self.sliders = {}
        INDICATORS = [
            ("stress",        "Stress Level",     1, 10,  5, 1),
            ("mood",          "Mood Quality",      1, 10,  5, 1),
            ("sleep",         "Sleep (hours)",     0, 12,  7, 0.5),
            ("concentration", "Concentration",     1, 10,  5, 1),
            ("social",        "Social Connection", 1, 10,  5, 1),
            ("appetite",      "Appetite / Energy", 1, 10,  5, 1),
            ("activity",      "Activity (days)",   0,  7,  3, 1),
            ("substance",     "Substance Use",     0, 10,  0, 1),
        ]

        for key, label, mn, mx, default, step in INDICATORS:
            s = IndicatorSlider(key, label, mn, mx, default, step)
            self.sliders[key] = s
            layout.addWidget(s)

        btn_row = QHBoxLayout()

        self.assess_btn = QPushButton("▶  Run Assessment")
        self.assess_btn.clicked.connect(self._run_assessment)

        clear_btn = QPushButton("Reset")
        clear_btn.setObjectName("secondary")
        clear_btn.clicked.connect(self._reset_sliders)

        btn_row.addWidget(self.assess_btn)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

        return group

    def _build_score_panel(self):
        group  = QGroupBox("RISK SCORE DASHBOARD")
        layout = QHBoxLayout(group)
        layout.setSpacing(20)

        # Left: tier badge
        badge_col = QVBoxLayout()
        badge_col.setSpacing(4)

        badge_frame = QWidget()
        badge_frame.setFixedSize(120, 100)
        badge_frame.setStyleSheet(f"""
            QWidget {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border_hi']};
                border-radius: 12px;
            }}
        """)
        badge_inner = QVBoxLayout(badge_frame)
        badge_inner.setContentsMargins(8, 8, 8, 8)

        self.tier_label = QLabel("—")
        self.tier_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tier_label.setFont(QFont("Trebuchet MS", 20, QFont.Weight.Bold))
        self.tier_label.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent; border: none;")

        self.composite_label = QLabel("—")
        self.composite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.composite_label.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 11px; font-family: 'Consolas', monospace; background: transparent; border: none;"
        )
        tier_tag = QLabel("RISK TIER")
        tier_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tier_tag.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 9px; letter-spacing: 1.5px; background: transparent; border: none;")

        badge_inner.addWidget(tier_tag)
        badge_inner.addWidget(self.tier_label)
        badge_inner.addWidget(self.composite_label)

        badge_col.addWidget(badge_frame)
        badge_col.addStretch()

        # Right: score bars
        bars_col = QVBoxLayout()
        bars_col.setSpacing(2)

        self.anxiety_bar   = ScoreBar("Anxiety Severity",   COLORS["HIGH"])
        self.burnout_bar   = ScoreBar("Burnout Likelihood",  COLORS["MODERATE"])
        self.composite_bar = ScoreBar("Composite Risk",      COLORS["teal"])

        bars_col.addWidget(self.anxiety_bar)
        bars_col.addWidget(self.burnout_bar)
        bars_col.addWidget(self.composite_bar)

        self.referral_label = QLabel("")
        self.referral_label.setStyleSheet(
            f"font-size: 11px; color: {COLORS['HIGH']}; padding: 2px 0; font-weight: bold;"
        )
        bars_col.addWidget(self.referral_label)

        self.flags_label = QLabel("")
        self.flags_label.setWordWrap(True)
        self.flags_label.setStyleSheet(
            f"font-size: 10px; color: {COLORS['text_dim']}; padding: 1px 0;"
        )
        bars_col.addWidget(self.flags_label)

        layout.addLayout(badge_col)
        layout.addLayout(bars_col, stretch=1)

        return group

    def _build_suggestion_panel(self):
        group  = QGroupBox("SUGGESTIONS")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.suggestion_summary = QLabel("Run an assessment to see personalised suggestions.")
        self.suggestion_summary.setWordWrap(True)
        self.suggestion_summary.setStyleSheet(f"""
            color: {COLORS['text_bright']};
            font-size: 12px;
            padding: 10px 12px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {COLORS['bg_card']}, stop:1 {COLORS['bg_card2']});
            border: 1px solid {COLORS['border_hi']};
            border-left: 3px solid {COLORS['teal']};
            border-radius: 6px;
            line-height: 1.4;
        """)

        self.actions_text = QTextEdit()
        self.actions_text.setReadOnly(True)
        self.actions_text.setFixedHeight(100)
        self.actions_text.setPlaceholderText("Suggested actions will appear here...")
        self.actions_text.setStyleSheet(f"""
            QTextEdit {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 10px;
                color: {COLORS['text_main']};
                font-size: 11px;
                line-height: 1.6;
            }}
        """)

        self.resources_label = QLabel("")
        self.resources_label.setWordWrap(True)
        self.resources_label.setStyleSheet(
            f"color: {COLORS['teal']}; font-size: 10px; padding: 2px 4px; letter-spacing: 0.3px;"
        )

        layout.addWidget(self.suggestion_summary)
        layout.addWidget(self.actions_text)
        layout.addWidget(self.resources_label)

        return group

    def _build_history_panel(self):
        group  = QGroupBox("ASSESSMENT HISTORY")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setFixedHeight(80)
        self.history_text.setPlaceholderText("Past assessments will appear here...")
        self.history_text.setStyleSheet(f"""
            QTextEdit {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px;
                color: {COLORS['text_dim']};
                font-size: 11px;
                font-family: 'Consolas', monospace;
            }}
        """)

        clear_btn = QPushButton("Clear History")
        clear_btn.setObjectName("secondary")
        clear_btn.setFixedWidth(120)
        clear_btn.clicked.connect(self._clear_history)

        layout.addWidget(self.history_text)
        layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignRight)

        return group

    def _build_monitor_panel(self):
        """
        NEW PANEL — shows text captured by text_monitor.py in real time.
        Reads directly from monitor_history.db (monitor_storage.py).
        """
        group  = QGroupBox("TEXT MONITOR  —  LIVE CAPTURES")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        # ── Summary row ───────────────────────────────────────
        summary_row = QHBoxLayout()

        self.mon_total_lbl  = self._stat_badge("Total",  "0", COLORS["accent"])
        self.mon_high_lbl   = self._stat_badge("🔴 High", "0", COLORS["CRISIS"])
        self.mon_medium_lbl = self._stat_badge("🟡 Med",  "0", COLORS["MODERATE"])
        self.mon_low_lbl    = self._stat_badge("🟢 Low",  "0", COLORS["LOW"])
        self.mon_avg_lbl    = self._stat_badge("Avg Score", "—", COLORS["text_dim"])

        for w in [self.mon_total_lbl, self.mon_high_lbl,
                  self.mon_medium_lbl, self.mon_low_lbl, self.mon_avg_lbl]:
            summary_row.addWidget(w)
        summary_row.addStretch()
        layout.addLayout(summary_row)

        # ── Captured text feed ────────────────────────────────
        self.monitor_feed = QTextEdit()
        self.monitor_feed.setReadOnly(True)
        self.monitor_feed.setFixedHeight(160)
        self.monitor_feed.setPlaceholderText(
            "No captures yet.\n\n"
            "Run  python text_monitor.py  in a separate terminal,\n"
            "then type or copy text — scored entries will appear here automatically."
        )
        self.monitor_feed.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px;
                color: {COLORS['text_main']};
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }}
        """)
        layout.addWidget(self.monitor_feed)

        # ── Button row ────────────────────────────────────────
        btn_row = QHBoxLayout()

        refresh_btn = QPushButton("🔄  Refresh Now")
        refresh_btn.clicked.connect(self.load_monitor_history)
        refresh_btn.setFixedWidth(130)

        self.mon_status_lbl = QLabel("Auto-refreshes every 10 s")
        self.mon_status_lbl.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 11px;"
        )

        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(self.mon_status_lbl)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return group

    def _stat_badge(self, label: str, value: str, color: str) -> QWidget:
        """Small stat card used in the monitor summary row."""
        w      = QWidget()
        w.setFixedWidth(82)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(1)
        w.setStyleSheet(f"""
            QWidget {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
        """)

        val_lbl = QLabel(value)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        val_lbl.setStyleSheet(f"color: {color}; border: none; background: transparent;")

        key_lbl = QLabel(label)
        key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        key_lbl.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 10px; border: none; background: transparent;"
        )

        layout.addWidget(val_lbl)
        layout.addWidget(key_lbl)

        # Store reference so load_monitor_history can update the value
        w._val_lbl = val_lbl
        return w

    # ── ACTIONS ───────────────────────────────────────────────

    def _run_assessment(self):
        payload = {k: s.get_value() for k, s in self.sliders.items()}
        self.assess_btn.setEnabled(False)
        self.assess_btn.setText("⏳  Running...")
        self.status.showMessage("Sending assessment to API...")

        self._worker = ApiWorker("/assess", payload)
        self._worker.result.connect(self._on_assessment_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_assessment_result(self, data):
        self.assess_btn.setEnabled(True)
        self.assess_btn.setText("▶  Run Assessment")

        tier      = data.get("tier", "LOW")
        color     = TIER_COLORS.get(tier, COLORS["accent"])
        composite = data.get("composite_score", 0)

        # Update score dashboard
        self.tier_label.setText(tier)
        self.tier_label.setStyleSheet(
            f"color: {color}; font-size: 20px; font-weight: bold; background: transparent; border: none;"
        )

        self.composite_label.setText(f"{composite:.2f}")
        self.composite_label.setStyleSheet(
            f"color: {color}; font-size: 12px; font-family: 'Consolas', monospace; background: transparent; border: none;"
        )

        self.anxiety_bar.set_value(data.get("anxiety_score", 0))
        self.burnout_bar.set_value(data.get("burnout_score", 0))
        self.composite_bar.set_value(composite)

        # Referral flag
        if data.get("professional_referral"):
            self.referral_label.setText("⚠  Professional referral recommended")
        else:
            self.referral_label.setText("")

        # Override flags
        flags = data.get("override_flags", [])
        self.flags_label.setText("\n".join(f"⚑ {f}" for f in flags) if flags else "")

        # Suggestions
        self.suggestion_summary.setText(
            data.get("suggestion_summary", "No summary available.")
        )

        actions = data.get("suggested_actions", [])
        self.actions_text.setPlainText(
            "\n".join(f"  {i+1}. {a}" for i, a in enumerate(actions))
        )

        resources = data.get("resources", [])
        if resources:
            self.resources_label.setText(
                "Resources: " + "  |  ".join(resources)
            )
        else:
            self.resources_label.setText("")

        # Add to history
        timestamp = datetime.now().strftime("%H:%M:%S")
        dominant  = ", ".join(data.get("dominant_factors", []))
        entry     = (
            f"[{timestamp}]  Tier: {tier:<10}"
            f"Score: {composite:.2f}   "
            f"Drivers: {dominant}"
        )
        self.history.insert(0, entry)
        self.history_text.setPlainText("\n".join(self.history[:20]))

        self.status.showMessage(
            f"Assessment complete — Tier: {tier}  |  "
            f"Composite: {composite:.2f}  |  {timestamp}"
        )

    def _on_error(self, msg):
        self.assess_btn.setEnabled(True)
        self.assess_btn.setText("▶  Run Assessment")
        self.status.showMessage(f"Error: {msg}")
        self.suggestion_summary.setText(f"⚠  {msg}")
        self.suggestion_summary.setStyleSheet(
            f"color: {COLORS['CRITICAL']}; font-size: 13px; "
            f"padding: 6px; background: {COLORS['bg_card']}; border-radius: 6px;"
        )

    def _reset_sliders(self):
        defaults = {
            "stress": 5, "mood": 5, "sleep": 7,
            "concentration": 5, "social": 5,
            "appetite": 5, "activity": 3, "substance": 0,
        }
        for key, val in defaults.items():
            s  = self.sliders[key]
            iv = int((val - s.min_v) / s.step)
            s.slider.setValue(iv)

    def _clear_history(self):
        self.history.clear()
        self.history_text.clear()

    # ── HEALTH POLLING ────────────────────────────────────────

    def _start_health_poll(self):
        self._check_health()
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._check_health)
        self._poll_timer.start(10_000)   # every 10 seconds

        # ── Monitor history auto-refresh ──────────────────────
        self.load_monitor_history()                     # load once on startup
        self._monitor_timer = QTimer(self)
        self._monitor_timer.timeout.connect(self.load_monitor_history)
        self._monitor_timer.start(10_000)               # refresh every 10 s

    def load_monitor_history(self):
        """
        Read captured text history from monitor_history.db
        (written by text_monitor.py via monitor_storage.py)
        and display it in the monitor feed panel.
        """
        try:
            from monitor_storage import MonitorStorage

            db      = MonitorStorage()
            rows    = db.query_recent(limit=30)
            summary = db.get_summary()
            db.close()

            # ── Update summary badges ─────────────────────────
            self.mon_total_lbl._val_lbl.setText(
                str(summary.get("total", 0))
            )
            self.mon_high_lbl._val_lbl.setText(
                str(summary.get("high_count", 0))
            )
            self.mon_medium_lbl._val_lbl.setText(
                str(summary.get("medium_count", 0))
            )
            self.mon_low_lbl._val_lbl.setText(
                str(summary.get("low_count", 0))
            )
            avg = summary.get("avg_score")
            self.mon_avg_lbl._val_lbl.setText(
                f"{avg:.1f}" if avg else "—"
            )

            # ── Update feed ───────────────────────────────────
            if not rows:
                self.monitor_feed.setPlaceholderText(
                    "No captures yet.\n\n"
                    "Run  python text_monitor.py  in a separate terminal,\n"
                    "then type or copy text — scored entries will appear here."
                )
                self.monitor_feed.clear()
                self.mon_status_lbl.setText("Waiting for text_monitor.py...")
                return

            # Colour-code each line by risk level
            LEVEL_COLORS = {
                "high"  : COLORS["CRITICAL"],
                "medium": COLORS["MODERATE"],
                "low"   : COLORS["LOW"],
            }

            self.monitor_feed.clear()
            cursor = self.monitor_feed.textCursor()

            from PyQt6.QtGui import QTextCharFormat, QColor as QC

            for row in rows:
                level  = (row.get("risk_level") or "low").lower()
                color  = LEVEL_COLORS.get(level, COLORS["text_main"])
                label  = row.get("risk_label") or "—"
                score  = row.get("composite_score")
                score_str = f"{score:.1f}" if score is not None else "—"
                source = (row.get("source") or "").upper()
                ts     = (row.get("timestamp") or "")[-8:]   # HH:MM:SS
                text   = (row.get("raw_text") or "")[:55]
                if len(row.get("raw_text", "")) > 55:
                    text += "…"

                fmt = QTextCharFormat()
                fmt.setForeground(QC(color))
                cursor.setCharFormat(fmt)
                cursor.insertText(
                    f"[{ts}] {source:<10} {label:<12} ({score_str:>5})  {text}\n"
                )

            now = datetime.now().strftime("%H:%M:%S")
            self.mon_status_lbl.setText(f"Last refreshed: {now}  · auto every 10 s")

        except FileNotFoundError:
            self.mon_status_lbl.setText(
                "monitor_history.db not found — start text_monitor.py first"
            )
        except ImportError:
            self.mon_status_lbl.setText(
                "monitor_storage.py not found in project folder"
            )
        except Exception as exc:
            self.mon_status_lbl.setText(f"Error: {exc}")

    def _check_health(self):
        self._health_worker = ApiWorker("/health")
        self._health_worker.result.connect(self._on_health)
        self._health_worker.error.connect(self._on_health_error)
        self._health_worker.start()

    def _on_health(self, data):
        ok = data.get("status") == "healthy"
        self.api_dot.setStyleSheet(
            f"color: {COLORS['healthy'] if ok else COLORS['unhealthy']}; font-size: 18px;"
        )
        vectors = data.get("total_vectors", 0)
        self.api_lbl.setText(
            f"API healthy · {vectors} vectors" if ok else "API unhealthy"
        )
        self.api_lbl.setStyleSheet(
            f"color: {COLORS['healthy'] if ok else COLORS['unhealthy']}; font-size: 12px;"
        )

    def _on_health_error(self, _):
        self.api_dot.setStyleSheet(f"color: {COLORS['unhealthy']}; font-size: 18px;")
        self.api_lbl.setText("Server offline")
        self.api_lbl.setStyleSheet(
            f"color: {COLORS['unhealthy']}; font-size: 12px;"
        )


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app    = QApplication(sys.argv)
    window = MonitoringApp()
    window.show()
    sys.exit(app.exec())