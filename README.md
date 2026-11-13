# Hyperion Planner

Hyperion Planner is a local-first tool in development for designing and comparing dense wavelength-division multiplexing (DWDM) networks. The goal is to take an optical design from a route on a map to a documented engineering and cost decision in one workspace.

**[Try the runnable M1 prototype](https://github.com/Figment-Fiber/Hyperion-Planner/blob/metis/gnpy-m1/README.md)** · [Download M1 source ZIP](https://github.com/Figment-Fiber/Hyperion-Planner/archive/refs/heads/metis/gnpy-m1.zip)

## What you can run today

M1 runs a real GNPy 3.0.1 example in a local browser. It models two sites, one fiber span, one optical amplifier, and 76 channels. You can drag the sites on a schematic map, apply an engineered span length, rerun the simulation, and download an Excel workbook with the completed run's inputs, per-channel results, and comparison with the bundled case. Browser results were checked against the GNPy command line for both the bundled 80 km span and an engineered 85.25 km span.

This branch also contains the original [M0 interface prototype](Hyperion_M0_Prototype.html) and its [milestone record](Hyperion_M0_Milestone_Record.md). Use the M1 link above for installation and launch instructions.

## Where Hyperion is headed

The target workflow is to draw a network, choose the equipment and services, check whether the design works, then compare its cost with other options. These are planned capabilities.

| Planning step | What Hyperion aims to support |
| --- | --- |
| **Build the network on a geographic map** | Click to place and move sites, draw and edit fiber spans, and inspect a service route. Use dropdowns to choose node roles such as a terminal, an amplifier site, or a ROADM that adds, drops, or redirects wavelengths. Start with a map distance estimate and record a surveyed or engineered fiber length when available. |
| **Model the optical link** | Configure fiber types, span losses, connectors and splices, amplifiers, and transceiver modes. Use GNPy-backed calculations to inspect optical power, loss, amplifier gain and noise, optical and generalized signal-to-noise ratios (OSNR and GSNR), and margin against the selected mode's requirements. Compare design assumptions, including end-of-life allowances. |
| **Plan services and spectrum** | Assign services to routes and wavelengths, with both 50 GHz fixed-grid and flexible-grid options. Overlay assigned slots and occupied signal bandwidth, flag overlaps and insufficient guard bands, and explain which channels and spans are affected. Suggest valid placements using the equipment's supported modes, baud rate, modulation, and spectral limits. |
| **Compare real equipment options** | Build a library of sourced vendor and model specifications for transponders, pluggables, amplifiers, and ROADMs. Compare equipment scenarios and show which figures came from vendor documentation, project inputs, or engineering assumptions. |
| **Estimate and compare costs** | Build an itemized bill of materials from a design. Use quote-based or user-entered pricing to compare equipment, fiber and installation assumptions, and recurring operating costs where data is available. See how a route, equipment choice, or capacity change affects both optical margin and cost. |
| **Review and share the design** | Export topology, inputs, channel allocations, validation findings, optical results, and cost estimates for review. Expand the existing Excel export toward spreadsheet import and scenario comparison so the assumptions behind a recommendation stay with the results. |

For example, an engineer evaluating a 400 Gb/s service could draw two candidate routes, choose a specific transceiver mode, and see whether each route has enough free spectrum and optical margin. They could then compare the equipment and cost of both options and export the assumptions behind the decision.

## Development milestones

- **M0** established the map, span editor, and results workflow.
- **M1** connects that workflow to one verified optical reference case and adds Excel export.
- **Future milestones** expand geographic and multi-span editing, spectrum allocation, vendor profiles, and cost comparisons. The [M1 plan and spectrum roadmap](https://github.com/Figment-Fiber/Hyperion-Planner/blob/metis/gnpy-m1/Hyperion_M1_Plan.md) documents the engineering evidence and planned guard-band checks.
