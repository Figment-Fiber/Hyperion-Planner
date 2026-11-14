"""Run the fixed Hyperion reference case through GNPy's transmission CLI."""

from copy import deepcopy
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
ANSI = re.compile(r"\x1b\[[0-9;]*m")
NUMBER = r"(-?\d+\.\d+)"
CHANNEL_ROW = re.compile(r"\s*(\d+)" + (r"\s+" + NUMBER) * 5 + r"\s*")


def run_reference(length_override_km=None, second_span_km=None, booster_gain_db=None):
    """Return destination channel values and the input used for this run."""
    for length in (length_override_km, second_span_km):
        if length is not None and (
            type(length) not in (int, float) or not 0 < length <= sys.float_info.max
            or not math.isfinite(length)
        ):
            raise ValueError("Enter a finite, positive span length in km.")

    package = distribution("gnpy")
    if package.version != GNPY_VERSION:
        raise RuntimeError(f"GNPy {GNPY_VERSION} is required. Found {package.version}.")
    examples = Path(package.locate_file("gnpy/example-data"))
    bundled = examples / "edfa_example_network.json"
    topology = json.loads(bundled.read_bytes())
    span = next(element for element in topology["elements"] if element["uid"] == "Span1")
    if second_span_km is not None:
        topology["network_name"] = "Oahu two-span express ROADM"
        second = deepcopy(span)
        second["uid"] = "Span2"
        second["params"]["length"] = second_span_km
        amplifier = deepcopy(next(element for element in topology["elements"] if element["uid"] == "Edfa1"))
        amplifier["uid"] = "Edfa2"
        topology["elements"].extend([{"uid": "Roadm_C", "type": "Roadm", "type_variety": "default"}, second, amplifier])
        route = ["Site_A", "Span1", "Edfa1", "Roadm_C", "Span2", "Edfa2", "Site_B"]
        topology["connections"] = [
            {"from_node": left, "to_node": right} for left, right in zip(route, route[1:])
        ]
    if booster_gain_db is not None:
        if type(booster_gain_db) not in (int, float) or not 10 <= booster_gain_db <= 18:
            raise ValueError("Enter a generic booster gain target between 10 and 18 dB.")
        topology["elements"].append({
            "uid": "User_Booster_A", "type": "Edfa", "type_variety": "std_low_gain",
            "operational": {"gain_target": booster_gain_db, "tilt_target": 0, "out_voa": 0},
        })
        first = next(link for link in topology["connections"] if link["from_node"] == "Site_A")
        destination = first["to_node"]
        first["to_node"] = "User_Booster_A"
        topology["connections"].append({"from_node": "User_Booster_A", "to_node": destination})

    with TemporaryDirectory() as run_dir:
        topology_path = bundled
        if length_override_km is not None or second_span_km is not None or booster_gain_db is not None:
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

    output = ANSI.sub("", completed.stdout)
    report, _, _ = output.partition(CHANNEL_HEADING)
    return {
        "engine_version": package.version,
        "span_length_km": round(span["params"]["length"] + (second_span_km or 0), 6),
        "span_lengths_km": [span["params"]["length"]] + ([second_span_km] if second_span_km is not None else []),
        "topology_input": topology,
        "topology_sha256": topology_hash,
        "topology": topology["network_name"],
        "equipment": "eqpt_config.json",
        "equipment_sha256": hashlib.sha256((examples / "eqpt_config.json").read_bytes()).hexdigest(),
        "spectrum": json.loads((examples / "eqpt_config.json").read_bytes())["SI"][0],
        "length_source": "Bundled topology" if length_override_km is None else "Engineered override",
        "reference_bandwidth": "signal",
        "channels": parse_channels(output),
        "report": report.strip(),
    }


def parse_channels(output):
    _, heading, table = output.partition(CHANNEL_HEADING)
    if not heading or "OSNR ASE (signal bw, dB)" not in table or "GSNR (signal bw, dB)" not in table:
        raise RuntimeError("GNPy did not report the expected signal-bandwidth channel table.")
    channels = []
    for line in table.splitlines():
        row = CHANNEL_ROW.fullmatch(line)
        if row:
            channel, frequency, power, osnr, nli, gsnr = row.groups()
            channels.append({
                "channel": int(channel),
                "frequency_thz": float(frequency),
                "power_dbm": float(power),
                "osnr_ase_db": float(osnr),
                "snr_nli_db": float(nli),
                "gsnr_db": float(gsnr),
            })
    if [row["channel"] for row in channels] != list(range(1, 77)):
        raise RuntimeError("GNPy did not return all 76 reference channels.")
    return channels
