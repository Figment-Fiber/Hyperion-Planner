"use strict";

const $ = id => document.getElementById(id);
const metrics = ["power_dbm", "osnr_ase_db", "snr_nli_db", "gsnr_db"];
const input = $("length");
const choice = $("span-choice");
const start = [[21.335, -158.058], [21.307, -157.858]];
const map = L.map("map", {maxZoom: 18}).setView([21.47, -157.98], 10);
const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);
const route = L.polyline([], {color: "#147cc0", weight: 4}).addTo(map);
const markers = {};
let ids = ["a", "b"];
let overrides = [null];
let estimates = [];
let bundled = false;
let selected = 0;
let placing = false;
let lastRun = null;
let running = false;
let distanceRequest = 0;

function updateStatus(message) {
  $("status").textContent = message;
}

tiles.once("tileerror", () => {
  $("map-title").textContent = "Route map · some tiles unavailable";
});

function currentDesign() {
  return {
    coordinates: ids.map(id => {
      const point = markers[id].getLatLng();
      return [point.lat, point.lng];
    }),
    site_names: ids.map(id => $("name-" + id).value.trim() || $("name-" + id).defaultValue),
    span_overrides: [...overrides],
    bundled,
  };
}

function unapplied() {
  return input.validity.badInput || input.value !== String(overrides[selected] ?? "");
}

function refreshStatus() {
  $("stale-results").hidden = !lastRun || (!unapplied() &&
    JSON.stringify(lastRun) === JSON.stringify(currentDesign()));
  if (running) return;
  if (placing) {
    updateStatus("Click the map to place the intermediate ROADM.");
  } else if (unapplied()) {
    updateStatus("Apply the edited length, then rerun.");
  } else if (lastRun && JSON.stringify(lastRun) !== JSON.stringify(currentDesign())) {
    updateStatus("Inputs changed. Rerun to update results and Excel.");
  } else {
    updateStatus(lastRun ? "Simulation complete." : "Drag a site to move it. Scroll or use + and − to zoom.");
  }
}

function renderLength() {
  const estimate = estimates[selected];
  $("estimate").textContent = estimate === undefined ? "—" : estimate.toFixed(3) + " km";
  $("source").textContent = bundled ? "80 km · Bundled topology" :
    overrides[selected] !== null ? overrides[selected] + " km · Engineered override" :
    estimate === undefined ? "Calculating geographic distance…" : estimate.toFixed(3) + " km · WGS84 geodesic";
}

function selectSpan(index) {
  selected = index;
  choice.value = String(index);
  input.value = String(overrides[index] ?? "");
  $("length-error").textContent = "";
  renderLength();
  refreshStatus();
}

function updateSpanOptions() {
  choice.replaceChildren(...ids.slice(1).map((id, index) =>
    new Option(ids[index].toUpperCase() + " → " + id.toUpperCase(), index)));
  $("clear-length").hidden = ids.length > 2;
  $("route-order").textContent = ids.map(id => id.toUpperCase()).join(" → ");
  selectSpan(0);
}

async function updateRoute() {
  const design = currentDesign();
  route.setLatLngs(design.coordinates);
  estimates = [];
  renderLength();
  refreshStatus();
  const request = ++distanceRequest;
  try {
    const response = await fetch("/api/distances", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({coordinates: design.coordinates}),
    });
    if (!response.ok) throw new Error("Distance request failed.");
    const distances = await response.json();
    if (request === distanceRequest) {
      estimates = distances;
      renderLength();
    }
  } catch (error) {
    if (request === distanceRequest) $("estimate").textContent = "Unavailable";
  }
}

function addMarker(id, point) {
  const label = id.toUpperCase();
  const icon = L.divIcon({className: "site-marker " + (id === "c" ? "roadm" : ""),
    html: label, iconSize: [30, 30]});
  const marker = L.marker(point, {icon, draggable: true, title: "Site " + label}).addTo(map);
  marker.getElement().id = "point-" + id;
  marker.on("drag", () => route.setLatLngs(currentDesign().coordinates));
  marker.on("dragend", updateRoute);
  markers[id] = marker;
}

function removeRoadm() {
  if (markers.c) map.removeLayer(markers.c);
  delete markers.c;
  ids = ["a", "b"];
  overrides = [null];
  bundled = false;
  placing = false;
  $("roadm-fields").hidden = true;
  $("remove-roadm").hidden = true;
  $("add-roadm").hidden = false;
  updateSpanOptions();
  updateRoute();
}

