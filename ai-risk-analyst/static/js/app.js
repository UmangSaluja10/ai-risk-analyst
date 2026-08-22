// Phase 0: wires the form to the dummy /analyze endpoint and updates the UI.
// Later phases will replace the dummy backend logic, not this file's structure.

const CIRCLE_CIRCUMFERENCE = 283; // 2 * PI * r(45), matches the SVG in index.html

const form = document.getElementById("analyzeForm");
const analyzeBtn = document.getElementById("analyzeBtn");
const analyzeBtnLabel = document.getElementById("analyzeBtnLabel");
const liveFeed = document.getElementById("liveFeed");

let requestCounter = 8820;

// Default the timestamp field to "now" so the form isn't empty on load
const tsInput = document.getElementById("inputTimestamp");
if (tsInput && !tsInput.value) {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  tsInput.value = now.toISOString().slice(0, 16);
}

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

    if (data.profile) {
      document.getElementById("userAvgTx").textContent =
        data.profile.transaction_count > 0 ? `Rs.${data.profile.avg_amount.toLocaleString()}` : "No history yet";
      document.getElementById("userAccountAge").textContent =
        data.profile.transaction_count > 0 ? `${data.profile.account_age_days} days` : "New user";
    }
  } catch (err) {
    document.getElementById("aiExplanationText").textContent =
      "Error contacting backend: " + err.message;
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtnLabel.textContent = "ANALYZE RISK";
  }
});