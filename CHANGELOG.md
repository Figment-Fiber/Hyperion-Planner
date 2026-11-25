# Hyperion Routes change notes

## M07 — November 24, 2026

- Draw bends switches directly between physical spans at multi-degree sites. Clicking another line no longer keeps adding bends to the previously selected branch.
- New bends enter the nearest segment of the selected polyline instead of always appending at the far end. Moving a bend is protected from asynchronous preview redraws.
- Existing fiber, losses, equipment, service connections and engineered length overrides are preserved. Geographic length feeds GNPy when no engineered override is set.
- Added production-handler regressions and real-GNPy branch-isolation, effective-length, receiver-loss, override, splice and amplifier-noise checks. See `evidence/m07/verification.md` for scope and model limitations.

## M06 site-drop fix — November 24, 2026

- Wider site-to-span drop target with a highlighted target during dragging; Yes/No confirmation remains required.
- Background preview redraws cannot remove a marker during its drag. Final drop coordinates are read directly from the marker.
- Verified straight and bent span insertion in the browser, cancellation restoring the site and original span, and confirmed insertion producing a two-degree intermediate site.
- Regression checks: `node verify_m6_drop.cjs` and `node verify_m6_editing.cjs`.

## M06 — November 24, 2026

Development build on `metis/m6`, based on the approved beige M05 visual refresh. The last LinkedIn baseline is assumed to be M04 from Kevin's recollection; posting history was not independently verified.

### Engineering workflow

- Explicit terminal, ROADM, amplifier-site, splice-site, passive pass-through and OEO roles.
- Incoming preamps and outgoing boosters configured by site and connected direction. Use amplifier is optional; unchecked stages are excluded from the actual GNPy topology, with controls disabled. Enabled stages have automatic estimated output targets or manual gain and generic model selection.
- No hidden EDFAs: M06 invokes real GNPy 3.0.1 with `--no-insert-edfas`. A physically powered-off amplifier is not modeled as an ideal bypass; unchecked means absent from the active path.
- Insert a site into a span with Yes/No confirmation, preserved bends and apportioned engineering length. No/cancel does not split; Yes is one undoable edit. Existing field splice and inline-amplifier assignments are retained and flagged where review is required.
- Twenty-site network authoring and validation. Selecting a site/span opens its inspector at the top; map nodes open their settings directly.
- Copy site setup with a preview/confirmation and retained target amplifier overrides. Destructive site/span removal requires confirmation in M06.
- Unsaved/revision indicators, browser-local recovery draft and stale-result notices. Recovery is local browser storage, not a durable saved project or account sync.

### Service and spectrum calculation

- A What must this route support? panel sets the client rate, generic optical mode, grid, carriers, frequency, spacing, allocated slot, guard requirement, launch power and reserve. Advanced inputs expose generic receiver/GSNR thresholds, transmitter OSNR, baud rate and roll-off.
- A separate comparison view calculates alternative generic 100G, 400G and 800G modes on the same physical route. Each rate uses its own mode/slot defaults. Columns report actual propagated GSNR/power, section margin, spectral usage and verdict, with per-case details and comparison Excel download.
- Fixed/flex-grid validation checks occupied bandwidth, channel centers, slot overlap, guard gaps and band limits. Guard bandwidth does not automatically increase with distance.
- Actual enabled components drive loss, gain, ASE/NLI and quality. Hardware incompatibility, missing characterization and WSS constraints affect the verdict. Unsupported vendor modes remain unevaluated.
- OEO nodes split the selected service into independently propagated optical sections. An earlier failed section cannot be hidden by a passing final section. All sections appear in the basic Excel export.

### Important boundaries

The supplied generic modes and their GSNR/receiver thresholds are explicitly illustrative, editable engineering assumptions. They are not certified Ciena/Nokia modes, measured FEC curves or vendor reach guarantees. Selecting a vendor catalog entry does not create missing vendor optical data. WSS band/width violations are checked; a measured vendor transfer/narrowing model is not invented.

GNPy's reported OSNR ASE column includes configured transmitter noise at the receiver; a route with no EDFAs can still show finite OSNR. The topology and stage counts establish whether amplifier ASE was added. A zero-loss ROADM interface element works around a GNPy 3.0.1 bookkeeping bug; it adds neither physical attenuation nor amplification.

Zones still uses the limited bundled v0.6 polygons unless a feed is configured. No production live Zones service, permitting clearance or complete geographic coverage is claimed.

Deferred at Kevin's request: growth/resilience and protection studies, formal engineering handover packages, field-measurement integration and new suite synchronization. Existing project/Excel/quantity export remains.

## M05 and visual refresh — changes since M04

- Expanded from the earlier route prototype to six-site physical networks with branches and selected service routing.
- Added segmented/bendable fiber routes, summed WGS84 distances, continental U.S./Hawaii views and retained engineered overrides.
- Added editable Corning Centrix panel assumptions and quantities, connector/pigtail losses, fiber model/attenuation selection and sourced equipment compatibility references.
- Added local ROADM add/drop modeling, full-network quantities and selected-service amplifier inventory.
- Added whole-polyline Zones screening with explicit source/fallback status and geographic vertices in Excel.
- Added undo/redo, editable project names, resizable map/settings and revision-linked save/load/evidence/quantity downloads.
- Replaced the navy appearance with the approved cream/beige visual language, local Barlow fonts and outlined icons, without circuit-board border decoration.
- Fixed display of results when optional planning thresholds are blank.

M04 already included splice editing, gain controls, amplification review, marine screening and planning-margin warnings. These should not be presented as newly invented in M06.

## Validation record

See `evidence/m06/`, `verify_m6_engine.py`, `verify_m6_services.py`, `verify_m6_geometry.py`, `verify_m6_editing.cjs`, `verify_m6_equipment.py` and `verify_m6_integration.py`. The original 80 km and 85.25 km regression fixtures remain under `evidence/gnpy-3.0.1`.
