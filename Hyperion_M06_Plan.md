# Hyperion Routes M06 · Design review and service comparison

November 17, 2026 HST. Status: planned, requested by Kevin. Carry forward M05 and verify its delivered capabilities before implementing this milestone.

## Service and spectrum comparison

### Suite visual direction — November 20, 2026

Kevin selected https://learn-arduino-red.vercel.app/ as the visual reference across the Hyperion suite, applied first to Routes. Use warm beige/cream windows, muted colors, dark ink, readable Barlow body text and condensed headings, outlined playful icons, thin tan frames and restrained depth. Omit circuit-board traces and decorative border circuitry. This supersedes the earlier navy-theme preference. Keep engineering Fail/Review warnings red and maintain units, numeric readability, resizing, keyboard navigation and mobile behavior. Routes provides reusable suite colors/type in `assets/branding/hyperion-theme.css`, with locally served open-license fonts. Applying the theme to the other suite applications remains a separate integration task; this change implements Routes.

### Design Requirements and complete vendor builds

Confirmed November 17. On opening a new project, offer **Design Requirements** with **Configure requirements** and **Use defaults**. The latter creates an explicitly generic 100 Gb/s service baseline. Keep an accessible Design Requirements button near the route title to reopen the complete list. Save the selected requirements and identify assumed values.

- Capture service endpoints and direction, client handoff and aggregate demand, protection, vendor preference or generic equipment, allowed spectrum bands and grids, design reserve and any latency or site constraints. Treat measured fiber characteristics as engineering inputs. A service-rate change triggers a feasibility evaluation of the chosen fiber and equipment.
- Provide sourced Nokia and Ciena complete-build candidates including compatible chassis, cards, client optics, integrated or pluggable line interfaces, photonic equipment, panels and amplifiers. Start with the generic build when the user accepts defaults. A vendor choice proposes a documented supported equipment chain and marks any missing engineering data as unverified. Preserve user-entered route geometry and independent settings.
- Recheck equipment after changes to service rate, vendor, modem mode, grid or slot width, route or span length, fiber, loss, amplification, ROADM path and site capacity. In Automatic Design, propose supported replacement equipment and show the change and rationale. In Advanced Design, retain overrides visibly flagged until the user chooses a valid replacement. Include replacements in undo/redo and the saved project.
- Gray out documented incompatible equipment while keeping its explanation keyboard accessible and clickable. Missing specifications receive Compatibility unverified. Distinguish a single 400GbE client interface from aggregated 100GbE clients and from coherent line capacity. Verify hardware, software or license dependencies where sourced.
- Acceptance: open a generic 100 Gb/s default project, switch to a single 400GbE handoff and verify incompatible client interfaces are disabled with reasons and the supported candidate chain updates. Repeat for 800GbE and each vendor with sufficient evidence. Test an unavailable combination, a missing mode threshold, manual overrides, requirement changes back to 100GbE, undo/redo and save/load. Compare accepted simulation inputs, per-service results and exported equipment quantities.

- Compare 100, 400 and 800 Gb/s services on the same route. Distinguish client handoff rate, aggregate demand, coherent line payload, carrier count and grooming. Select a specific generic or sourced vendor mode for each case, with baud rate, modulation, FEC, launch power, receiver limits and required signal quality. Identify missing mode data and unsupported combinations.
- Support fixed-grid and flex-grid plans with editable supported center frequencies and slot widths. Show occupied signal bandwidth, guard bands, spectrum conflicts, loading, available capacity and per-span continuity. Use the selected equipment's tuning and filter constraints. A 75 GHz slot is one possible allocation. Rate alone does not determine its required width.
- Propagate the accepted spectrum and loading through GNPy. Compare optical margin, receive power, spectral consumption, equipment and port quantities, and latency across the three service cases. Keep service compatibility and optical results independently inspectable.
- Acceptance: test supported and unsupported modes, a too-narrow slot, neighboring-channel collision, missing receiver threshold, and a slot unavailable on one shared span. Compare a mixed-spectrum run against the independent CLI. Export all three scenario inputs, outcomes and differences.

