# Hyperion Planner M2 acceptance plan

November 12, 2026 HST. Status: proposed next milestone. Implementation baseline: `d08128d` (`metis/oahu-roadm`).

## Baseline and roadmap

| Gate | Status and evidence |
| --- | --- |
| M0 workflow | Approved per the M1 record. |
| M1 real GNPy browser run | Demonstrated locally. The bundled 80 km case and 85.25 km override matched the independent CLI across 76 channels when rerun for this review. |
| M2 geographic editor | Partial. The Oʻahu prototype supports named, draggable A/B sites, one optional express ROADM C, WGS84 distances and independent span overrides. The saved three-node browser and CLI reports match across all 76 rows and six displayed columns. General six-node editing remains open. |
| M3 engineering and simulation | Basic optical reporting works. Editable equipment and operating modes, per-span spectrum validation, multi-degree ROADM behavior and validated vendor profiles remain open. |
| M4 Excel exchange | Export exists. Import, mapping and round-trip validation remain open. |
| M5 project workflows and M6 desktop release | Open. Cost estimation and equipment recommendations also remain on the roadmap. |

Local HEAD matched the cached `origin/metis/oahu-roadm` ref. Live GitHub access was unavailable during this review. The three-node comparison used the committed browser and CLI captures in [evidence/oahu-roadm](evidence/oahu-roadm/).

## Next gate: six-node route authoring and simulation

Use a synthetic six-node Oʻahu fixture with two terminals, four intermediate sites, and five spans. Model one selected unidirectional service with generic supported equipment.

1. **Author the route.** Place, name, drag, connect and remove nodes and spans. Select the service endpoints and show the five ordered spans. Reject a disconnected route with an actionable message.
2. **Verify distances.** Compare all five WGS84 distances with an independent geodesic reference within 0.01 km. Override one span with a known engineered length, move an adjacent site, and confirm only geographic estimates recalculate while the override remains fixed.
3. **Validate the GNPy translation.** Capture the actual topology and effective span lengths used by the browser, then run a separate GNPy CLI simulation with equivalent inputs. Match all 76 channel rows at displayed precision, including frequency, channel power, ASE OSNR, SNR NLI and GSNR. Retain the existing 80 km, 85.25 km and three-node ROADM fixtures as regressions.
4. **Verify the Excel export.** Check the five spans, their coordinates, length sources and effective lengths against the completed run. After an edit, mark the results as requiring a rerun and verify that the workbook still represents the last completed run.

Save the fixture, CLI output, browser comparison and sample workbook together. The next user checkpoint is a walkthrough of route editing, one engineered override and the matching export.

## First M3 benchmark

The separate **Titan Route Atlas** project will maintain source-dated screening data for North America and the Pacific. A future Hyperion integration should intersect a designed route with versioned public GeoJSON or a live endpoint and retain the source, activity-specific restriction, date, geometry precision and reviewer status. Treat verified prohibitions, permit review, natural hazards, community reports and existing infrastructure as separate layers. Keep the route-screening result independent of optical feasibility.

### Configuration results and feasibility alerts

**Known check for every engineering edit.** Trace the setting from the saved route through the submitted snapshot to the actual GNPy topology or equipment file, or the applicable validation rule. Verify all affected rendered readings, thresholds, warnings and Excel values. Compare against an independently launched GNPy case for changes that affect propagation. Mark affected results stale until a new run finishes and retain the exact completed run for export. Treat a resolved placement warning and a passing optical margin as separate evidence.

