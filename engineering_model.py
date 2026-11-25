"""Equipment compatibility, panel terminations and revision-linked quantities.

Vendor catalog entries describe documented hardware capabilities. GNPy optical
propagation uses the configured generic modes until a validated vendor mode exists.
"""

from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re


CATALOG_PATH = Path(__file__).with_name("equipment_catalog.json")
VENDORS = ("generic", "ciena", "nokia")
DEFAULT_PROFILES = {
    "generic": "generic-gnpy-reference",
    "ciena": "ciena-6500-s14-wl6e-motr",
    "nokia": "nokia-1830-pss-hc-4cp4t8",
}
DEFAULT_PANEL = {
    "enabled": True,
    "pairs_per_degree": 1,
    "connector_loss_db": 0.5,
    "splices_per_degree": 1,
    "splice_loss_db": 0.1,
}
PANEL_ASSUMPTION = (
    "One mated connector pair at 0.50 dB and one fusion splice at 0.10 dB "
    "per traversed line termination are editable planning assumptions."
)


@lru_cache(maxsize=1)
def catalog():
    return json.loads(CATALOG_PATH.read_bytes())


def finite_number(value, low, high, label):
    if type(value) not in (int, float) or not low <= value <= high:
        raise ValueError(f"{label} must be between {low:g} and {high:g}.")
    return value


def whole_number(value, low, high, label):
    finite_number(value, low, high, label)
    if int(value) != value:
        raise ValueError(f"{label} must be a whole number.")
    return int(value)


def safe_id(value, fallback):
    if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}", value):
        return value
    return fallback


def equipment_settings(payload):
    """Normalize route-ordered equipment without mutating the saved project."""
    names = payload.get("site_names", [])
    count = len(names) or len(payload.get("coordinates", []))
    if count < 2:
        raise ValueError("Equipment requires at least two route sites.")
    supplied = payload.get("equipment")
    if supplied is None:
        supplied = {}
    if not isinstance(supplied, dict):
        raise ValueError("Equipment settings must be an object.")
    vendor = supplied.get("vendor", "generic").lower()
    if vendor not in VENDORS:
        raise ValueError("Choose generic, Ciena or Nokia equipment.")
    service = finite_number(supplied.get("service_gbps", 100), 1, 1600, "Service rate")
    mode = supplied.get("mode", "automatic")
    if mode not in ("automatic", "advanced"):
        raise ValueError("Choose automatic or advanced design.")
    node_input = supplied.get("nodes", [])
    if not isinstance(node_input, (list, dict)):
        raise ValueError("Node equipment must be a list or keyed object.")
    old_ids = ["a", "b"] if count == 2 else ["a", "c", "b"]
    nodes = []
    for index in range(count):
        fallback = old_ids[index] if count <= 3 else f"site-{index + 1}"
        site_ids = payload.get("site_ids", [])
        node_id = site_ids[index] if index < len(site_ids) else fallback
        entry = node_input.get(node_id, {}) if isinstance(node_input, dict) else (
            node_input[index] if index < len(node_input) else {}
        )
        if not isinstance(entry, dict):
            raise ValueError("Each node equipment entry must be an object.")
        node_vendor = entry.get("vendor", vendor).lower()
        if node_vendor not in VENDORS:
            raise ValueError("Choose a supported vendor for each site.")
        endpoint = index in (0, count - 1)
        panel_input = entry.get("panel", {})
        if not isinstance(panel_input, dict):
            raise ValueError("Panel settings must be an object.")
        panel = {**DEFAULT_PANEL, **panel_input}
        if type(panel["enabled"]) is not bool:
            raise ValueError("Panel enabled must be true or false.")
        for key in ("pairs_per_degree", "splices_per_degree"):
            panel[key] = whole_number(panel[key], 0, 24, key.replace("_", " "))
        for key in ("connector_loss_db", "splice_loss_db"):
            finite_number(panel[key], 0, 10, key.replace("_", " "))
        degrees = whole_number(entry.get("degrees", 1 if endpoint else 2), 1, 32, "Line degrees")
        local = entry.get("local_add_drop", endpoint)
        if type(local) is not bool:
            raise ValueError("Local add/drop must be true or false.")
        nodes.append({
            "id": safe_id(entry.get("id", node_id), fallback),
            "name": names[index] if index < len(names) else f"Site {index + 1}",
            "vendor": node_vendor,
            "profile_id": entry.get("profile_id", DEFAULT_PROFILES[node_vendor]),
            "degrees": degrees,
            "local_add_drop": local,
            "panel": panel,
            "role": entry.get("role", "terminal" if endpoint else "roadm"),
        })
    return {"vendor": vendor, "service_gbps": service, "mode": mode, "nodes": nodes}