## Explicit node types and pass-through — November 17, 2026

Confirmed by Kevin: add a node-type selector in node settings and the map node popup. Offer Terminal, ROADM, Amplifier site, Splice site and Optical pass-through, alongside the planned OEO regeneration role. ROADMs are equipment within a site, not a separate geographic object. Permit explicit equipment add/remove instead of deriving a ROADM solely from the number of connected spans. Propose suitable defaults, preserve manual choices, and flag missing switching equipment or unsupported connectivity rather than silently changing the site type.

- Add a per-service pass-through option at intermediate sites, including sites that also contain a modem/transponder. A transit service bypasses that modem; installed local equipment can remain in inventory for other services. Show the selected ingress/egress and actual optical connections. Do not imply that a modem provides transparent optical transit: a service traversing its receiver/transmitter requires the explicit OEO role.
- Distinguish passive fiber/panel pass-through from ROADM express transit. A passive two-port connection does not provide wavelength switching or fan-out. A branching site needs explicit supported connections and appropriate switching equipment where required.
- Preserve fiber, traversed connector/splice/panel loss and any selected amplifier ASE/NLI effects. A bypassed modem contributes neither a new transmitter nor a receiver threshold or regenerated noise budget to the transit service. ROADM express transit retains its applicable modeled impairments. Removing a ROADM removes its optical effects only when a valid bypass connection replaces it.
- Reflect role, installed equipment, bypass/express connections and affected service paths in settings, map summaries, GNPy topology, results, equipment quantities, Estimator handoff, saved projects, undo/redo and Excel. Keep installed inventory distinct from equipment traversed by a particular service.
- Acceptance: change a two-span intermediate site between ROADM express and passive pass-through; verify actual engine elements and loss/noise changes against independent CLI runs. At a site with an installed modem, pass a transit service around it while retaining that modem in inventory. Verify no accidental OEO/noise reset, unsupported branching warnings, role/equipment removal, save/load, undo/redo and exported connection schedules.

## Long routes, OEO regeneration and 20-node networks

- Support authoring, saving and loading networks with up to 20 named sites, including terminals, express/add-drop ROADMs, amplifier sites and regeneration sites. Keep geographic bend points separate from the site count. Validate topology and service paths and show an actionable error for a 21st site.
- Add an optional OEO regeneration role to an intermediate site. Model the receiving interface, electrical regeneration and transmitting interface with supported service rate, framing, FEC and equipment compatibility. Track ports, cards, optics, power and equipment quantities for the Estimator handoff.
- Split an end-to-end service into separate optical sections at each OEO site. Run GNPy for each section with its own input spectrum, transmitter quality, power, amplifiers and receiver mode. Start a new optical noise budget after supported regeneration while retaining the end-to-end service mapping and latency. Derive any regeneration delay from sourced data or mark it unknown.
- Offer regeneration as a candidate correction when supported optical sections cannot meet the selected mode's requirements. Compare candidate locations with amplification, an alternate mode or routing options using completed calculations. Keep the recommendation rationale and any missing data visible. Long unrepeatered fiber still requires a viable optical power and signal-quality budget before it reaches the regenerator.
- Acceptance: exercise a 20-site fixture and save/load it, reject a 21st site, run a deliberately failing long route, insert a supported regeneration site, and compare both optical sections independently with CLI runs. Verify that the overall service passes only when every section and interface compatibility check passes. Test a section that remains infeasible after regeneration, a rate mismatch, unavailable mode data and node removal. Export section boundaries, per-section margins, regeneration equipment, delay assumptions and end-to-end findings.

## Senior engineering review requirements

