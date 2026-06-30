const form = document.getElementById("calc-form");
const errorBox = document.getElementById("form-error");

const yearsSlider = document.getElementById("years_slider");
const yearsDisplay = document.getElementById("years_display");
const monthsInput = document.getElementById("months_input");

const withdrawalSlider = document.getElementById("withdrawal_rate");
const withdrawalDisplay = document.getElementById("withdrawal_rate_display");
const nominalSlider = document.getElementById("nominal_return");
const nominalDisplay = document.getElementById("nominal_return_display");
const inflationSlider = document.getElementById("inflation");
const inflationDisplay = document.getElementById("inflation_display");

let chart = null;
let debounceTimer = null;
let currentTarget = 0;

function fmt(n) {
  return Math.round(n).toLocaleString("en-US");
}

function pct(n) {
  return (n * 100).toFixed(1);
}

function refreshSliderDisplays() {
  withdrawalDisplay.textContent = pct(parseFloat(withdrawalSlider.value));
  nominalDisplay.textContent = pct(parseFloat(nominalSlider.value));
  inflationDisplay.textContent = pct(parseFloat(inflationSlider.value));
}

// Keep the years slider and the months input in sync with each other.
yearsSlider.addEventListener("input", () => {
  yearsDisplay.textContent = yearsSlider.value;
  monthsInput.value = Math.round(parseFloat(yearsSlider.value) * 12);
  scheduleCalculate();
});

monthsInput.addEventListener("input", () => {
  const months = parseFloat(monthsInput.value) || 1;
  const years = months / 12;
  yearsSlider.value = Math.min(Math.max(years, 1), 40);
  yearsDisplay.textContent = (Math.round(years * 10) / 10).toString();
  scheduleCalculate();
});

[withdrawalSlider, nominalSlider, inflationSlider].forEach((el) => {
  el.addEventListener("input", () => {
    refreshSliderDisplays();
    scheduleCalculate();
  });
});

document.getElementById("desired_monthly_income").addEventListener("input", scheduleCalculate);
document.getElementById("current_savings").addEventListener("input", scheduleCalculate);

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

  const payload = {
    desired_monthly_income: document.getElementById("desired_monthly_income").value,
    years: parseFloat(monthsInput.value) / 12,
    withdrawal_rate: withdrawalSlider.value,
    nominal_return: nominalSlider.value,
    inflation: inflationSlider.value,
    current_savings: document.getElementById("current_savings").value,
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
  document.getElementById("required_monthly_savings").textContent = fmt(data.required_monthly_savings);
  document.getElementById("annual_income_needed").textContent = fmt(data.annual_income_needed);
  document.getElementById("target_amount").textContent = fmt(data.target_amount);
  document.getElementById("real_annual_return").textContent = pct(data.real_annual_return) + "%";
  document.getElementById("total_contributed").textContent = fmt(data.total_contributed);
  document.getElementById("total_growth").textContent = fmt(data.total_growth);
}

function renderChart(data) {
  if (typeof Chart === "undefined") {
    document.getElementById("chart-fallback").hidden = false;
    return;
  }

  const labels = data.projection.map((p) => (p.month / 12).toFixed(1));
  const values = data.projection.map((p) => Math.round(p.value));
  currentTarget = data.target_amount;

  const ctx = document.getElementById("projection_chart");

  if (chart) {
    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.data.datasets[1].data = labels.map(() => currentTarget);
    chart.update();
    return;
  }

  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Projected net worth",
          data: values,
          borderColor: "#2F6F52",
          backgroundColor: "rgba(47, 111, 82, 0.08)",
          fill: true,
          tension: 0.15,
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          label: "Target",
          data: labels.map(() => currentTarget),
          borderColor: "#B3402F",
          borderDash: [6, 5],
          pointRadius: 0,
          borderWidth: 1.5,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { title: { display: true, text: "Years" } },
        y: {
          title: { display: true, text: "Net worth (today's money)" },
          ticks: {
            callback: (value) => Number(value).toLocaleString("en-US"),
          },
        },
      },
      plugins: {
        legend: { position: "bottom" },
        tooltip: {
          callbacks: {
            label: (item) => {
              const saved = item.parsed.y;
              if (item.dataset.label !== "Projected net worth") {
                return `${item.dataset.label}: ${Number(saved).toLocaleString("en-US")}`;
              }
              const remaining = Math.max(currentTarget - saved, 0);
              return [
                `Projected saved: ${Number(saved).toLocaleString("en-US")}`,
                `Remaining to target: ${Number(remaining).toLocaleString("en-US")}`,
              ];
            },
          },
        },
      },
    },
  });
}

// Initial paint on page load.
refreshSliderDisplays();
calculate();
