// Phase 0: wires the form to the dummy /analyze endpoint and updates the UI.
// Later phases will replace the dummy backend logic, not this file's structure.

const CIRCLE_CIRCUMFERENCE = 283; // 2 * PI * r(45), matches the SVG in index.html

const form = document.getElementById("analyzeForm");
const analyzeBtn = document.getElementById("analyzeBtn");
const analyzeBtnLabel = document.getElementById("analyzeBtnLabel");
const liveFeed = document.getElementById("liveFeed");

// View switching (generic, covers all sidebar views)
const views = {
  single: document.getElementById("singleView"),
  batch: document.getElementById("batchView"),
  logs: document.getElementById("logsView"),
  profiles: document.getElementById("profilesView"),
  insights: document.getElementById("insightsView"),
  settings: document.getElementById("settingsView"),
};
const navLinks = {
  single: document.getElementById("navSingle"),
  batch: document.getElementById("navBatch"),
  logs: document.getElementById("navLogs"),
  profiles: document.getElementById("navProfiles"),
  insights: document.getElementById("navInsights"),
  settings: document.getElementById("navSettings"),
};

function switchView(viewName) {
  Object.entries(views).forEach(([name, el]) => {
    if (!el) return;
    el.classList.toggle("hidden", name !== viewName);
  });
  Object.entries(navLinks).forEach(([name, el]) => {
    if (!el) return;
    const active = name === viewName;
    el.classList.toggle("text-primary", active);
    el.classList.toggle("font-bold", active);
    el.classList.toggle("bg-primary/10", active);
    el.classList.toggle("shadow-[0_0_15px_rgba(173,198,255,0.3)]", active);
    el.classList.toggle("scale-95", active);
    el.classList.toggle("text-on-surface-variant", !active);
  });

  if (viewName === "logs") loadLogs();
  if (viewName === "profiles") loadProfiles();
  if (viewName === "insights") loadInsights();
  if (viewName === "settings") loadSettings();
}

Object.entries(navLinks).forEach(([name, el]) => {
  if (el) el.addEventListener("click", () => switchView(name));
});

switchView("single");

// Logs view
async function loadLogs(query) {
  const q = query !== undefined ? query : document.getElementById("logsSearchInput").value;
  const res = await fetch(`/logs?q=${encodeURIComponent(q || "")}`);
  const data = await res.json();
  const tbody = document.getElementById("logsTableBody");
  const statusColor = { Suspicious: "text-error", Review: "text-tertiary", Cleared: "text-primary" };
  tbody.innerHTML = (data.logs || [])
    .map(
      (l) => `
    <tr class="border-b border-white/5">
      <td class="py-2 pr-4 font-data-point text-data-point text-on-surface-variant">${l.tx_id}</td>
      <td class="py-2 pr-4">${l.user_id}</td>
      <td class="py-2 pr-4 font-data-point text-data-point">Rs.${l.amount.toLocaleString()}</td>
      <td class="py-2 pr-4 font-bold font-data-point ${statusColor[l.status] || ""}">${l.risk_score}</td>
      <td class="py-2 pr-4 ${statusColor[l.status] || ""}">${l.status}</td>
      <td class="py-2 pr-4 text-on-surface-variant">${new Date(l.timestamp).toLocaleString()}</td>
    </tr>`
    )
    .join("");
}
document.getElementById("logsSearchInput")?.addEventListener("input", (e) => loadLogs(e.target.value));

