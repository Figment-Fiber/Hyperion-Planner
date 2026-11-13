"use strict";

const $ = id => document.getElementById(id);
const pins = [$("point-a"), $("point-b")];
const nameInputs = [$("name-a"), $("name-b")];
const siteNames = () => nameInputs.map((field, index) => field.value.trim() || ["Site_A", "Site_B"][index]);
const metrics = ["power_dbm", "osnr_ase_db", "snr_nli_db", "gsnr_db"];
const initialPoints = () => [[0.23, 0.66], [0.74, 0.28]];
const input = $("length");
const map = $("map");
let points = initialPoints();
let override = null;
let useMap = false;
let lastRun = null;
let running = false;
let drag = null;

function updateStatus(message) {
  $("status").textContent = message;
}

function updateInputs() {
  const [a, b] = points;
  pins.forEach((pin, index) => {
    pin.style.left = (points[index][0] * 100) + "%";
    pin.style.top = (points[index][1] * 100) + "%";
  });
  for (const [attribute, value] of Object.entries({x1: a[0], y1: a[1], x2: b[0], y2: b[1]})) {
    $("span-line").setAttribute(attribute, value * 100);
  }
  const estimate = Math.hypot((b[0] - a[0]) * 120, (b[1] - a[1]) * 70).toFixed(1);
  $("estimate").textContent = estimate + " km";
  $("source").textContent = useMap ? estimate + " km · Schematic map estimate" :
    override === null ? "80 km · Bundled topology" : override + " km · Engineered override";
}

function refreshStatus() {
  if (running) return;
  if (input.validity.badInput || input.value !== (override === null ? "" : String(override))) {
    updateStatus("Apply the edited length, then rerun for updated results.");
  } else if (lastRun && (
    lastRun.override !== override || lastRun.useMap !== useMap ||
    JSON.stringify(lastRun.names) !== JSON.stringify(siteNames()) ||
    JSON.stringify(lastRun.points) !== JSON.stringify(points)
  )) {
    updateStatus("Inputs changed. Rerun for updated results. Excel still exports the last completed run.");
  } else {
    updateStatus(lastRun ? "Simulation complete." : "Ready to run the simulation.");
  }
}

function setOverride(value, fromMap = false) {
  useMap = fromMap;
  override = value;
  input.value = value === null ? "" : String(value);
  $("length-error").textContent = "";
  updateInputs();
  refreshStatus();
}

$("span-form").addEventListener("submit", event => {
  event.preventDefault();
  const value = input.valueAsNumber;
  if (!Number.isFinite(value) || value <= 0) {
    $("length-error").textContent = "Enter a finite, positive length.";
    input.focus();
    return;
  }
  setOverride(value);
});
input.addEventListener("input", refreshStatus);
nameInputs.forEach(field => field.addEventListener("input", refreshStatus));
$("use-map").addEventListener("click", () => setOverride(null, true));
$("clear-length").addEventListener("click", () => setOverride(null));
$("sample").addEventListener("click", () => {
  points = initialPoints();
  nameInputs.forEach(field => { field.value = field.defaultValue; });
  setOverride(null);
});

function movePoint(index, x, y) {
  const clamp = value => Math.max(0.04, Math.min(0.96, value));
  points[index] = [clamp(x), clamp(y)];
  updateInputs();
  refreshStatus();
}

pins.forEach((pin, index) => {
  pin.addEventListener("pointerdown", event => {
    if (event.button !== 0 || drag) return;
    pin.setPointerCapture(event.pointerId);
    drag = {id: event.pointerId, index};
  });
  pin.addEventListener("pointermove", event => {
    if (drag?.id !== event.pointerId || drag.index !== index) return;
    const box = map.getBoundingClientRect();
    movePoint(index, (event.clientX - box.left) / box.width, (event.clientY - box.top) / box.height);
  });
  pin.addEventListener("lostpointercapture", event => {
    if (drag?.id === event.pointerId) drag = null;
  });
  pin.addEventListener("keydown", event => {
    const offsets = {ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0]};
    const offset = offsets[event.key];
    if (!offset) return;
    event.preventDefault();
    movePoint(index, points[index][0] + offset[0] * 0.02, points[index][1] + offset[1] * 0.02);
  });
});

function showResult(result) {
  $("result-summary").textContent = result.site_names.join(" → ") + " · " + result.channels.length + " channels · " +
    result.span_length_km + " km · " + result.length_source + " · GNPy " +
    result.engine_version + " · Map estimate at run: " + result.map_estimate_km.toFixed(1) + " km";
  $("channels").replaceChildren(...result.channels.map(channel => {
    const row = document.createElement("tr");
    const values = [channel.channel, channel.frequency_thz.toFixed(5), ...metrics.map(key => channel[key].toFixed(2))];
    for (const value of values) row.insertCell().textContent = value;
    return row;
  }));
  $("comparison").hidden = !result.baseline;
  if (result.baseline) {
    const deltas = result.channels.map((row, index) => row.gsnr_db - result.baseline.channels[index].gsnr_db);
    $("comparison").textContent = "GSNR change versus bundled 80 km (signal bandwidth) · " +
      Math.min(...deltas).toFixed(2) + " to " + Math.max(...deltas).toFixed(2) + " dB";
  }
  $("report").textContent = result.report;
  $("channel-table").hidden = false;
  $("transmission").hidden = false;
  $("download").href = result.workbook_url;
  $("download").hidden = false;
}

$("run").addEventListener("click", async () => {
  if (input.validity.badInput || input.value !== (override === null ? "" : String(override))) {
    refreshStatus();
    input.focus();
    return;
  }
  const snapshot = {override, useMap, names: siteNames(), points: points.map(point => [...point])};
  running = true;
  $("run").disabled = true;
  updateStatus("Running GNPy…");
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        length_override_km: snapshot.override, use_map_estimate: snapshot.useMap,
        site_names: snapshot.names, points: snapshot.points,
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    showResult(result);
    lastRun = snapshot;
    running = false;
    refreshStatus();
  } catch (error) {
    updateStatus("Simulation failed. " + error.message);
  } finally {
    running = false;
    $("run").disabled = false;
  }
});

updateInputs();
