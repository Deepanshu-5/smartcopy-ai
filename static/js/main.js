// ─────────────────────────────────────────
//  SmartCopy AI — main.js  (Phase 5)
// ─────────────────────────────────────────

const API_URL = "/generate";

// ── Output state ───────────────────────────
let currentOutput = {
  cold_email:  { subject: "", body: "" },
  follow_up:   { subject: "", body: "" },
  linkedin_dm: { body: "" },
};
let activeTab  = "cold";
let usageToday = 0;   // loaded from server, not localStorage
let dailyLimit = 5;

// ── DOM refs ───────────────────────────────
const yourName        = () => document.getElementById("yourName")?.value.trim()        || "";
const yourCompany     = () => document.getElementById("yourCompany")?.value.trim()     || "";
const serviceOffered  = () => document.getElementById("serviceOffered")?.value.trim()  || "";
const portfolioInput  = () => document.getElementById("portfolio")?.value.trim()       || "";
const prospectName    = () => document.getElementById("prospectName")?.value.trim()    || "";
const prospectCompany = () => document.getElementById("prospectCompany")?.value.trim() || "";

const getActivePill           = (groupId) => document.querySelector(`#${groupId} .pill.active`)?.dataset.val || "";
const getActivePersonalization = ()        => document.querySelector(".p-level.active")?.dataset.val || "Quick";
const getActiveGoal            = ()        => document.querySelector("#goalGroup .goal-pill.active")?.dataset.val || "Get a Reply";

const generateBtn    = document.getElementById("generateBtn");
const btnDefault     = document.getElementById("btn-default");
const btnLoading     = document.getElementById("btn-loading");
const formError      = document.getElementById("formError");
const errorMsg       = document.getElementById("errorMsg");
const emptyState     = document.getElementById("emptyState");
const aiThinking     = document.getElementById("aiThinking");
const emailResult    = document.getElementById("emailResult");
const outputActions  = document.getElementById("outputActions");
const outputTabs     = document.getElementById("outputTabs");
const outputSubtitle = document.getElementById("outputSubtitle");
const emailSubject   = document.getElementById("emailSubject");
const emailBody      = document.getElementById("emailBody");
const subjectBlock   = document.querySelector(".email-subject-block");
const emailSep       = document.querySelector(".email-sep");
const scoreP         = document.getElementById("scoreP");
const scoreS         = document.getElementById("scoreS");
const scoreR         = document.getElementById("scoreR");
const copyBtn        = document.getElementById("copyBtn");
const regenBtn       = document.getElementById("regenBtn");
const copyToast      = document.getElementById("copyToast");
const emailsToday    = document.getElementById("emailsToday");

// ── Init ───────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  setupExperiencePills();
  setupTonePills();
  setupPersonalizationTrack();
  setupGoalPills();
  setupTabs();
  setupCharCounter();
  setupLiveChecklist();
  setupGenerateBtn();
  setupCopyBtn();
  setupRegenBtn();
  setupTopbarBtns();

  // Load real usage from server
  await fetchAndUpdateUsage();
});

// ── Fetch usage from server ────────────────
async function fetchAndUpdateUsage() {
  try {
    const res  = await fetch("/api/usage");
    const data = await res.json();
    usageToday = data.usage      || 0;
    dailyLimit = data.daily_limit || 5;
    updateUsageDisplay();
  } catch {
    // Silently fail — UI stays at 0
  }
}

function updateUsageDisplay() {
  if (emailsToday) emailsToday.textContent = usageToday;

  const planEl = document.querySelector(".user-plan");
  if (planEl) {
    const left = Math.max(0, dailyLimit - usageToday);
    // Preserve plan name prefix (e.g. "Free · ")
    const current = planEl.textContent;
    const prefix  = current.includes("·") ? current.split("·")[0].trim() : "Free";
    planEl.textContent = `${prefix} · ${left} left today`;
  }

  if (generateBtn) {
    generateBtn.disabled = usageToday >= dailyLimit;
    if (usageToday >= dailyLimit && btnDefault) {
      btnDefault.textContent = "Daily limit reached — Upgrade to Pro";
    }
  }
}

// ── Pill groups ────────────────────────────
function setupExperiencePills() {
  document.querySelectorAll("#expGroup .pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll("#expGroup .pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
    });
  });
}

function setupTonePills() {
  document.querySelectorAll("#toneGroup .pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll("#toneGroup .pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
    });
  });
}

function setupPersonalizationTrack() {
  document.querySelectorAll(".p-level").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".p-level").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });
}

function setupGoalPills() {
  document.querySelectorAll("#goalGroup .goal-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll("#goalGroup .goal-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
    });
  });
}

