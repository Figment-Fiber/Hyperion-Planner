# Hyperion Planner M1

November 12, 2026 HST. The standalone GNPy baseline and the engine adapter comparison passed. The M0 handoff records workflow approval as pending. Browser implementation and acceptance are pending that review.

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
4. **Branding.** Render the approved two-color Hyperion H with its cross-node from the final supplied asset. The final file was unavailable in the clone and the project index records that linked images were absent from the source attachment.

The existing M0 preset computes a schematic map estimate of 66.7 km. Keep that estimate visible as a separate field when the reference run uses the bundled 80 km or an engineered override.
