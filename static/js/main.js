'use strict';

/* ── State ───────────────────────────────────────── */
const S = {
  tone:    'Professional',
  goal:    'Book a Call',
  exp:     'Expert',
  persona: 'Quick',
  emails:  0,
};

/* ── Helpers ─────────────────────────────────────── */
const $ = id => document.getElementById(id);
const show = el => el && el.classList.remove('hidden');
const hide = el => el && el.classList.add('hidden');

/* ── Pill Group ──────────────────────────────────── */
function initPills(groupId, stateKey, selector = '.pill') {
  const g = $(groupId);
  if (!g) return;
  g.addEventListener('click', e => {
    const p = e.target.closest(selector);
    if (!p) return;
    g.querySelectorAll(selector).forEach(x => x.classList.remove('active'));
    p.classList.add('active');
    S[stateKey] = p.dataset.val;
    updateChecklist();
  });
}

/* ── Personalization Track ───────────────────────── */
function initPersonalization() {
  document.querySelectorAll('.p-level').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.p-level').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      S.persona = btn.dataset.val;
    });
  });
}

/* ── Live Checklist ──────────────────────────────── */
function updateChecklist() {
  const userFilled =
    $('yourName').value.trim() &&
    $('serviceOffered').value.trim();

  const targetFilled =
    $('prospectName').value.trim() &&
    $('prospectCompany').value.trim();

  const dotUser   = $('dot-user');
  const dotTarget = $('dot-target');

  if (dotUser) {
    dotUser.classList.toggle('done', !!userFilled);
  }
  if (dotTarget) {
    dotTarget.classList.toggle('done', !!targetFilled);
  }
}

/* ── Char Counter ────────────────────────────────── */
function initCharCounter() {
  const ta = $('serviceOffered');
  const ct = $('charNow');
  if (!ta || !ct) return;
  ta.addEventListener('input', () => {
    const n = ta.value.length;
    ct.textContent = n;
    ct.style.color = n > 250 ? '#EF4444' : '';
    updateChecklist();
  });
}

/* ── Output States ───────────────────────────────── */
function setOutput(state) {
  hide($('emptyState'));
  hide($('aiThinking'));
  hide($('emailResult'));
  $('outputActions').style.display = 'none';
  $('outputTabs').style.display   = 'none';

  if (state === 'empty')   { show($('emptyState')); }
  if (state === 'loading') { show($('aiThinking')); }
  if (state === 'result') {
    show($('emailResult'));
    $('outputActions').style.display = 'flex';
    $('outputTabs').style.display    = 'flex';
  }
}

/* ── AI Thinking Animation ───────────────────────── */
async function runThinkingAnimation() {
  const steps = ['ts-1', 'ts-2', 'ts-3', 'ts-4'];
  const delays = [0, 500, 1000, 1600];

  // Reset all
  steps.forEach(id => {
    const el = $(id);
    if (el) {
      el.classList.remove('active', 'done');
      const fill = el.querySelector('.ts-fill');
      if (fill) fill.style.width = '0%';
    }
  });

  // Animate each step
  for (let i = 0; i < steps.length; i++) {
    await new Promise(r => setTimeout(r, delays[i]));
    const el = $(steps[i]);
    if (!el) continue;

    // Mark previous as done
    if (i > 0) {
      const prev = $(steps[i - 1]);
      if (prev) prev.classList.replace('active', 'done');
    }

    el.classList.add('active');
    const fill = el.querySelector('.ts-fill');
    if (fill) {
      requestAnimationFrame(() => { fill.style.width = '60%'; });
    }
  }
}

/* ── Generate button state ───────────────────────── */
function setBtn(loading) {
  const btn = $('generateBtn');
  btn.disabled = loading;
  $('btn-default').classList.toggle('hidden', loading);
  $('btn-loading').classList.toggle('hidden', !loading);
}

/* ── Validation ──────────────────────────────────── */
function getValues() {
  return {
    sender_name:      $('yourName').value.trim(),
    sender_company:   $('yourCompany').value.trim(),
    offering:         $('serviceOffered').value.trim(),
    experience:       S.exp,
    portfolio:        $('portfolio').value.trim(),
    prospect_name:    $('prospectName').value.trim(),
    prospect_company: $('prospectCompany').value.trim(),
    tone:             S.tone,
    personalization:  S.persona,
    goal:             S.goal,
  };
}