1. Maintain a service register with endpoints, direction, client handoff, demand, selected line mode, protection requirements and latency targets. Report a verdict for each service.
2. Show power before and after each traversed panel, splice, fiber section, ROADM and amplifier. Include passive loss, gain, noise figure, output limits and receiver margins, with units and bandwidths.
3. Compare beginning-of-life and end-of-life designs with explicit aging, repairs, loading and reserve assumptions. Prevent duplicated allowances.
4. Calculate and present both directions independently with their own settings and measured or assumed losses.
5. Evaluate working and protection routes, shared cable/conduit risks and service impact from a fiber, amplifier or node failure.
6. Produce a connection schedule with site, chassis, slot, card, port, connector, FDP termination, strand, wavelength and ROADM degree. Track spare port, slot and panel capacity.
7. Compare current and planned channel loading and show the effect of growth on existing services and remaining spectrum.
8. Maintain an assumption register identifying measured, vendor-specified, generic and user-entered inputs, with source dates, engine version and project revision.
9. Export an acceptance checklist with predicted loss and receive levels and supported performance limits. Link field measurements and test files to the applicable route, strand and service for design-versus-installed review.
10. Add a Design Review view showing delivered services, limiting components/channels, unresolved assumptions, required equipment/connections and changes from the prior saved revision.

## Shared project handoff

Routes owns engineering results, connections and equipment quantities. Estimator imports the revision-linked saved project and owns quotes, unit prices and estimate revisions. Rooms owns physical rack layout and site placement data. Validate IDs and revision consistency across handoffs.

## Current baseline

The inspected M04 reference uses 76 channels at 32 GBd, 50 GHz spacing and 0.15 roll-off. It remains the regression fixture as configurable service modes and spectrum are introduced.


## November 24 scope and authorization record

Kevin approved the narrowed M06 build, replacing the earlier planning hold. Current status: implemented development build on metis/m6; see CHANGELOG.md, README.md and evidence/m06/README.md for verified delivered behavior and remaining limits. The earlier detailed roadmap above is retained as historical context. This dated revision takes precedence.

### Current engineering scope

Keep the approved usability changes, explicit node/equipment roles, confirmed span insertion, optional per-direction amplification, 20-node target, supported generic service modes, fixed/flex spectrum checks, real optical calculation and OEO sections.

Defer growth/resilience: future demand scenarios, beginning/end-of-life comparison, protection routing, shared-risk and failure/survivability evaluation. Current channel loading and design reserve remain core optical inputs.

Defer formal engineering deliverables: installation/port/strand schedules, acceptance packages, field-measurement integration and comprehensive handover/Design Review packages. Retain basic save/load, results, Excel, model provenance and component readings.

Defer new suite integration with Estimator/Rooms or synchronized projects. Retain existing quantity exports and the approved shared beige visual language. Earlier references to deferred work do not reactivate it.

### Explicit optional amplification

Each supported direction has Use amplifier, with OFF controls grayed out and the amplifier excluded from actual GNPy input and effective topology. Enabled hardware uses an automatic output target or manual gain and model selection; automatic control must not silently add hardware or overwrite manual settings. Preserve disabled settings for reuse. Count installed versus absent/bypassed equipment accurately. A physically powered-off installed device is not an assumed lossless bypass.

Show incoming preamps and outgoing boosters separately at terminal and intermediate sites and by connected neighbor. Keep inline stages at their explicit location. Display requested versus actual gain, noise figure and input/output power with units, revision and operating-limit warnings. Respect the engine's actual supported control modes.

Permit short paths with zero EDFAs. A failing unamplified path must fail or remain unevaluated where specifications are missing, rather than being repaired with hidden gain. Keep the 80-km placement-review rule separate from calculated receiver and quality feasibility. Compare exact serialized CLI inputs, ensure disabled stages contribute no amplifier ASE and verify reenable, reverse direction, save/load and undo/redo.

### Insert a site into an existing span

Select A-B, place a node and choose its role to propose A-C and C-B. Placement or dragging over an existing segment must ask Yes, split span or No, keep span unchanged; proximity or dismissal never counts as approval. Show the affected span and connections. No/cancel preserves the original span, configuration and service continuity; an existing moved node must not acquire new connections without approval.

