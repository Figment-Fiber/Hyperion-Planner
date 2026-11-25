# M06 verification record

November 24, 2026. Development branch `metis/m6`.

Implemented the narrowed M06 scope: explicit roles and optional directed amplifiers, 20 sites, confirmed span insertion, rate-specific generic spectrum comparisons, OEO section propagation, validation, basic exports and workflow improvements. The approved beige theme is retained.

## Checks completed

- Six service-allocation regression groups: rate/mode matching, fixed/flex allocations, slot/guard/band constraints, generic provenance and GNPy spectrum parsing.
- Editing tests: no source mutation before confirmation, bends, exact total override, endpoint losses, inline amplifier position, reversal, undo-friendly cloned changes, role normalization and compatible copy behavior.
- Twenty-site/nineteen-span geometry and twenty-first-site rejection.
- Nine real GNPy engine groups, with added component-reading and amplifier target assertions: exact channels, zero hidden amps, splice sensitivity, gain/ASE, directional OFF, all-section OEO verdict, 20 sites, CLI replay and JSON-safe values. A later loading correction ensures enabled amplifier design uses the actual requested channel count rather than the full-band reference count. Engine and independent integration passed again after this correction.
- Fourteen independent integration checks across twelve real GNPy runs: hardware/rate/missing-mode verdicts, actual ROADM loss changes, WSS band/width failure, zero-dBm target, explicit amplifier exclusion, OEO earlier-section failure and site limits.
- Inventory checks: installed stages on active/inactive branches, per-neighbor OFF, OEO equipment, no double counting and preserved existing quantity export. M05 equipment checks also pass.
- Original 80-km and 85.25-km regression: all 76 channel rows match saved CLI tables.
- Browser: new default runs; disabled amplifier controls gray out; Yes/No insertion and undo/redo work; local draft restores the inserted node; amplifier ON appears in actual GNPy component path and OFF removes it; three comparison columns run; Excel endpoint returns a readable workbook with Rate Comparison and Optical Sections sheets. The browser's automated download-event watcher timed out, so file contents were verified through the same local workbook URL. Save-project feedback completed successfully; a clean-machine Windows download dialog was not independently tested.

## Evidence

`integration/results.json` contains check outcomes, inputs, output and per-channel results. Browser screenshots, workbook and on/off run evidence are under `browser/`. Re-run the verifier commands in README to reproduce locally. No paid service was used. Main/deployment configuration is unchanged.

## Remaining limits

Mode thresholds are explicit hypothetical generic assumptions, not certified vendor modes or measured FEC curves. Uniform-carrier allocation is configurable; arbitrary mixed-baud manual spectrum entry is not yet exposed. WSS width/band validation does not synthesize missing vendor filtering/narrowing data. Zones coverage remains the limited v0.6 snapshot unless configured. Growth/resilience, formal engineering handover packages and new suite integration are deferred.

Workstation paths in public JSON evidence are sanitized; exact local originals were retained privately. Propagation inputs and channel values are otherwise unchanged.