- Give each placed amplifier a stable ID and an expandable settings entry under its terminal or inline span. Save its position, direction, profile and requested settings with the route. On rerun link it to the actual GNPy element and show effective gain, noise figure, and input/output power. List engine-inserted equipment separately and flag adjustments to requested settings.
- Show **Pass**, **Fail**, **Review**, or **Not evaluated** for each check and summarize the limiting channel, frequency, measured value, limit and remaining margin. Fail if a verified hard limit is violated. Use Review for a passing result within an explicitly configured warning margin. Use Not evaluated when required inputs or a validated limit are missing. An overall Pass requires all required checks to be evaluated and passed.
- Use the selected receiver mode and GNPy's feasibility metric at its stated reference bandwidth. For a conventional mode, compare the engine's generalized SNR after applicable penalties with the mode requirement and configured design reserve. Track receiver power limits, spectrum and guard-band conflicts, and equipment operating limits as independent checks. Show passive loss by component and correlate it with power and noise results. Any passive-loss limit must come from an explicit design constraint.
- Mark existing alerts stale when route inputs change. Export the run's findings, limits and sources alongside the actual topology and readings. Test an adequate case, a borderline case, a negative-margin case, a receiver overload case and a missing-mode case. Compare the optical inputs and available feasibility results with independent GNPy CLI runs.

