# Hyperion Routes M06 · Design review and service comparison

November 17, 2026 HST. Status: planned, requested by Kevin. Carry forward M05 and verify its delivered capabilities before implementing this milestone.

## Service and spectrum comparison

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
