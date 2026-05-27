// background.js
// ─────────────────────────────────────────────────────────────
// MindGuard — Service Worker (Background Script)
// Receives text from content.js → calls FastAPI backend →
// updates extension badge with risk level colour.
//
// New in Phase 2:
//   • Maintains scoreHistory[] (500 entries, 14-day rolling window)
//   • Computes session aggregate (avg, max, count, trend)
//   • Calls /analyze/context with last 5 texts + pre-aggregated stats
//   • RESET_SESSION message handler
//   • Notifies guardians via /analyze/context → backend crisis trigger
// ─────────────────────────────────────────────────────────────

const API_BASE         = "http://localhost:8000";
const API_KEY          = "dev-secret-key-change-in-prod";
const MAX_HISTORY      = 500;          // ~14 days of browsing
const HISTORY_MAX_DAYS = 14;           // purge entries older than this
const CONTEXT_TEXTS    = 5;            // how many raw texts to send for live scoring

// Badge colours per risk tier
const BADGE_COLORS = {
  none   : "#6b7280",
  low    : "#10b981",
  medium : "#f59e0b",
  high   : "#f97316",
  crisis : "#ef4444",
};

// ── Handle messages from content.js and popup.js ──────────────
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "ANALYSE_TEXT") {
    analyseText(msg.text, msg.sessionId, sender.tab?.id)
      .then(sendResponse)
      .catch((err) => sendResponse({ error: err.message }));
    return true;
  }

  if (msg.type === "RESET_SESSION") {
    resetSession().then(sendResponse).catch(() => sendResponse({ ok: false }));
    return true;
  }
});

// ── Reset session scores ──────────────────────────────────────
async function resetSession() {
  await chrome.storage.local.set({
    scoreHistory  : [],
    sessionStats  : { total: 0, high: 0, crisis: 0, avgScore: 0, maxScore: 0 },
    latestResult  : null,
    lastUpdated   : null,
    sessionTexts  : [],
  });
  return { ok: true };
}

// ── Call the FastAPI /analyze endpoint ───────────────────────
async function analyseText(text, sessionId, tabId) {
  // Guard: ensure we always have a real sessionId, never send as anonymous
  const effectiveId = sessionId || ("browser_" + Math.random().toString(36).slice(2, 11));
  if (!sessionId) {
    console.warn("[MindGuard] No sessionId — generated a temporary one:", effectiveId);
    chrome.storage.local.set({ sessionId: effectiveId });
  }

  try {
    const resp = await fetch(`${API_BASE}/analyze?user_id=${effectiveId}`, {
      method  : "POST",
      headers : {
        "Content-Type": "application/json",
        "X-API-Key"   : API_KEY,
      },
      body: JSON.stringify({ text, include_rag: false }),
    });

    if (!resp.ok) {
      console.warn("[MindGuard] API error:", resp.status);
      return { error: `API ${resp.status}` };
    }

    const data  = await resp.json();
    const level = (data.risk_level || "low").toLowerCase();
    const score = data.composite_score || 0;

    console.log(`[MindGuard] Analysed — level: ${level}, score: ${score}, user: ${effectiveId}`);

    // ── Update badge (global + per-tab) ───────────────────────
    updateBadge(tabId, level);

    // ── Update score history (500-entry rolling window) ───────
    await updateHistory(score, level, text, effectiveId);

    // ── Persist latest result for popup ───────────────────────
    chrome.storage.local.set({ latestResult: data, lastUpdated: Date.now() });

    // ── Show notification for high/crisis tier ────────────────
    if (level === "crisis" || level === "high") {
      showCrisisNotification(level, score);
    }

    return data;
  } catch (err) {
    console.error("[MindGuard] Fetch error:", err);
    return { error: err.message };
  }
}

