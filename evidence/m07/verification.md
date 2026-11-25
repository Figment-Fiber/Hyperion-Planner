# M07 bend editing verification — November 24, 2026

## Defects and behavior

Map clicks previously used the selected span, and new bends were appended to its bend list. M07 permits direct switching to another clicked/nearby span and inserts each bend into the nearest displayed segment. A click away from any line still bends the selected span. Segment choice uses map projection; physical distances use the existing WGS84 geodesic calculation. Bend geometry does not create a site, an amplifier or a microbend-loss event.

The site-drop confirmation remains mandatory. Map redraws are suppressed during both site and bend drags. Original engineering overrides and equipment/loss assignments remain intact.

## Automated evidence

- `node verify_m7_bends.cjs m7-fixtures.json`: passed the actual map and polyline handlers for A–B → B–C → B–D, insertion into an earlier segment, bend drag redraw protection, serialization and unchanged engineering settings.
- `python verify_m7_engineering.py m7-fixtures.json`: 12 checks passed with real GNPy 3.0.1. Actual generated fiber lengths match effective route lengths; a B–C detour changes downstream receiver power at 0.2 dB/km. A–B–D channel values remain identical when only B–C is edited. Reverse service reverses bends and retains distances. An explicit 60 km B–C override preserves optical results despite changed drawn geometry. An extra 0.3 dB splice reduces propagated power by 0.3 dB. An enabled B→C amplifier adds one EDFA with positive noise figure and reduces ASE OSNR; it is absent from A–B–D propagation.
- `verify_m6_integration.py`: all 14 existing checks passed, including vendor qualification blocking, equipment compatibility, ROADM path loss and target, WSS band/width checks, disabled amplifiers, OEO all-section failure handling and the site limit.
- Existing service/spectrum suite: six tests passed. Twenty-site geometry and full-network equipment/quantity reconciliation checks passed.
- Existing M06 engine checks passed, including exact three-channel loading, amplifier ASE, per-degree OFF, twenty-site propagation and replay of saved inputs through the CLI. Zones checks passed for bent rerouting, segment crossings, boundaries, holes, dateline and source/cache behavior.
- Original bundled single-span reference: all 76 per-channel OSNR and GSNR values still match the saved CLI tables at both 80 km and the 85.25 km engineered override (`verify_gnpy_reference.py`).
- `verify_m6_drop.cjs` and `verify_m6_editing.cjs`: existing drop, immutable insertion, bend partition, loss assignment, override, amplifier-position and copy checks passed.

One downstream detour example changed receiver power from −26.69 to −30.28 dBm at 193.1 THz. ASE OSNR remained 35.92 dB and GSNR 34.88 dB, both referenced to signal bandwidth. Passive attenuation can reduce signal and existing noise together; it must not be represented as invented ASE. Receiver power and the configured mode limits remain separate feasibility checks.

Exact local raw runs and browser fixtures are retained privately; no private recordings or machine paths are included here.

## Browser workflow

An isolated local server loaded a synthetic A–B / B–C / B–D project. With Draw bends left active, direct clicks changed the inspector from A–B to B–C to B–D and created one bend on each span. Dragging B–D's bend changed that branch. The downloaded project retained distinct bend arrays for all three spans. Undo/redo restored the edited geometry. A subsequent browser run completed for A–B–C. Reopening the local recovery draft in the final M07 build retained the branches; a further B–D bend drag followed by a B–C click again switched correctly. A private screenshot records the final bent branches.

## Model limits

These checks validate the stated model and edited workflow, not a full vendor acceptance test. Generic 100G/400G/800G thresholds remain illustrative. Sourced Ciena/Nokia hardware references do not supply certified optical mode thresholds or WSS transfer curves. Missing vendor qualification must not produce a vendor-certified Pass. Each run evaluates one selected service; simultaneous branch loading and a network-wide spectrum allocator remain outside this build. Zone screening uses its stated dataset coverage and is not permitting clearance.
