// Phase 0: wires the form to the dummy /analyze endpoint and updates the UI.
// Later phases will replace the dummy backend logic, not this file's structure.

const CIRCLE_CIRCUMFERENCE = 283; // 2 * PI * r(45), matches the SVG in index.html

const form = document.getElementById("analyzeForm");
const analyzeBtn = document.getElementById("analyzeBtn");
const analyzeBtnLabel = document.getElementById("analyzeBtnLabel");
const liveFeed = document.getElementById("liveFeed");

// View switching (Dashboard <-> Batch Analysis)
const navSingle = document.getElementById("navSingle");
const navBatch = document.getElementById("navBatch");
const singleView = document.getElementById("singleView");
const batchView = document.getElementById("batchView");

function setActiveNav(activeEl, inactiveEl) {
  activeEl.classList.add("text-primary", "font-bold", "bg-primary/10", "shadow-[0_0_15px_rgba(173,198,255,0.3)]", "scale-95");
  activeEl.classList.remove("text-on-surface-variant");
  inactiveEl.classList.remove("text-primary", "font-bold", "bg-primary/10", "shadow-[0_0_15px_rgba(173,198,255,0.3)]", "scale-95");
  inactiveEl.classList.add("text-on-surface-variant");
}

navSingle.addEventListener("click", () => {
  singleView.classList.remove("hidden");
  batchView.classList.add("hidden");
  setActiveNav(navSingle, navBatch);
});

navBatch.addEventListener("click", () => {
  batchView.classList.remove("hidden");
  singleView.classList.add("hidden");
  setActiveNav(navBatch, navSingle);
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

document.getElementById("runBatchBtn").addEventListener("click", async () => {
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

document.getElementById("batchFilterFlagged").addEventListener("change", (e) => {
  if (lastBatchResult) renderBatchTable(e.target.checked);
});

document.getElementById("exportCsvBtn").addEventListener("click", () => {
  if (!lastBatchResult) return;
  const blob = new Blob([lastBatchResult.csv_export], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "risk_analysis_results.csv";
  a.click();
  URL.revokeObjectURL(url);
});

let requestCounter = 8820;

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

function addFeedEntry(status) {
  requestCounter += 1;
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
  row.innerHTML = `<span class="font-data-point text-data-point text-on-surface-variant">TX-${requestCounter}</span>${badge}`;
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
    addFeedEntry(data.status);

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