// Profiles view
async function loadProfiles() {
  const res = await fetch("/profiles");
  const data = await res.json();
  const tbody = document.getElementById("profilesTableBody");
  tbody.innerHTML = (data.profiles || [])
    .map((p) => {
      const bars = p.recent_scores
        .map((s) => {
          const color = s >= 60 ? "bg-error" : s >= 30 ? "bg-tertiary" : "bg-primary";
          return `<div class="${color} w-1.5 rounded-t" style="height:${Math.max(s, 8)}%"></div>`;
        })
        .join("");
      return `
      <tr class="border-b border-white/5">
        <td class="py-2 pr-4 font-data-point text-data-point">${p.user_id}</td>
        <td class="py-2 pr-4">${p.transaction_count}</td>
        <td class="py-2 pr-4 font-data-point text-data-point">Rs.${p.avg_amount.toLocaleString()}</td>
        <td class="py-2 pr-4 ${p.flagged_count > 0 ? "text-error font-bold" : ""}">${p.flagged_count}</td>
        <td class="py-2 pr-4 text-on-surface-variant">${p.last_active ? new Date(p.last_active).toLocaleDateString() : "--"}</td>
        <td class="py-2 pr-4"><div class="flex items-end gap-0.5 h-8">${bars}</div></td>
      </tr>`;
    })
    .join("");
}

// Insights view
async function loadInsights() {
  const res = await fetch("/insights");
  const data = await res.json();
  document.getElementById("insightTotal").textContent = data.total_transactions;
  document.getElementById("insightFlaggedPct").textContent = `${data.flagged_pct}%`;
  document.getElementById("insightPeakWindow").textContent = data.peak_fraud_window;

  const list = document.getElementById("insightsList");
  const dynamicInsights = [
    `${data.flagged_pct}% of all analyzed transactions were flagged as Review or Suspicious.`,
    `Most flagged transactions cluster around the ${data.peak_fraud_window} window.`,
    `${data.top_risky_location} is the most common location among flagged transactions.`,
  ];
  list.innerHTML = dynamicInsights.map((s) => `<li>- ${s}</li>`).join("");
}

// Settings view
async function loadSettings() {
  const res = await fetch("/system_status");
  const data = await res.json();
  document.getElementById("settingsVersion").textContent = data.version;
  document.getElementById("settingsGroq").textContent = data.groq_configured ? "Connected" : "Not configured";
  document.getElementById("settingsFirebase").textContent = data.firebase_connected ? "Connected" : "Using local JSON fallback";
}

// Alerts dropdown
const alertsBellBtn = document.getElementById("alertsBellBtn");
const alertsDropdown = document.getElementById("alertsDropdown");
if (alertsBellBtn && alertsDropdown) {
alertsBellBtn.addEventListener("click", async (e) => {
  e.stopPropagation();
  const isHidden = alertsDropdown.classList.contains("hidden");
  if (isHidden) {
    const res = await fetch("/logs");
    const data = await res.json();
    const highRisk = (data.logs || []).filter((l) => l.status === "Suspicious").slice(0, 5);
    const alertsList = document.getElementById("alertsList");
    alertsList.innerHTML = highRisk.length
      ? highRisk.map((l) => `<div class="text-sm border-b border-white/5 py-2"><span class="text-error font-bold">${l.tx_id}</span> flagged (High Risk) -- ${l.user_id}, Rs.${l.amount.toLocaleString()}</div>`).join("")
      : '<p class="text-on-surface-variant text-sm py-2">No high-risk alerts.</p>';
    const badge = document.getElementById("alertsBadge");
    if (highRisk.length > 0) {
      badge.textContent = highRisk.length;
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  }
  alertsDropdown.classList.toggle("hidden");
});
document.addEventListener("click", (e) => {
  if (!alertsDropdown.contains(e.target) && e.target !== alertsBellBtn) {
    alertsDropdown.classList.add("hidden");
  }
});
}

// Global search bar -> jumps to Logs view filtered
document.getElementById("globalSearchInput")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    const q = e.target.value;
    switchView("logs");
    document.getElementById("logsSearchInput").value = q;
    loadLogs(q);
  }
});

// Batch Analysis logic
let lastBatchResult = null;

