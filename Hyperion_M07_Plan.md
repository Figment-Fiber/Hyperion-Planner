# Hyperion Routes — Mark 7 working backlog

## Draw bends between segments

- Recorded: November 24, 2026, at Kevin's request after testing M06.
- Status: implemented on `metis/m7` after Kevin authorized the fix and engineering checks; verification recorded in `evidence/m07/verification.md`.
- Report: Draw bends is not working correctly between segments.
- Required work: reproduce the segment-selection and bend-placement behavior; ensure a new bend edits the intended span and segment in route order rather than another segment or an unintended route position.
- Acceptance: test a span with multiple existing segments and a route with multiple spans. Adding, moving and removing a bend must affect only the selected geometry; undo/redo and save/reopen must preserve it. Recheck geographic distance, engineered length overrides, zone screening and subsequent GNPy inputs/results wherever affected. Do not change connectivity or duplicate/drop equipment or loss assignments.
- Authorization history: the initial request was to log only. Kevin subsequently clarified the A–B / B–C / B–D failure and authorized correction and engineering validation.
