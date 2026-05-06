// popup.js — MindGuard Extension (Adolescent-First, Guardian-Ward Flow)
'use strict';

const API_BASE = 'http://localhost:8000';

const TIER_COLORS = {
  none:'#6b7280', low:'#10b981', medium:'#f59e0b', high:'#f97316', crisis:'#ef4444'
};
const TIER_LABELS = {
  none:'No Risk Detected', low:'Low Risk', medium:'Moderate Risk',
  high:'High Risk', crisis:'⚠ CRISIS — Seek Support'
};

// ── DOM refs ────────────────────────────────────────────────
const toggle    = document.getElementById('monitoring-toggle');
const toggleSub = document.getElementById('toggle-sub');
const riskDot   = document.getElementById('risk-dot');
const riskLabel = document.getElementById('risk-label');
const riskScore = document.getElementById('risk-score');
const riskTime  = document.getElementById('risk-time');
const trendRow  = document.getElementById('trend-row');
const trendChip = document.getElementById('trend-chip');
const scoreDotsEl = document.getElementById('score-dots');
const histCount = document.getElementById('hist-count');
const apiDot    = document.getElementById('api-dot');
const apiStatus = document.getElementById('api-status-text');

// Account sections
const guardianProfileSection = document.getElementById('guardian-profile-section');
const wardProfileSection     = document.getElementById('ward-profile-section');
const setupSection           = document.getElementById('setup-section');
const linkSection            = document.getElementById('link-section');

// State
let currentFilter = 'today';
let allHistory    = [];
let guardianId    = null;  // stored if this is a guardian's device
let wardId        = null;  // stored if this is a ward's device

// ── Tab switching ─────────────────────────────────────────
window.switchTab = function(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.getElementById(`tab-${tab}`).classList.add('active');
  document.getElementById(`panel-${tab}`).classList.add('active');
};

// ── Initialise on popup open ──────────────────────────────
chrome.storage.local.get(
  ['monitoringEnabled','latestResult','lastUpdated','scoreHistory',
   'contextResult','guardianId','wardId','guardianName','wardName'],
  (result) => {
    const enabled = result.monitoringEnabled || false;
    toggle.checked = enabled;
    toggleSub.textContent = enabled ? 'Enabled — monitoring active' : 'Disabled — click to enable';

    if (result.latestResult) updateRiskDisplay(result.latestResult, result.lastUpdated);
    allHistory = result.scoreHistory || [];
    renderHistoryDots(allHistory, currentFilter);
    if (result.contextResult) renderTrend(result.contextResult);

    guardianId = result.guardianId || null;
    wardId     = result.wardId     || null;

    if (guardianId) {
      showGuardianProfile(guardianId, result.guardianName || guardianId);
      loadWards(guardianId);
    } else if (wardId) {
      showWardProfile(wardId, result.wardName || wardId);
    }
    // else: show setup wizard (default)
  }
);

// ── DOB max = today ───────────────────────────────────────
document.getElementById('w-dob').max = new Date().toISOString().split('T')[0];

// ── Monitoring toggle ────────────────────────────────────
toggle.addEventListener('change', () => {
  const enabled = toggle.checked;
  chrome.storage.local.set({ monitoringEnabled: enabled });
  toggleSub.textContent = enabled ? 'Enabled — monitoring active' : 'Disabled — click to enable';
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) chrome.tabs.sendMessage(tabs[0].id, { type: 'MONITORING_TOGGLE', enabled }).catch(() => {});
  });
});

// ── Risk display ─────────────────────────────────────────
function updateRiskDisplay(data, timestamp) {
  const level = (data.risk_level || 'low').toLowerCase();
  const color = TIER_COLORS[level] || TIER_COLORS.low;
  riskDot.style.background = color;
  riskLabel.textContent    = TIER_LABELS[level] || level;
  riskLabel.style.color    = color;
  riskScore.textContent    = 'Activity logged securely';
  if (timestamp) {
    riskTime.textContent = new Date(timestamp).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
  }
}