def panel_connections(payload):
    """Return optical losses per active span end, or None for legacy defaults.

    The aggregate end loss replaces the existing connector allowance in GNPy.
    Panel pigtail splices are separate from the user's cable-plant splice list.
    """
    if payload.get("equipment") is None:
        return None
    nodes = equipment_settings(payload)["nodes"]

    def termination(node):
        panel = node["panel"]
        if not panel["enabled"]:
            return {"connector_db": 0.0, "splice_db": 0.0, "total_db": 0.0}
        connector = panel["pairs_per_degree"] * panel["connector_loss_db"]
        splice = panel["splices_per_degree"] * panel["splice_loss_db"]
        return {"connector_db": connector, "splice_db": splice,
                "total_db": round(connector + splice, 6)}

    ends = [termination(node) for node in nodes]
    return [
        {"con_in_db": left["total_db"], "con_out_db": right["total_db"],
         "connector_db": round(left["connector_db"] + right["connector_db"], 6),
         "panel_splice_db": round(left["splice_db"] + right["splice_db"], 6),
         "panel_loss_db": round(left["total_db"] + right["total_db"], 6)}
        for left, right in zip(ends, ends[1:])
    ]


def profile_compatibility(profile, service, vendor=None):
    """Evaluate documented client handoff capability, not optical reach."""
    reasons = []
    rates = profile.get("client_rates_gbps")
    if vendor and vendor != "generic" and profile.get("vendor", "").lower() not in ("generic", vendor):
        reasons.append(f"{profile.get('vendor')} equipment differs from the selected {vendor.title()} preset.")
    if rates and service not in rates:
        reasons.append(
            f"Does not support the requested single {service:g}GbE client handoff. "
            f"Documented client rates: {', '.join(f'{rate:g}GbE' for rate in rates)}."
        )
    if reasons:
        return {"status": "Fail", "reason": " ".join(reasons)}
    if not rates:
        return {"status": "Not evaluated", "reason": "Client-interface capability evidence is missing."}
    return {"status": "Pass", "reason": (
        "Generic client rate assumption." if profile["id"] == "generic-gnpy-reference" else
        "The published card supports the requested client handoff rate. Optical mode remains unverified."
    )}


def equipment_options(payload):
    settings = equipment_settings(payload)
    return [
        {"node_id": node["id"], "options": [
            {**deepcopy(profile), **(
                profile_compatibility(profile, settings["service_gbps"], node["vendor"])
                if node["role"] == "terminal" or node["local_add_drop"] else
                {"status": "Not applicable", "reason": "Express-only site has no local client transponder."})}
            for profile in catalog()["profiles"]
        ]}
        for node in settings["nodes"]
    ]


