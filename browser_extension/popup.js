// popup.js — MindGuard Extension Popup Logic (Phase 2)
// Handles: tabbed UI, sign-up/consent, guardian management,
//          14-day score history display, trend indicator, reset session.

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

// ── DOM refs — Monitor tab ──────────────────────────────────
const toggle     = document.getElementById("monitoring-toggle");
const toggleSub  = document.getElementById("toggle-sub");
const riskDot    = document.getElementById("risk-dot");
const riskLabel  = document.getElementById("risk-label");
const riskScore  = document.getElementById("risk-score");
const riskTime   = document.getElementById("risk-time");

const trendRow   = document.getElementById("trend-row");
const trendChip  = document.getElementById("trend-chip");
const trendDetail= document.getElementById("trend-detail");

// ── DOM refs — History tab ──────────────────────────────────
const scoreDotsEl = document.getElementById("score-dots");
const histAvg     = document.getElementById("hist-avg");
const histMax     = document.getElementById("hist-max");
const histCount   = document.getElementById("hist-count");

// ── DOM refs — Account tab ──────────────────────────────────
const profileSection = document.getElementById("profile-section");
const signupSection  = document.getElementById("signup-section");
const profileName    = document.getElementById("profile-name");
const profileId      = document.getElementById("profile-id");
const guardianList   = document.getElementById("guardian-list");
const guardianMsg    = document.getElementById("guardian-msg");
const signupMsg      = document.getElementById("signup-msg");

// ── DOM refs — API status ───────────────────────────────────
const apiDot    = document.getElementById("api-dot");
const apiStatus = document.getElementById("api-status-text");

// ── State ───────────────────────────────────────────────────
let currentFilter = "today";
let allHistory    = [];

// ── Tab switching ────────────────────────────────────────────
window.switchTab = function(tab) {
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  document.getElementById(`tab-${tab}`).classList.add("active");
  document.getElementById(`panel-${tab}`).classList.add("active");
};

// ── Load state on popup open ────────────────────────────────
chrome.storage.local.get(
  ["monitoringEnabled", "latestResult", "lastUpdated",
   "sessionStats", "scoreHistory", "contextResult",
   "userId", "displayName"],
  (result) => {
    // Monitoring toggle
    const enabled = result.monitoringEnabled || false;
    toggle.checked = enabled;
    toggleSub.textContent = enabled ? "Enabled — monitoring active" : "Disabled — click to enable";

    // Latest risk result
    if (result.latestResult) {
      updateRiskDisplay(result.latestResult, result.lastUpdated);
    }


    // Score history
    allHistory = result.scoreHistory || [];
    renderHistoryDots(allHistory, currentFilter);

    // Context window trend (from last /analyze/context call)
    if (result.contextResult) {
      renderTrend(result.contextResult);
    }

    // Account section
    const userId      = result.userId;
    const displayName = result.displayName;
    if (userId) {
      showProfile(userId, displayName);
      loadGuardians(userId);
    }
  }
);

// ── Monitoring toggle ────────────────────────────────────────
toggle.addEventListener("change", () => {
  const enabled = toggle.checked;
  chrome.storage.local.set({ monitoringEnabled: enabled });
  toggleSub.textContent = enabled ? "Enabled — monitoring active" : "Disabled — click to enable";
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
      chrome.tabs.sendMessage(tabs[0].id, {
        type: "MONITORING_TOGGLE", enabled,
      }).catch(() => {});
    }
  });
});

