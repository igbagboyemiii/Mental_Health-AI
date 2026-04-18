// content.js
// ─────────────────────────────────────────────────────────────
// MindGuard Browser Extension — Content Script
// Runs in the context of every page (except excluded sites).
// Captures text from textarea / contenteditable fields
// ONLY when the user has enabled monitoring via the popup.
//
// Privacy rules enforced here:
//   ✅ Only captures when monitoring toggle is ON
//   ✅ Only captures textareas and contenteditable elements
//   ✅ Skips password inputs and payment-related fields
//   ✅ Sends text only after FLUSH_WORD_COUNT words are buffered
//   ✅ Minimum MIN_CHARS chars required before sending
// ─────────────────────────────────────────────────────────────

const MIN_CHARS        = 40;     // minimum chars before sending
const FLUSH_WORD_COUNT = 10;     // words before auto-send
const DEBOUNCE_MS      = 1200;   // ms after last keypress before buffering

let monitoringEnabled = false;
let wordBuffer        = [];
let debounceTimer     = null;
let sessionId         = null;

// ── Load initial state from storage ──────────────────────────
chrome.storage.local.get(["monitoringEnabled", "sessionId"], (result) => {
  monitoringEnabled = result.monitoringEnabled || false;
  sessionId         = result.sessionId || generateSessionId();
  chrome.storage.local.set({ sessionId });
});

// ── Listen for toggle updates from popup ─────────────────────
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "MONITORING_TOGGLE") {
    monitoringEnabled = msg.enabled;
  }
});

// ── Generate a session ID (anonymous, not user-linked) ────────
function generateSessionId() {
  return "browser_" + Math.random().toString(36).slice(2, 11);
}

// ── Safety check: skip password and payment fields ────────────
function isSensitiveField(el) {
  if (!el) return true;
  const type  = (el.getAttribute("type") || "").toLowerCase();
  const name  = (el.getAttribute("name") || "").toLowerCase();
  const id    = (el.getAttribute("id")   || "").toLowerCase();
  const label = (el.getAttribute("aria-label") || "").toLowerCase();

  const sensitiveTypes  = ["password", "hidden", "credit-card", "tel"];
  const sensitiveNames  = ["card", "cvv", "ccv", "expiry", "pin", "ssn", "nonce"];

  if (sensitiveTypes.some(t => type.includes(t)))         return true;
  if (sensitiveNames.some(n => name.includes(n) || id.includes(n))) return true;
  if (label.includes("password") || label.includes("card")) return true;
  return false;
}

// ── Extract text from active element ─────────────────────────
function getTextFromElement(el) {
  if (!el) return "";
  if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") {
    return el.value || "";
  }
  if (el.isContentEditable) {
    return el.innerText || "";
  }
  return "";
}

// ── Send text to background script for API call ───────────────
function flushBuffer(force = false) {
  const text = wordBuffer.join(" ").trim();
  wordBuffer = [];

  if (!text || text.length < MIN_CHARS) return;

  chrome.runtime.sendMessage({
    type      : "ANALYSE_TEXT",
    text      : text,
    sessionId : sessionId,
    url       : window.location.hostname,
  });
}

// ── Keydown handler on any editable element ───────────────────
function onKeyDown(e) {
  if (!monitoringEnabled) return;

  const el = e.target;
  if (!el) return;
  if (isSensitiveField(el)) return;
  if (el.tagName !== "TEXTAREA" && !el.isContentEditable) return;

  // On space or enter — add current word to buffer
  if (e.key === " " || e.key === "Enter") {
    const fullText = getTextFromElement(el);
    const words    = fullText.trim().split(/\s+/).filter(Boolean);
    wordBuffer     = words;

    if (wordBuffer.length >= FLUSH_WORD_COUNT) {
      clearTimeout(debounceTimer);
      flushBuffer();
    }
    return;
  }

  // Debounce: after user stops typing, flush
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    const fullText = getTextFromElement(el);
    const words    = fullText.trim().split(/\s+/).filter(Boolean);
    wordBuffer     = words;
    flushBuffer();
  }, DEBOUNCE_MS);
}

// ── Attach listener ───────────────────────────────────────────
document.addEventListener("keydown", onKeyDown, { capture: true });