function renderBatchTable(showFlaggedOnly) {
  const tbody = document.getElementById("batchResultsBody");
  const rows = showFlaggedOnly ? lastBatchResult.flagged_only : lastBatchResult.results;
  tbody.innerHTML = "";

  const statusColor = { Suspicious: "text-error", Review: "text-tertiary", Cleared: "text-primary" };

  rows.forEach((r) => {
    const tr = document.createElement("tr");
    tr.className = "border-b border-white/5";
    tr.innerHTML = `
      <td class="py-2 pr-4 font-data-point text-data-point text-on-surface-variant">${r.payment_id}</td>
      <td class="py-2 pr-4">${r.user_id}</td>
      <td class="py-2 pr-4 font-data-point text-data-point">Rs.${r.amount.toLocaleString()}</td>
      <td class="py-2 pr-4">${r.payment_type}</td>
      <td class="py-2 pr-4 font-bold font-data-point ${statusColor[r.status] || ""}">${r.risk_score}</td>
      <td class="py-2 pr-4 ${statusColor[r.status] || ""}">${r.status}</td>
      <td class="py-2 pr-4">${r.confidence}</td>
      <td class="py-2 pr-4 text-on-surface-variant max-w-xs truncate" title="${r.explanation.replace(/"/g, '&quot;')}">${r.explanation}</td>
    `;
    tbody.appendChild(tr);
  });
}

document.getElementById("runBatchBtn")?.addEventListener("click", async () => {
  const fileInput = document.getElementById("batchFileInput");
  const btn = document.getElementById("runBatchBtn");
  const btnLabel = document.getElementById("runBatchBtnLabel");

  if (!fileInput.files.length) {
    alert("Choose a CSV or JSON file first.");
    return;
  }

  btn.disabled = true;
  btnLabel.textContent = "PROCESSING...";

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  try {
    const res = await fetch("/analyze_batch", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      alert(`Batch failed: ${data.error || "unknown error"}\n${(data.details || []).join("\n")}`);
      return;
    }

    lastBatchResult = data;

    const summaryList = document.getElementById("batchSummaryList");
    summaryList.innerHTML = data.summary_insights.map((s) => `<li>- ${s}</li>`).join("");
    document.getElementById("batchSummaryPanel").classList.remove("hidden");

    document.getElementById("batchResultsPanel").classList.remove("hidden");
    renderBatchTable(document.getElementById("batchFilterFlagged").checked);
  } catch (err) {
    alert("Error processing batch: " + err.message);
  } finally {
    btn.disabled = false;
    btnLabel.textContent = "RUN BATCH ANALYSIS";
  }
});

document.getElementById("batchFilterFlagged")?.addEventListener("change", (e) => {
  if (lastBatchResult) renderBatchTable(e.target.checked);
});

