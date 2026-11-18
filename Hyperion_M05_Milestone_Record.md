# Hyperion Routes M05 milestone record

Status: implemented and locally verified; development prototype. Date: November 17, 2026.
Branch: `metis/m5`. Main and deployment settings are unchanged. No paid services or purchases were used.

## Delivered

- Six-site physical networks and selected services, physical node degrees, generic express/add/drop ROADMs and source/destination local termination paths.
- Segmented geographic routes, editable bends, continental U.S./Hawaii views, WGS84 distance, preserved engineered overrides, save/load and undo/redo.
- Editable Corning Centrix panel assumptions and quantities, connector/pigtail/field splice losses, fiber models/attenuation, inline EDFAs and booster/preamp settings.
- Public Ciena/Nokia/Corning catalog references, client compatibility, per-node overrides and clickable explanations for incompatible equipment.
- Full saved-network quantity summary plus explicitly scoped modeled selected-service amplifiers; Estimator adapter with revision checks and quote-preserving reconciliation.
- Zones polygon API client with source freshness/fallback reporting and full bent-path screening; versioned demonstration snapshot when no live feed is configured.
- Hyperion wordmark, readable navy layout, editable route names, resizable settings/map, red warnings and completed-run Excel/evidence downloads.
- Known engineering check: inputs affect their modeled optical, geographic, validation and inventory dependencies; old results are flagged after edits.

## Verification evidence

- `verify_gnpy_reference.py`: all 76 channels match saved CLI tables at 80 km and engineered 85.25 km.
- `verify_m05_browser.cjs`: real browser/API runs also match both tables; branched route, panels/WSS, incompatibility explanation, bends, undo/redo, attenuation, losses, resizing, JSON/Excel download and narrow layout pass.
- `verify_m5_model.py`: geographic validation, reverse-direction connector orientation, selected four-site optical path with a branch, 76-channel independent CLI equality and connector sensitivity pass.
- `verify_m5_integration.py`: eight independent CLI comparisons covering the saved browser run, local ROADM add/drop, booster order, splices, attenuation, inline EDFA and WSS minimum-loss/output-target changes. Every comparison covers all six displayed channel columns for 76 channels. Optical edit sensitivity and workbook values pass.
- `verify_m5_equipment.py`: panel capacity scaling, quantities, express-only client applicability, actual amplifier inventory/deduplication, saved-project import, stale rejection and quote retention pass.
- `verify_m5_zones.py`: polyline/polygon crossings, bends, holes, boundaries, dateline, malformed features, point exclusion, cache/stale/fallback and live-source validation pass.
- Raw inputs, outputs, commands and comparison manifests: `evidence/m05/branched-route` and `evidence/m05/integration`. Browser outputs, workbook, saved project and desktop/mobile screenshots: `evidence/m05/browser`. Original exact baseline: `evidence/gnpy-3.0.1`.

Independent work: geometry/engine verification, equipment/source/accounting verification, and Zones/acceptance review were delegated separately. Final review identified and resolved reverse connector orientation, source booster placement, local panel budget visibility, panel capacity scaling and amplifier inventory omissions.

## Engineering limitations and deferred work

This is a generic diagnostic model. Public vendor cards do not supply all mode/FEC thresholds or WSS transfer curves. Unknown vendor feasibility remains Not evaluated. Selecting a client rate does not change the generic 76-channel, 32-GBd waveform. WSS configured band violations are flagged; filtering/narrowing is not a measured vendor transfer model. Multi-service simultaneous spectrum loading is not implemented.

Zones has no configured production live feed. The fallback is a small approximate demonstration snapshot, not a complete permitting database. Marine screening does not determine armor class or submarine repeater design. The 80-km amplifier placement flag is a review rule, not proof of reach.

Quantity inventory includes the whole saved physical network; inferred amplifier stages cover only the simulated service. Save the current completed revision to retain those stages. Estimator integration is the supplied import adapter; pricing and a complete Estimator application remain separate. No prices are fabricated.

M06 carries rate-specific/flex-grid allocation, guard-band checks, full vendor-mode builds, OEO regeneration, a 20-node target and further engineering review requirements. See `Hyperion_M06_Plan.md`.
