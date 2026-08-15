const form = document.getElementById("calc-form");
const errorBox = document.getElementById("form-error");

const monthlyContributionInput = document.getElementById("monthly_contribution");
const startingBalanceInput = document.getElementById("starting_balance");

const tabYears = document.getElementById("tab-years");
const tabAge = document.getElementById("tab-age");
const yearsFields = document.getElementById("years-fields");
const ageFields = document.getElementById("age-fields");

const yearsSlider = document.getElementById("years_slider");
const yearsDisplay = document.getElementById("years_display");

const currentAgeYearsInput = document.getElementById("current_age_years");
const currentAgeMonthsInput = document.getElementById("current_age_months");
const endAgeYearsInput = document.getElementById("end_age_years");

const horizonSummary = document.getElementById("horizon_summary");

const nominalSlider = document.getElementById("nominal_return_pct");
const nominalDisplay = document.getElementById("nominal_return_display");
const inflationSlider = document.getElementById("inflation_pct");
const inflationDisplay = document.getElementById("inflation_display");
const withdrawalSlider = document.getElementById("withdrawal_rate_pct");
const withdrawalDisplay = document.getElementById("withdrawal_display");

let horizonMode = "years";
let chart = null;
let debounceTimer = null;

function fmt(n) {
  return Math.round(n).toLocaleString("en-US");
}

function refreshSliderDisplays() {
  nominalDisplay.textContent = parseFloat(nominalSlider.value).toFixed(1);
  inflationDisplay.textContent = parseFloat(inflationSlider.value).toFixed(1);
  withdrawalDisplay.textContent = parseFloat(withdrawalSlider.value).toFixed(1);
}

function currentDurationMonths() {
  if (horizonMode === "age") {
    const currentTotal = (parseFloat(currentAgeYearsInput.value) || 0) * 12
      + (parseFloat(currentAgeMonthsInput.value) || 0);
    const endTotal = Math.round((parseFloat(endAgeYearsInput.value) || 0) * 12);
    return endTotal - currentTotal;
  }
  return Math.round((parseFloat(yearsSlider.value) || 0) * 12);
}

function refreshHorizonSummary() {
  const months = currentDurationMonths();
  if (months < 1) {
    horizonSummary.textContent = "not a valid horizon — check the ages above";
    horizonSummary.style.color = "var(--brick)";
    return;
  }
  horizonSummary.style.color = "";
  const y = Math.floor(months / 12);
  const m = months % 12;
  horizonSummary.textContent = `${y}y ${m}m (${months} months)`;
}

function setHorizonMode(mode) {
  horizonMode = mode;
  tabYears.classList.toggle("active", mode === "years");
  tabAge.classList.toggle("active", mode === "age");
  yearsFields.hidden = mode !== "years";
  ageFields.hidden = mode !== "age";
  refreshHorizonSummary();
  scheduleCalculate();
}

tabYears.addEventListener("click", () => setHorizonMode("years"));
tabAge.addEventListener("click", () => setHorizonMode("age"));

yearsSlider.addEventListener("input", () => {
  yearsDisplay.textContent = yearsSlider.value;
  refreshHorizonSummary();
  scheduleCalculate();
});

[currentAgeYearsInput, currentAgeMonthsInput, endAgeYearsInput].forEach((el) => {
  el.addEventListener("input", () => {
    refreshHorizonSummary();
    scheduleCalculate();
  });
});

[nominalSlider, inflationSlider, withdrawalSlider].forEach((el) => {
  el.addEventListener("input", () => {
    refreshSliderDisplays();
    scheduleCalculate();
  });
});

[monthlyContributionInput, startingBalanceInput].forEach((el) => {
  el.addEventListener("input", scheduleCalculate);
});

function scheduleCalculate() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(calculate, 200);
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  calculate();
});

