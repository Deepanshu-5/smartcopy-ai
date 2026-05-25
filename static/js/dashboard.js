'use strict';

/* ══════════════════════════════════════════════════════
   SmartCopy AI — dashboard.js
   Reads session/localStorage data from generate page,
   renders real stats, activity feed, tone breakdown
══════════════════════════════════════════════════════ */

/* ── Helpers ─────────────────────────────────────── */
const $ = id => document.getElementById(id);

/* ── AI Tips Pool ────────────────────────────────── */
const AI_TIPS = [
  `Use the <strong>Deep</strong> personalization level when targeting decision-makers — it increases reply rates by up to 40% compared to Quick mode.`,
  `<strong>Tuesday and Thursday mornings</strong> (9–11am local time) have the highest cold email open rates across industries.`,
  `Keep your subject line under <strong>7 words</strong>. Short subject lines get 21% higher open rates than longer ones.`,
  `The <strong>Friendly</strong> tone performs best for creative agencies and startups. <strong>Professional</strong> wins for enterprise and finance.`,
  `Always lead with <strong>their problem</strong>, not your solution. Emails that open with the prospect's pain point get 3x more replies.`,
  `<strong>One clear CTA</strong> per email. Giving two options (call or reply?) reduces response rates by 31%.`,
  `Mention their <strong>company name</strong> in the first sentence. Personalized openers increase reply rates by 26%.`,
  `Follow-up emails get <strong>40% of all replies</strong>. Never send just one email — always plan a follow-up 3–5 days later.`,
];

let currentTipIndex = 0;

/* ── Date & Greeting ─────────────────────────────── */
function setDateAndGreeting() {
  const now    = new Date();
  const hour   = now.getHours();
  const days   = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const dateStr  = `${days[now.getDay()]}, ${months[now.getMonth()]} ${now.getDate()}, ${now.getFullYear()}`;

  const gt = $('greetingTime');
  const td = $('todayDate');
  if (gt) gt.textContent = greeting;
  if (td) td.textContent = dateStr;
}

/* ── Load History from localStorage ─────────────── */
function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem('smartcopy_history') || '[]');
  } catch {
    return [];
  }
}

/* ── Stats ───────────────────────────────────────── */
function renderStats(history) {
  const total = history.length;
  const timeSaved = total * 8;

  // Total emails
  animateCount($('statEmailsTotal'), total);
  animateCount($('weekEmails'), total);

  // Time saved
  const el = $('statTimeSaved');
  if (el) el.textContent = timeSaved >= 60 ? `${(timeSaved / 60).toFixed(1)}h` : `${timeSaved}m`;

  // Usage bar (free = 5/day)
  const todayCount = getTodayCount(history);
  const usagePct   = Math.min((todayCount / 5) * 100, 100);
  const uf = $('usageFill');
  const ut = $('usageText');
  if (uf) setTimeout(() => { uf.style.width = usagePct + '%'; }, 300);
  if (ut) ut.innerHTML = `<strong>${todayCount} / 5 emails used today</strong>`;

  // Change bar color based on usage
  if (uf) {
    if (usagePct >= 100) uf.style.background = 'linear-gradient(90deg,#EF4444,#F87171)';
    else if (usagePct >= 60) uf.style.background = 'linear-gradient(90deg,#F59E0B,#FBBF24)';
  }
}

function getTodayCount(history) {
  const today = new Date().toDateString();
  return history.filter(e => new Date(e.timestamp).toDateString() === today).length;
}

function animateCount(el, target) {
  if (!el || target === 0) return;
  let current = 0;
  const step = Math.max(1, Math.floor(target / 20));
  const interval = setInterval(() => {
    current = Math.min(current + step, target);
    el.textContent = current;
    if (current >= target) clearInterval(interval);
  }, 40);
}

/* ── Week Stats ──────────────────────────────────── */
function renderWeekStats(history) {
  if (!history.length) return;

  // Most used tone
  const toneCount = {};
  history.forEach(e => { toneCount[e.tone] = (toneCount[e.tone] || 0) + 1; });
  const topTone = Object.entries(toneCount).sort((a,b) => b[1]-a[1])[0];
  const wt = $('weekTone');
  if (wt && topTone) wt.textContent = topTone[0];

  // Top goal
  const goalCount = {};
  history.forEach(e => { goalCount[e.goal] = (goalCount[e.goal] || 0) + 1; });
  const topGoal = Object.entries(goalCount).sort((a,b) => b[1]-a[1])[0];
  const wg = $('weekGoal');
  if (wg && topGoal) wg.textContent = topGoal[0];

  // Avg personalization
  const personaMap = { Quick: 1, Standard: 2, Deep: 3 };
  const personaNames = ['—', 'Quick', 'Standard', 'Deep'];
  const avg = Math.round(history.reduce((s, e) => s + (personaMap[e.personalization] || 1), 0) / history.length);
  const wp = $('weekPersona');
  if (wp) wp.textContent = personaNames[avg] || '—';
}

