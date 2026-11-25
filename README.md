# Hyperion Routes · Mark Six

This branch applies the approved November 20 Hyperion design direction: warm beige and cream, muted teal/sage accents, ink-colored text, Barlow typography, outlined icons and softly framed windows. It follows the visual reference at [Learn Arduino](https://learn-arduino-red.vercel.app/) without its circuit-board border decoration. Fonts are served locally under their bundled SIL Open Font License. Shared suite tokens live in `assets/branding/hyperion-theme.css`.

Hyperion Routes is a local optical route planning prototype. Draw a network on a map, edit its equipment and losses, and run a selected service through **real GNPy 3.0.1**. The visible brand is **Hyperion**.

The long-term goal combines geographic routing, optical engineering, vendor equipment, spectrum planning, construction constraints and an equipment handoff to Hyperion Estimator. This build uses generic optical models with sourced vendor references. It is not a vendor-certified design system.

## Download and launch

[Download Mark Six ZIP](https://github.com/Figment-Fiber/Hyperion-Planner/archive/refs/heads/metis/m6.zip), extract it, and open the folder containing `hyperion.py` and `requirements.txt`. In Windows File Explorer, type `powershell` in that folder's address bar and press Enter. The earlier beige M05 build remains on `metis/routes-beige-refresh`.

Alternatively:

```powershell
git clone --branch metis/m6 https://github.com/Figment-Fiber/Hyperion-Planner.git
cd Hyperion-Planner
```

Use **uv with Python 3.12**, running each line separately. If uv is unavailable but Python 3.12 is installed, use `py -3.12 -m venv .venv` for the first line:

```powershell
uv venv --seed --python 3.12 .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe hyperion.py
```

For an existing checkout, switch to `metis/m6`, pull, and repeat the dependency install. Stop an old server with Ctrl+C first.

Keep the server window open. Wait for **Hyperion Routes is ready**, then open **http://127.0.0.1:8765/** in Firefox, Edge or Chrome. Do not open the Python or HTML file directly: the app needs its local server. If the address cannot be reached, inspect the terminal error and confirm the server is still running.

For another port, run `.\.venv\Scripts\python.exe hyperion.py --port 8766` and open **http://127.0.0.1:8766/**. On macOS/Linux use `python3.12 -m venv .venv` and `.venv/bin/python` instead of the Windows Python path. Windows with Python 3.12 and Edge is the tested configuration.

## What Mark Six includes

- Author networks with up to **20 sites**, bent spans, geographic distance and persistent engineered overrides. Insert a site into a span with Yes/No confirmation and one-step undo. Click a node/span to open its inspector.
- Choose terminal, ROADM, amplifier-site, splice-site, passive pass-through or OEO regeneration roles. Set incoming/outgoing amplifiers by connected direction. **Use amplifier** is optional: OFF excludes the stage from the actual engine topology. Automatic targets do not install equipment; manual settings remain editable.
- Set requirements for 100/400/800 GbE, an illustrative generic optical mode, carrier count, frequency, fixed/flex-grid spacing, slot width, guard gap, launch power and reserve. Advanced fields expose baud/roll-off, transmitter OSNR and generic receiver/GSNR limits.
- **Compare 100G / 400G / 800G** computes three alternative modes on the same physical route, with rate-specific defaults and actual propagated power/GSNR. Download comparison Excel. These are alternatives, not simultaneous traffic unless configured as loading.
- GNPy 3.0.1 receives the exact selected spectrum and explicit topology with **--no-insert-edfas**. Loss, enabled amplifier ASE, nonlinear noise, hardware compatibility, WSS constraints and mode margins drive the result. OEO nodes create independent optical sections; every section must meet its requirements.
- Use visible equipment settings, setup copying, undo/redo, local recovery drafts and revision-linked save/load. A recovery draft is browser-local and may be unavailable if storage is cleared or disabled. Save a project file for durable retention. Geometry edits preserve engineered length.
- Results and basic Excel include optical sections, channel readings, configured spectrum, warnings and equipment. The CLI OSNR ASE column includes transmitter noise: no EDFA does not necessarily mean infinite reported OSNR. All units/reference bandwidths remain labeled.
- Zones retains full-polyline screening and source coverage/freshness status. It uses the limited bundled v0.6 snapshot unless a feed is configured; no production live connection is claimed.

**Model limits:** generic mode GSNR and receiver thresholds are explicit editable hypothetical assumptions, not measured vendor FEC curves or certified reach. Unqualified vendor modes remain Not evaluated. WSS width/edge violations fail validation; a measured vendor narrowing model is not fabricated. The fixed-grid option supports a generic uniform spacing plan, not every standardized/vendor channel arrangement. The flex option checks 6.25-GHz centers and 12.5-GHz slot increments. The current editor uses uniform carrier allocations; arbitrary mixed-baud per-channel editing is not yet provided.

Automatic amplifier control estimates the needed gain for the requested channel output and reports actual GNPy operation/limits. Review any target mismatch. An unchecked amplifier means absent/bypassed; a physically powered-off installed device is not assumed to be lossless. An 80-km placement review is not a universal amplifier reach rule. Panels default to editable allowances of 0.50 dB per mated pair and 0.10 dB per pigtail splice, with explicit field splices separately accounted.

**Legacy regression:** Load 80 km reference opens the original M05 optical model with 76 channels; its 85.25-km override remains verified against the saved CLI table. Existing M05 projects retain their old engine behavior until you explicitly select Enable M06 controls. Review amplification and mode assumptions when upgrading; the new model does not silently reproduce legacy automatic amplifiers.

The pinned GNPy 3.0.1 ROADM-to-fiber bookkeeping path needs an explicit zero-loss interface element. This compatibility element adds no attenuation or amplifier; serialized inputs and CLI replay evidence show it.

To evaluate the opposite direction, swap Transmit site and Receive site and rerun; per-neighbor incoming/outgoing stages follow that direction. The editor evaluates one selected service at a time.

## Vendor data and Estimator

`equipment_catalog.json` includes public source links for Ciena, Nokia and Corning. Client handoff capabilities differ from line-side modes. M06 changes the actual generic waveform for each mode (32/64/128 GBd defaults). Selecting a catalog vendor does not transform those assumptions into a qualified vendor waveform. Missing licensed modes, thresholds and filter narrowing curves remain unevaluated. WSS band limits flag unsupported channels; they do not replace a measured transfer function.

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

See [change notes](CHANGELOG.md) and [LinkedIn update notes since M04](LINKEDIN_CHANGE_NOTES.md). The recalled last LinkedIn baseline is not independently confirmed. Growth/resilience, formal engineering handover packages and new suite integration are deferred.

```powershell
.\.venv\Scripts\python.exe verify_m6_services.py
node verify_m6_editing.cjs
.\.venv\Scripts\python.exe verify_m6_geometry.py
.\.venv\Scripts\python.exe verify_m6_engine.py
.\.venv\Scripts\python.exe verify_m6_equipment.py
.\.venv\Scripts\python.exe verify_m6_integration.py
```

Browser workflow evidence and comparison workbook are under `evidence/m06/browser`; independent engine checks are under `evidence/m06/integration`.

The **known engineering check** traces each edit into the geometry, actual engine inputs, propagation, compatibility, quantities and exports it affects. Completed-run downloads remain attached to that run after edits. The local server retains the latest 32 runs; download files to preserve them across restarts.

```powershell
.\.venv\Scripts\python.exe verify_gnpy_reference.py
.\.venv\Scripts\python.exe verify_m5_model.py
.\.venv\Scripts\python.exe verify_m5_equipment.py
.\.venv\Scripts\python.exe verify_m5_zones.py
.\.venv\Scripts\python.exe verify_m5_integration.py
```

Browser acceptance uses `verify_m05_browser.cjs`, Playwright via `PLAYWRIGHT_MODULE`, an installed browser via `HYPERION_BROWSER`, and the running app via `HYPERION_URL`. The earlier `verify_browser.cjs` targets the archived M1 interface.

See the [M05 milestone record](Hyperion_M05_Milestone_Record.md), [original baseline](evidence/gnpy-3.0.1), and [M05 evidence](evidence/m05). Qualified vendor modes and measured WSS transfer data remain outside the generic model. The [M06 plan](Hyperion_M06_Plan.md) preserves the scope and deferred items.
