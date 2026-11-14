# Hyperion Planner · Oʻahu route prototype

M3 adds an explicit generic Terminal A booster and a user-defined GSNR planning check. Open Terminal A to enter a booster gain target. The transmission report shows the actual GNPy element and effective gain, which auto-design can change. In **GSNR planning limits**, enter a required GSNR at signal bandwidth and a design reserve. Results identify the limiting channel and remaining margin. This is one planning check. Vendor-mode feasibility, receive-power limits and spectrum validation are separate work.

The map opens on Oʻahu with two draggable endpoints. Scroll, pinch, or use the zoom controls to change scale. Span estimates are WGS84 straight-line distances between site coordinates. Use an engineered length for surveyed fiber, conduit routing, or slack. Map tiles require internet access and are credited in the map. The local simulation and distance calculations can run without tiles.

Use **Save route** to download a JSON file with the current sites, coordinates and span overrides. **Load route** restores that design. **New route** opens an editable two-site starter in Oʻahu. Apply pending span edits before saving. Changing a completed design flags the results for a rerun. Excel continues to export the completed simulation.

Open **Route settings** to inspect terminals, an optional ROADM and each span. Click a map marker, then **Open site settings**, to jump to that site. Site names and per-span lengths are editable. The equipment catalog lists generic and vendor references. GNPy runs use the generic reference equipment.

Select **Place ROADM C**, then click the map to insert an intermediate express ROADM between A and B. The span dropdown switches between A → C and C → B. Each span can use its geographic distance or an independent engineered length. The GNPy report shows both spans, the generic ROADM, and any amplifiers GNPy adds during auto-design. Excel includes the coordinates, distance, effective length, and source per span.

This route uses one unidirectional service and the bundled spectrum and equipment models. The next engineering milestone is editable transceiver and ROADM profiles, fixed-grid and flex-grid allocations, and overlap and guard-band validation on both spans.

Run the bundled GNPy 3.0.1 EDFA example from a local browser. The demo uses two sites, one SSMF span, one EDFA and 76 channels. It runs locally after installing the dependencies.

## Download and start

On GitHub, select the M1 branch or release and choose **Code → Download ZIP**, or clone the repository and switch to the M1 branch. Extract the ZIP and open a terminal in the folder containing this README.

Use Python 3.12. The commands below are for Windows PowerShell.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe hyperion.py
```

On macOS or Linux with Python 3.12, use `python3.12 -m venv .venv` and replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.

On Windows, if Python 3.12 is managed by uv, use `uv venv --seed --python 3.12 .venv` for the first command. Windows with Python 3.12 and Edge is the tested configuration.

Wait for **Hyperion Planner is ready** in PowerShell. Keep the server running in that window and open the printed address in your browser. The default is **http://127.0.0.1:8765/**. Use Ctrl+C in the terminal to stop the app.

If you need a different port, start the app with the full Python command:

```powershell
.\.venv\Scripts\python.exe hyperion.py --port 8766
```

Then open **http://127.0.0.1:8766/**. If PowerShell returns to the `PS ...>` prompt, the foreground server has stopped. Check the terminal output and rerun the full launch command.

## Run and export

1. Select **Use bundled**, then **Run simulation** for the original 80 km reference case. Select **Use map estimate** to return to geographic mode.
2. Enter **85.25** and select **Apply length**, then **Run simulation**.
3. Drag A and B, or move a focused endpoint with the arrow keys. The schematic estimate updates. The applied engineering length continues to drive the optical simulation.
4. Select **Download Excel** for the completed run. An engineered run includes bundled results and differences. Edits after a completed run require another simulation to update the workbook.
5. Select **Use bundled** and rerun to restore the reference optical case.

Edit **Site A name** and **Site B name** to label your design. Select **Use map estimate** to run the current schematic distance. Moving a site updates that distance in map mode. Select **Apply length** to use an engineered length that stays fixed when you drag a site. Site labels and the length source are captured in the workbook when you run.

The workbook links are valid for the latest 32 runs in the current server session. Save the workbook locally to keep it. See the [M1 plan](Hyperion_M1_Plan.md) for baseline evidence and acceptance criteria.

## Verify the reference cases

With the app running, install Playwright in a separate test environment or make its module available via `PLAYWRIGHT_MODULE`. Install its Chromium browser, or set `HYPERION_BROWSER` to an installed Edge or Chromium executable. Run `node verify_browser.cjs` from this folder. The test compares all rendered channel rows with the two saved GNPy CLI runs, then exercises dragging, validation, reset and workbook downloads.
