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
    console.log("Passed browser CLI parity for 76 channels in both cases, A/B drag, stale and fresh downloads, validation and reset.");
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