def evaluate_design(payload, result):
    """Build transparent compatibility findings and a deduplicated equipment BOM."""
    settings = equipment_settings(payload)
    profiles = {profile["id"]: profile for profile in catalog()["profiles"]}
    issues = []
    bom = []
    sites = []

    def item(site_id, suffix, label, quantity, kind, catalog_id=None, status="unverified"):
        if quantity:
            bom.append({
                "id": f"{site_id}.{suffix}", "site_id": site_id, "description": label,
                "quantity": quantity, "unit": "each", "kind": kind,
                "catalog_id": catalog_id, "unit_cost": None, "currency": None,
                "price_status": "missing", "status": status,
            })

    for node in settings["nodes"]:
        profile = profiles.get(node["profile_id"])
        if profile is None:
            raise ValueError(f"Unknown equipment profile at {node['name']}.")
        has_transponder = node["role"] in ("terminal", "oeo") or node["local_add_drop"]
        transponder_count = 2 if node["role"] == "oeo" else 1
        compatibility = (profile_compatibility(profile, settings["service_gbps"], node["vendor"])
                         if has_transponder else
                         {"status": "Not applicable", "reason": "Express-only site has no local client transponder."})
        if has_transponder and compatibility["status"] != "Pass":
            issues.append({"node_id": node["id"], "check": "Client equipment",
                           **compatibility, "action": "Choose a supported card or change the requested handoff."})
        if has_transponder and profile.get("vendor", "Generic").lower() != "generic":
            issues.append({
                "node_id": node["id"], "check": "Vendor optical mode", "status": "Not evaluated",
                "reason": "Propagation uses generic GNPy optical parameters. A validated vendor operating mode is required.",
                "action": "Supply a sourced mode with launch, spectrum and receiver thresholds.",
            })
        panel = node["panel"]
        termination_count = node["degrees"] + int(node["local_add_drop"])
        used_ports = termination_count * 2 * panel["pairs_per_degree"]
        fiber_positions = termination_count * 2 * max(panel["pairs_per_degree"], panel["splices_per_degree"])
        housings = math.ceil(fiber_positions / 108) if panel["enabled"] else 0
        cassettes = math.ceil(fiber_positions / 36) if panel["enabled"] else 0
        site = {**node, "profile_label": profile["label"], "compatibility": compatibility,
                "panel_used_ports": used_ports if panel["enabled"] else 0,
                "panel_capacity": housings * 108, "panel_housings": housings,
                "panel_cassettes": cassettes, "panel_fiber_positions": fiber_positions if panel["enabled"] else 0,
                "panel_assumption": PANEL_ASSUMPTION}
        sites.append(site)
        item(node["id"], "panel", "Corning Centrix CTX-S1U housing", housings,
             "patch-panel", "corning-centrix-ctx-s1u")
        item(node["id"], "cassette", "Corning Centrix 36-LC pigtailed cassette", cassettes,
             "cassette", "corning-centrix-lc36")
        if panel["enabled"]:
            item(node["id"], "patch-cord", "Generic duplex patch cord",
                 termination_count * panel["pairs_per_degree"], "patch-cord")
        if has_transponder:
            chassis = profile.get("compatible_chassis", [None])[0]
            item(node["id"], "chassis", profile.get("platform", "Generic transport chassis"),
                 1, "chassis", chassis)
            item(node["id"], "transponder", profile.get("card", "Generic transponder"),
                 transponder_count, "transponder", profile["id"])
            item(node["id"], "client-optic", f"Generic {settings['service_gbps']:g}GbE client optic",
                 0 if node["role"] == "oeo" else 1, "optic", "generic-client-optic")
            if profile.get("line_interface_type") != "integrated":
                item(node["id"], "line-interface", profile.get("line_interface_label", "Generic coherent line interface"),
                     transponder_count, "line-interface", "generic-coherent-line-interface")
            if profile.get("line_interface_type") == "separate_line_card":
                issues.append({
                    "node_id": node["id"], "check": "Coherent line termination", "status": "Not evaluated",
                    "reason": "This aggregation card needs a separate compatible coherent line card.",
                    "action": "Select the line card and its validated operating mode.",
                })
        if node["role"] == "roadm":
            photonic = {"ciena": "ciena-rls-rla32", "nokia": "nokia-iroadm32"}.get(node["vendor"])
            item(node["id"], "roadm", "ROADM/WSS photonic function",
                 1, "roadm", photonic)
            item(node["id"], "line-degree", "ROADM line-degree connection",
                 node["degrees"], "line-degree")
            if photonic:
                issues.append({
                    "node_id": node["id"], "check": "WSS impairment model", "status": "Not evaluated",
                    "reason": "Published switching and band capabilities do not specify a complete optical transfer function.",
                    "action": "Use the generic impairment settings or supply validated vendor path-loss and passband data.",
                })
    sections = result.get("sections") or [result]
    topology = {"elements": [element for section in sections for element in section.get("topology_input", {}).get("elements", [])]}
    amplifier_inputs = {element["uid"]: element for element in topology.get("elements", [])
                        if element.get("type") == "Edfa"}
    effective = {element["uid"]: element for section in sections for element in section.get("effective_topology", {}).get("elements", [])
                 if element.get("type") == "Edfa"}
    amplifier_ids = set(amplifier_inputs) | set(effective)
    amplifier_ids.update(re.findall(r"^Edfa (.+)$", result.get("report", ""), re.MULTILINE))
    for amplifier_id in sorted(amplifier_ids):
        element = effective.get(amplifier_id, amplifier_inputs.get(amplifier_id, {}))
        bom.append({"id": f"optical.{amplifier_id}", "site_id": None,
                        "description": f"EDFA {amplifier_id} · {element.get('type_variety', 'engine auto-design')}",
                        "quantity": 1, "unit": "each", "kind": "amplifier",
                        "catalog_id": element.get("type_variety"), "unit_cost": None,
                        "currency": None, "price_status": "missing", "status": "unverified",
                        "placement_source": "explicit topology" if amplifier_id in amplifier_inputs else "GNPy auto-design"})
    for span_index, span in enumerate(result.get("spans", []), 1):
        losses = span.get("splice_losses_db", [])
        if losses:
            item(f"span-{span_index}", "field-splice", "Field fusion splice", len(losses), "splice")
    project_id = safe_id(payload.get("project_id"), "hyperion-route")
    revision = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()[:16]
    project_name = payload.get("route_name", "DWDM Route")
    quantity_export = estimator_quantities(payload, result, project_id, project_name, revision, sites)
    return {
        "schema": "hyperion.equipment-summary/1", "project_id": project_id,
        "project_name": project_name, "revision": revision, "service_gbps": settings["service_gbps"],
        "sites": sites, "issues": issues, "bom": bom, "options": equipment_options(payload),
        "cost_status": "Unit prices and quotes are maintained in Hyperion Estimator.",
        "quantity_export": quantity_export,
        "estimator_equipment": {
            "schema": "hyperion.equipment-quantities/1", "projectId": project_id,
            "projectName": project_name, "revision": revision, "items": deepcopy(bom),
            "import_status": "Equipment extension requires an Estimator importer supporting this schema.",
        },
    }


