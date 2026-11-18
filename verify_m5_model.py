"""Verify geographic routing and the M05 engine adapter with independent CLI output."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from time import perf_counter

from gnpy_reference import run_reference
from route_geometry import resolve_network, segmented_route


ROOT = Path(__file__).resolve().parent


def network_fixture():
    return {
        "active_service": "west-east",
        "network": {
            "nodes": [
                {"id": "a", "name": "Kapolei", "lat": 21.335, "lon": -158.058},
                {"id": "b", "name": "Pearl City", "lat": 21.397, "lon": -157.975},
                {"id": "c", "name": "Honolulu", "lat": 21.307, "lon": -157.858},
                {"id": "d", "name": "East Terminal", "lat": 21.29, "lon": -157.76},
                {"id": "e", "name": "North Branch", "lat": 21.5, "lon": -157.98},
            ],
            "links": [
                {"id": "ab", "from": "a", "to": "b", "bends": [[21.36, -158.04]], "override": 25},
                {"id": "bc", "from": "b", "to": "c", "bends": [[21.37, -157.91]], "override": 30},
                {"id": "cd", "from": "c", "to": "d", "bends": [], "override": 35},
                {"id": "be", "from": "b", "to": "e", "bends": []},
            ],
            "services": [{"id": "west-east", "source": "a", "target": "d"}],
        },
    }


def design_fixture(resolved):
    return {
        "route_name": "M05 branched Oahu verification",
        "site_ids": [node["id"] for node in resolved["nodes"]],
        "lengths": resolved["span_overrides"],
        "fibers": [{"type_variety": "SSMF", "loss_coef": 0.2} for _ in resolved["links"]],
        "connections": [{"con_in_db": 0.5, "con_out_db": 0.5} for _ in resolved["links"]],
        "splices": [[0.1], [0.1, 0.1], []],
        "inline_gains": [None, None, None],
        "roadms": [
            {"target_pch_out_db": -20, "path_loss_db": 2},
            {"target_pch_out_db": -20, "path_loss_db": 3},
        ],
    }


def verify_geometry():
    straight = segmented_route([[0, 0], [0, 2]])
    bent = segmented_route([[0, 0], [0, 2]], [[[1, 1]]], lambda path: [False, True])
    assert straight["km"] == [222.638982]
    assert bent["km"][0] > straight["km"][0]
    assert bent["marine"] == [True]
    assert segmented_route([[0, 179.9], [0, -179.9]])["km"][0] < 23
    payload = network_fixture()
    resolved = resolve_network(payload)
    assert resolved["site_names"] == ["Kapolei", "Pearl City", "Honolulu", "East Terminal"]
    assert resolved["degrees"]["b"] == 3
    assert len(segmented_route(resolved["coordinates"], resolved["span_bends"])["km"]) == 3
    payload["network"]["services"][0].update(source="d", target="a")
    reverse = resolve_network(payload)
    assert reverse["span_overrides"] == [35, 30, 25]
    assert reverse["span_bends"][-1] == [[21.36, -158.04]]
    payload["network"]["links"][0].update(connector_in_db=.2, connector_out_db=.8)
    reverse = resolve_network(payload)
    assert reverse["links"][-1]["connector_in_db"] == .8
    assert reverse["links"][-1]["connector_out_db"] == .2
    disconnected = network_fixture()
    disconnected["network"]["links"] = disconnected["network"]["links"][:2]
    assert_invalid(lambda: resolve_network(disconnected))
    assert_invalid(lambda: segmented_route([[0, 0], [0, float("nan")]]))
    assert_invalid(lambda: segmented_route([[True, 0], [0, 1]]))
    return resolved


def assert_invalid(operation):
    try:
        operation()
    except ValueError:
        return
    raise AssertionError("An invalid route was accepted")


def cli_channels(output):
    """Parse separately from the engine adapter, comparing all displayed columns."""
    table = output.split("Channel frequency (THz)", 1)[1]
    rows = []
    for line in table.splitlines()[1:]:
        values = line.split()
        if len(values) == 6 and values[0].isdigit():
            rows.append((int(values[0]), *map(float, values[1:])))
    return rows


def verify_engine(evidence):
    resolved = verify_geometry()
    design = design_fixture(resolved)
    started = perf_counter()
    result = run_reference(design=design)
    elapsed = perf_counter() - started
    assert result["span_lengths_km"] == [25, 30, 35]
    fibers = [element for element in result["topology_input"]["elements"] if element["type"] == "Fiber"]
    assert [round(element["params"]["con_out"], 6) for element in fibers] == [0.6, 0.7, 0.5]
    assert "Roadm_b" in result["report"] and "Roadm_c" in result["report"]
    assert "North Branch" not in result["report"]
    evidence.mkdir(parents=True, exist_ok=True)
    topology_path = evidence / "topology.json"
    equipment_path = evidence / "equipment.json"
    topology_path.write_text(json.dumps(result["topology_input"], indent=2) + "\n", encoding="utf-8")
    equipment_path.write_text(json.dumps(result["equipment_input"], indent=2) + "\n", encoding="utf-8")
    command = [
        sys.executable,
        "-c",
        "from gnpy.tools.cli_examples import transmission_main_example; transmission_main_example()",
        str(topology_path), "Site_A", "Site_B", "--show-channels", "-e", str(equipment_path),
    ]
    independent = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=True, timeout=90)
    actual = [
        tuple(row[key] for key in ("channel", "frequency_thz", "power_dbm", "osnr_ase_db", "snr_nli_db", "gsnr_db"))
        for row in result["channels"]
    ]
    assert len(actual) == 76 and actual == cli_channels(independent.stdout)
    changed = deepcopy(design)
    changed["connections"][0]["con_out_db"] += 1
    alternative = run_reference(design=changed)
    assert alternative["channels"] != result["channels"]
    changed_fiber = next(element for element in alternative["topology_input"]["elements"] if element["uid"] == "Span1")
    assert abs(changed_fiber["params"]["con_out"] - 1.6) < 1e-9
    (evidence / "network.json").write_text(json.dumps(network_fixture(), indent=2) + "\n", encoding="utf-8")
    (evidence / "design.json").write_text(json.dumps(design, indent=2) + "\n", encoding="utf-8")
    (evidence / "cli.stdout.txt").write_text(independent.stdout, encoding="utf-8")
    (evidence / "cli.stderr.txt").write_text(independent.stderr, encoding="utf-8")
    (evidence / "adapter.channels.json").write_text(json.dumps(result["channels"], indent=2) + "\n", encoding="utf-8")
    summary = {
        "command": command,
        "python": sys.version,
        "gnpy": result["engine_version"],
        "runtime_seconds": elapsed,
        "matched_channels": len(actual),
        "reference_bandwidth": result["reference_bandwidth"],
        "topology_file_sha256": hashlib.sha256(topology_path.read_bytes()).hexdigest(),
        "equipment_file_sha256": hashlib.sha256(equipment_path.read_bytes()).hexdigest(),
        "selected_site_ids": [node["id"] for node in resolved["nodes"]],
        "branch_degrees": resolved["degrees"],
        "changed_connector_loss_affects_channels": True,
    }
    (evidence / "verification.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("Passed M05 geometry, branch path, 76 independent CLI channel comparisons and connector-loss sensitivity.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry-only", action="store_true")
    parser.add_argument("--evidence", type=Path, default=ROOT / "evidence" / "m05" / "branched-route")
    args = parser.parse_args()
    if args.geometry_only:
        verify_geometry()
        print("Passed M05 geographic and network validation.")
    else:
        verify_engine(args.evidence)