// ── Update risk display ──────────────────────────────────────
function updateRiskDisplay(data, timestamp) {
  const level = (data.risk_level || "low").toLowerCase();
  const score = data.composite_score || 0;
  const color = TIER_COLORS[level] || TIER_COLORS.low;
  riskDot.style.background = color;
  riskLabel.textContent    = TIER_LABELS[level] || level;
  riskLabel.style.color    = color;
  riskScore.textContent    = `Activity logged securely`;
  if (timestamp) {
    const d = new Date(timestamp);
    riskTime.textContent = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
}

// ── Render trend indicator ───────────────────────────────────
function renderTrend(ctx) {
  if (!ctx) return;
  const trend    = ctx.temporal_summary?.trend || "stable";
  const avgScore = ctx.merged_avg || 0;
  const maxScore = ctx.merged_max || 0;

  trendRow.style.display = "flex";
  trendChip.textContent  = trend === "escalating" ? "↑ Escalating"
                         : trend === "improving"  ? "↓ Improving"
                         : "→ Stable";
  trendChip.className = `trend-chip trend-${trend}`;
  trendDetail.textContent = ``;
}

// ── History tab ──────────────────────────────────────────────
window.filterHistory = function(period) {
  currentFilter = period;
  document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
  document.getElementById(`filt-${period}`).classList.add("active");
  renderHistoryDots(allHistory, period);
};

function getFilteredHistory(history, period) {
  const now = Date.now();
  const windows = {
    today: 24 * 60 * 60 * 1000,
    "7d" : 7  * 24 * 60 * 60 * 1000,
    "14d": 14 * 24 * 60 * 60 * 1000,
  };
  const ms = windows[period] || windows["14d"];
  return history.filter(e => (now - e.ts) < ms);
}

function renderHistoryDots(history, period) {
  const filtered = getFilteredHistory(history, period);

  if (!filtered.length) {
    scoreDotsEl.innerHTML = `
      <div class="empty-state" style="width:100%; padding:10px 0;">
        <div>📊</div>No history for this period.
      </div>`;
    histCount.textContent = "0";
    return;
  }

  // Dot color by risk level
  const dotColor = (level) => TIER_COLORS[level] || TIER_COLORS.low;

  scoreDotsEl.innerHTML = "";
  filtered.forEach(entry => {
    const dot = document.createElement("div");
    dot.className = "score-dot";
    dot.style.background = dotColor(entry.level);
    dot.title = `${entry.level.toUpperCase()} · ${new Date(entry.ts).toLocaleString()}`;
    scoreDotsEl.appendChild(dot);
  });

  histCount.textContent = filtered.length;
}

// ── Reset session ────────────────────────────────────────────
window.resetSession = function() {
  if (!confirm("Reset all session scores? This cannot be undone.")) return;
  chrome.runtime.sendMessage({ type: "RESET_SESSION" }, (resp) => {
    if (resp?.ok) {
      allHistory = [];
      renderHistoryDots([], currentFilter);
      trendRow.style.display = "none";
      riskLabel.textContent  = "No data yet";
      riskScore.textContent  = "Session reset";
      riskDot.style.background = "#4a6080";
    }
  });
};

// ── Account / Sign-up ────────────────────────────────────────
function showProfile(userId, name) {
  signupSection.style.display  = "none";
  profileSection.style.display = "block";
  profileName.textContent = name || userId;
  profileId.textContent   = userId;
}

window.signUp = async function() {
  const wardName = document.getElementById("reg-ward-name").value.trim();
  const email    = document.getElementById("reg-guardian-email").value.trim();
  const gName    = document.getElementById("reg-guardian-name").value.trim();
  const rel      = document.getElementById("reg-relationship").value;
  const country  = document.getElementById("reg-country").value;
  const consent  = document.getElementById("reg-consent").checked;
  const btn      = document.getElementById("signup-btn");

  signupMsg.className = "msg";

  if (!wardName || !email) {
    signupMsg.textContent = "Please provide the monitored person's name and your email.";
    signupMsg.className   = "msg error";
    return;
  }
  if (!consent) {
    signupMsg.textContent = "Please confirm you have consent.";
    signupMsg.className   = "msg error";
    return;
  }

  btn.disabled     = true;
  btn.textContent  = "Setting Up…";

  try {
    const resp = await fetch(`${API_BASE}/auth/register`, {
      method  : "POST",
      headers : { "Content-Type": "application/json" },
      body    : JSON.stringify({
        username     : wardName,
        email        : email,
        display_name : wardName,
        country_code : country === "GLOBAL" ? "GL" : country,
        consent      : true,
      }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || "Registration failed");
    }

    const data = await resp.json();
    const userId = data.user_id;

    // Automatically register the guardian
    const gResp = await fetch(`${API_BASE}/auth/guardian`, {
      method  : "POST",
      headers : { "Content-Type": "application/json" },
      body    : JSON.stringify({
        user_id        : userId,
        guardian_email : email,
        guardian_name  : gName || "Guardian",
        relationship   : rel,
      }),
    });

    // Persist userId in extension storage
    await chrome.storage.local.set({ userId, displayName: wardName, sessionId: userId });

    signupMsg.textContent = "✓ Monitoring successfully set up!";
    signupMsg.className   = "msg success";
    setTimeout(() => {
      showProfile(userId, wardName);
      loadGuardians(userId);
    }, 1200);
  } catch (err) {
    signupMsg.textContent = `Error: ${err.message}`;
    signupMsg.className   = "msg error";
  } finally {
    btn.disabled    = false;
    btn.textContent = "Set Up Monitoring & Alerts";
  }
};

// ── Guardian management ──────────────────────────────────────
async function loadGuardians(userId) {
  try {
    const resp = await fetch(`${API_BASE}/auth/guardians/${userId}`);
    if (!resp.ok) return;
    const data = await resp.json();
    renderGuardians(data.guardians || [], userId);
  } catch (err) {
    console.warn("[MindGuard] Could not load guardians:", err.message);
  }
}

function renderGuardians(guardians, userId) {
  if (!guardians.length) {
    guardianList.innerHTML = `<div class="empty-state" style="padding:8px 0; font-size:11px; color:#4a6080;">No trusted contacts yet.</div>`;
    return;
  }
  guardianList.innerHTML = guardians.map(g => `
    <div class="guardian-item">
      <div>
        <div class="guardian-email">${g.guardian_email}</div>
        <div class="guardian-rel">${g.guardian_name || ""} · ${g.relationship}</div>
      </div>
      <button class="guardian-remove" data-email="${g.guardian_email}" title="Remove">✕</button>
    </div>
  `).join("");

  document.querySelectorAll('.guardian-remove').forEach(btn => {
    btn.addEventListener('click', (e) => {
      removeGuardian(userId, e.target.dataset.email);
    });
  });
}

window.addGuardian = async function() {
  const stored = await chrome.storage.local.get(["userId"]);
  const userId = stored.userId;
  if (!userId) {
    guardianMsg.textContent = "Please sign up first.";
    guardianMsg.className   = "msg error";
    return;
  }

  const email = document.getElementById("g-email").value.trim();
  const name  = document.getElementById("g-name").value.trim();
  const rel   = document.getElementById("g-rel").value;

  guardianMsg.className = "msg";

  if (!email) {
    guardianMsg.textContent = "Please enter a contact email.";
    guardianMsg.className   = "msg error";
    return;
  }

  const btn      = document.getElementById("add-guardian-btn");
  btn.disabled   = true;
  btn.textContent= "Adding…";

  try {
    const resp = await fetch(`${API_BASE}/auth/guardian`, {
      method  : "POST",
      headers : { "Content-Type": "application/json" },
      body    : JSON.stringify({
        user_id        : userId,
        guardian_email : email,
        guardian_name  : name,
        relationship   : rel,
      }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || "Failed to add contact");
    }
    guardianMsg.textContent = `✓ ${email} added as a trusted contact.`;
    guardianMsg.className   = "msg success";
    document.getElementById("g-email").value = "";
    document.getElementById("g-name").value  = "";
    await loadGuardians(userId);
  } catch (err) {
    guardianMsg.textContent = `Error: ${err.message}`;
    guardianMsg.className   = "msg error";
  } finally {
    btn.disabled    = false;
    btn.textContent = "+ Add Trusted Contact";
  }
};

window.removeGuardian = async function(userId, email) {
  if (!confirm(`Remove ${email} from your trusted contacts?`)) return;
  try {
    await fetch(`${API_BASE}/auth/guardian?user_id=${encodeURIComponent(userId)}&guardian_email=${encodeURIComponent(email)}`, {
      method: "DELETE",
    });
    await loadGuardians(userId);
  } catch (err) {
    console.warn("[MindGuard] Remove guardian failed:", err.message);
  }
};

// ── Check backend health ──────────────────────────────────────
async function checkHealth() {
  try {
    const resp = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    if (resp.ok) {
      apiDot.className      = "api-dot online";
      apiStatus.textContent = "Backend connected (localhost:8000)";
    } else { throw new Error("non-OK"); }
  } catch {
    apiDot.className      = "api-dot offline";
    apiStatus.textContent = "Backend offline — start main.py";
  }
}

checkHealth();

// ── Event Listeners (CSP compliant) ──────────────────────────
document.getElementById('tab-monitor').addEventListener('click', () => switchTab('monitor'));
document.getElementById('tab-history').addEventListener('click', () => switchTab('history'));
document.getElementById('tab-account').addEventListener('click', () => switchTab('account'));

document.getElementById('filt-today').addEventListener('click', () => filterHistory('today'));
document.getElementById('filt-7d').addEventListener('click', () => filterHistory('7d'));
document.getElementById('filt-14d').addEventListener('click', () => filterHistory('14d'));

document.getElementById('reset-btn').addEventListener('click', resetSession);
document.getElementById('add-guardian-btn').addEventListener('click', addGuardian);
document.getElementById('signup-btn').addEventListener('click', signUp);
