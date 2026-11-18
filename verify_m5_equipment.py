"""Regression checks for full-network panels, compatibility and quantity handoff."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from engineering_model import evaluate_design, panel_connections, summarize_network


def fixture():
    return {
        "version": 2, "project_id": "equipment-test", "revision": 1, "route_name": "Equipment test",
        "active_service": "ac",
        "network": {
            "nodes": [
                {"id": "a", "name": "A", "lat": 21.3, "lon": -158.1},
                {"id": "b", "name": "B", "lat": 21.4, "lon": -158.0},
                {"id": "c", "name": "C", "lat": 21.5, "lon": -157.9},
                {"id": "d", "name": "D", "lat": 21.6, "lon": -158.0},
            ],
            "links": [
                {"id": "ab", "from": "a", "to": "b", "override": 20, "splices": [.1]},
                {"id": "bc", "from": "b", "to": "c", "override": 25, "splices": []},
                {"id": "bd", "from": "b", "to": "d", "override": 30, "splices": [.1, .1],
                 "inline_gain": 8},
            ],
            "services": [{"id": "ac", "source": "a", "target": "c"}],
        },
        "equipment": {"vendor": "ciena", "service_gbps": 400, "mode": "advanced", "nodes": {
            "a": {"profile_id": "ciena-2x100g-motr"},
        }},
    }


def main():
    project = fixture()
    summary = summarize_network(project)
    assert len(summary["sites"]) == 4
    junction = next(site for site in summary["sites"] if site["id"] == "b")
    assert junction["role"] == "roadm" and junction["degrees"] == 3
    assert junction["panel_housings"] == 1 and junction["panel_used_ports"] == 6
    assert len([item for item in summary["bom"] if item["id"] == "b.panel"]) == 1
    assert {span["id"] for span in summary["quantity_export"]["segments"]} == {"ab", "bc", "bd"}
    assert any(issue["node_id"] == "a" and issue["status"] == "Fail" for issue in summary["issues"])
    assert any(item["id"] == "bd.inline-edfa" for item in summary["bom"])
    assert next(item for item in summary["bom"] if item["id"] == "bd.field-splices")["quantity"] == 2
    assert all(item["unit_cost"] is None for item in summary["bom"])
    assert "pending simulation" in summary["inventory_status"]
    panel_edit = deepcopy(project)
    panel_edit["equipment"]["nodes"]["b"] = {
        "profile_id": "ciena-2x100g-motr",
        "panel": {"pairs_per_degree": 8},
    }
    panel_summary = summarize_network(panel_edit)
    junction = next(site for site in panel_summary["sites"] if site["id"] == "b")
    assert junction["panel_used_ports"] == 48 and junction["panel_cassettes"] == 2
    assert next(row for row in panel_summary["bom"] if row["id"] == "b.patch-cord")["quantity"] == 24
    assert junction["compatibility"]["status"] == "Not applicable"
    assert not any(issue["node_id"] == "b" and issue["check"] in
                   ("Client equipment", "Vendor optical mode") for issue in panel_summary["issues"])
    active_project = deepcopy(project)
    active_project["active_service"] = "ad"
    active_project["network"]["services"].append({"id": "ad", "source": "a", "target": "d"})
    active_result = {
        "service_id": "ad",
        "selected_path": {
            "nodes": [active_project["network"]["nodes"][index] for index in (0, 1, 3)],
            "links": [active_project["network"]["links"][index] for index in (0, 2)],
        },
        "topology_input": {"elements": [
            {"uid": "Edfa1", "type": "Edfa", "type_variety": "std_low_gain"},
            {"uid": "Edfa2", "type": "Edfa", "type_variety": "std_low_gain"},
            {"uid": "Span2_User_ILA", "type": "Edfa", "type_variety": "std_low_gain"},
        ]},
        "report": "Edfa Edfa1\nEdfa Edfa2\nEdfa Span2_User_ILA\nEdfa Edfa_booster_Roadm_1_to_Span2",
    }
    active_summary = summarize_network(active_project, active_result)
    assert len(active_summary["actual_service_amplifiers"]) == 4
    assert len([item for item in active_summary["bom"] if item["id"] == "bd.inline-edfa"]) == 1
    assert len([item for item in active_summary["bom"] if item["kind"] == "amplifier"]) == 4
    assert any(item["id"] == "bd.receive-at.d" for item in active_summary["estimator_equipment"]["items"])
    changed_direction = deepcopy(active_result)
    changed_direction["topology_input"]["elements"].reverse()
    assert [item["id"] for item in summarize_network(active_project, changed_direction)["actual_service_amplifiers"]] == [
        item["id"] for item in active_summary["actual_service_amplifiers"]]

    active = {"site_ids": ["a", "b", "c"], "site_names": ["A", "B", "C"],
              "equipment": {"nodes": [{}, {}, {}]}}
    assert panel_connections(active)[0]["con_in_db"] == .6
    active["equipment"]["nodes"][1]["panel"] = {"connector_loss_db": .8}
    assert panel_connections(active)[0]["con_out_db"] == .9
    active["equipment"]["nodes"][1]["panel"] = {"splice_loss_db": float("nan")}
    try:
        panel_connections(active)
    except ValueError:
        pass
    else:
        raise AssertionError("Non-finite panel losses must be rejected")

    project["equipment_summary"] = summary
    changed = deepcopy(project)
    changed["revision"] = 2
    changed["network"]["links"][0]["splices"].append(.1)
    changed["equipment_summary"] = summarize_network(changed)
    with TemporaryDirectory() as temp:
        first, second = Path(temp) / "first.json", Path(temp) / "second.json"
        first.write_text(json.dumps(project), encoding="utf8")
        second.write_text(json.dumps(changed), encoding="utf8")
        script = """
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {importRoutesProject,reconcileRoutesImport} = require('./estimator_adapter.js');
const first=JSON.parse(fs.readFileSync(process.argv[1]));
const second=JSON.parse(fs.readFileSync(process.argv[2]));
const estimate=importRoutesProject(first);
const row=estimate.quantities.find(row=>row.sourceObjectId==='ab.field-splices');
row.unitPrice=20;row.currency='USD';row.priceSource='test quote';
const next=reconcileRoutesImport(estimate,second);
assert.equal(next.quantities.find(row=>row.sourceObjectId==='ab.field-splices').extendedCost,40);
assert.equal(row.quantity,1);
assert(next.changes.some(row=>row.sourceObjectId==='ab.field-splices'&&row.change==='changed'));
const sameRevisionEdit=structuredClone(first);
sameRevisionEdit.equipment.service_gbps=800;
assert.throws(()=>importRoutesProject(sameRevisionEdit),/inputs changed/);
first.revision=9;
assert.throws(()=>importRoutesProject(first),/stale/);
console.log('Saved project import, stable quantity updates, quote retention and stale summary rejection passed.');
"""
        subprocess.run(["node", "-e", script, str(first), str(second)], check=True,
                       cwd=Path(__file__).parent)
    print("Full-network panel, sourced compatibility, branch quantities and Estimator handoff passed.")


if __name__ == "__main__":
    main()
