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


def run_reference(length_override_km=None, second_span_km=None, booster_gain_db=None, tx_power_dbm=None,
                  span_splices=None, roadm_connectors=None, inline_gains=None, preamp_gain_db=None):
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
    equipment_path = examples / "eqpt_config.json"
    equipment = json.loads(equipment_path.read_bytes())
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
        if roadm_connectors:
            ingress, egress = roadm_connectors
            if ingress is not None:
                span["params"]["con_out"] = ingress
            if egress is not None:
                second["params"]["con_in"] = egress
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

    if span_splices:
        for index, losses in enumerate(span_splices, 1):
            fiber = next(element for element in topology["elements"] if element["uid"] == f"Span{index}")
            fiber["params"]["con_out"] += math.fsum(losses)

    if length_override_km is not None:
        span["params"]["length"] = length_override_km
    spans = [element for element in topology["elements"] if element["type"] == "Fiber"]
    lengths = [element["params"]["length"] for element in spans]
    for fiber, gain in zip(spans, inline_gains or []):
        if gain is None:
            continue
        uid = fiber["uid"]
        downstream = deepcopy(fiber)
        downstream["uid"] = uid + "_After_ILA"
        downstream["params"]["length"] /= 2
        fiber["params"]["length"] /= 2
        fiber["params"]["con_out"] = 0
        downstream["params"]["con_in"] = 0
        amplifier = configured_edfa(uid + "_User_ILA", gain)
        outgoing = next(link for link in topology["connections"] if link["from_node"] == uid)
        destination = outgoing["to_node"]
        outgoing["to_node"] = amplifier["uid"]
        topology["elements"].extend([amplifier, downstream])
        topology["connections"].extend([
            {"from_node": amplifier["uid"], "to_node": downstream["uid"]},
            {"from_node": downstream["uid"], "to_node": destination},
        ])
    if preamp_gain_db is not None:
        uid = f"Edfa{len(spans)}"
        receiver_stage = next(element for element in topology["elements"] if element["uid"] == uid)
        receiver_stage.update(configured_edfa(uid, preamp_gain_db))

    with TemporaryDirectory() as run_dir:
        topology_path = bundled
        if (length_override_km is not None or second_span_km is not None or booster_gain_db is not None
                or span_splices or inline_gains or preamp_gain_db is not None):
            topology_path = Path(run_dir) / bundled.name
            topology_path.write_text(json.dumps(topology, indent=2) + "\n", encoding="utf-8")
        topology_hash = hashlib.sha256(topology_path.read_bytes()).hexdigest()
        options = []
        manual_gain_mode = any(gain is not None for gain in inline_gains or []) or preamp_gain_db is not None
        if tx_power_dbm is not None:
            if type(tx_power_dbm) not in (int, float) or not -20 <= tx_power_dbm <= 8:
                raise ValueError("Enter a generic transmitter output between −20 and +8 dBm/channel.")
            equipment["SI"][0]["tx_power_dbm"] = tx_power_dbm
        if manual_gain_mode:
            equipment["Span"][0]["power_mode"] = False
        if tx_power_dbm is not None or manual_gain_mode:
            equipment_path = Path(run_dir) / equipment_path.name
            equipment_path.write_text(json.dumps(equipment), encoding="utf-8")
            options = ["-e", str(equipment_path)]
        equipment_hash = hashlib.sha256(equipment_path.read_bytes()).hexdigest()
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
                *options,
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
        "span_length_km": round(math.fsum(lengths), 6),
        "span_lengths_km": lengths,
        "topology_input": topology,
        "topology_sha256": topology_hash,
        "topology": topology["network_name"],
        "equipment": "eqpt_config.json",
        "equipment_sha256": equipment_hash,
        "manual_gain_mode": manual_gain_mode,
        "equipment_input": equipment if options else None,
        "spectrum": equipment["SI"][0],
        "length_source": "Bundled topology" if length_override_km is None else "Engineered override",
        "reference_bandwidth": "signal",
        "channels": parse_channels(output),
        "report": report.strip(),
    }


def configured_edfa(uid, gain):
    if type(gain) not in (int, float) or not 8 <= gain <= 35:
        raise ValueError("Enter an amplifier gain between 8 and 35 dB.")
    variety = "std_low_gain" if gain <= 16 else "std_medium_gain" if gain <= 26 else "std_high_gain"
    return {"uid": uid, "type": "Edfa", "type_variety": variety,
            "operational": {"gain_target": gain, "tilt_target": 0, "out_voa": 0}}


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