/* ── Tone Bars ───────────────────────────────────── */
function renderToneBars(history) {
  const emptyMsg = $('toneEmptyMsg');
  if (!history.length) { if (emptyMsg) emptyMsg.style.display = 'block'; return; }
  if (emptyMsg) emptyMsg.style.display = 'none';

  const total = history.length;
  const counts = { Professional: 0, Friendly: 0, Direct: 0, Casual: 0 };
  history.forEach(e => { if (counts[e.tone] !== undefined) counts[e.tone]++; });

  const bars = {
    Professional: { bar: $('toneBarP'), pct: $('tonePctP') },
    Friendly:     { bar: $('toneBarF'), pct: $('tonePctF') },
    Direct:       { bar: $('toneBarD'), pct: $('tonePctD') },
    Casual:       { bar: $('toneBarC'), pct: $('tonePctC') },
  };

  setTimeout(() => {
    Object.entries(counts).forEach(([tone, count]) => {
      const pct = total ? Math.round((count / total) * 100) : 0;
      if (bars[tone].bar) bars[tone].bar.style.width = pct + '%';
      if (bars[tone].pct) bars[tone].pct.textContent = pct + '%';
    });
  }, 400);
}

/* ── Activity Feed ───────────────────────────────── */
function renderActivity(history) {
  const emptyEl  = $('activityEmpty');
  const itemsEl  = $('activityItems');
  if (!emptyEl || !itemsEl) return;

  if (!history.length) {
    emptyEl.style.display = 'flex';
    itemsEl.classList.add('hidden');
    return;
  }

  emptyEl.style.display = 'none';
  itemsEl.classList.remove('hidden');

  // Show last 6 emails, newest first
  const recent = [...history].reverse().slice(0, 6);

  itemsEl.innerHTML = recent.map(email => {
    const initials = getInitials(email.prospect_name, email.prospect_company);
    const avatarColor = getAvatarColor(email.prospect_company || email.prospect_name);
    const timeAgo = formatTimeAgo(email.timestamp);
    const preview = truncate(email.subject || 'Email generated', 60);

    return `
      <div class="activity-item">
        <div class="activity-avatar" style="background:${avatarColor}">${initials}</div>
        <div class="activity-body">
          <div class="activity-name-row">
            <span class="activity-name">${escHtml(email.prospect_name)} · ${escHtml(email.prospect_company)}</span>
            <span class="activity-time">${timeAgo}</span>
          </div>
          <p class="activity-preview">${escHtml(preview)}</p>
          <div class="activity-tags">
            <span class="activity-tag activity-tag--tone">${escHtml(email.tone || 'Professional')}</span>
            <span class="activity-tag activity-tag--goal">${escHtml(email.goal || 'Book a Call')}</span>
            ${email.personalization ? `<span class="activity-tag activity-tag--persona">${escHtml(email.personalization)}</span>` : ''}
          </div>
        </div>
        <div class="activity-actions">
          <button class="activity-btn" onclick="copyEmail(${email.id})">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
            Copy
          </button>
          <button class="activity-btn" onclick="regenEmail(${email.id})">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/></svg>
            Regen
          </button>
        </div>
      </div>
    `;
  }).join('');
}

/* ── Activity actions ────────────────────────────── */
window.copyEmail = function(id) {
  const history = loadHistory();
  const email   = history.find(e => e.id === id);
  if (!email) return;
  const text = `Subject: ${email.subject}\n\n${email.body}`;
  navigator.clipboard.writeText(text).catch(() => {});
};

window.regenEmail = function(id) {
  // Store the id to pre-fill on generate page, then navigate
  sessionStorage.setItem('smartcopy_regen', id);
  window.location.href = '/generate';
};

/* ── AI Tips ─────────────────────────────────────── */
function renderTip(index) {
  const el = $('aiTipText');
  if (el) el.innerHTML = `"${AI_TIPS[index % AI_TIPS.length]}"`;
}

function initTips() {
  currentTipIndex = Math.floor(Math.random() * AI_TIPS.length);
  renderTip(currentTipIndex);
  const btn = $('tipRefreshBtn');
  if (btn) {
    btn.addEventListener('click', () => {
      currentTipIndex = (currentTipIndex + 1) % AI_TIPS.length;
      const el = $('aiTipText');
      if (el) {
        el.style.opacity = '0';
        setTimeout(() => {
          renderTip(currentTipIndex);
          el.style.opacity = '1';
        }, 200);
      }
    });
  }
}

/* ── Helpers ─────────────────────────────────────── */
function getInitials(name, company) {
  if (name) {
    const parts = name.trim().split(' ');
    return parts.length >= 2
      ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
      : parts[0].slice(0, 2).toUpperCase();
  }
  return company ? company.slice(0, 2).toUpperCase() : 'SC';
}

const AVATAR_COLORS = [
  'linear-gradient(135deg,#5B5EF4,#8B5CF6)',
  'linear-gradient(135deg,#0EA5E9,#38BDF8)',
  'linear-gradient(135deg,#10B981,#34D399)',
  'linear-gradient(135deg,#F59E0B,#FBBF24)',
  'linear-gradient(135deg,#EF4444,#F87171)',
  'linear-gradient(135deg,#8B5CF6,#C084FC)',
];
function getAvatarColor(str) {
  let hash = 0;
  for (let i = 0; i < (str || '').length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function formatTimeAgo(timestamp) {
  if (!timestamp) return 'Just now';
  const diff = Date.now() - new Date(timestamp).getTime();
  const mins  = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days  = Math.floor(diff / 86400000);
  if (mins < 1)  return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return `${days}d ago`;
}

function truncate(str, len) {
  return str.length > len ? str.slice(0, len) + '…' : str;
}

function escHtml(str) {
  return String(str || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

/* ── Boot ────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  setDateAndGreeting();
  initTips();

  const history = loadHistory();
  renderStats(history);
  renderWeekStats(history);
  renderToneBars(history);
  renderActivity(history);
});