function validate(v) {
  return v.sender_name && v.offering && v.prospect_name && v.prospect_company;
}

function showError(msg) {
  const el = $('formError');
  $('errorMsg').textContent = msg;
  show(el);
  setTimeout(() => hide(el), 4000);

  // Highlight blank required fields
  [
    ['yourName', $('yourName').value.trim()],
    ['serviceOffered', $('serviceOffered').value.trim()],
    ['prospectName', $('prospectName').value.trim()],
    ['prospectCompany', $('prospectCompany').value.trim()],
  ].forEach(([id, val]) => {
    if (!val) {
      const inp = $(id);
      inp.style.borderColor = '#EF4444';
      inp.addEventListener('input', function fix() {
        inp.style.borderColor = '';
        inp.removeEventListener('input', fix);
      });
    }
  });
}

/* ── Score generator (AI-simulated) ─────────────── */
function getScores(persona) {
  const map = {
    Quick:    { p: '72%', s: 'Low',  r: '23%' },
    Standard: { p: '85%', s: 'Safe', r: '34%' },
    Deep:     { p: '96%', s: 'Safe', r: '48%' },
  };
  return map[persona] || map.Standard;
}

/* ── Render Email ────────────────────────────────── */
function renderEmail(data) {
  $('emailSubject').textContent = data.subject;
  $('emailBody').textContent    = data.body;
  $('outputSubtitle').textContent = `For ${data.prospect_name || 'your prospect'} · ${S.tone} · ${S.goal}`;

  const sc = getScores(S.persona);
  $('scoreP').textContent = sc.p;
  $('scoreS').textContent = sc.s;
  $('scoreR').textContent = sc.r;

  hide($('copyToast'));
}

/* ── Update today counter ────────────────────────── */
function bumpCounter() {
  S.emails += 1;
  const el = $('emailsToday');
  if (el) el.textContent = S.emails;
}

/* ── Copy ────────────────────────────────────────── */
function copyEmail() {
  const sub  = $('emailSubject').textContent;
  const body = $('emailBody').textContent;
  const text = `Subject: ${sub}\n\n${body}`;

  navigator.clipboard.writeText(text).then(() => {
    const btn = $('copyBtn');
    const orig = btn.innerHTML;
    btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg> Copied!`;
    btn.style.color = '#10B981';
    btn.style.borderColor = '#10B981';
    show($('copyToast'));
    setTimeout(() => {
      btn.innerHTML = orig;
      btn.style.color = '';
      btn.style.borderColor = '';
      hide($('copyToast'));
    }, 2500);
  }).catch(() => {
    const ta = document.createElement('textarea');
    ta.value = text; document.body.appendChild(ta);
    ta.select(); document.execCommand('copy');
    document.body.removeChild(ta);
  });
}

/* ── API Call ────────────────────────────────────── */
async function callGenerate(values) {
  const res = await fetch('/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(values),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Server ${res.status}`);
  }
  return res.json();
}

/* ── Main Handler ────────────────────────────────── */
async function handleGenerate() {
  hide($('formError'));
  const v = getValues();

  if (!validate(v)) {
    showError('Please fill in: Your Name, Service Offered, Prospect Name & Company.');
    return;
  }

  setBtn(true);
  setOutput('loading');

  // Run animation + API call in parallel
  const [data] = await Promise.all([
    callGenerate(v).catch(err => {
      setBtn(false);
      setOutput('empty');
      showError(`Generation failed: ${err.message}`);
      return null;
    }),
    runThinkingAnimation(),
    new Promise(r => setTimeout(r, 2200)),   // min animation time for good UX
  ]);

  if (!data) return;

  if (data.success) {
    // Mark last step done
    const last = $('ts-4');
    if (last) { last.classList.remove('active'); last.classList.add('done'); }
    await new Promise(r => setTimeout(r, 300));

    // Patch prospect_name into data so render can use it
    data.prospect_name = v.prospect_name;

    renderEmail(data);
    setOutput('result');
    bumpCounter();
    saveToHistory(data, v);
  } else {
    setOutput('empty');
    showError(data.error || 'Something went wrong. Try again.');
  }

  setBtn(false);
}