// ── Output tabs ────────────────────────────
function setupTabs() {
  document.querySelectorAll(".out-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".out-tab").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeTab = btn.dataset.tab;
      renderActiveTab();
    });
  });
}

function renderActiveTab() {
  switch (activeTab) {
    case "cold":
      if (emailSubject) emailSubject.textContent = currentOutput.cold_email.subject;
      if (emailBody)    emailBody.textContent    = currentOutput.cold_email.body;
      showSubjectBlock(true);
      if (outputSubtitle) outputSubtitle.textContent = "Cold outreach email";
      break;
    case "followup":
      if (emailSubject) emailSubject.textContent = currentOutput.follow_up.subject;
      if (emailBody)    emailBody.textContent    = currentOutput.follow_up.body;
      showSubjectBlock(true);
      if (outputSubtitle) outputSubtitle.textContent = "Follow-up email";
      break;
    case "linkedin":
      if (emailSubject) emailSubject.textContent = "";
      if (emailBody)    emailBody.textContent    = currentOutput.linkedin_dm.body;
      showSubjectBlock(false);
      if (outputSubtitle) outputSubtitle.textContent = "LinkedIn DM";
      break;
  }
}

function showSubjectBlock(show) {
  if (subjectBlock) subjectBlock.style.display = show ? "" : "none";
  if (emailSep)     emailSep.style.display     = show ? "" : "none";
}

// ── Char counter ───────────────────────────
function setupCharCounter() {
  const textarea = document.getElementById("serviceOffered");
  const counter  = document.getElementById("charNow");
  if (!textarea || !counter) return;
  textarea.addEventListener("input", () => {
    const len = textarea.value.length;
    counter.textContent = len;
    counter.style.color = len > 260 ? "#ef4444" : "";
  });
}

// ── Live checklist ─────────────────────────
function setupLiveChecklist() {
  const nameInput    = document.getElementById("yourName");
  const serviceInput = document.getElementById("serviceOffered");
  const pNameInput   = document.getElementById("prospectName");
  const pCompInput   = document.getElementById("prospectCompany");
  const dotUser      = document.getElementById("dot-user");
  const dotTarget    = document.getElementById("dot-target");

  function check() {
    const userOk   = nameInput?.value.trim() && serviceInput?.value.trim();
    const targetOk = pNameInput?.value.trim() && pCompInput?.value.trim();
    if (dotUser)   dotUser.classList.toggle("done", !!userOk);
    if (dotTarget) dotTarget.classList.toggle("done", !!targetOk);
  }

  [nameInput, serviceInput, pNameInput, pCompInput].forEach(el => el?.addEventListener("input", check));
}

// ── Thinking animation ─────────────────────
function startThinking() {
  emptyState?.classList.add("hidden");
  emailResult?.classList.add("hidden");
  aiThinking?.classList.remove("hidden");

  const steps = document.querySelectorAll(".thinking-step");
  steps.forEach(s => s.classList.remove("active", "done"));
  steps.forEach((step, i) => {
    setTimeout(() => {
      if (i > 0) steps[i - 1].classList.replace("active", "done");
      step.classList.add("active");
    }, i * 900);
  });
}

function stopThinking() {
  aiThinking?.classList.add("hidden");
}

// ── Error display ──────────────────────────
function showError(msg) {
  if (!formError || !errorMsg) return;
  errorMsg.textContent = msg;
  formError.classList.remove("hidden");
  setTimeout(() => formError.classList.add("hidden"), 5000);
}

// ── Score pills ────────────────────────────
function updateScores(personalization, tone, goal) {
  const personMap = { Quick: "62%", Standard: "78%", Deep: "94%" };
  const spamMap   = { Professional: "12%", Friendly: "9%", Direct: "15%", Casual: "8%" };
  const replyMap  = { "Book a Call": "31%", "Get a Reply": "44%", "Demo Request": "28%", "Share Resource": "22%" };
  if (scoreP) scoreP.textContent = personMap[personalization] || "78%";
  if (scoreS) scoreS.textContent = spamMap[tone]              || "12%";
  if (scoreR) scoreR.textContent = replyMap[goal]             || "35%";
}

// ── Form helpers ───────────────────────────
function collectFormData() {
  return {
    sender_name:      yourName(),
    sender_company:   yourCompany(),
    offering:         serviceOffered(),
    experience:       getActivePill("expGroup") || "Expert",
    portfolio:        portfolioInput(),
    prospect_name:    prospectName(),
    prospect_company: prospectCompany(),
    tone:             getActivePill("toneGroup") || "Professional",
    personalization:  getActivePersonalization(),
    goal:             getActiveGoal(),
  };
}

function validateForm(data) {
  if (!data.sender_name)      return "Your Name is required.";
  if (!data.offering)         return "Service / Skill is required.";
  if (!data.prospect_name)    return "Prospect Name is required.";
  if (!data.prospect_company) return "Prospect Company is required.";
  return null;
}

