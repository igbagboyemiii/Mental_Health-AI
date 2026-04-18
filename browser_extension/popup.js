// popup.js — MindGuard Extension Popup Logic

const API_BASE = "http://localhost:8000";

const TIER_COLORS = {
  none   : "#6b7280",
  low    : "#10b981",
  medium : "#f59e0b",
  high   : "#f97316",
  crisis : "#ef4444",
};

const TIER_LABELS = {
  none   : "No Risk Detected",
  low    : "Low Risk",
  medium : "Moderate Risk",
  high   : "High Risk",
  crisis : "⚠ CRISIS — Seek Support",
};

// ── DOM refs ──────────────────────────────────────────────────
const toggle      = document.getElementById("monitoring-toggle");
const toggleSub   = document.getElementById("toggle-sub");
const riskDot     = document.getElementById("risk-dot");
const riskLabel   = document.getElementById("risk-label");
const riskScore   = document.getElementById("risk-score");
const riskTime    = document.getElementById("risk-time");
const statTotal   = document.getElementById("stat-total");
const statHigh    = document.getElementById("stat-high");
const statCrisis  = document.getElementById("stat-crisis");
const apiDot      = document.getElementById("api-dot");
const apiStatus   = document.getElementById("api-status-text");

// ── Load stored state ─────────────────────────────────────────
chrome.storage.local.get(
  ["monitoringEnabled", "latestResult", "lastUpdated", "sessionStats"],
  (result) => {
    const enabled = result.monitoringEnabled || false;
    toggle.checked = enabled;
    toggleSub.textContent = enabled ? "Enabled — monitoring active" : "Disabled — click to enable";

    if (result.latestResult) {
      updateRiskDisplay(result.latestResult, result.lastUpdated);
    }

    const stats = result.sessionStats || { total: 0, high: 0, crisis: 0 };
    statTotal.textContent  = stats.total;
    statHigh.textContent   = stats.high;
    statCrisis.textContent = stats.crisis;
  }
);

// ── Toggle monitoring ─────────────────────────────────────────
toggle.addEventListener("change", () => {
  const enabled = toggle.checked;
  chrome.storage.local.set({ monitoringEnabled: enabled });
  toggleSub.textContent = enabled ? "Enabled — monitoring active" : "Disabled — click to enable";

  // Notify all content scripts on the current tab
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
      chrome.tabs.sendMessage(tabs[0].id, {
        type: "MONITORING_TOGGLE", enabled,
      }).catch(() => {}); // ignore if content script not loaded
    }
  });
});

// ── Update risk display ───────────────────────────────────────
function updateRiskDisplay(data, timestamp) {
  const level = (data.risk_level || "low").toLowerCase();
  const score = data.composite_score || 0;
  const color = TIER_COLORS[level] || TIER_COLORS.low;

  riskDot.style.background = color;
  riskLabel.textContent     = TIER_LABELS[level] || level;
  riskLabel.style.color     = color;
  riskScore.textContent     = `Score: ${score.toFixed ? score.toFixed(1) : score} / 10`;

  if (timestamp) {
    const d = new Date(timestamp);
    riskTime.textContent = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
}

// ── Check backend health ──────────────────────────────────────
async function checkHealth() {
  try {
    const resp = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    if (resp.ok) {
      apiDot.className  = "api-dot online";
      apiStatus.textContent = "Backend connected (localhost:8000)";
    } else {
      throw new Error("non-OK");
    }
  } catch {
    apiDot.className  = "api-dot offline";
    apiStatus.textContent = "Backend offline — start main.py";
  }
}

checkHealth();
