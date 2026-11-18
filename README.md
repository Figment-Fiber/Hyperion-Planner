# Hyperion Routes · Mark Five

Hyperion Routes is a local optical route planning prototype. Draw a network on a map, edit its equipment and losses, and run a selected service through **real GNPy 3.0.1**. The visible brand is **Hyperion**.

The long-term goal combines geographic routing, optical engineering, vendor equipment, spectrum planning, construction constraints and an equipment handoff to Hyperion Estimator. This build uses generic optical models with sourced vendor references. It is not a vendor-certified design system.

## Download and launch

[Download Mark Five ZIP](https://github.com/Figment-Fiber/Hyperion-Planner/archive/refs/heads/metis/m5.zip), extract it, and open the folder containing `hyperion.py` and `requirements.txt`. In Windows File Explorer, type `powershell` in that folder's address bar and press Enter.

Alternatively:

```powershell
git clone --branch metis/m5 https://github.com/Figment-Fiber/Hyperion-Planner.git
cd Hyperion-Planner
```

Use **Python 3.12**, running each line separately:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe hyperion.py
```

For an existing checkout, switch to `metis/m5`, pull, and repeat the dependency install. Stop an old server with Ctrl+C first.

Keep the server window open. Wait for **Hyperion Routes is ready**, then open **http://127.0.0.1:8765/** in Firefox, Edge or Chrome. Do not open the Python or HTML file directly: the app needs its local server. If the address cannot be reached, inspect the terminal error and confirm the server is still running.

For another port, run `.\.venv\Scripts\python.exe hyperion.py --port 8766` and open **http://127.0.0.1:8766/**. On macOS/Linux use `python3.12 -m venv .venv` and `.venv/bin/python` instead of the Windows Python path. Windows with Python 3.12 and Edge is the tested configuration.

## What Mark Five includes

- **Geography:** up to six sites, connected spans, continental U.S. and Hawaiʻi map views, zoom, draggable sites, and up to 50 editable bends per span. Length sums WGS84 geodesic segments. Engineered overrides survive site and bend movement.
- **Selected service:** choose source/destination and optional intermediate site IDs. GNPy propagates this route through the physical degrees. The default search chooses the fewest links. Branches establish node degree and inventory; this does not load simultaneous traffic on every branch.
- **Settings:** node names, generic/Ciena/Nokia equipment references, per-node overrides, Corning Centrix panel assumptions, connector/pigtail losses, removable field splices, fiber profiles and attenuation, transmitter output, booster/preamp gain and midpoint amplifiers.
- **ROADM/WSS:** generic express and local add/drop paths, editable minimum internal loss, output target and passband checks. Source/destination ROADMs are included where their physical degree requires them.
- **Results:** 76 per-channel readings for frequency, power, ASE OSNR, nonlinear-noise SNR and GSNR, plus the actual GNPy report. OSNR/SNR/GSNR are in dB at **signal bandwidth**, not automatically at 0.1 nm.
- **Warnings:** over-80-km amplification review, amplifier operating limits, optional GSNR/ASE planning thresholds and reserves, incompatible equipment, WSS passbands, marine screening and Zones. Review and Fail entries are red in the browser and Excel.
- **Workspace:** editable route names, locally numbered DWDM Route starters, Save/Load project JSON, Back, Undo/Redo, resizable settings and map, and optional recalculation after edits. Changed inputs flag old results.
- **Downloads:** completed-run Excel, run evidence and Estimator quantities. Excel includes channels, spans, vertices, checks, source status and equipment. Saved projects retain the physical network and editable settings.

Select **Load 80 km reference** and **Run simulation** for the bundled case. Select its span and enter **85.25 km** for an override. Both cases are verified against independent CLI channel tables.

Panels default to **0.50 dB per mated pair** and **0.10 dB per pigtail splice**; field splices start at 0.10 dB. These are editable planning allowances, not measured loss or guaranteed Corning specifications. Panel losses replace corresponding fiber-end allowances to prevent double counting. External passive loss is itemized separately from internal ROADM behavior and amplifier gain/noise.

The 80-km rule requests placement review; it is not a universal reach limit. Adding an amplifier clears that placement warning, while optical checks still apply. GNPy includes amplifier ASE. FEC remains **Not evaluated** without a validated modem threshold. A generic optical result does not establish a vendor-mode pass.

## Vendor data and Estimator

`equipment_catalog.json` includes public source links for Ciena, Nokia and Corning. Client handoff capabilities differ from line-side modes. Selecting 100/400/800 Gb/s runs compatibility checks; it does **not** turn the generic 32-GBd spectrum into a vendor waveform. Missing licensed modes, thresholds and filter narrowing curves remain unevaluated. WSS band limits flag unsupported channels; they do not replace a measured transfer function.

Routes maintains quantities. **Hyperion Estimator owns pricing, quotes and cost totals**; construction pricing is excluded. Save after a successful current-revision run to include modeled selected-service amplifiers. A pre-simulation save identifies amplifier inventory as pending. Other directions/services need their own optical design.

The supplied Node.js import adapter reads saved project files:

```powershell
node estimator_adapter.js hyperion-route.json > equipment-import.json
```

Its importer checks revision and source snapshot. Reconciliation retains quotes for unchanged items and reports quantity changes. This is an import interface, not an embedded pricing screen.

## Zones and marine limitations

The local Zones endpoint screens the **whole bent route** against polygons. The default is an explicitly labeled v0.6 demonstration snapshot with only three approximate area polygons. Reference points are not boundaries. No-crossing results do not establish permitting clearance or complete geographic coverage.

Optional environment variable `HYPERION_ZONES_URL` points to a GeoJSON service. The app reports live/cache/stale/fallback status and exports unresolved crossings. No production live feed is configured.

Marine screening uses an approximate coastline check. It requests cable armor/wet-plant review; it does not establish depth or require single/double armor in deep water. See [ITU-T G.978](https://www.itu.int/epublications/publication/itu-t-g-978-2025-05-characteristics-of-optical-fibre-submarine-cables) and [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/). Map tiles require internet. Local optical calculations need no paid service.

## Verification

The **known engineering check** traces each edit into the geometry, actual engine inputs, propagation, compatibility, quantities and exports it affects. Completed-run downloads remain attached to that run after edits. The local server retains the latest 32 runs; download files to preserve them across restarts.

```powershell
.\.venv\Scripts\python.exe verify_gnpy_reference.py
.\.venv\Scripts\python.exe verify_m5_model.py
.\.venv\Scripts\python.exe verify_m5_equipment.py
.\.venv\Scripts\python.exe verify_m5_zones.py
.\.venv\Scripts\python.exe verify_m5_integration.py
```

Browser acceptance uses `verify_m05_browser.cjs`, Playwright via `PLAYWRIGHT_MODULE`, an installed browser via `HYPERION_BROWSER`, and the running app via `HYPERION_URL`. The earlier `verify_browser.cjs` targets the archived M1 interface.

See the [M05 milestone record](Hyperion_M05_Milestone_Record.md), [original baseline](evidence/gnpy-3.0.1), and [M05 evidence](evidence/m05). Full vendor modes, rate-specific/flex-grid allocation, OEO regeneration and the 20-node target are tracked in the [M06 plan](Hyperion_M06_Plan.md).
