// Run with Playwright installed and Hyperion listening on port 8765.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");

function cliRows(name) {
  const output = fs.readFileSync(path.join(__dirname, "evidence", "gnpy-3.0.1", name + ".stdout.txt"), "utf8");
  return output.split(/\r?\n/).map(line => line.trim().split(/\s+/))
    .filter(fields => fields.length === 6 && /^\d+$/.test(fields[0]) && /^\d+\.\d{5}$/.test(fields[1]));
}

async function main() {
  const browser = await chromium.launch({executablePath: process.env.HYPERION_BROWSER || undefined});
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 850}});
    await page.goto(process.env.HYPERION_URL || "http://127.0.0.1:8765/");
    assert(await page.locator(".brand img").evaluate(img => img.complete && img.naturalWidth > 0));
    await page.locator("#route-settings > summary").click();
    assert(!(await page.locator("#span-choice").isVisible()));
    await page.locator("#point-a").click();
    await page.getByRole("button", {name: "Open site settings"}).click();
    assert(await page.locator("#name-a").isVisible());
    await page.getByText("Equipment catalog", {exact: true}).click();
    await page.locator("#catalog-profile").selectOption("nokia-1830-pss-hc-4cp4t8");
    assert.match(await page.locator("#catalog-description").innerText(), /generic GNPy equipment/);
    const run = async () => {
      const pending = page.waitForResponse(response => response.url().endsWith("/api/run"), {timeout: 100000});
      await page.getByRole("button", {name: "Run simulation"}).click();
      const response = await pending;
      assert.equal(response.status(), 200);
      await page.waitForFunction(() => !document.getElementById("run").disabled);
      return response.json();
    };
    const rows = () => page.locator("#channels tr").evaluateAll(elements =>
      elements.map(row => Array.from(row.cells, cell => cell.textContent)));
    await page.getByRole("button", {name: "Use bundled"}).click();
    const bundled = await run();
    assert.equal(bundled.span_length_km, 80);
    assert.deepEqual(await rows(), cliRows("bundled"));
    await page.locator("#length").fill("85.25");
    await page.getByRole("button", {name: "Apply length"}).click();
    const engineered = await run();
    assert.equal(engineered.span_length_km, 85.25);
    assert.notEqual(engineered.topology_sha256, bundled.topology_sha256);
    assert.deepEqual(await rows(), cliRows("override"));
    assert.match(engineered.report, /length \(km\):\s+85\.25/);
    assert.match(await page.locator("#comparison").innerText(), /versus bundled 80 km/);

    for (const [id, dx, dy] of [["point-a", 40, -30], ["point-b", -38, 28]]) {
      const pin = page.locator("#" + id);
      const before = await pin.boundingBox();
      const x = before.x + before.width / 2;
      const y = before.y + before.height / 2;
      await page.mouse.move(x, y);
      await page.mouse.down();
      await page.mouse.move(x + dx, y + dy, {steps: 5});
      await page.mouse.up();
      assert.notEqual((await pin.boundingBox()).x, before.x);
    }
    assert.match(await page.locator("#source").innerText(), /85\.25 km/);
    const dragged = await run();
    assert.equal(dragged.span_length_km, 85.25);
    assert.notEqual(dragged.map_estimate_km, engineered.map_estimate_km);
    assert.deepEqual(await rows(), cliRows("override"));

    await page.locator("#length").fill("90");
    assert.match(await page.locator("#status").innerText(), /rerun/i);
    assert.match(await page.locator("#result-summary").innerText(), /85\.25 km/);
    const download = page.waitForEvent("download");
    await page.getByRole("link", {name: "Download Excel"}).click();
    const workbook = await download;
    assert.equal(workbook.suggestedFilename(), "hyperion-run.xlsx");
    if (process.env.HYPERION_TEST_XLSX) await workbook.saveAs(process.env.HYPERION_TEST_XLSX);
    await page.getByRole("button", {name: "Apply length"}).click();
    assert.equal((await run()).span_length_km, 90);
    assert.match(await page.locator("#result-summary").innerText(), /90 km/);
    const nextDownload = page.waitForEvent("download");
    await page.getByRole("link", {name: "Download Excel"}).click();
    const newWorkbook = await nextDownload;
    if (process.env.HYPERION_TEST_XLSX) await newWorkbook.saveAs(process.env.HYPERION_TEST_XLSX + ".90.xlsx");
    await page.locator("#length").fill("-1");
    await page.getByRole("button", {name: "Apply length"}).click();
    assert.match(await page.locator("#length-error").innerText(), /positive/);
    assert.match(await page.locator("#source").innerText(), /90 km/);
    await page.getByRole("button", {name: "Use bundled"}).click();
    assert.equal((await run()).span_length_km, 80);
    assert.deepEqual(await rows(), cliRows("bundled"));
    await page.getByRole("button", {name: "Use map estimate"}).click();
    const geographic = await run();
    assert.equal(geographic.spans[0].source, "WGS84 geodesic");
    assert.equal(geographic.span_length_km, geographic.spans[0].geodesic_km);
    const beforeZoom = await page.locator("#point-a").boundingBox();
    await page.locator(".leaflet-control-zoom-in").click();
    await page.waitForFunction(x => Math.abs(document.getElementById("point-a").getBoundingClientRect().x - x) > 2, beforeZoom.x);
    await page.getByRole("button", {name: "Place ROADM C"}).click();
    await page.locator("#map").click({position: {x: 260, y: 175}});
    await page.locator("#point-c").click();
    await page.getByRole("button", {name: "Open site settings"}).click();
    await page.locator("#name-c").fill("Intermediate");
    await page.locator("#span-choice").selectOption("1");
    await page.locator("#length").fill("23");
    await page.getByRole("button", {name: "Apply length"}).click();
    const roadm = await run();
    assert.equal(roadm.site_names[1], "Intermediate");
    assert.equal(roadm.spans[1].simulation_km, 23);
    assert.equal(roadm.spans[0].simulation_km, roadm.spans[0].geodesic_km);
    assert.match(roadm.report, /Roadm Roadm_C/);
    assert.equal((await rows()).length, 76);
    const saved = page.waitForEvent("download");
    await page.getByRole("button", {name: "Save route"}).click();
    const routeFile = await saved;
    const routeContents = fs.readFileSync(await routeFile.path());
    await page.getByRole("button", {name: "New route"}).click();
    assert.equal(await page.locator("#route-order").innerText(), "A → B");
    assert(await page.locator("#stale-results").isVisible());
    await page.locator("#route-file").setInputFiles({
      name: "route.json", mimeType: "application/json", buffer: routeContents,
    });
    await page.waitForFunction(() => document.getElementById("route-order").textContent === "A → C → B");
    assert.equal(await page.locator("#name-c").inputValue(), "Intermediate");
    await page.locator("#span-choice").selectOption("1");
    assert.equal(await page.locator("#length").inputValue(), "23");
    if (process.env.HYPERION_ROADM_JSON) fs.writeFileSync(process.env.HYPERION_ROADM_JSON, JSON.stringify({roadm, rows: await rows()}));
    await page.getByRole("button", {name: "Remove ROADM C"}).click();
    assert.equal((await run()).spans.length, 1);
    console.log("Passed browser CLI parity for 76 channels in both cases, A/B drag, stale and fresh downloads, validation and reset.");
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