Use the same route to test fixed- and flex-grid allocation with editable generic transceiver profiles. Reuse the [M1 spectrum acceptance cases](Hyperion_M1_Plan.md#acceptance), including the synthetic 400 Gb/s mode that exceeds a 50 GHz slot. Add a candidate slot that is clear on four spans but occupied on the fifth, and require the validator to identify the blocking span and both channels. Compare the accepted mixed spectrum with an independent GNPy run and export its slot and guard-band decisions.

## Next build requirements from the prototype walkthrough

### Route settings and equipment placement

**Implementation status, November 13.** The Oʻahu build has editable site names, draggable locations, WGS84 endpoint distances, an optional generic express ROADM and per-span length overrides. The route-wide equipment editor and map settings popups, fiber selector, bends, splice placement, editable amplifier placement, and modern spectrum simulation remain planned. The current ROADM run may include GNPy auto-designed amplification.

**Initial equipment catalog.** [equipment_catalog.json](equipment_catalog.json) seeds the future selector with the generic GNPy reference, Ciena 6500-S14 with WaveLogic 6 Extreme 1.6T MOTR, and Nokia 1830 PSS-HC with 4CP4T8/PSE-6s. Vendor entries carry published product information for equipment selection and documentation. Before enabling vendor simulation, require a specific operating mode with sourced launch power, slot width or spectral mask, receiver threshold and reference bandwidth, and relevant line-system amplifier and WSS characteristics. Keep vendor catalog labels distinct from the model used for a run.

- **Editable defaults and change flags.** Prefill a new fusion splice with a visibly labeled 0.10 dB planning assumption. Prefill an amplifier from the selected generic or sourced equipment profile, with a suggested gain based on its role and span budget when available. Track defaults, user overrides and effective GNPy settings. Flag each affected node or span after an edit, and flag results as stale until a new run completes. Keep the current route file round-trip compatible when adding these settings.

- **One settings panel for the route.** List nodes and spans in route order, with expandable equipment and loss sections. Let the user collapse and reopen the panel while retaining selection and edits. Clicking a map node opens a compact summary with its role, equipment and key settings, plus an action that focuses the same item in the panel. Edits and map summaries read from one route model.
- **Terminals A and B.** Record chassis, equipment model, modem or transponder and operating mode. Include line rate, baud rate, modulation, carrier frequency, slot width and per-channel launch power. Show whether a directional booster or preamp is installed and its configuration. Show modeled receiver power, ASE OSNR, nonlinear SNR, GSNR and margin when a sourced mode threshold is available. Confirm whether “ESC” refers to the optical supervisory channel (OSC). If so, track its equipment and channel settings as management metadata until there is a validated simulation use.
- **Intermediate site C.** Show the node role and equipment actually installed. For a ROADM, show ingress and egress degrees, express/add/drop path, WSS filter or passband settings, equalization and path impairments. Show a modem and its settings when the site terminates or regenerates a service. Allow directional amplifier placement from the node.
- **Spans and splice points.** List the selected fiber profile, geographic and engineered lengths, attenuation, connectors, bends and discrete losses. Add a **Place splice** action in the Network tools beside the node controls, then click a span to place it and enter insertion loss in dB. Keep splices attached to their span and allow editing or removal. Report the resulting receive metrics. Derive nonlinear interference from GNPy propagation. A passive splice contributes insertion loss.
- **Amplifier placement.** Support a node booster or preamp and a click-to-place inline EDFA. Require the correct direction and show its gain target, tilt, noise model and output limits. Represent inline amplification at its actual position in the topology so propagation runs through the fiber on each side. Mark explicit and auto-inserted equipment in the report. Prevent invalid placements and expose any engine adjustments to requested settings.
- **Simulation and export traceability.** Label each setting as a GNPy input, an allocation or validation constraint, or descriptive metadata. Capture the exact effective values and ordered topology for each run. Mark results stale after an edit and keep Excel tied to the completed run. Compare the same route before and after a modem setting change, a placed splice and an inline EDFA. Verify the emitted inputs, passive loss and displayed power/noise metrics against independent CLI runs. Use a separate fixture to verify ROADM filter behavior before showing a numerical filter penalty.

- **Span bends.** Add, drag and remove bend points on each span. Sum WGS84 distances along the polyline and preserve engineered overrides. Keep one optical span between equipment sites regardless of bend count.
- **Modern DWDM line build.** Keep the bundled 76-channel reference and add a modern coherent flex-grid scenario informed by Ciena WaveLogic 6 Extreme. Track baud rate, modulation, payload rate, occupied bandwidth, slot width, guard and passband per direction. Show the spectrum overlay and report occupied and available spectrum, allocated carriers and aggregate payload per direction. Compare C-band with C+L only when the selected line equipment supports both. Use the vendor's published capabilities with explicit planning assumptions for any missing mode thresholds, spectral masks or slot widths. Label those assumptions and withhold vendor feasibility claims until validated.
- **Splices and loss.** Let users record individual splice losses and positions or enter a count and loss per splice. Itemize fiber attenuation, splices, connectors and other passive losses. Show gross passive loss, amplifier gain and net optical budget separately. Feed the losses into GNPy and report receive power, ASE OSNR, nonlinear SNR and GSNR as distinct quantities. Avoid double counting connectors or applying both a splice total and its component entries.
- **Visual amplifier placement.** Select a node and add a directional booster or preamp, or place an inline amplifier on a span with an explicit optical boundary. Show equipment placement on the route, include explicit settings in the simulation topology and identify any GNPy auto-inserted equipment in the output. Report gain, noise figure, output power and changes in receiver metrics when rerun.
- **Acceptance.** Confirm bends change geographic length while leaving an applied engineered length intact. Add three 0.1 dB splices and verify 0.3 dB additional passive loss in the budget and the intended loss elements in the engine topology. Run the same route before and after adding an amplifier, compare reported optical metrics with the independent CLI and verify the export captures placement and inputs. Verify the modern spectrum's slot edges, guard bands, carrier count and capacity against independent calculations before comparing its GNPy results.

[Ciena WaveLogic 6 Extreme MOTR specifications](https://www.ciena.com/insights/data-sheets/1-6t-wavelogic-6-extreme-motr) · [Ciena C/L-band module specifications](https://www.ciena.com/insights/data-sheets/wavelogic-6-extreme-2-x-16t-8-x-qsfp-dd-qsfp-dd800-module)

## November 13 cutover additions

### Optical model inputs and span fiber selector

- **ROADM.** Show the selected ingress and egress degrees and express, add or drop path type. Expose target output per channel or power spectral density, frequency-dependent path loss, PMD and PDL. Display actual input/output power and effective loss. Apply an equivalent OSNR contribution only when the selected path profile supplies one. Track WSS passband and cascade penalties as separate validated inputs. Require evidence that the engine applies a penalty before displaying it as simulated. The current generic express fixture uses a −20 dBm/channel target, default zero PMD/PDL and no generic express OSNR term. GNPy's default 38 dB add/drop OSNR setting is not applied to that express path.
- **EDFA.** Expose direction and role, band, gain target and limits, gain tilt, output power limit, and noise figure or validated gain-dependent NF model. Report effective gain, actual input/output power, noise figure and resulting ASE. Identify auto-inserted stages separately. Compare received power, ASE OSNR, SNR NLI and GSNR at the same reference bandwidth. Adding gain can restore signal power while adding ASE and changing downstream nonlinear noise.
- **Fiber selector in Span settings.** Start with generic G.652.D-style SSMF, G.654.E-style low-loss large-effective-area fiber, G.655-style legacy NZDSF and an editable custom profile. Show attenuation by wavelength in dB/km, chromatic dispersion and slope, effective area or nonlinear coefficient, PMD, and sourced operating wavelength bounds. Include separate splice entries and identify measured versus assumed data. Preserve the installed GNPy reference fixture. Its generic SSMF, LOF and NZDF are modeling starting points and need explicit attenuation and validated data before assigning commercial product names. C/L feasibility depends on the complete optical path, including amplifiers and WSS passbands. Erbium-doped gain fiber belongs in the EDFA model. Passive transmission-fiber selection changes loss, dispersion and nonlinear interference without adding amplifier ASE.
- **Acceptance.** Run the same length, spectrum and equipment with each fiber profile. Check passive loss against attenuation times length plus discrete losses. Confirm the topology carries each selected profile and compare browser power, ASE OSNR, SNR NLI, GSNR, CD and PMD with the CLI. Exercise ROADM express versus add/drop with sourced impairment fixtures and an explicit amplifier before/after case. Record whether auto-design changed amplifier settings during each run.

[GNPy optical inputs](https://gnpy.readthedocs.io/en/master/json.html) · [ITU-T fiber classifications](https://www.itu.int/epublications/publication/itu-t-g-978-2025-05-characteristics-of-optical-fibre-submarine-cables) · [Corning long-haul fiber examples](https://www.corning.com/content/dam/corning/media/worldwide/coc/documents/Fiber/FiberSelectionGuide.pdf)

**Planned after the core geographic milestone.** Add two ways to bring existing route geometry into the editor.

- **KML/KMZ route import.** Extract georeferenced line geometry, vertices, bends and available metadata. Display the imported route on the same map as an editable polyline. Show distances along its segments and preserve the original geometry and subsequent user corrections. Let the user explicitly choose which points define optical span boundaries, amplifier sites and other equipment locations. A route bend does not create an optical node.
- **Route reconstruction from screenshots.** Trace a top-down route using map labels, roads, landmarks and user-supplied control points to establish location and scale. Show calibration confidence and distance uncertainty, request more control points when needed, and let the user correct the trace. Require review and acceptance before converting the trace into optical inputs. Treat unverified screenshot distances as approximate.
- **Conversion acceptance.** Import a known route with bends and compare coordinates, shape and segment distances against an independent reference. Calibrate a screenshot with known control points and exercise an ambiguous screenshot that requires user input. Edit and approve both routes, then verify the resulting optical spans preserve the approved geometry and engineered overrides and that exports identify each length source.

**Engineering backlog.** Expand generic models to configurable ROADM degrees and WSS filtering, EDFA settings and placement, and OEO regeneration. Report launch power, OSNR/GSNR, mode margin and equipment compatibility alongside spectrum and guard-band checks. Use sourced Ciena and Nokia model data before making vendor-specific claims. Keep recommendations editable and carry cost estimation forward with explicit construction, equipment, labor, permitting and contingency inputs.

## November 16 · Next Hyperion Routes build

**Status: Planned for M05.** Logged at Kevin's request for later implementation after M04.

Follow-on engineering review and 100/400/800 Gb/s fixed/flex-grid comparison requirements are recorded in the [M06 plan](Hyperion_M06_Plan.md).

**Approved cost handoff, November 17.** Routes owns the equipment summary and revision-linked quantities in its saved project. Hyperion Estimator imports that saved project, preserves stable item and site IDs, and owns editable prices, quotes and estimate calculations. Routes may display an Estimator subtotal with pricing date and revision. Changes to a Routes design must identify the changed quantities when Estimator reimports it and preserve previously approved estimate revisions.

### Required M05 interface changes

- Gray out vendor equipment incompatible with the selected requirements and allow clicking it to open the specific reason. Apply the M05 equipment selection acceptance checks below.

- Set the default logo wordmark to **Hyperion**. The product name remains **Hyperion Routes** in the page title and documentation.
- Make the **Route settings** sidebar horizontally resizable. Provide a visible resize handle and keyboard controls. Keep it scrollable within the workspace so opening equipment and span sections does not push **Simulation results** farther down. On narrow screens where a sidebar cannot fit, use the collapsible Settings control.
- Acceptance: verify the Hyperion wordmark, widen and narrow the panel, expand several settings sections, and confirm that Simulation results stay accessible. Check desktop and narrow layouts.

### Required M05 engineering changes

- Add Google Earth-style segmented spans with editable bends, geodesic distance along the polyline, preserved engineered length overrides, and saved vertices. Add a continental U.S. map view alongside Hawaiʻi.
- Add equipment-only cost by site and span. Include vendor cards and optics, compatible pluggables, Corning fiber distribution panels, filters, ROADMs and amplifiers. Label generic pluggable prices as editable estimates, show unknown prices, and exclude construction.
- Expand sourced Ciena and Nokia catalogs with chassis, cards, transponders, line and client optics, compatible ports, and span termination requirements.
- Consume the separate Zones API, screen the entire drawn polyline, and show affected spans, reasons and source status. Carry unresolved crossings into the completed simulation results and Excel.
- Add multi-degree nodes with selected ingress and egress degrees, express/add/drop behavior, and ROADM/WSS filter requirements. Verify modeled path loss, passband and supported impairments against GNPy.
- Apply the known engineering check to every edit. Trace each component into the GNPy inputs, equipment compatibility, cost, or geographic rules it affects, and verify the resulting browser and Excel outputs.

### Required M05 equipment selection changes — November 17, 2026

### Required M05 node panels and termination accounting

Confirmed November 17. Propose an editable generic Corning panel arrangement at intermediate ROADM/add-drop sites, with line-facing termination capacity for each connected degree and local patch capacity when a local transponder is present. Count physical housings separately from used ports and optical connections. Use a splice enclosure for a splice-through site and an explicit CTE/CTB or documented termination arrangement for submarine terminals.

Show the panel under node settings and in the map node summary, including role, housing or model, capacity, used ports, connector type, mated connector-pair count, splice count and editable insertion losses with sources or assumption labels. Count loss on each traversed connection. Calculate express, add and drop service paths through the actual components they use. Replace existing allowances where the same connection is explicitly itemized to prevent double counting. Include jumpers and passive optics when present and distinguish their losses from the transponder power setting and ROADM internal loss.

Acceptance: inspect the default panel at an intermediate ROADM, change its connector and splice loss, and verify the affected path's actual GNPy inputs, optical readings, warnings, saved project and exported quantities. Verify a shared physical panel does not duplicate housing quantities across degrees. Carry the quantities and project revision into the proposed Estimator handoff.

- Re-evaluate the vendor equipment choices whenever the user changes a service requirement or relevant setting. Check chassis, cards, transponders, optics and their supported combinations against sourced capability records.
- Gray out known-incompatible choices while keeping their explanation control clickable and keyboard accessible. Clicking or activating the option opens a compact pop-up describing the conflicting requirement and capability. Do not apply the incompatible choice.
- Example: for a requested single 400GbE client handoff, a card whose highest supported client rate is 100GbE displays: "Does not support a 400GbE client handoff required by your settings. Maximum supported client rate: 100GbE." Distinguish client handoff rate from coherent line rate, aggregate capacity and multi-carrier delivery. Assess a chassis through the cards, slots and combinations it can support.
- Apply this behavior to documented constraints such as chassis/card compatibility, port type, client and line rates, modem mode, tuning range, grid or slot width, and supported FEC. Derive the explanation from the actual failed check.
- If capability data are missing, display "Compatibility unverified" with the missing evidence. Keep this distinct from a documented incompatibility.
- If a changed requirement invalidates an existing selection, retain it visibly flagged and require a supported replacement before claiming design compatibility. Refresh option availability when the requirement is changed back.
- Acceptance: a known 100GbE-only card is gray under a single 400GbE handoff requirement and its explanation opens without selecting it; a sourced compatible combination remains selectable; an unsupported frequency is explained; missing capability data shows unverified; and changing requirements re-evaluates both the existing selection and available options.

### M05 final equipment and presentation additions · November 17

Status: planned. These additions extend the existing M05 scope.

- **Optics checks after moving sites or bends.** Recalculate geographic route length and re-evaluate affected optics and pluggables after dragging ends. Use the effective engineered length when an override is active and keep the map estimate separately visible. Mark prior findings pending or stale while debounced validation runs. Recheck the selected service, port/card compatibility, power budget, receiver limits, spectrum and supported GNPy signal-quality requirements. In Automatic Design propose supported replacements and explain the differences; preserve Advanced overrides with warnings. ZR or other advertised reach labels are candidate filters and require mode- and path-specific checks. Missing thresholds remain unverified. Acceptance: move a route across a supported reach or loss limit, verify an actionable warning and candidate update, restore the route, and test that an engineered override remains authoritative and exports match the completed run.

- Default applicable terrestrial equipment sites to a Corning Centrix modular housing and compatible cassette arrangement sized to the required termination count. Select a documented regional variant and connector type. Keep capacity, populated cassettes, used ports, splice and connector losses separately editable. Corning's Centrix central-office reference describes 1U, 2U and 4U options with different connector capacities. Source https://www.corning.com/optical-communications/worldwide/en/home/applications/central-office-headend-solutions/solutions/centrix.html
- Include generic client optics and line pluggables or integrated line interfaces as appropriate to the selected card. Record rate, form factor, connector, wavelength, power limits, reach category and sourced compatibility. Generic cost and engineering assumptions must remain labeled and editable. Include matching endpoints and required patching in saved quantities and the Estimator handoff.
- Include the ROADM WSS/filter function and its supported degree, band and frequency-slot constraints. Global Ciena/Nokia selection proposes compatible photonic equipment and updates dependent validation and simulation inputs. Preserve local overrides with incompatibility or missing-data flags. Use sourced path loss and filtering penalties where available. A catalog product's supported switching directions does not establish its insertion-loss or spectral-transfer model.
- Candidate vendor references are Ciena 6500 RLS and Nokia 1830 PSS/PSI-L photonic equipment. Sources https://www.ciena.com/insights/data-sheets/rls and https://www.nokia.com/optical-networks/1830-pss-psi-l-optical-line-systems/
- Replace the Oʻahu-specific heading with the editable project route name. Default new designs to DWDM Route 1, DWDM Route 2, etc., advancing from locally saved route records and preserving explicit names on load. Document the scope of numbering. Save and export the name.
- Put Back, Undo and Redo near the route title. Back returns from a focused node/span view to the route overview. Undo and Redo restore actual design history and affected dependencies. Disable unavailable actions.
- Retain the navy palette and refine typography, spacing, contrast, control hierarchy and table readability. Use a professional engineering workspace layout and verify desktop and narrow-screen usability.
- Add vertical map resizing with an accessible handle or equivalent control, allowing a roughly square map in a suitably wide viewport. Set practical minimum and maximum dimensions from available viewport space, preserve zoom and positions on resize, and keep the resizable settings panel and simulation results usable.
- Verify names and numbering, route save/load, panel quantities and losses, optics compatibility, vendor WSS changes, history, map resizing, and all affected GNPy/browser/Excel outputs under the known engineering check.
