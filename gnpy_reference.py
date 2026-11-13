"""Run the fixed Hyperion reference case through GNPy's transmission CLI."""

import hashlib
import json
import math
import re
import subprocess
import sys
from importlib.metadata import distribution
from pathlib import Path
from tempfile import TemporaryDirectory


GNPY_VERSION = "3.0.1"
CHANNEL_HEADING = "The GSNR per channel at the end of the line is:"
NUMBER = r"(-?\d+\.\d+)"
CHANNEL_ROW = re.compile(r"\s*(\d+)" + (r"\s+" + NUMBER) * 5 + r"\s*")


def run_reference(length_override_km=None):
    """Return destination channel values and the input used for this run."""
    if length_override_km is not None and (
        type(length_override_km) not in (int, float)
        or not 0 < length_override_km
        or not math.isfinite(length_override_km)
    ):
        raise ValueError("Enter a finite, positive span length in km.")

    package = distribution("gnpy")
    if package.version != GNPY_VERSION:
        raise RuntimeError(f"GNPy {GNPY_VERSION} is required. Found {package.version}.")
    examples = Path(package.locate_file("gnpy/example-data"))
    bundled = examples / "edfa_example_network.json"
    topology = json.loads(bundled.read_bytes())
    span = next(element for element in topology["elements"] if element["uid"] == "Span1")

    with TemporaryDirectory() as run_dir:
        topology_path = bundled
        if length_override_km is not None:
            span["params"]["length"] = length_override_km
            topology_path = Path(run_dir) / bundled.name
            topology_path.write_text(json.dumps(topology, indent=2) + "\n", encoding="utf-8")
        topology_hash = hashlib.sha256(topology_path.read_bytes()).hexdigest()
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "from gnpy.tools.cli_examples import transmission_main_example; "
                "transmission_main_example()",
                str(topology_path),
                "Site_A",
                "Site_B",
                "--show-channels",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
        )
        if completed.returncode:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"GNPy exited with status {completed.returncode}. {detail}")

    return {
        "engine_version": package.version,
        "span_length_km": span["params"]["length"],
        "topology_sha256": topology_hash,
        "reference_bandwidth": "signal",
        "channels": parse_channels(completed.stdout),
    }


def parse_channels(output):
    _, heading, table = output.partition(CHANNEL_HEADING)
    if not heading or "OSNR ASE (signal bw, dB)" not in table or "GSNR (signal bw, dB)" not in table:
        raise RuntimeError("GNPy did not report the expected signal-bandwidth channel table.")
    channels = []
    for line in table.splitlines():
        row = CHANNEL_ROW.fullmatch(line)
        if row:
            channel, frequency, _, osnr, _, gsnr = row.groups()
            channels.append({
                "channel": int(channel),
                "frequency_thz": float(frequency),
                "osnr_ase_db": float(osnr),
                "gsnr_db": float(gsnr),
            })
    if [row["channel"] for row in channels] != list(range(1, 77)):
        raise RuntimeError("GNPy did not return all 76 reference channels.")
    return channels
