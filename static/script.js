/**
 * QueueCare – Client-side JavaScript
 * Handles:
 *  1. Rule-based AI Department Recommendation & Auto-selection
 *  2. Phone number validation
 *  3. Live real-time token tracking (Auto-polling API)
 *  4. Audio chime notification when token is called
 */

document.addEventListener("DOMContentLoaded", () => {
  // Initialize AI Symptom Checker if present on page
  initAiRecommendation();

  // Initialize Phone validation if registration form exists
  initFormValidation();

  // Initialize Live Token Tracker if on token.html
  initLiveTokenTracker();
});

/* -------------------------------------------------------------
 * 1. AI Department Recommendation Feature
 * ------------------------------------------------------------- */
function initAiRecommendation() {
  const btnAnalyze = document.getElementById("btn-ai-analyze");
  const symptomsInput = document.getElementById("ai-symptoms-input");
  const resultBox = document.getElementById("ai-result-box");
  const resultDeptName = document.getElementById("ai-result-dept");
  const resultReason = document.getElementById("ai-result-reason");
  const btnApply = document.getElementById("btn-apply-recommendation");
  const hiddenSymptoms = document.getElementById("hidden-symptoms");

  if (!btnAnalyze || !symptomsInput) return;

  const runAnalysis = async () => {
    const symptoms = symptomsInput.value.trim();
    if (!symptoms) {
      alert("Please describe your symptoms first (e.g., 'severe knee pain', 'fever and headache').");
      symptomsInput.focus();
      return;
    }

    btnAnalyze.disabled = true;
    btnAnalyze.innerHTML = `<span>⏳ Analyzing...</span>`;

    try {
      const response = await fetch("/api/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symptoms }),
      });

      if (!response.ok) throw new Error("Failed to get recommendation");

      const data = await response.json();

      // Update UI with recommendation
      if (resultDeptName) resultDeptName.textContent = `${data.icon} ${data.department}`;
      if (resultReason) resultReason.textContent = data.reason;
      if (resultBox) resultBox.classList.add("show");

      // Save to hidden input so it gets submitted with token
      if (hiddenSymptoms) hiddenSymptoms.value = symptoms;

      // Handle Apply Recommendation Click
      if (btnApply) {
        btnApply.onclick = () => {
          const targetRadio = document.querySelector(`input[name="department"][value="${data.department}"]`);
          if (targetRadio) {
            targetRadio.checked = true;
            // Scroll smoothly to registration form
            targetRadio.closest(".dept-radio-label").scrollIntoView({ behavior: "smooth", block: "center" });
            // Add a brief pulse highlight
            const card = targetRadio.closest(".dept-radio-label").querySelector(".dept-card-opt");
            if (card) {
              card.style.transition = "all 0.3s ease";
              card.style.borderColor = "#0d9488";
              card.style.transform = "scale(1.03)";
              setTimeout(() => {
                card.style.transform = "scale(1)";
              }, 400);
            }
          }
        };
      }
    } catch (err) {
      console.error(err);
      alert("Could not complete AI analysis. Please choose a department manually.");
    } finally {
      btnAnalyze.disabled = false;
      btnAnalyze.innerHTML = `<span>✨ Recommend Department</span>`;
    }
  };

  btnAnalyze.addEventListener("click", runAnalysis);

  // Trigger on Enter key
  symptomsInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      runAnalysis();
    }
  });
}

/* -------------------------------------------------------------
 * 2. Form Validation (10-digit phone number)
 * ------------------------------------------------------------- */
function initFormValidation() {
  const form = document.getElementById("token-form");
  const phoneInput = document.getElementById("phone");
  const nameInput = document.getElementById("patient_name");

  if (!form || !phoneInput) return;

  // Allow only digits while typing
  phoneInput.addEventListener("input", (e) => {
    e.target.value = e.target.value.replace(/\D/g, "").slice(0, 10);
  });

  form.addEventListener("submit", (e) => {
    const phone = phoneInput.value.trim();
    const name = nameInput ? nameInput.value.trim() : "";

    if (!name) {
      alert("Please enter patient name.");
      e.preventDefault();
      return;
    }

    if (!/^\d{10}$/.test(phone)) {
      alert("Please enter a valid 10-digit mobile number.");
      phoneInput.focus();
      e.preventDefault();
      return;
    }

    const deptSelected = document.querySelector('input[name="department"]:checked');
    if (!deptSelected) {
      alert("Please select a hospital department.");
      e.preventDefault();
      return;
    }
  });
}

/* -------------------------------------------------------------
 * 3. Live Token Tracker (Polls every 3.5 seconds on token.html)
 * ------------------------------------------------------------- */
function initLiveTokenTracker() {
  // If window.TRACK_TOKEN_NUMBER is set by token.html
  const tokenNumber = window.TRACK_TOKEN_NUMBER;
  if (!tokenNumber) return;

  let currentStatus = window.CURRENT_STATUS || "Waiting";

  const fetchTokenUpdate = async () => {
    try {
      const res = await fetch(`/api/token/${tokenNumber}`);
      if (!res.ok) return;

      const data = await res.json();

      // 1. Update Currently Serving
      const servingEl = document.getElementById("live-currently-serving");
      if (servingEl) servingEl.textContent = data.currently_serving || "--";

      // 2. Update People Ahead
      const aheadEl = document.getElementById("live-people-ahead");
      if (aheadEl) {
        aheadEl.textContent = data.status === "Waiting" ? data.people_ahead : "0";
      }

      // 3. Update Status Badge & Timeline
      const statusBadge = document.getElementById("live-status-badge");
      if (statusBadge && data.status !== currentStatus) {
        currentStatus = data.status;
        statusBadge.className = `token-status-banner status-${data.status.toLowerCase()}`;

        if (data.status === "Serving") {
          statusBadge.innerHTML = `🔔 You are Being Served Now! Please proceed to the Doctor Room.`;
          playNotificationChime();
        } else if (data.status === "Completed") {
          statusBadge.innerHTML = `✅ Consultation Completed. Thank you!`;
        } else {
          statusBadge.innerHTML = `⏳ In Queue (Waiting)`;
        }

        updateTimeline(data.status);
      }
    } catch (err) {
      console.warn("Live queue update poll error:", err);
    }
  };

  // Poll every 3.5 seconds
  setInterval(fetchTokenUpdate, 3500);
}

function updateTimeline(status) {
  const stepRegistered = document.getElementById("step-registered");
  const stepWaiting = document.getElementById("step-waiting");
  const stepServing = document.getElementById("step-serving");
  const stepCompleted = document.getElementById("step-completed");

  if (!stepRegistered) return;

  // Reset classes
  [stepRegistered, stepWaiting, stepServing, stepCompleted].forEach((el) => {
    if (el) el.className = "progress-step";
  });

  stepRegistered.classList.add("done");

  if (status === "Waiting") {
    stepWaiting.classList.add("active");
  } else if (status === "Serving") {
    stepWaiting.classList.add("done");
    stepServing.classList.add("active");
  } else if (status === "Completed") {
    stepWaiting.classList.add("done");
    stepServing.classList.add("done");
    stepCompleted.classList.add("done");
  }
}

/* Pleasant chime using Web Audio API (Zero audio assets required!) */
function playNotificationChime() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
    osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.3); // A5

    gain.gain.setValueAtTime(0.25, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.6);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.6);
  } catch (e) {
    // Ignore audio autoplay restrictions gracefully
  }
}