// ── Update rolling 14-day / 500-entry score history ──────────
async function updateHistory(score, level, text, sessionId) {
  const stored = await chrome.storage.local.get([
    "scoreHistory", "sessionStats", "sessionTexts"
  ]);

  let history = stored.scoreHistory || [];
  let texts   = stored.sessionTexts  || [];

  const now      = Date.now();
  const cutoffMs = HISTORY_MAX_DAYS * 24 * 60 * 60 * 1000;

  // Remove entries older than 14 days
  history = history.filter(e => (now - e.ts) < cutoffMs);
  texts   = texts.filter(e => (now - e.ts) < cutoffMs);

  // Add new entry
  history.push({ ts: now, score, level });
  texts.push({ ts: now, text: text.slice(0, 300) });

  // Cap at MAX_HISTORY
  if (history.length > MAX_HISTORY) history = history.slice(-MAX_HISTORY);
  if (texts.length   > MAX_HISTORY) texts   = texts.slice(-MAX_HISTORY);

  // Recompute session stats
  const scores     = history.map(e => e.score);
  const avgScore   = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
  const maxScore   = scores.length ? Math.max(...scores) : 0;
  const highCount  = history.filter(e => e.level === "high").length;
  const crisisCount= history.filter(e => e.level === "crisis").length;

  const sessionStats = {
    total    : history.length,
    high     : highCount,
    crisis   : crisisCount,
    avgScore : Math.round(avgScore * 10) / 10,
    maxScore : Math.round(maxScore * 10) / 10,
  };

  await chrome.storage.local.set({ scoreHistory: history, sessionStats, sessionTexts: texts });

  // ── Every 5 flushes, call /analyze/context for rolling summary ──
  if (history.length % 5 === 0 || level === "high" || level === "crisis") {
    const recentTexts = texts.slice(-CONTEXT_TEXTS).map(e => e.text);
    sendContextWindow(sessionId, recentTexts, sessionStats).catch(() => {});
  }
}

// ── Send rolling context window to backend ────────────────────
async function sendContextWindow(sessionId, texts, stats) {
  try {
    const body = {
      user_id      : sessionId,
      texts        : texts,
      session_avg  : stats.avgScore,
      session_max  : stats.maxScore,
      session_count: stats.total,
      window_days  : 14,
    };

    const resp = await fetch(`${API_BASE}/analyze/context`, {
      method  : "POST",
      headers : { "Content-Type": "application/json" },
      body    : JSON.stringify(body),
    });

    if (!resp.ok) return;

    const ctx = await resp.json();

    // Store context window result for popup to display
    chrome.storage.local.set({
      contextResult: {
        ...ctx,
        fetchedAt: Date.now(),
      }
    });

    // If backend detected a crisis via context, show notification
    if (ctx.crisis_triggered) {
      showCrisisNotification("crisis", ctx.merged_max);
    } else if (ctx.escalating) {
      showEscalationNotification(ctx.merged_avg);
    }
  } catch (err) {
    console.warn("[MindGuard] Context window call failed:", err.message);
  }
}

// ── Update extension icon badge ───────────────────────────────
// Sets badge globally (no tabId) so it persists when switching tabs.
// Also sets it per-tab as a fallback for multi-window setups.
function updateBadge(tabId, level) {
  const color = BADGE_COLORS[level] || BADGE_COLORS.low;
  const text  = level === "crisis" ? "!" :
                level === "high"   ? "H" :
                level === "medium" ? "M" : "";

  // ── Global badge (survives tab switches) ─────────────────────
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color });

  // ── Per-tab badge (overrides global for that specific tab) ───
  if (tabId) {
    chrome.action.setBadgeText({ text, tabId });
    chrome.action.setBadgeBackgroundColor({ color, tabId });
  }
}

// ── Crisis / escalation notifications ────────────────────────
function showCrisisNotification(level, score) {
  const isCrisis = level === "crisis";
  chrome.notifications.create({
    type    : "basic",
    iconUrl : "icons/icon48.png",
    title   : isCrisis ? "🚨 MindGuard — Crisis Detected" : "⚠️ MindGuard — High Risk Detected",
    message : isCrisis
      ? "Significant distress detected. Please reach out for support: call or text 988."
      : `Elevated emotional distress detected (score: ${(score || 0).toFixed(1)}). Consider taking a break.`,
    priority: 2,
  });
}

function showEscalationNotification(avgScore) {
  chrome.notifications.create({
    type    : "basic",
    iconUrl : "icons/icon48.png",
    title   : "📈 MindGuard — Risk Escalating",
    message : `Your distress indicators have been rising over the past 2 weeks (avg: ${avgScore.toFixed(1)}/10). Consider speaking to someone you trust.`,
    priority: 1,
  });
}