async function calculate() {
  errorBox.hidden = true;

  if (currentDurationMonths() < 1) {
    // Don't even call the server for an obviously invalid horizon (e.g.
    // end age below the child's current age) — the inline summary above
    // already flags it in red.
    return;
  }

  const payload = {
    monthly_contribution: monthlyContributionInput.value,
    starting_balance: startingBalanceInput.value,
    horizon_mode: horizonMode,
    years: yearsSlider.value,
    current_age_years: currentAgeYearsInput.value,
    current_age_months: currentAgeMonthsInput.value,
    end_age_years: endAgeYearsInput.value,
    nominal_return_pct: nominalSlider.value,
    inflation_pct: inflationSlider.value,
    withdrawal_rate_pct: withdrawalSlider.value,
  };

  let response;
  try {
    response = await fetch("calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    showError("Couldn't reach the server. Is app.py still running?");
    return;
  }

  const data = await response.json();

  if (!response.ok) {
    showError(data.error || "Something went wrong with those numbers.");
    return;
  }

  renderResults(data);
  renderChart(data);
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function renderResults(data) {
  const f = data.flat;
  const r = data.rising;

  document.getElementById("flat_final_balance").textContent = fmt(f.final_balance);
  document.getElementById("rising_final_balance").textContent = fmt(r.final_balance);

  document.getElementById("flat_final_balance_today").textContent = fmt(f.final_balance_today);
  document.getElementById("rising_final_balance_today").textContent = fmt(r.final_balance_today);

  document.getElementById("flat_total_contributed").textContent = fmt(f.total_contributed);
  document.getElementById("rising_total_contributed").textContent = fmt(r.total_contributed);

  document.getElementById("flat_total_growth").textContent = fmt(f.total_growth);
  document.getElementById("rising_total_growth").textContent = fmt(r.total_growth);

  document.getElementById("flat_final_contribution").textContent = fmt(f.final_contribution) + "/mo";
  document.getElementById("rising_final_contribution").textContent = fmt(r.final_contribution) + "/mo";

  document.getElementById("flat_monthly_income").textContent = fmt(f.monthly_income) + "/mo";
  document.getElementById("rising_monthly_income").textContent = fmt(r.monthly_income) + "/mo";

  document.getElementById("flat_monthly_income_today").textContent = fmt(f.monthly_income_today) + "/mo";
  document.getElementById("rising_monthly_income_today").textContent = fmt(r.monthly_income_today) + "/mo";
}

function renderChart(data) {
  if (typeof Chart === "undefined") {
    document.getElementById("chart-fallback").hidden = false;
    return;
  }

  const labels = data.flat.projection.map((p) => (p.month / 12).toFixed(1));
  const flatValues = data.flat.projection.map((p) => Math.round(p.value));
  const risingValues = data.rising.projection.map((p) => Math.round(p.value));

  const ctx = document.getElementById("projection_chart");

  if (chart) {
    chart.data.labels = labels;
    chart.data.datasets[0].data = flatValues;
    chart.data.datasets[1].data = risingValues;
    chart.update();
    return;
  }

  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Flat contribution",
          data: flatValues,
          borderColor: "#6E7A73",
          backgroundColor: "rgba(110, 122, 115, 0.08)",
          fill: true,
          tension: 0.15,
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          label: "Rising with inflation",
          data: risingValues,
          borderColor: "#2F6F52",
          backgroundColor: "rgba(47, 111, 82, 0.10)",
          fill: true,
          tension: 0.15,
          pointRadius: 0,
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { title: { display: true, text: "Years" } },
        y: {
          title: { display: true, text: "Balance (nominal)" },
          ticks: {
            callback: (value) => Number(value).toLocaleString("en-US"),
          },
        },
      },
      plugins: {
        legend: { position: "bottom" },
        tooltip: {
          callbacks: {
            label: (item) => `${item.dataset.label}: ${Number(item.parsed.y).toLocaleString("en-US")}`,
          },
        },
      },
    },
  });
}

// Initial paint on page load.
refreshSliderDisplays();
refreshHorizonSummary();
calculate();