function renderTrend(ctx) {
  if (!ctx) return;
  const trend = ctx.temporal_summary?.trend || 'stable';
  trendRow.style.display = 'flex';
  trendChip.textContent  = trend === 'escalating' ? '↑ Escalating' : trend === 'improving' ? '↓ Improving' : '→ Stable';
  trendChip.className    = `trend-chip trend-${trend}`;
}

// ── History tab ──────────────────────────────────────────
window.filterHistory = function(period) {
  currentFilter = period;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`filt-${period}`).classList.add('active');
  renderHistoryDots(allHistory, period);
};

function getFilteredHistory(history, period) {
  const now = Date.now();
  const windows = { today: 86400000, '7d': 604800000, '14d': 1209600000 };
  const ms = windows[period] || windows['14d'];
  return history.filter(e => (now - e.ts) < ms);
}

function renderHistoryDots(history, period) {
  const filtered = getFilteredHistory(history, period);
  if (!filtered.length) {
    scoreDotsEl.innerHTML = '<div class="empty-state" style="width:100%;padding:10px 0;"><div>📊</div>No history for this period.</div>';
    histCount.textContent = '0';
    return;
  }
  scoreDotsEl.innerHTML = '';
  filtered.forEach(entry => {
    const dot = document.createElement('div');
    dot.className = 'score-dot';
    dot.style.background = TIER_COLORS[entry.level] || TIER_COLORS.low;
    dot.title = `${entry.level.toUpperCase()} · ${new Date(entry.ts).toLocaleString()}`;
    scoreDotsEl.appendChild(dot);
  });
  histCount.textContent = filtered.length;
}

window.resetSession = function() {
  if (!confirm('Reset all session scores? This cannot be undone.')) return;
  chrome.runtime.sendMessage({ type: 'RESET_SESSION' }, (resp) => {
    if (resp?.ok) {
      allHistory = [];
      renderHistoryDots([], currentFilter);
      trendRow.style.display = 'none';
      riskLabel.textContent  = 'No data yet';
      riskScore.textContent  = 'Session reset';
      riskDot.style.background = '#4a6080';
    }
  });
};

// ── Profile display helpers ──────────────────────────────
function showGuardianProfile(gId, gName) {
  setupSection.style.display          = 'none';
  linkSection.style.display           = 'none';
  wardProfileSection.style.display    = 'none';
  guardianProfileSection.style.display = 'block';
  document.getElementById('gp-name').textContent = gName;
  document.getElementById('gp-id').textContent   = gId;
}

function showWardProfile(wId, wName) {
  setupSection.style.display           = 'none';
  linkSection.style.display            = 'none';
  guardianProfileSection.style.display = 'none';
  wardProfileSection.style.display     = 'block';
  document.getElementById('wp-name').textContent = wName;
  document.getElementById('wp-id').textContent   = wId;
}

// ── Step wizard helpers ──────────────────────────────────
function goToStep(step) {
  document.querySelectorAll('.step-panel').forEach(p => p.classList.remove('active'));
  document.getElementById(`step-${step}`).classList.add('active');
  // Update dots
  for (let i = 1; i <= 3; i++) {
    const dot  = document.getElementById(`s-dot-${i}`);
    const line = document.getElementById(`s-line-${i}`);
    if (i < step)       { dot.className = 'step-dot done'; dot.textContent = '✓'; }
    else if (i === step){ dot.className = 'step-dot active'; dot.textContent = i; }
    else                { dot.className = 'step-dot'; dot.textContent = i; }
    if (line) line.className = i < step ? 'step-line done' : 'step-line';
  }
}

function showMsg(id, text, type) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.className   = `msg ${type}`;
}

function computeAge(dob) {
  const today = new Date();
  const d     = new Date(dob);
  let age = today.getFullYear() - d.getFullYear();
  if ((today.getMonth() * 100 + today.getDate()) < (d.getMonth() * 100 + d.getDate())) age--;
  return age;
}

