# Hyperion Planner M1

November 12, 2026 HST. Kevin approved the M0 workflow. The standalone GNPy baseline and engine adapter comparison passed. The browser demo and Excel download run from the local application described in the [README](README.md).

## GNPy evidence

Run from the repository root with Windows CPython 3.12.15 and GNPy 3.0.1. The executable below is from the isolated `.hyperion-gnpy\Scripts` directory at the Titan Command Center root.

```powershell
& '..\..\.hyperion-gnpy\Scripts\gnpy-transmission-example.exe' --show-channels
& '..\..\.hyperion-gnpy\Scripts\gnpy-transmission-example.exe' evidence/gnpy-3.0.1/override-85.25-km.json Site_A Site_B --show-channels
& '..\..\.hyperion-gnpy\Scripts\python.exe' -B verify_gnpy_reference.py
```

The bundled topology is `edfa_example_network.json`. It routes Site_A → Span1 → Edfa1 → Site_B. Span1 is 80 km of SSMF at 0.2 dB/km with 0.5 dB at each connector. Edfa1 uses `std_low_gain` with a 17 dB configured gain target and a 15 dB effective gain in the baseline after GNPy auto-design. Both runs use the default `eqpt_config.json` and its bundled auxiliary amplifier configuration files. The two advanced configurations are loaded by default and the selected amplifier is the standard low-gain model. There is no separate spectrum input file. The equipment SI block supplies 76 channels at 191.35000–195.10000 THz, 50 GHz spacing, 32 GBd, 0.15 roll-off, 0 dBm launch per channel and 40 dB configured transmitter OSNR.

| Case | CLI exit | Wall time | OSNR ASE range (dB) | GSNR range (dB) | Final GSNR (dB, 0.1 nm) |
|---|---:|---:|---:|---:|---:|
| Bundled 80 km | 0 | 22.499 s | 29.18–29.25 | 26.98–27.69 | 31.17 |
| Engineered 85.25 km | 0 | 3.013 s | 28.43–28.50 | 26.50–27.14 | 30.68 |

The two ranges use the CLI's signal-bandwidth columns. Wall time includes process startup and output capture. These are single-run timings. Both runs logged the GNPy warning about the missing ROADM equipment type, which defaults to `default`. The sample path has no ROADM.

The [evidence directory](evidence/gnpy-3.0.1/) contains raw stdout and stderr, input SHA-256 hashes, installed dependency versions, timing and exit status, the CLI override topology, and the adapter's channel output. The CLI override changes only the `Span1.params.length` value in the parsed topology. The adapter serializes an equivalent override independently, so its override file hash differs. Its results matched all 76 channels in each independently captured CLI table at the displayed precision.

## Browser scope and acceptance

After M0 workflow review, serve the reviewed page and a single simulation endpoint from a local loopback service. Send an optional engineered span length in km to the adapter and render channel frequency, ASE OSNR and GSNR with the CLI's units and bandwidth labels. Show the GNPy version, actual span length and its source in the results. Surface engine errors visibly. This demo requires no paid service.

1. **Bundled run.** Open the served page in a real browser and run with no override. Verify the input topology hash matches the installed bundled file and the reported length is 80 km. Compare all 76 rendered rows against a separately launched CLI, keyed by channel and frequency. Require the same OSNR and GSNR rounded to two decimal places and frequency to five decimals in THz. Use signal bandwidth for these metrics.
2. **Engineered run.** Apply 85.25 km and run. Inspect the topology passed to GNPy and verify the only semantic change is `Span1.params.length`. Verify GNPy reports 85.25 km and compare all 76 rendered rows against the independent override CLI run. Verify the results differ from the bundled case.
3. **A/B dragging and reset.** Apply the override and drag each endpoint. Verify each position updates and the map estimate responds. Rerun and verify 85.25 km still reaches GNPy and all channel values match the override CLI. Clear the override and verify that the bundled case returns. Reject invalid engineered lengths and keep the last valid selection.
4. **Branding.** Use the checked-in [approved logo and icon](assets/branding/README.md) and verify they load from a clean checkout.
5. **Excel download.** Export the last successful run as an `.xlsx` workbook. Record the effective span length and source, map estimate at run time, topology, equipment and spectrum identifiers, engine version, and metric units and reference bandwidth. Include all 76 channel results. For an engineered run, include the bundled values and per-channel differences alongside the engineered values. Verify the workbook values against the browser and independent CLI. After a run at 85.25 km, edit the input to 90 km and confirm the browser indicates a rerun is needed and the export still identifies 85.25 km. Rerun and verify the new download reflects the completed 90 km run.
6. **GitHub download and local run.** Include a root README with supported Python and OS versions, pinned dependencies, setup and launch commands, and instructions for the bundled run, override, and Excel export. Verify the documented flow from a fresh source download with a new virtual environment and no workspace-specific paths. The download must include the assets and all application files needed to run locally after dependency installation.