document.getElementById("exportCsvBtn")?.addEventListener("click", () => {
  if (!lastBatchResult) return;
  const blob = new Blob([lastBatchResult.csv_export], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "risk_analysis_results.csv";
  a.click();
  URL.revokeObjectURL(url);
});

// Default the timestamp field to "now" so the form isn't empty on load
const tsInput = document.getElementById("inputTimestamp");
if (tsInput && !tsInput.value) {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  tsInput.value = now.toISOString().slice(0, 16);
}

// Auto-detect the real IP/location for a realistic default, but keep the field
// editable so you can still manually test risky/VPN locations for demos.
(async function detectLocation() {
  const locationInput = document.getElementById("inputLocation");
  try {
    const res = await fetch("https://ipapi.co/json/");
    const data = await res.json();
    if (data && data.ip) {
      locationInput.value = `${data.ip} (${data.country_code || "IN"})`;
    } else {
      locationInput.value = "103.21.58.10 (IN)"; // Indian IP fallback
    }
  } catch (err) {
    locationInput.value = "103.21.58.10 (IN)"; // Indian IP fallback if detection fails/blocked
  }
})();

function colorClass(color) {
  // maps backend "color" keys to Tailwind classes already defined in the design tokens
  const map = {
    error: { text: "text-error", bar: "bg-error", glow: "shadow-[0_0_10px_rgba(255,180,171,0.5)]" },
    tertiary: { text: "text-tertiary", bar: "bg-tertiary", glow: "shadow-[0_0_10px_rgba(255,181,149,0.5)]" },
    primary: { text: "text-primary", bar: "bg-primary", glow: "shadow-[0_0_10px_rgba(173,198,255,0.5)]" },
  };
  return map[color] || map.primary;
}

function renderFactors(factors) {
  const container = document.getElementById("riskFactorsContainer");
  container.innerHTML = "";
  factors.forEach((factor) => {
    const c = colorClass(factor.color);
    const row = document.createElement("div");
    row.innerHTML = `
      <div class="flex justify-between text-sm mb-1">
        <span class="text-on-surface">${factor.label}</span>
        <span class="${c.text} font-bold font-data-point">+${factor.score}</span>
      </div>
      <div class="w-full bg-surface-container-highest rounded-full h-2">
        <div class="${c.bar} h-2 rounded-full ${c.glow}" style="width: ${factor.score}%"></div>
      </div>
    `;
    container.appendChild(row);
  });
}

function statusStyling(status) {
  const panel = document.getElementById("riskScorePanel");
  const heading = document.getElementById("riskStatusHeading");
  const scoreValue = document.getElementById("riskScoreValue");
  const circle = document.getElementById("scoreCircle");

  panel.classList.remove("glass-panel-danger", "glass-panel-safe", "glass-panel");
  heading.classList.remove("text-error", "text-primary", "text-tertiary");
  scoreValue.classList.remove("text-error", "text-primary", "text-tertiary");

  if (status === "Suspicious" || status === "Critical") {
    panel.classList.add("glass-panel-danger");
    heading.classList.add("text-error");
    scoreValue.classList.add("text-error");
    circle.setAttribute("stroke", "#ffb4ab");
  } else if (status === "Review") {
    panel.classList.add("glass-panel-danger");
    heading.classList.add("text-tertiary");
    scoreValue.classList.add("text-tertiary");
    circle.setAttribute("stroke", "#ffb595");
  } else {
    panel.classList.add("glass-panel-safe");
    heading.classList.add("text-primary");
    scoreValue.classList.add("text-primary");
    circle.setAttribute("stroke", "#adc6ff");
  }
}

function addFeedEntry(status, txId) {
  let badge = '<span class="text-xs text-primary bg-primary/10 px-2 py-1 rounded">CLEARED</span>';
  if (status === "Suspicious" || status === "Critical") {
    badge = '<span class="text-xs text-error bg-error/10 px-2 py-1 rounded">FLAGGED</span>';
  } else if (status === "Review") {
    badge = '<span class="text-xs text-tertiary bg-tertiary/10 px-2 py-1 rounded">REVIEW</span>';
  }

  if (liveFeed.children.length === 1 && liveFeed.children[0].innerText.includes("No requests")) {
    liveFeed.innerHTML = "";
  }

  const row = document.createElement("div");
  row.className = "flex justify-between items-center py-2 border-b border-white/5";
  row.innerHTML = `<span class="font-data-point text-data-point text-on-surface-variant">${txId || "TX-????"}</span>${badge}`;
  liveFeed.prepend(row);
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  analyzeBtn.disabled = true;
  analyzeBtnLabel.textContent = "ANALYZING...";

  const payload = {
    user_id: document.getElementById("inputUserId").value,
    amount: document.getElementById("inputAmount").value,
    location: document.getElementById("inputLocation").value,
    payment_type: document.getElementById("inputPaymentType").value,
    timestamp: document.getElementById("inputTimestamp").value || undefined,
  };

  try {
    const res = await fetch("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (!res.ok) {
      // Phase 1: backend validation failures come back as {error, details: [...]}
      const details = (data.details || []).join(" | ");
      document.getElementById("aiExplanationText").textContent =
        `Validation error: ${data.error || "unknown"}. ${details}`;
      document.getElementById("riskStatusHeading").textContent = "INVALID INPUT";
      document.getElementById("riskStatusSubtitle").textContent = "Fix the highlighted fields and try again.";
      return;
    }

    document.getElementById("riskScoreValue").textContent = data.risk_score;
    const headingMap = {
      Suspicious: "RISK DETECTED",
      Critical: "RISK DETECTED",
      Review: "NEEDS REVIEW",
    };
    const subtitleMap = {
      Suspicious: "Transaction paused pending manual review.",
      Critical: "Transaction paused pending manual review.",
      Review: "Some anomalies found -- manual review recommended.",
    };
    document.getElementById("riskStatusHeading").textContent = headingMap[data.status] || "TRANSACTION CLEARED";
    document.getElementById("riskStatusSubtitle").textContent = subtitleMap[data.status] || "No significant anomalies detected.";
    document.getElementById("aiExplanationText").textContent = data.explanation;

    const offset = CIRCLE_CIRCUMFERENCE - (CIRCLE_CIRCUMFERENCE * data.risk_score) / 100;
    document.getElementById("scoreCircle").setAttribute("stroke-dashoffset", offset);

    statusStyling(data.status);
    renderFactors(data.factors || []);
    addFeedEntry(data.status, data.tx_id);

    const confBadge = document.getElementById("confidenceBadge");
    if (data.confidence) {
      const confColors = {
        High: "bg-primary/20 text-primary",
        Medium: "bg-tertiary/20 text-tertiary",
        Low: "bg-error/20 text-error",
      };
      confBadge.className = `text-xs font-bold px-2 py-1 rounded-full mb-3 relative z-10 ${confColors[data.confidence] || ""}`;
      confBadge.textContent = `CONFIDENCE: ${data.confidence.toUpperCase()}`;
      confBadge.classList.remove("hidden");
    }

    if (data.pipeline) {
      const pipelineContainer = document.getElementById("pipelineStatus");
      const labels = {
        rule_engine: "Rule Engine",
        user_profiling: "User Profiling",
        llm_reasoning: "LLM Reasoning",
        rag: "RAG",
      };
      pipelineContainer.innerHTML = Object.entries(data.pipeline)
        .map(([key, ran]) => {
          const icon = ran ? "check_circle" : "cancel";
          const color = ran ? "text-primary" : "text-on-surface-variant";
          return `<span class="flex items-center gap-1 ${color}"><span class="material-symbols-outlined text-[16px]">${icon}</span>${labels[key] || key}</span>`;
        })
        .join("");
    }

    if (data.profile) {
      document.getElementById("userAvgTx").textContent =
        data.profile.transaction_count > 0 ? `Rs.${data.profile.avg_amount.toLocaleString()}` : "No history yet";
      document.getElementById("userAccountAge").textContent =
        data.profile.transaction_count > 0 ? `${data.profile.account_age_days} days` : "New user";
    }

    if (data.rag_context) {
      const ragContainer = document.getElementById("ragContext");
      ragContainer.innerHTML = "";
      if (data.rag_context.length === 0) {
        ragContainer.innerHTML = '<p class="text-on-surface-variant text-sm">No matching fraud patterns found.</p>';
      } else {
        data.rag_context.forEach((doc) => {
          const div = document.createElement("div");
          div.className = "text-sm border-l-2 border-outline pl-3 py-1";
          div.innerHTML = `<p class="text-on-surface-variant leading-relaxed"><span class="text-primary font-bold bg-primary/10 px-1 rounded">${doc.title}</span> ${doc.content}</p>`;
          ragContainer.appendChild(div);
        });
      }
    }
  } catch (err) {
    document.getElementById("aiExplanationText").textContent =
      "Error contacting backend: " + err.message;
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtnLabel.textContent = "ANALYZE RISK";
  }
});