/* ── Regen ───────────────────────────────────────── */
async function handleRegen() {
  const v = getValues();
  if (!validate(v)) return;

  setOutput('loading');
  $('regenBtn').disabled = true;

  const [data] = await Promise.all([
    callGenerate(v).catch(() => null),
    runThinkingAnimation(),
    new Promise(r => setTimeout(r, 2200)),
  ]);

  if (data && data.success) {
    data.prospect_name = v.prospect_name;
    renderEmail(data);
    setOutput('result');
    bumpCounter();
    saveToHistory(data, v);
  } else {
    setOutput('result');
  }
  $('regenBtn').disabled = false;
}

/* ── Reset ───────────────────────────────────────── */
function handleReset() {
  ['yourName','yourCompany','serviceOffered','portfolio','prospectName','prospectCompany']
    .forEach(id => { const el = $(id); if (el) el.value = ''; });

  $('charNow').textContent = '0';

  // Reset pill groups to defaults
  document.querySelectorAll('#toneGroup .pill').forEach((p, i) => p.classList.toggle('active', i === 0));
  document.querySelectorAll('#expGroup .pill').forEach((p, i) => p.classList.toggle('active', i === 2));
  document.querySelectorAll('.p-level').forEach((p, i) => p.classList.toggle('active', i === 0));
  document.querySelectorAll('#goalGroup .goal-pill').forEach((p, i) => p.classList.toggle('active', i === 0));

  S.tone = 'Professional'; S.goal = 'Book a Call'; S.exp = 'Expert'; S.persona = 'Quick';

  setOutput('empty');
  updateChecklist();
  $('yourName').focus();
}

/* ── Output Tabs (shell) ─────────────────────────── */
function initOutputTabs() {
  document.querySelectorAll('.out-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.out-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      // Phase 2: will swap content based on tab.dataset.tab
    });
  });
}

/* ── Live input listeners for checklist ─────────── */
function initLiveChecklist() {
  ['yourName', 'serviceOffered', 'prospectName', 'prospectCompany'].forEach(id => {
    const el = $(id);
    if (el) el.addEventListener('input', updateChecklist);
  });
}

/* ── Enter key shortcut ──────────────────────────── */
function initEnterKey() {
  ['yourName','yourCompany','prospectName','prospectCompany','portfolio'].forEach(id => {
    const el = $(id);
    if (el) el.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); handleGenerate(); }
    });
  });
}

/* ── Nav active state ────────────────────────────── */
function initNav() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
      item.classList.add('active');
    });
  });
}

/* ── Boot ────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initPills('toneGroup', 'tone');
  initPills('expGroup', 'exp');
  initPills('goalGroup', 'goal', '.goal-pill');
  initPersonalization();
  initCharCounter();
  initLiveChecklist();
  initOutputTabs();
  initEnterKey();
  initNav();

  $('generateBtn').addEventListener('click', handleGenerate);
  $('copyBtn').addEventListener('click', copyEmail);
  $('regenBtn').addEventListener('click', handleRegen);
  $('clearBtn').addEventListener('click', handleReset);
  $('newBtn').addEventListener('click', handleReset);

  updateChecklist();
});

/* ── Save to localStorage (feeds Dashboard) ──────── */
function saveToHistory(data, values) {
  try {
    const history = JSON.parse(localStorage.getItem('smartcopy_history') || '[]');
    history.push({
      id:               Date.now(),
      timestamp:        new Date().toISOString(),
      subject:          data.subject,
      body:             data.body,
      tone:             values.tone,
      goal:             values.goal,
      personalization:  values.personalization,
      prospect_name:    values.prospect_name,
      prospect_company: values.prospect_company,
      sender_name:      values.sender_name,
    });
    // Keep last 50 only
    if (history.length > 50) history.splice(0, history.length - 50);
    localStorage.setItem('smartcopy_history', JSON.stringify(history));
  } catch { /* silent fail */ }
}