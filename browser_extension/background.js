// background.js
// ─────────────────────────────────────────────────────────────
// MindGuard — Service Worker (Background Script)
// Receives text from content.js → calls FastAPI backend →
// updates extension badge with risk level colour.
// ─────────────────────────────────────────────────────────────

const API_BASE = "http://localhost:8000";
const API_KEY  = "dev-secret-key-change-in-prod"; // match DESKTOP_APP_API_KEY

// Badge colours per risk tier
const BADGE_COLORS = {
  none     : "#6b7280", // grey
  low      : "#10b981", // green
  medium   : "#f59e0b", // amber
  high     : "#f97316", // orange
  crisis   : "#ef4444", // red
};

// ── Handle messages from content.js ──────────────────────────
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "ANALYSE_TEXT") {
    analyseText(msg.text, msg.sessionId, sender.tab?.id)
      .then(sendResponse)
      .catch((err) => sendResponse({ error: err.message }));
    return true; // keep channel open for async
  }
});

// ── Call the FastAPI /analyze endpoint ───────────────────────
async function analyseText(text, sessionId, tabId) {
  try {
    const resp = await fetch(`${API_BASE}/analyze?user_id=${sessionId}`, {
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

    const data = await resp.json();
    const level = (data.risk_level || "low").toLowerCase();

    // Update badge on the tab that sent the text
    if (tabId) {
      updateBadge(tabId, level);
    }

    // Persist latest result for popup to read
    chrome.storage.local.set({ latestResult: data, lastUpdated: Date.now() });

    // Show notification for high/crisis tier
    if (level === "crisis" || level === "high") {
      showCrisisNotification(level, data.composite_score);
    }

    return data;
  } catch (err) {
    console.error("[MindGuard] Fetch error:", err);
    return { error: err.message };
  }
}

// ── Update extension icon badge ───────────────────────────────
function updateBadge(tabId, level) {
  const color = BADGE_COLORS[level] || BADGE_COLORS.low;
  const text  = level === "crisis" ? "!" :
                level === "high"   ? "H" :
                level === "medium" ? "M" : "";

  chrome.action.setBadgeText({ text, tabId });
  chrome.action.setBadgeBackgroundColor({ color, tabId });
}

// ── Crisis notification ───────────────────────────────────────
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
