# Hyperion Planner | M0 review and GNPy baseline

**Date:** November 11, 2026 HST  
**Status:** Screen sketch and interaction prototype ready for review. Standalone GNPy run blocked by package access.  
**Plan:** [Hyperion Planner Product Brief v1.0](https://chatgpt.com/library?file_id=libfile_7bd9dfa42930819181e31dd5f8da9107&account_id=personal)

## Review the prototype

Open Hyperion_M0_Prototype.html in a desktop browser. It starts with a connected example and works from a local file.

1. Select the fiber span. Confirm that the map estimate and the simulation length are easy to distinguish.
2. Enter 85.25 km as the engineered length and click **Apply length**. Click **Run simulation** and check the length and source in the results.
3. Click **Use map**, then run again. To try manual placement, choose **Clear design**, place two sites, and connect them. **Place at preset point** supports the same flow without map clicking.
4. Review the sketch for the network list, map, span editor, and results layout. The map is schematic. The run uses a deliberate 450 ms display delay and illustrative OSNR and GSNR values. Neither the displayed optical values nor the delay is a GNPy measurement.

A JavaScript check using a simulated DOM passed 14 assertions covering the sample, run states, invalid length, override, reset, placement and connection. Headless Edge and Firefox did not complete a browser render in this workspace. The sketch was drawn and inspected separately.

## Benchmark and scope

Smartoptics describes map-based topology, service path visualization, route and wavelength suggestions, end-of-life feasibility, and amplifier scenarios. M0 takes the map, selected span, service path, and results workflow as its reference. A real authenticated click-through of SoSmart was unavailable. M1 connects the reviewed interface to one real sample. Editable multi-span designs, recommendations, vendor-specific behavior, and cost estimation have their own later milestones.

- [Smartoptics SoSmart product description](https://smartoptics.com/products/sosmart/)
- [Smartoptics SoSmart technical datasheet, Revision H](https://connect.smartoptics.com/hubfs/Marketing/00.%20Smartoptics.com/SoSmart%20Software%20Suite/DataSheet%20-%20SO-DS-SoSmart_H.pdf)

## Standalone GNPy reference case

**Engine pin:** GNPy 3.0.1, published as BSD-3-Clause. The package lists Python 3.11–3.12.  
**Input:** The pinned distribution’s bundled EDFA single-span topology and default equipment and spectrum settings.  
**Command:** gnpy-transmission-example --show-channels  
**Observed environment:** Windows, Python 3.12, separate virtual environment. Both the initial package lookup and isolated pinned PyPI retry returned no candidate. An HTTPS diagnostic reported “No such host is known” for pypi.org. GNPy was unavailable locally.  
**Evidence outstanding:** CLI exit status, raw channel output, exact input hashes and elapsed time. The prototype values are UI placeholders.

Run the following from PowerShell with Python 3.12 available and access to PyPI. This records the installed versions, the two named default inputs, and one timed CLI run. Preserve the full log and any supplementary input files used by the pinned case.

~~~powershell
py -3.12 -m venv .venv-hyperion
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment setup failed.' }
$baselinePython = '.\.venv-hyperion\Scripts\python.exe'
& $baselinePython -m pip install 'gnpy==3.0.1'
if ($LASTEXITCODE -ne 0) { throw 'GNPy installation failed.' }
& $baselinePython --version
& $baselinePython -m pip freeze | Set-Content -Encoding utf8 gnpy-versions.txt
$examples = & $baselinePython -c "from importlib.metadata import distribution; print(distribution('gnpy').locate_file('gnpy/example-data'))"
$inputFiles = @('edfa_example_network.json', 'eqpt_config.json') | ForEach-Object { Join-Path $examples $_ }
Get-FileHash -Algorithm SHA256 -LiteralPath $inputFiles | Format-Table -AutoSize | Out-String | Set-Content -Encoding utf8 gnpy-input-hashes.txt
$baselineClock = [System.Diagnostics.Stopwatch]::StartNew()
& '.\.venv-hyperion\Scripts\gnpy-transmission-example.exe' --show-channels 2>&1 | Tee-Object -FilePath gnpy-baseline.txt
$baselineExitCode = $LASTEXITCODE
$baselineClock.Stop()
"Exit $baselineExitCode. Elapsed $($baselineClock.Elapsed.TotalSeconds) s." | Tee-Object -Append -FilePath gnpy-baseline.txt
if ($baselineExitCode -ne 0) { throw 'GNPy baseline run failed.' }
~~~

M1 acceptance uses the same topology, equipment, spectrum and engine version. Compare the browser and CLI on the same channel and metric definitions, with the tolerance tied to the CLI display precision. Record units and reference bandwidth where reported.

- [GNPy 3.0.1 package and license](https://pypi.org/project/gnpy/3.0.1/)
- [GNPy bundled single-span example](https://gnpy.readthedocs.io/en/master/intro.html)
- [GNPy CLI options](https://gnpy.readthedocs.io/en/master/cli_options.html)
