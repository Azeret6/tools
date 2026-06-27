// Color Palette Generator - frontend logic.
// All actual palette math happens server-side (color_palette_generator.py);
// this file only converts the native color picker's hex to a hue (for the
// API request) and renders the JSON response as swatch cards.

function hexToHue(hex) {
  hex = hex.replace("#", "");
  const r = parseInt(hex.substring(0, 2), 16) / 255;
  const g = parseInt(hex.substring(2, 4), 16) / 255;
  const b = parseInt(hex.substring(4, 6), 16) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;

  if (delta === 0) return 0;

  let hue;
  if (max === r) hue = ((g - b) / delta) % 6;
  else if (max === g) hue = (b - r) / delta + 2;
  else hue = (r - g) / delta + 4;

  hue *= 60;
  if (hue < 0) hue += 360;
  return hue;
}

function hslToHex(h, s, l) {
  s /= 100;
  l /= 100;
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  let r = 0, g = 0, b = 0;

  if (h < 60) { r = c; g = x; b = 0; }
  else if (h < 120) { r = x; g = c; b = 0; }
  else if (h < 180) { r = 0; g = c; b = x; }
  else if (h < 240) { r = 0; g = x; b = c; }
  else if (h < 300) { r = x; g = 0; b = c; }
  else { r = c; g = 0; b = x; }

  const toHex = (v) => Math.round((v + m) * 255).toString(16).padStart(2, "0");
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

const baseColorInput = document.getElementById("base-color");
const hexReadout = document.getElementById("hex-readout");
const countInput = document.getElementById("count");
const countReadout = document.getElementById("count-readout");
const formError = document.getElementById("form-error");
const resultsContent = document.getElementById("results-content");

function getCheckedValue(name) {
  const checked = document.querySelector(`input[name="${name}"]:checked`);
  return checked ? checked.value : null;
}

function renderSwatches(data) {
  const grid = document.createElement("div");
  grid.className = "swatch-grid";

  data.swatches.forEach((swatch) => {
    const card = document.createElement("div");
    card.className = "swatch-card";

    const color = document.createElement("div");
    color.className = "swatch-color";
    color.style.background = swatch.hex;

    const hex = document.createElement("p");
    hex.className = "swatch-hex";
    hex.textContent = swatch.hex;

    const contrast = document.createElement("div");
    contrast.className = "contrast-row";

    const white = document.createElement("span");
    white.className = swatch.aa_on_white ? "contrast-pass" : "contrast-fail";
    white.textContent = `white ${swatch.contrast_on_white.toFixed(1)}:1`;

    const black = document.createElement("span");
    black.className = swatch.aa_on_black ? "contrast-pass" : "contrast-fail";
    black.textContent = `black ${swatch.contrast_on_black.toFixed(1)}:1`;

    contrast.appendChild(white);
    contrast.appendChild(black);

    card.appendChild(color);
    card.appendChild(hex);
    card.appendChild(contrast);
    grid.appendChild(card);
  });

  resultsContent.innerHTML = "";
  resultsContent.appendChild(grid);
}

async function generate() {
  const baseHue = hexToHue(baseColorInput.value);
  const harmony = getCheckedValue("harmony");
  const style = getCheckedValue("style");
  const count = parseInt(countInput.value, 10);

  formError.hidden = true;

  try {
    const response = await fetch("generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ base_hue: baseHue, harmony, style, count }),
    });
    const data = await response.json();

    if (!response.ok) {
      formError.textContent = data.error || "Something went wrong.";
      formError.hidden = false;
      return;
    }

    renderSwatches(data);
  } catch (err) {
    formError.textContent = "Could not reach the server. Is it running?";
    formError.hidden = false;
  }
}

function setRandomBaseColor() {
  const hue = Math.random() * 360;
  const hex = hslToHex(hue, 70, 50);
  baseColorInput.value = hex;
  hexReadout.textContent = hex;
}

baseColorInput.addEventListener("input", () => {
  hexReadout.textContent = baseColorInput.value;
});
baseColorInput.addEventListener("change", generate);

document.getElementById("random-btn").addEventListener("click", () => {
  setRandomBaseColor();
  generate();
});

document.getElementById("shuffle-btn").addEventListener("click", () => {
  setRandomBaseColor();
  generate();
});

document.getElementById("generate-btn").addEventListener("click", generate);

document.querySelectorAll('input[name="harmony"]').forEach((el) =>
  el.addEventListener("change", generate)
);
document.querySelectorAll('input[name="style"]').forEach((el) =>
  el.addEventListener("change", generate)
);

countInput.addEventListener("input", () => {
  countReadout.textContent = countInput.value;
});
countInput.addEventListener("change", generate);

// Initial palette on page load, using the default control values.
generate();
