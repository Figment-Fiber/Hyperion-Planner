"""Check service add/drop translation and saved browser results against GNPy CLI."""

from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys

from openpyxl import load_workbook

from hyperion import network_simulation, prepare_network, workbook
from verify_m5_model import cli_channels


ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence" / "m05" / "integration"
FIELDS = ("channel", "frequency_thz", "power_dbm", "osnr_ase_db", "snr_nli_db", "gsnr_db")


def independent_cli(result, name):
    folder = EVIDENCE / name
    folder.mkdir(parents=True, exist_ok=True)
    topology = folder / "topology.json"
    equipment = folder / "equipment.json"
    topology.write_text(json.dumps(result["topology_input"], indent=2) + "\n", encoding="utf-8")
    equipment.write_text(json.dumps(result["equipment_input"], indent=2) + "\n", encoding="utf-8")
    command = [sys.executable, "-c",
               "from gnpy.tools.cli_examples import transmission_main_example; transmission_main_example()",
               str(topology), "Site_A", "Site_B", "--show-channels", "-e", str(equipment)]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=True, timeout=90)
    (folder / "cli.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (folder / "cli.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    actual = [tuple(row[key] for key in FIELDS) for row in result["channels"]]
    assert len(actual) == 76 and actual == cli_channels(completed.stdout), name
    (folder / "channels.json").write_text(json.dumps(result["channels"], indent=2) + "\n", encoding="utf-8")
    return {"case": name, "channel_rows": 76, "command": command, "exit_code": completed.returncode}


def ordered_uids(result):
    connections = {edge["from_node"]: edge["to_node"] for edge in result["topology_input"]["connections"]}
    route = ["Site_A"]
    while route[-1] != "Site_B":
        route.append(connections[route[-1]])
        assert len(route) < 100
    return route


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    browser_file = ROOT / "evidence" / "m05" / "browser" / "run.json"
    browser = json.loads(browser_file.read_bytes())
    summary = [independent_cli(browser, "browser-completed-run")]
    original = browser["snapshot"]

    # C is a three-degree ROADM with a local service added toward D.
    added = deepcopy(original)
    added["network"]["services"] = [{"id": "local-add", "source": "C", "target": "D"}]
    added["active_service"] = "local-add"
    added["booster_gain_db"] = 10
    _, _, _, design = prepare_network(added)
    assert design["degree_counts"] == [3, 1]
    add_result = network_simulation(added)
    add_route = ordered_uids(add_result)
    assert add_route.index("Local_Panel_A") < add_route.index("Roadm_C")
    assert add_route.index("Roadm_C") < add_route.index("User_Booster_A") < add_route.index("Span1")
    add_panel = next(element for element in add_result["topology_input"]["elements"]
                     if element["uid"] == "Local_Panel_A")
    assert abs(add_panel["params"]["loss"] - 0.9) < 1e-9
    assert abs(add_result["passive_budget"]["local_add_panel_db"] - 0.9) < 1e-9
    assert add_result["passive_budget"]["local_drop_panel_db"] == 0
    assert abs(add_result["passive_budget"]["total_external_passive_db"] -
               add_result["spans"][0]["passive_loss_db"] - 0.9) < 1e-9
    summary.append(independent_cli(add_result, "local-add-with-booster"))

    dropped = deepcopy(original)
    dropped["network"]["services"] = [{"id": "local-drop", "source": "A", "target": "C"}]
    dropped["active_service"] = "local-drop"
    drop_result = network_simulation(dropped)
    drop_route = ordered_uids(drop_result)
    assert drop_route.index("Roadm_C") < drop_route.index("Local_Panel_B") < drop_route.index("Site_B")
    assert drop_result["passive_budget"]["local_add_panel_db"] == 0
    assert abs(drop_result["passive_budget"]["local_drop_panel_db"] - 0.9) < 1e-9
    summary.append(independent_cli(drop_result, "local-drop"))

    baseline = network_simulation(original)
    variations = []
    spliced = deepcopy(original)
    spliced["network"]["links"][0]["splices"].append(0.3)
    variations.append(("extra-splice", spliced))
    attenuated = deepcopy(original)
    attenuated["network"]["links"][0]["fiber"]["loss_coef"] = 0.24
    variations.append(("fiber-attenuation", attenuated))
    amplified = deepcopy(original)
    amplified["network"]["links"][0]["inline_gain"] = 8
    variations.append(("inline-amplifier", amplified))
    roadm_loss = deepcopy(original)
    roadm_loss["equipment"]["nodes"]["C"]["roadm"]["path_loss_db"] = 25
    variations.append(("roadm-path-loss", roadm_loss))
    roadm_target = deepcopy(original)
    roadm_target["equipment"]["nodes"]["C"]["roadm"]["target_pch_out_db"] = -15
    variations.append(("roadm-output-target", roadm_target))
    for name, payload in variations:
        result = network_simulation(payload)
        assert result["channels"] != baseline["channels"], f"{name} did not affect channel results"
        if name == "extra-splice":
            assert abs(result["passive_budget"]["total_external_passive_db"] -
                       baseline["passive_budget"]["total_external_passive_db"] - 0.3) < 1e-9
        summary.append(independent_cli(result, name))

    # Export must retain local terminations as well as the selected path readings.
    add_result["quality_check"] = {"status": "Not evaluated"}
    add_result["ase_check"] = {"status": "Not evaluated"}
    add_result["catalog_checks"] = []
    book_bytes = workbook(add_result)
    (EVIDENCE / "local-add.xlsx").write_bytes(book_bytes)
    book = load_workbook(BytesIO(book_bytes), data_only=True)
    assert book.sheetnames and "Channel Results" in book.sheetnames
    summary_values = dict(book["Run Summary"].values)
    assert any("local add panel" in str(key) and abs(value - 0.9) < 1e-9
               for key, value in summary_values.items() if isinstance(value, (int, float)))
    assert any("total external passive" in str(key) and value == add_result["passive_budget"]["total_external_passive_db"]
               for key, value in summary_values.items())
    channel_rows = list(book["Channel Results"].values)[1:]
    assert channel_rows == [tuple(row[key] for key in FIELDS) for row in add_result["channels"]]
    (EVIDENCE / "verification.json").write_text(json.dumps({
        "cases": summary,
        "checks": ["source panel/ROADM/booster ordering", "local add/drop passive budget",
                   "splice/attenuation/inline EDFA/ROADM loss and target sensitivity", "workbook generation"],
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Passed {len(summary)} independent 76-channel CLI comparisons, add/drop topology, passive budgets and edit sensitivities.")


if __name__ == "__main__":
    main()