Preserve bends and split the drawn polyline at the insertion point. Preserve total engineered length, initially apportioned by geographic subpath length, with editable child overrides. Retain connector, field-splice and amplifier assignments without dropping or duplicating loss. Preserve actual inline-amplifier position; flag ambiguous assignments for review and acknowledgment. Commit confirmed insertion as one undoable operation. Validate straight/bent paths, overrides, Yes/No/cancel, removal, topology, optical results, quantities and exports.

### Service requirements and three-rate comparison

One route editor has What must this route support? and a separate Compare 100G / 400G / 800G view. Columns are alternative scenarios, not simultaneous services. Hold the physical route, fiber and equipment fixed; make proposed changes explicit. Distinguish one client handoff, aggregate demand and coherent carriers rather than equating eight 100G clients with one 800G interface.

Resolve an explicit mode, baud rate, modulation/FEC assumptions, launch/Tx OSNR, spectrum allocation, supported receive levels, quality threshold and reserve for each case. Generic illustrative thresholds are not certified vendor data. Unqualified or missing vendor mode data must not yield a vendor pass. Hardware incompatibility and optical feasibility both matter. Reevaluate after any relevant equipment, length, fiber, loss, power, ROADM or spectrum change.

Show allocated and occupied spectrum, guard gaps, overlap and band/filter constraints. Guard-band width does not automatically grow with distance. If reaching a longer distance requires another mode, propose it and recompute bandwidth and quality together. Enforce allocation continuity; do not invent a vendor WSS transfer/narrowing model or double-count penalties. ASE comes from actual enabled stages; NLI uses actual fiber, power and loading. Added gain or larger spacing is not an automatic pass.

OEO explicitly receives, regenerates and transmits; split the service into independently propagated optical sections. Evaluate all sections and compatibility. A failed earlier section cannot be hidden by clean final output. Preserve per-section inputs, assumptions and basic exported results.

### Ten approved user-workflow improvements

1. Persistent selected-object inspector: clicking a node/span opens its relevant controls at the top, with selection highlight and an obvious return to overview.
2. Discoverable contextual Add amplifier, Add ROADM, Add splice and Insert site controls, with explanations for unavailable actions. A site can house multiple components.
3. Clickable actual optical component path, distinguishing passive bypass, ROADM express and OEO, with actual readings where reported.
4. Everyday controls first; detailed modem/filter/model inputs under Advanced, with units/defaults/assumptions and visible warnings.
5. Keep active service, endpoints, direction and effective distance visible. Distinguish off-path inventory from active propagation and drawn from engineered lengths.
6. Actionable findings: component/service, units, threshold/value and settings navigation; separate placement review, calculated failure and missing characterization. Proposed corrections require review.
7. Deliberate copy/batch defaults for compatible sites/spans, with preview, preserved manual overrides and undo.
8. Unsaved/revision indicators, browser-local recovery, current versus last-calculated results and stale export warnings. A draft is not durable project storage.
9. Preview destructive edits and impacted service paths, preserve settings on cancel and avoid silent engineering-data loss.
10. First-time-user acceptance: create A-B, insert C, choose roles, add/disable equipment, set length, run, follow a finding, compare rerun, undo and save/reopen/export without developer guidance. Record usability failures separately from numerical parity.

### Zones and scope boundaries

Retain M05 full-polyline polygon screening, map overlays, warnings and basic exports. Default coverage is the limited bundled v0.6 snapshot; an optional configured feed is not a configured production live service. Show coverage/freshness. Recompute geometry screening after path changes. Do not turn geographic review into an optical attenuation penalty or legal permitting clearance.

User-requested engineering change rule remains: every change must reach all calculations, validation, quantities and exports it can affect. Exact GNPy CLI comparison and effective-topology inspection are required for new optical paths. The recalled M04 LinkedIn baseline remains unverified as posting history; change notes distinguish existing M04 behavior from subsequent additions.