The existing M0 preset computes a schematic map estimate of 66.7 km. Keep that estimate visible as a separate field when the reference run uses the bundled 80 km or an engineered override.

## Bundled GNPy demo coverage

The M1 reference is the GNPy 3.0.1 single-span EDFA transmission example. In addition to the per-channel OSNR and GSNR acceptance metrics, expose the example's channel power and SNR NLI, destination summaries with their reported bandwidths, and per-element transmission details. Include those results in the workbook and verify their units and values against the CLI. The same run and export workflow applies to the bundled case and an engineered length. Mesh path requests and custom equipment or spectrum authoring are separate GNPy workflows.

## Roadmap — Spectrum allocation and guard-band validation

Start with the existing two-site route and mixed channel profiles. Extend the same checks to every shared fiber segment and direction when multi-span routing is available.

- **Spectrum overlay.** Show center frequency, assigned slot edges, occupied signal edges, and guard space in GHz. Identify the specific channels and span where slots overlap, a signal exceeds its slot, the guard falls below policy, or a slot exceeds the equipment passband. Display both the measured gap between occupied signal edges and the required minimum. Adjacent slots may touch when the signal edges still have sufficient separation.
- **Profiles and defaults.** Offer a 50 GHz fixed-grid preset and an ITU-T G.694.1 flex-grid preset with 6.25 GHz center steps from 193.1 THz and 12.5 GHz slot-width steps. Show the guard policy and its source. Use a supported equipment or transceiver profile first, with a labeled, editable planning default when none is specified. For the first generic demo, propose 5 GHz of total separation between neighboring occupied signals as a configurable planning assumption. Require an explicit zero setting and show the resulting actual gap. Mark generic estimates as requiring equipment validation.
- **Automatic placement.** Capture line rate in Gb/s, baud rate in GBd, modulation, roll-off or vendor spectral mask, and supported slot widths. Use the vendor profile when available. For a raised-cosine estimate, occupied width in GHz is baud rate in GBd multiplied by (1 + roll-off). Propose the smallest supported slot and a free grid-aligned center that meet the guard policy across the route. Allow users to shift frequency or adjust guard settings and revalidate immediately. A 400 Gb/s selection requires a specific mode or explicit signal parameters before Hyperion can size the slot.
- **GNPy and Excel.** Validate the plan before simulation and pass the accepted centers, slot widths, baud rates, and roll-off to GNPy. Report spectrum validity and optical feasibility as distinct results. Export the channel plan, guard policy and source, measured gaps, conflict locations, and the exact inputs used for the completed run.

### Acceptance

1. Load the M1 spectrum. At 32 GBd and 0.15 roll-off, the nominal occupied width is 36.8 GHz. With 50 GHz center spacing, show 13.2 GHz between adjacent occupied edges and pass the demo's 5 GHz planning policy.
2. Use a synthetic 400 Gb/s mode at 60 GBd and 0.10 roll-off. Show that its nominal 66 GHz signal fails the 50 GHz slot check. With an equipment fixture allowing 75 GHz slots, propose a valid flex-grid placement that meets the configured guard. Move it onto an occupied slot and verify the overlap flag identifies both channels. Exercise a case with no slot overlap but insufficient guard.
3. Exercise exact slot-edge adjacency, explicit zero guard, missing mode data, band edges, and a route where a slot is free on one segment but occupied on another. Verify that accepted allocation inputs and all exported values agree with the submitted plan. Compare optical output against a separately run GNPy CLI case using the same mixed spectrum.

[ITU-T G.694.1](https://www.itu.int/rec/T-REC-G.694.1-202010-I/en) · [GNPy spectrum inputs](https://gnpy.readthedocs.io/en/master/json.html)