addMarker("a", start[0]);
addMarker("b", start[1]);
$("add-roadm").addEventListener("click", () => {
  placing = !placing;
  refreshStatus();
});
map.on("click", event => {
  if (!placing) return;
  placing = false;
  addMarker("c", event.latlng);
  ids = ["a", "c", "b"];
  overrides = [null, null];
  bundled = false;
  $("roadm-fields").hidden = false;
  $("remove-roadm").hidden = false;
  $("add-roadm").hidden = true;
  updateSpanOptions();
  updateRoute();
});
$("remove-roadm").addEventListener("click", removeRoadm);
choice.addEventListener("change", () => selectSpan(Number(choice.value)));
input.addEventListener("input", refreshStatus);
for (const id of ["a", "b", "c"]) $("name-" + id).addEventListener("input", refreshStatus);
$("span-form").addEventListener("submit", event => {
  event.preventDefault();
  const value = input.valueAsNumber;
  if (!Number.isFinite(value) || value <= 0) {
    $("length-error").textContent = "Enter a finite, positive length.";
    return;
  }
  bundled = false;
  overrides[selected] = value;
  selectSpan(selected);
});
$("use-map").addEventListener("click", () => {
  bundled = false;
  overrides[selected] = null;
  selectSpan(selected);
});
$("clear-length").addEventListener("click", () => {
  bundled = true;
  overrides = [null];
  selectSpan(0);
});
$("sample").addEventListener("click", () => {
  markers.a.setLatLng(start[0]);
  markers.b.setLatLng(start[1]);
  for (const id of ["a", "b", "c"]) $("name-" + id).value = $("name-" + id).defaultValue;
  map.setView([21.47, -157.98], 10);
  removeRoadm();
});

function applyRoute(design) {
  removeRoadm();
  if (design.coordinates.length === 3) {
    addMarker("c", design.coordinates[1]);
    ids = ["a", "c", "b"];
    $("roadm-fields").hidden = false;
    $("remove-roadm").hidden = false;
    $("add-roadm").hidden = true;
  }
  ids.forEach((id, index) => {
    markers[id].setLatLng(design.coordinates[index]);
    $("name-" + id).value = design.site_names[index];
  });
  overrides = [...design.span_overrides];
  bundled = design.bundled;
  updateSpanOptions();
  map.fitBounds(L.latLngBounds(design.coordinates), {padding: [35, 35], maxZoom: 12});
  updateRoute();
}

function validRoute(design) {
  if (!design || design.version !== 1 || !Array.isArray(design.coordinates)) return false;
  const count = design.coordinates.length;
  return [2, 3].includes(count) &&
    design.coordinates.every(point => Array.isArray(point) && point.length === 2 &&
      point.every(Number.isFinite) && Math.abs(point[0]) <= 85 && Math.abs(point[1]) <= 180) &&
    Array.isArray(design.site_names) && design.site_names.length === count &&
    design.site_names.every(name => typeof name === "string" && name.trim() && name.length <= 60) &&
    Array.isArray(design.span_overrides) && design.span_overrides.length === count - 1 &&
    design.span_overrides.every(value => value === null || (Number.isFinite(value) && value > 0)) &&
    typeof design.bundled === "boolean" &&
    (!design.bundled || (count === 2 && design.span_overrides[0] === null));
}

$("new-route").addEventListener("click", () => {
  applyRoute({coordinates: start, site_names: ["Site A", "Site B"], span_overrides: [null], bundled: false});
});
$("save-route").addEventListener("click", () => {
  if (unapplied()) {
    updateStatus("Apply the edited length before saving the route.");
    input.focus();
    return;
  }
  const url = URL.createObjectURL(new Blob(
    [JSON.stringify({version: 1, ...currentDesign()}, null, 2)], {type: "application/json"}));
  const link = document.createElement("a");
  link.href = url;
  link.download = "hyperion-route.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  updateStatus("Route file downloaded.");
});
$("load-route").addEventListener("click", () => $("route-file").click());
$("route-file").addEventListener("change", async event => {
  const file = event.target.files[0];
  event.target.value = "";
  if (!file) return;
  try {
    if (file.size > 65536) throw new Error("Route file is too large.");
    const design = JSON.parse(await file.text());
    if (!validRoute(design)) throw new Error("Choose a valid Hyperion route JSON file.");
    applyRoute(design);
  } catch (error) {
    updateStatus("Could not load route. " + error.message);
  }
});

updateSpanOptions();

function showResult(result) {
  $("result-summary").textContent = result.site_names.join(" → ") + " · " + result.channels.length + " channels · " +
    result.span_length_km + " km · " + result.length_source + " · GNPy " +
    result.engine_version + " · Map estimate at run: " + result.map_estimate_km.toFixed(1) + " km";
  $("result-summary").textContent += " · " + result.spans.map(span => span.from + " → " + span.to + " " + span.simulation_km.toFixed(2) + " km (" + span.source + ")").join(" / ");
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
  if (unapplied()) {
    refreshStatus();
    input.focus();
    return;
  }
  const snapshot = currentDesign();
  running = true;
  $("run").disabled = true;
  updateStatus("Running GNPy…");
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(snapshot),
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

updateRoute();
