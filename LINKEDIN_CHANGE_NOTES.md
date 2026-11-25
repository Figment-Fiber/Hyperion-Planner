# LinkedIn update notes · since M04

Baseline: M04 is Kevin's recalled last posted version, not independently confirmed. Use these notes after reviewing the M06 build. Nothing has been posted automatically.

## Suggested description

I've continued building Hyperion Routes, my local DWDM route-planning prototype powered by GNPy.

Since the earlier version, I've added bendable geographic routes, more flexible node/equipment editing, explicit amplifier controls, and a clearer engineering workspace. The latest build compares illustrative 100G, 400G and 800G optical scenarios on the same route, checks their spectrum allocations and guard bands, and models OEO regeneration as separate optical sections.

A major focus has been making the workflow easier to use: click a site to inspect its equipment, insert a node into an existing span with confirmation, and turn amplifier stages on or off without hidden amplification being added back. Results, warnings and section data can be exported to Excel.

This remains an engineering prototype. Generic mode thresholds are editable assumptions, not vendor-certified Ciena/Nokia performance or reach guarantees. I'm continuing to test the calculations and improve the workflow.

## Demonstrate in a short screen recording

1. Show the beige Routes workspace and select a fiber span.
2. Insert an intermediate site, demonstrating the Yes/No confirmation.
3. Show its passive/ROADM/amplifier role and optional amplifier checkbox.
4. Run the same route through the three-rate comparison.
5. Show a spectrum or margin warning and the Excel export.

## Claims to avoid

Do not claim certified vendor designs, complete live Zones coverage, automatic permitting clearance, a finished cost estimator, production security certification, or a complete growth/protection planning platform.