// ── Step 1: Guardian Registration ────────────────────────
document.getElementById('step1-btn').addEventListener('click', async () => {
  const name    = document.getElementById('g-name').value.trim();
  const email   = document.getElementById('g-email').value.trim();
  const country = document.getElementById('g-country').value;
  const consent = document.getElementById('g-consent').checked;
  const btn     = document.getElementById('step1-btn');

  if (!name || !email) { showMsg('step1-msg','Please enter your name and email.','error'); return; }
  if (!consent)         { showMsg('step1-msg','Please confirm you are the guardian/parent.','error'); return; }

  btn.disabled = true; btn.textContent = 'Creating account…';
  try {
    const resp = await fetch(`${API_BASE}/auth/guardian/register`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ guardian_name:name, guardian_email:email, country_code:country, consent:true })
    });
    if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail || 'Registration failed'); }
    const data = await resp.json();
    guardianId = data.guardian_id;
    await chrome.storage.local.set({ guardianId, guardianName: name });
    showMsg('step1-msg', `✓ Account created! Guardian ID: ${guardianId}`, 'success');
    setTimeout(() => goToStep(2), 1000);
  } catch(e) {
    showMsg('step1-msg', `Error: ${e.message}`, 'error');
  } finally {
    btn.disabled = false; btn.textContent = 'Create Guardian Account →';
  }
});

// ── Adult consent visibility ──────────────────────────────
document.getElementById('w-dob').addEventListener('change', () => {
  const dob = document.getElementById('w-dob').value;
  if (!dob) return;
  const age = computeAge(dob);
  const box = document.getElementById('adult-consent-box');
  box.style.display = age >= 18 ? 'block' : 'none';
});

// ── Step 2: Ward Registration ─────────────────────────────
document.getElementById('step2-btn').addEventListener('click', async () => {
  const name    = document.getElementById('w-name').value.trim();
  const dob     = document.getElementById('w-dob').value;
  const rel     = document.getElementById('w-rel').value;
  const consent = document.getElementById('w-consent').checked;
  const btn     = document.getElementById('step2-btn');

  if (!name || !dob) { showMsg('step2-msg','Please enter the child\'s name and date of birth.','error'); return; }
  const age = computeAge(dob);
  if (age < 10 || age > 24) { showMsg('step2-msg',`Age must be 10–24. Computed: ${age}.`,'error'); return; }
  if (!consent) { showMsg('step2-msg','Please confirm your guardian consent.','error'); return; }

  const adultConsent = age >= 18 ? document.getElementById('adult-consent-chk').checked : true;
  if (age >= 18 && !adultConsent) {
    showMsg('step2-msg','For ages 18–24: you must confirm the young adult is aware and consents.','error');
    return;
  }

  btn.disabled = true; btn.textContent = 'Registering…';
  try {
    const resp = await fetch(`${API_BASE}/auth/ward/register`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        guardian_id: guardianId, ward_name: name, ward_dob: dob,
        relationship: rel, guardian_consent: true, adult_aware_consent: adultConsent
      })
    });
    if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail || 'Ward registration failed'); }
    const data = await resp.json();
    wardId = data.ward_id;
    document.getElementById('link-code-display').textContent = data.link_code;
    goToStep(3);
  } catch(e) {
    showMsg('step2-msg', `Error: ${e.message}`, 'error');
  } finally {
    btn.disabled = false; btn.textContent = 'Register Child →';
  }
});

document.getElementById('step2-back-btn').addEventListener('click', () => goToStep(1));

// ── Step 3 buttons ────────────────────────────────────────
document.getElementById('step3-done-btn').addEventListener('click', async () => {
  const stored = await chrome.storage.local.get(['guardianId','guardianName']);
  showGuardianProfile(stored.guardianId, stored.guardianName);
  loadWards(stored.guardianId);
});