// ── Show result ────────────────────────────
function showResult(data, result) {
  currentOutput = {
    cold_email:  { subject: result.subject,          body: result.body },
    follow_up:   { subject: result.followup_subject, body: result.followup_body },
    linkedin_dm: { body: result.linkedin_body },
  };

  activeTab = "cold";
  document.querySelectorAll(".out-tab").forEach(b => {
    b.classList.toggle("active", b.dataset.tab === "cold");
  });

  renderActiveTab();
  updateScores(data.personalization, data.tone, data.goal);

  emailResult?.classList.remove("hidden");
  if (outputActions) outputActions.style.display = "";
  if (outputTabs)    outputTabs.style.display    = "";

  emailResult?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ── Generate button ────────────────────────
function setupGenerateBtn() {
  if (!generateBtn) return;

  generateBtn.addEventListener("click", async () => {
    if (usageToday >= dailyLimit) {
      showError("Daily limit reached. Upgrade to Pro for unlimited emails.");
      return;
    }

    const data  = collectFormData();
    const error = validateForm(data);
    if (error) { showError(error); return; }

    generateBtn.disabled = true;
    btnDefault?.classList.add("hidden");
    btnLoading?.classList.remove("hidden");
    formError?.classList.add("hidden");

    startThinking();

    try {
      const res    = await fetch(API_URL, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(data),
      });
      const result = await res.json();

      if (!res.ok || !result.success) {
        throw new Error(result.error || "Generation failed. Please try again.");
      }

      stopThinking();
      showResult(data, result);

      // Update usage from server response
      usageToday = result.usage      || usageToday + 1;
      dailyLimit = result.daily_limit || dailyLimit;
      updateUsageDisplay();

    } catch (err) {
      stopThinking();
      emptyState?.classList.remove("hidden");
      showError(err.message || "Something went wrong. Please try again.");
    } finally {
      // Re-check disable state after usage update
      generateBtn.disabled = usageToday >= dailyLimit;
      btnDefault?.classList.remove("hidden");
      btnLoading?.classList.add("hidden");
    }
  });
}

// ── Copy button ────────────────────────────
function setupCopyBtn() {
  if (!copyBtn) return;
  copyBtn.addEventListener("click", async () => {
    let text = "";
    if (activeTab === "linkedin") {
      text = currentOutput.linkedin_dm.body;
    } else {
      const src = activeTab === "cold" ? currentOutput.cold_email : currentOutput.follow_up;
      text = `Subject: ${src.subject}\n\n${src.body}`;
    }
    try {
      await navigator.clipboard.writeText(text);
      copyToast?.classList.remove("hidden");
      setTimeout(() => copyToast?.classList.add("hidden"), 2500);
    } catch {
      showError("Could not copy to clipboard.");
    }
  });
}

// ── Regen button ───────────────────────────
function setupRegenBtn() {
  if (!regenBtn) return;
  regenBtn.addEventListener("click", () => generateBtn?.click());
}

// ── Topbar buttons ─────────────────────────
function setupTopbarBtns() {
  document.getElementById("clearBtn")?.addEventListener("click", () => {
    ["yourName","yourCompany","serviceOffered","portfolio","prospectName","prospectCompany"]
      .forEach(id => { const el = document.getElementById(id); if (el) el.value = ""; });

    const charNow = document.getElementById("charNow");
    if (charNow) charNow.textContent = "0";

    document.querySelectorAll("#expGroup .pill").forEach(p => p.classList.remove("active"));
    document.querySelector("#expGroup .pill[data-val='Expert']")?.classList.add("active");
    document.querySelectorAll("#toneGroup .pill").forEach(p => p.classList.remove("active"));
    document.querySelector("#toneGroup .pill[data-val='Professional']")?.classList.add("active");
    document.querySelectorAll(".p-level").forEach(p => p.classList.remove("active"));
    document.querySelector(".p-level[data-val='Quick']")?.classList.add("active");
    document.querySelectorAll("#goalGroup .goal-pill").forEach(p => p.classList.remove("active"));
    document.querySelector("#goalGroup .goal-pill[data-val='Book a Call']")?.classList.add("active");

    emailResult?.classList.add("hidden");
    emptyState?.classList.remove("hidden");
    if (outputActions) outputActions.style.display = "none";
    if (outputTabs)    outputTabs.style.display    = "none";
    if (outputSubtitle) outputSubtitle.textContent = "Your email will appear here";
  });

  document.getElementById("newBtn")?.addEventListener("click", () => {
    document.getElementById("clearBtn")?.click();
    document.getElementById("yourName")?.focus();
  });
}