def summarize_network(payload, active_result=None):
    """Summarize every physical site and link once, independently of service order."""
    from geographiclib.geodesic import Geodesic
    from route_geometry import validate_coordinate

    network = payload.get("network")
    if not isinstance(network, dict):
        raise ValueError("Provide a network for the equipment summary.")
    nodes, links, services = (network.get(key, []) for key in ("nodes", "links", "services"))
    if not isinstance(nodes, list) or not 2 <= len(nodes) <= 20:
        raise ValueError("Equipment summaries support two to 20 sites.")
    node_ids = [node.get("id") for node in nodes if isinstance(node, dict)]
    if len(node_ids) != len(nodes) or len(set(node_ids)) != len(nodes):
        raise ValueError("Sites need unique stable IDs.")
    if any(safe_id(node_id, None) is None for node_id in node_ids):
        raise ValueError("Use valid stable site IDs.")
    if not isinstance(links, list) or not isinstance(services, list):
        raise ValueError("Provide links and services lists.")
    by_id = {node["id"]: node for node in nodes}
    degrees = dict.fromkeys(node_ids, 0)
    endpoints = set()
    for service in services:
        endpoints.update((service.get("source"), service.get("target")))
    link_ids = set()
    segments = []
    quantities = []
    field_splices = []
    inline_amplifiers = []
    for link in links:
        link_id = link.get("id")
        start_id, end_id = link.get("from"), link.get("to")
        if (safe_id(link_id, None) is None or link_id in link_ids or start_id == end_id
                or start_id not in by_id or end_id not in by_id):
            raise ValueError("Each link needs a unique ID and two existing, distinct endpoint sites.")
        link_ids.add(link_id)
        degrees[start_id] += 1
        degrees[end_id] += 1
        points = [[by_id[start_id]["lat"], by_id[start_id]["lon"]],
                  *link.get("bends", []), [by_id[end_id]["lat"], by_id[end_id]["lon"]]]
        for point in points:
            validate_coordinate(point)
        routed_km = math.fsum(Geodesic.WGS84.Inverse(*left, *right)["s12"] / 1000
                              for left, right in zip(points, points[1:]))
        override = link.get("override")
        if override is not None:
            finite_number(override, 0.000001, 40000, "Engineered span length")
        length = routed_km if override is None else override
        if length <= 0:
            raise ValueError("A span must have a positive length.")
        segment = {
            "id": link_id, "fromSiteId": start_id, "toSiteId": end_id, "method": "unspecified",
            "lengthM": round(length * 1000, 6),
            "lengthSource": "Engineered override" if override is not None else "Segmented WGS84",
            "status": "unverified",
        }
        segments.append(segment)
        losses = link.get("splices", [])
        if not isinstance(losses, list):
            raise ValueError("Splices must be a list.")
        for loss in losses:
            finite_number(loss, 0, 10, "Splice loss")
        quantities.extend([
            {"sourceObjectId": link_id + ".fiber", "segmentId": link_id, "kind": "fiber-length",
             "description": "Designed optical fiber length", "unit": "m",
             "quantity": segment["lengthM"], "itemKey": None, "status": "unverified"},
            {"sourceObjectId": link_id + ".splice", "segmentId": link_id, "kind": "splice-point",
             "description": "Entered field splice points", "unit": "each",
             "quantity": len(losses), "itemKey": None, "status": "unverified"},
        ])
        if losses:
            field_splices.append({
                "id": link_id + ".field-splices", "site_id": None, "segment_id": link_id,
                "description": "Field fusion splice", "quantity": len(losses), "unit": "each",
                "kind": "splice", "catalog_id": None, "unit_cost": None, "currency": None,
                "price_status": "missing", "status": "unverified",
            })
        if link.get("inline_gain") is not None:
            finite_number(link["inline_gain"], 8, 35, "Inline gain")
            inline_amplifiers.append({
                "id": link_id + ".inline-edfa", "site_id": None, "segment_id": link_id,
                "description": "Configured midpoint EDFA", "quantity": 1, "unit": "each",
                "kind": "amplifier", "catalog_id": "generic-edfa", "unit_cost": None,
                "currency": None, "price_status": "missing", "status": "unverified",
            })
    projected = deepcopy(payload)
    source_equipment = projected.setdefault("equipment", {})
    original = source_equipment.get("nodes", {})
    if not isinstance(original, dict):
        raise ValueError("Saved network node equipment must be keyed by stable site ID.")
    projected["site_ids"] = node_ids
    projected["site_names"] = [node.get("name", node["id"]) for node in nodes]
    projected["coordinates"] = [[node["lat"], node["lon"]] for node in nodes]
    source_equipment["nodes"] = [
        {**original.get(node_id, {}), "id": node_id, "degrees": max(1, degrees[node_id]),
         "local_add_drop": node_id in endpoints or original.get(node_id, {}).get("role") == "oeo",
         "role": original.get(node_id, {}).get("role", "roadm" if degrees[node_id] > 1 else "terminal")}
        for node_id in node_ids
    ]
    summary = evaluate_design(projected, {})
    # Installed direction settings apply to all physical neighbors, including inactive services.
    for node_id in node_ids:
        cfg = original.get(node_id, {}).get("amplifiers", {})
        neighbors = [link["to"] if link["from"] == node_id else link["from"]
                     for link in links if node_id in (link["from"], link["to"])]
        for neighbor in neighbors:
            for side in ("incoming", "outgoing"):
                setting = {**cfg.get(side, {}), **cfg.get("by_neighbor", {}).get(neighbor, {}).get(side, {})}
                if not setting.get("enabled", False):
                    continue
                summary["bom"].append({"id": f"{node_id}.amp.{side}.{neighbor}", "site_id": node_id,
                    "neighbor_id": neighbor, "side": side, "description": "Configured directional EDFA",
                    "quantity": 1, "unit": "each", "kind": "amplifier", "catalog_id": setting.get("model", "generic-edfa"),
                    "unit_cost": None, "currency": None, "price_status": "missing", "status": "unverified",
                    "quantity_scope": "Configured full network"})
    for node in summary["sites"]:
        node["connected_degrees"] = degrees[node["id"]]
        if degrees[node["id"]] == 0:
            summary["issues"].append({
                "node_id": node["id"], "check": "Physical connectivity", "status": "Review",
                "reason": "This site has no connected spans.", "action": "Connect or remove the site.",
            })
    project_id = safe_id(payload.get("project_id"), "hyperion-route")
    project_name = payload.get("route_name", "DWDM Route")
    source_payload = {key: value for key, value in payload.items() if key != "equipment_summary"}
    source_hash = hashlib.sha256(json.dumps(source_payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
    revision = str(payload.get("revision", source_hash[:16]))
    if safe_id(revision, None) is None:
        raise ValueError("Use a valid project revision.")
    summary.update(project_id=project_id, project_name=project_name, revision=revision,
                   source_hash=source_hash, source_snapshot=source_payload, scope="Full saved physical network")
    summary["bom"].extend(field_splices + inline_amplifiers)
    summary["quantity_export"].update(
        projectId=project_id, projectName=project_name, revision=revision,
        segments=segments, quantities=quantities,
    )
    summary["actual_service_amplifiers"] = []
    summary["inventory_status"] = "Planned equipment; optical amplifier inventory pending simulation."
    if active_result:
        active_summary = evaluate_design(projected, active_result)
        actual_amplifiers = [item for item in active_summary["bom"] if item["kind"] == "amplifier"]
        resolved = active_result.get("selected_path", {})
        route_links = resolved.get("links", [])
        route_nodes = resolved.get("nodes", [])
        service_id = active_result.get("service_id", payload.get("active_service", "selected-service"))
        existing_items = {item["id"]: item for item in summary["bom"]}
        for amplifier in actual_amplifiers:
            engine_id = amplifier["id"].removeprefix("optical.")
            item = deepcopy(amplifier)
            item.update(engine_element_id=engine_id, service_id=service_id, quantity_scope="Modeled selected service")
            m6_midpoint = re.fullmatch(r"ILA_(\d+)", engine_id)
            m6_node = re.fullmatch(r"Amp_(.+)_(incoming|outgoing)", engine_id)
            midpoint = re.fullmatch(r"Span(\d+)_User_ILA", engine_id)
            receiver = re.fullmatch(r"Edfa(\d+)", engine_id)
            outgoing = re.search(r"_to_Span(\d+)$", engine_id)
            if m6_node and any(node["id"] == m6_node[1] for node in route_nodes):
                index = next(i for i, node in enumerate(route_nodes) if node["id"] == m6_node[1])
                neighbor_index = index - 1 if m6_node[2] == "incoming" else index + 1
                if 0 <= neighbor_index < len(route_nodes):
                    neighbor = route_nodes[neighbor_index]["id"]
                    item.update(id=f"{m6_node[1]}.amp.{m6_node[2]}.{neighbor}", site_id=m6_node[1],
                                neighbor_id=neighbor, side=m6_node[2])
            elif m6_midpoint and int(m6_midpoint[1]) <= len(route_links):
                link = route_links[int(m6_midpoint[1]) - 1]
                item.update(id=link["id"] + ".inline-edfa", segment_id=link["id"])
            elif midpoint and int(midpoint[1]) <= len(route_links):
                link = route_links[int(midpoint[1]) - 1]
                item.update(id=link["id"] + ".inline-edfa", segment_id=link["id"])
            elif receiver and int(receiver[1]) <= len(route_links) and int(receiver[1]) < len(route_nodes):
                index = int(receiver[1])
                link, node = route_links[index - 1], route_nodes[index]
                item.update(id=f"{link['id']}.receive-at.{node['id']}",
                            segment_id=link["id"], site_id=node["id"])
            elif engine_id == "User_Booster_A" and route_links and route_nodes:
                link, node = route_links[0], route_nodes[0]
                item.update(id=f"{node['id']}.booster-to.{link['id']}",
                            segment_id=link["id"], site_id=node["id"])
            elif outgoing and int(outgoing[1]) <= len(route_links) and int(outgoing[1]) <= len(route_nodes):
                index = int(outgoing[1]) - 1
                link, node = route_links[index], route_nodes[index]
                item.update(id=f"{node['id']}.booster-to.{link['id']}",
                            segment_id=link["id"], site_id=node["id"])
            else:
                item["id"] = f"service.{service_id}.amplifier.{hashlib.sha256(engine_id.encode()).hexdigest()[:12]}"
            existing_items[item["id"]] = item
            summary["actual_service_amplifiers"].append(item)
        summary["bom"] = list(existing_items.values())
        summary["active_service_id"] = service_id
        summary["inventory_status"] = "Planned network plus modeled selected-service amplifier inventory."
    summary["estimator_equipment"].update(
        projectId=project_id, projectName=project_name, revision=revision,
        sites=[{"id": node["id"], "name": node["name"]} for node in summary["sites"]],
        segments=segments, items=deepcopy(summary["bom"]),
        import_status="Import with estimator_adapter.js",
        inventory_status=summary["inventory_status"],
    )
    return summary


def estimator_quantities(payload, result, project_id, project_name, revision, sites):
    """Produce the Routes v1 fragment supported by the existing Estimator importer."""
    segments = []
    quantities = []
    for index, span in enumerate(result.get("spans", [])):
        segment_id = f"span-{index + 1}"
        segments.append({
            "id": segment_id, "fromSiteId": sites[index]["id"], "toSiteId": sites[index + 1]["id"],
            "method": "unspecified", "lengthM": span["simulation_km"] * 1000,
            "lengthSource": span.get("source", "Route design"), "status": "unverified",
        })
        quantities.extend([
            {"sourceObjectId": segment_id + ".fiber", "segmentId": segment_id, "kind": "fiber-length",
             "description": "Designed optical fiber length", "unit": "m",
             "quantity": span["simulation_km"] * 1000, "itemKey": None, "status": "unverified"},
            {"sourceObjectId": segment_id + ".splice", "segmentId": segment_id, "kind": "splice-point",
             "description": "Entered field splice points", "unit": "each",
             "quantity": len(span.get("splice_losses_db", [])), "itemKey": None, "status": "unverified"},
        ])
    return {
        "schema": "hyperion.quantities/1", "sourceApplication": "routes",
        "projectId": project_id, "projectName": project_name, "revision": revision, "synthetic": False,
        "sites": [{"id": site["id"], "name": site["name"]} for site in sites],
        "segments": segments, "quantities": quantities,
        "assumptions": [
            "Quantities come from the selected service's modeled route and require engineering verification.",
            "Construction quantities and costs are outside this equipment summary.",
            "The equipment quantity extension is versioned separately from the Routes v1 segment importer.",
        ],
    }