document.getElementById('step3-add-another-btn').addEventListener('click', () => {
  document.getElementById('w-name').value = '';
  document.getElementById('w-dob').value  = '';
  document.getElementById('w-consent').checked = false;
  document.getElementById('adult-consent-chk').checked = false;
  document.getElementById('adult-consent-box').style.display = 'none';
  document.getElementById('step2-msg').className = 'msg';
  goToStep(2);
});

// ── Add another child from profile ───────────────────────
document.getElementById('add-ward-btn').addEventListener('click', () => {
  guardianProfileSection.style.display = 'none';
  setupSection.style.display = 'block';
  goToStep(2);
});

// ── Load wards for guardian profile ──────────────────────
async function loadWards(gId) {
  try {
    const resp = await fetch(`${API_BASE}/auth/guardian/${encodeURIComponent(gId)}/wards`);
    if (!resp.ok) return;
    const data = await resp.json();
    renderWards(data.wards || []);
  } catch(e) { console.warn('[MindGuard] Could not load wards:', e.message); }
}

function renderWards(wards) {
  const list = document.getElementById('ward-list');
  if (!wards.length) {
    list.innerHTML = '<div class="empty-state" style="padding:8px 0;">No children linked yet.</div>';
    return;
  }
  list.innerHTML = wards.map(w => {
    const trend  = w.temporal_summary?.trend || 'none';
    const tClass = `wt-${trend === 'none' ? 'none' : trend}`;
    const tLabel = trend === 'escalating' ? '↑ Escalating' : trend === 'improving' ? '↓ Improving' : trend === 'stable' ? '→ Stable' : '— No data';
    return `
      <div class="ward-item">
        <div>
          <div class="ward-name-txt">${w.ward_name}</div>
          <div class="ward-meta">${w.relationship} · Linked ${w.linked_at?.slice(0,10) || '—'}</div>
        </div>
        <span class="ward-trend ${tClass}">${tLabel}</span>
      </div>`;
  }).join('');
}

// ── Link Device (ward side) ──────────────────────────────
document.getElementById('link-btn').addEventListener('click', async () => {
  const code = document.getElementById('link-code').value.trim().toUpperCase();
  const btn  = document.getElementById('link-btn');
  const msg  = document.getElementById('link-msg');
  msg.className = 'msg';
  if (!code || code.length < 6) { showMsg('link-msg','Please enter a valid 6-character Link Code.','error'); return; }

  btn.disabled = true; btn.textContent = 'Linking…';
  try {
    const resp = await fetch(`${API_BASE}/auth/me?user_id=${encodeURIComponent(code)}`);
    if (!resp.ok) throw new Error('Invalid Link Code or account not found.');
    const data = await resp.json();
    const name = data.display_name || data.username || 'Linked Account';
    await chrome.storage.local.set({ wardId: code, wardName: name, sessionId: code });
    showMsg('link-msg','✓ Device successfully linked!','success');
    setTimeout(() => showWardProfile(code, name), 1200);
  } catch(e) {
    showMsg('link-msg', e.message, 'error');
  } finally {
    btn.disabled = false; btn.textContent = 'Link This Device';
  }
});

// ── Health check ─────────────────────────────────────────
async function checkHealth() {
  try {
    const resp = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    if (resp.ok) {
      apiDot.className      = 'api-dot online';
      apiStatus.textContent = 'Backend connected (localhost:8000)';
    } else throw new Error();
  } catch {
    apiDot.className      = 'api-dot offline';
    apiStatus.textContent = 'Backend offline — start main.py';
  }
}
checkHealth();

// ── Event listeners ──────────────────────────────────────
document.getElementById('tab-monitor').addEventListener('click', () => switchTab('monitor'));
document.getElementById('tab-history').addEventListener('click', () => switchTab('history'));
document.getElementById('tab-account').addEventListener('click', () => switchTab('account'));
document.getElementById('filt-today').addEventListener('click', () => filterHistory('today'));
document.getElementById('filt-7d').addEventListener('click',    () => filterHistory('7d'));
document.getElementById('filt-14d').addEventListener('click',   () => filterHistory('14d'));
document.getElementById('reset-btn').addEventListener('click',  resetSession);
