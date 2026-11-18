"""Local HTTP entry point for Hyperion Routes."""

import argparse
from collections import OrderedDict
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import math
import copy
import re
from pathlib import Path
from threading import Lock
from uuid import uuid4

import xlsxwriter
from geographiclib.geodesic import Geodesic

from gnpy_reference import run_reference
from route_geometry import resolve_network, segmented_route


ROOT = Path(__file__).resolve().parent
STATIC = {
    "/": ("hyperion.html", "text/html; charset=utf-8"),
    "/app.js": ("hyperion.js", "text/javascript; charset=utf-8"),
    "/app.css": ("hyperion.css", "text/css; charset=utf-8"),
    "/equipment-catalog.json": ("equipment_catalog.json", "application/json; charset=utf-8"),
    "/leaflet.js": ("assets/leaflet/leaflet.js", "text/javascript; charset=utf-8"),
    "/leaflet.css": ("assets/leaflet/leaflet.css", "text/css; charset=utf-8"),
    "/logo.png": ("assets/branding/Hyperion_Planner_Logo.png", "image/png"),
    "/favicon.ico": ("assets/branding/Hyperion_Planner.ico", "image/x-icon"),
}
METRICS = {
    "power_dbm": "Power (dBm)",
    "osnr_ase_db": "ASE OSNR (signal BW, dB)",
    "snr_nli_db": "SNR NLI (signal BW, dB)",
    "gsnr_db": "GSNR (signal BW, dB)",
}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
RUNS = OrderedDict()
RUNS_LOCK = Lock()


@lru_cache(maxsize=1)
def bundled_run():
    return run_reference()


def geographic_spans(points):
    if (
        not isinstance(points, list) or len(points) not in (2, 3)
        or any(not isinstance(point, list) or len(point) != 2 for point in points)
        or any(type(lat) not in (int, float) or type(lon) not in (int, float)
               or not -90 <= lat <= 90 or not -180 <= lon <= 180 for lat, lon in points)
    ):
        raise ValueError("Provide two or three valid latitude/longitude pairs.")
    return [
        round(Geodesic.WGS84.Inverse(*start, *end)["s12"] / 1000, 6)
        for start, end in zip(points, points[1:])
    ]


@lru_cache(maxsize=1)
def land_rings():
    features = json.loads((ROOT / "assets/land-50m.geojson").read_bytes())["features"]
    rings = []
    for feature in features:
        geometry = feature["geometry"]
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        for polygon in polygons:
            ring = polygon[0]
            longitudes, latitudes = zip(*ring)
            rings.append((min(longitudes), max(longitudes), min(latitudes), max(latitudes), ring))
    return rings


def on_land(lat, lon):
    for west, east, south, north, ring in land_rings():
        if not west <= lon <= east or not south <= lat <= north:
            continue
        inside = False
        for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                inside = not inside
        if inside:
            return True
    return False


def marine_screening(points):
    results = []
    for start, end in zip(points, points[1:]):
        line = Geodesic.WGS84.InverseLine(*start, *end)
        intervals = max(1, min(256, math.ceil(line.s13 / 2000)))
        crossing = False
        for index in range(intervals):
            point = line.Position(line.s13 * (index + 0.5) / intervals)
            if not on_land(point["lat2"], point["lon2"]):
                crossing = True
                break
        results.append(crossing)
    return results


def simulation(payload):
    if "network" in payload:
        return network_simulation(payload)
    if "coordinates" in payload:
        return geographic_simulation(payload)
    override = payload.get("length_override_km")
    points = payload["points"]
    if (
        not isinstance(points, list) or len(points) != 2
        or any(not isinstance(point, list) or len(point) != 2 for point in points)
        or any(type(value) not in (int, float) or not 0 <= value <= 1
               for point in points for value in point)
    ):
        raise ValueError("Provide two positions on the schematic map.")
    a, b = points
    names = payload.get("site_names", ["Site_A", "Site_B"])
    if (not isinstance(names, list) or len(names) != 2
        or any(not isinstance(name, str) or not name.strip() or len(name) > 60 for name in names)):
        raise ValueError("Provide two site names of up to 60 characters.")
    estimate = round(math.hypot((b[0] - a[0]) * 120, (b[1] - a[1]) * 70), 1)
    use_map = payload.get("use_map_estimate") is True
    if use_map:
        override = estimate
    result = bundled_run() if override is None else run_reference(override)
    return {
        **result,
        "points": points,
        "site_names": [name.strip() for name in names],
        "map_estimate_km": estimate,
        "length_source": "Schematic map estimate" if use_map else result["length_source"],
        "baseline": bundled_run() if override is not None else None,
    }


def prepare_network(payload):
    """Validate a saved project and derive the active service inputs."""
    from engineering_model import panel_connections
    resolved = resolve_network(payload)
    geometry = segmented_route(resolved["coordinates"], resolved["span_bends"], marine_screening)
    projected = copy.deepcopy(payload)
    projected.update(coordinates=resolved["coordinates"], site_names=resolved["site_names"],
                     site_ids=[node["id"] for node in resolved["nodes"]])
    equipment = projected.setdefault("equipment", {})
    original_nodes = equipment.get("nodes", {})
    equipment["nodes"] = [
        {**copy.deepcopy(original_nodes.get(node["id"], {})),
         "id": node["id"], "degrees": resolved["degrees"][node["id"]],
         "local_add_drop": index in (0, len(resolved["nodes"]) - 1)}
        for index, node in enumerate(resolved["nodes"])
    ]
    connections = panel_connections(projected)
    lengths, splices, gains, fibers = [], [], [], []
    for index, link in enumerate(resolved["links"]):
        length = link.get("override") or geometry["km"][index]
        if payload.get("reference_case") and len(resolved["links"]) == 1 and link.get("override") is None:
            length = 80
        losses = link.get("splices", [])
        if (not isinstance(losses, list) or len(losses) > 100 or
                any(type(loss) not in (int, float) or not 0 <= loss <= 10 for loss in losses)):
            raise ValueError("Splice losses must be 0–10 dB, with up to 100 entries per span.")
        gain = link.get("inline_gain")
        if gain is not None and (type(gain) not in (int, float) or not 8 <= gain <= 35):
            raise ValueError("Inline gain must be 8–35 dB.")
        lengths.append(length)
        splices.append(losses)
        gains.append(gain)
        fibers.append(link.get("fiber", {"type_variety": "SSMF", "loss_coef": 0.2}))
        for field, target in (("connector_in_db", "con_in_db"), ("connector_out_db", "con_out_db")):
            value = link.get(field)
            if value is not None:
                if type(value) not in (int, float) or not 0 <= value <= 10:
                    raise ValueError("Span end loss must be between 0 and 10 dB.")
                connections[index][target] = value
    roadms = [
        equipment["nodes"][index].get("roadm", {})
        for index in range(1, len(resolved["nodes"]) - 1)
    ]
    design = {"lengths": lengths, "connections": connections, "splices": splices, "inline_gains": gains,
              "fibers": fibers, "roadms": roadms, "site_ids": projected["site_ids"],
              "degree_counts": [resolved["degrees"][node["id"]] for node in resolved["nodes"]],
              "site_configs": [node.get("roadm", {}) for node in equipment["nodes"]],
              "terminal_panel_losses": [connections[0]["con_in_db"], connections[-1]["con_out_db"]],
              "route_name": "Hyperion selected service",
              "booster_gain_db": payload.get("booster_gain_db"), "preamp_gain_db": payload.get("preamp_gain_db")}
    return resolved, geometry, projected, design


def network_preview(payload):
    from engineering_model import equipment_options, summarize_network
    from zones_screening import screen_routes
    resolved, geometry, projected, design = prepare_network(payload)
    summary = summarize_network(payload)
    return {"geometry": geometry, "route": resolved, "options": equipment_options(projected),
            "zones": screen_routes(geometry["paths"]), "design": design, "equipment_summary": summary}


@lru_cache(maxsize=16)
def propagate_design(design_json, transmitter_power):
    design = json.loads(design_json)
    return run_reference(booster_gain_db=design.get("booster_gain_db"),
                         tx_power_dbm=transmitter_power,
                         preamp_gain_db=design.get("preamp_gain_db"), design=design)


def network_simulation(payload):
    from engineering_model import evaluate_design, summarize_network
    from zones_screening import screen_routes
    resolved, geometry, projected, design = prepare_network(payload)
    result = copy.deepcopy(propagate_design(json.dumps(design, sort_keys=True, allow_nan=False),
                                           payload.get("tx_power_dbm")))
    spans = []
    for index, link in enumerate(resolved["links"]):
        fiber = design["fibers"][index]
        connections = design["connections"][index]
        connector_loss = connections["con_in_db"] + connections["con_out_db"]
        splice_loss = math.fsum(design["splices"][index])
        spans.append({
            "id": link["id"], "from": resolved["site_names"][index], "to": resolved["site_names"][index + 1],
            "geodesic_km": geometry["km"][index], "simulation_km": design["lengths"][index],
            "source": "Engineered override" if link.get("override") is not None else "Bundled topology" if payload.get("reference_case") else "Segmented WGS84",
            "splice_losses_db": design["splices"][index], "splice_total_db": splice_loss,
            "connector_loss_db": connector_loss, "inline_gain_db": design["inline_gains"][index],
            "amplifier_warning": design["lengths"][index] > 80 and design["inline_gains"][index] is None,
            "marine_screening": geometry["marine"][index], "route_vertices": geometry["paths"][index],
            "passive_loss_db": round(design["lengths"][index] * fiber.get("loss_coef", 0.2) + connector_loss + splice_loss, 6),
        })
    result.update(
        route_name=payload.get("route_name", "DWDM Route"), project_id=payload.get("project_id"),
        revision=payload.get("revision", 1), points=resolved["coordinates"], site_names=resolved["site_names"],
        map_estimate_km=math.fsum(geometry["km"]), spans=spans, baseline=None,
        length_source="Per-span configuration", service_id=resolved["service_id"],
        selected_path=resolved, zones=screen_routes(geometry["paths"]), snapshot=payload,
    )
    result["engineering"] = evaluate_design(projected, result)
    local_losses = [loss if degree > 1 else 0 for loss, degree in
                    zip(design["terminal_panel_losses"], (design["degree_counts"][0], design["degree_counts"][-1]))]
    result["passive_budget"] = {
        "line_spans_db": round(math.fsum(span["passive_loss_db"] for span in spans), 6),
        "local_add_panel_db": local_losses[0], "local_drop_panel_db": local_losses[1],
        "total_external_passive_db": round(math.fsum(span["passive_loss_db"] for span in spans) + math.fsum(local_losses), 6),
        "scope": "External fiber, connectors and splices; ROADM internal loss and amplifier behavior are in the GNPy report.",
    }
    result["equipment_summary"] = summarize_network(payload, result)
    profiles = {item["type_variety"]: item for item in result["equipment_input"]["Edfa"]}
    for block in re.split(r"(?m)^Edfa ", result["report"])[1:]:
        uid = block.splitlines()[0]
        variety = re.search(r"type_variety:\s+(\S+)", block)
        gain = re.search(r"effective gain\(dB\):\s+(-?[\d.]+)", block)
        power = re.search(r"Power Out \(dBm\):\s+(-?[\d.]+)", block)
        if not variety or not gain:
            continue
        profile = profiles.get(variety.group(1), {})
        effective_gain = float(gain.group(1))
        lower, upper = profile.get("gain_min"), profile.get("gain_flatmax")
        detail = ""
        if lower is not None and effective_gain < lower - .01:
            detail = f"Effective gain {effective_gain} dB is below the profile's {lower} dB minimum. GNPy may add input attenuation."
        if upper is not None and effective_gain > upper + .01:
            detail = f"Effective gain {effective_gain} dB exceeds the profile's {upper} dB flat-gain limit."
        if power and profile.get("p_max") is not None and float(power.group(1)) >= profile["p_max"] - .1:
            detail += f" Total output is near the {profile['p_max']} dBm profile limit."
        if detail:
            result["engineering"]["issues"].append({
                "node_id": uid, "check": "Amplifier operating range", "status": "Review",
                "reason": detail, "action": "Inspect effective gain, input attenuation and output power; select a suitable stage and rerun.",
            })
    for index, node in enumerate(projected["equipment"]["nodes"]):
        roadm = node.get("roadm", {})
        if resolved["degrees"][node["id"]] > 1:
            low, high = roadm.get("band_min_thz", 191.3), roadm.get("band_max_thz", 196.1)
            if (type(low) not in (int, float) or type(high) not in (int, float)
                    or not 180 <= low < high <= 210):
                raise ValueError("WSS lower band edge must be below its upper edge within 180–210 THz.")
            half_width = result["spectrum"]["baud_rate"] * (1 + result["spectrum"]["roll_off"]) / 2e12
            invalid = [row["channel"] for row in result["channels"]
                       if row["frequency_thz"] - half_width < low or row["frequency_thz"] + half_width > high]
            if invalid:
                result["engineering"]["issues"].append({
                    "node_id": node["id"], "check": "WSS passband", "status": "Fail",
                    "reason": f"Channels {invalid} exceed the configured {low}–{high} THz passband.",
                    "action": "Choose a supported passband or reallocate the channels.",
                })
    return result


def geographic_simulation(payload):
    points = payload["coordinates"]
    estimates = geographic_spans(points)
    marine = marine_screening(points)
    names = payload.get("site_names")
    if (not isinstance(names, list) or len(names) != len(points)
        or any(not isinstance(name, str) or not name.strip() or len(name) > 60 for name in names)):
        raise ValueError("Enter a name of up to 60 characters for each site.")
    overrides = payload.get("span_overrides", [None] * len(estimates))
    if not isinstance(overrides, list) or len(overrides) != len(estimates):
        raise ValueError("Provide one length setting per span.")
    reference = len(points) == 2 and payload.get("bundled") is True and overrides == [None]
    lengths = [estimate if override is None else override for estimate, override in zip(estimates, overrides)]
    booster = payload.get("booster_gain_db")
    transmitter_power = payload.get("tx_power_dbm")
    effective_lengths = [80] if reference else lengths
    splices = payload.get("span_splices", [[] for _ in estimates])
    inline_gains = payload.get("inline_gains", [None] * len(estimates))
    preamp = payload.get("preamp_gain_db")
    if not isinstance(inline_gains, list) or len(inline_gains) != len(estimates):
        raise ValueError("Provide one inline amplifier setting per span.")
    connectors = payload.get("roadm_connectors", [None, None])
    if (not isinstance(connectors, list) or len(connectors) != 2
        or any(value is not None and (type(value) not in (int, float) or not 0 <= value <= 10)
               for value in connectors)
        or (len(estimates) == 1 and connectors != [None, None])):
        raise ValueError("ROADM connector losses require Site C and must be between 0 and 10 dB.")
    if (not isinstance(splices, list) or len(splices) != len(estimates)
        or any(not isinstance(losses, list) or len(losses) > 100 for losses in splices)
        or any(type(loss) not in (int, float) or not 0 <= loss <= 10
               for losses in splices for loss in losses)):
        raise ValueError("Enter up to 100 splice losses per span, each between 0 and 10 dB.")
    customized = booster is not None or transmitter_power is not None or any(splices) or any(
        gain is not None for gain in inline_gains) or preamp is not None
    result = (bundled_run() if reference and not customized else
              run_reference(*effective_lengths, booster_gain_db=booster, tx_power_dbm=transmitter_power,
                            span_splices=splices if any(splices) else None, roadm_connectors=connectors,
                            inline_gains=inline_gains, preamp_gain_db=preamp))
    connector_losses = [1.0] if len(estimates) == 1 else [
        0.5 + (0.5 if value is None else value) for value in connectors
    ]
    spans = [
        {"from": names[index], "to": names[index + 1], "geodesic_km": estimate,
         "simulation_km": result["span_lengths_km"][index],
         "source": "Bundled topology" if reference else "WGS84 geodesic" if overrides[index] is None else "Engineered override",
         "splice_losses_db": splices[index],
         "splice_total_db": round(math.fsum(splices[index]), 6),
         "connector_loss_db": connector_losses[index],
         "inline_gain_db": inline_gains[index],
         "amplifier_warning": result["span_lengths_km"][index] > 80 and inline_gains[index] is None,
         "marine_screening": marine[index],
         "passive_loss_db": round(0.2 * result["span_lengths_km"][index] + connector_losses[index] + math.fsum(splices[index]), 6)}
        for index, estimate in enumerate(estimates)
    ]
    return {
        **result,
        "points": points,
        "site_names": [name.strip() for name in names],
        "map_estimate_km": sum(estimates),
        "length_source": "Per-span lengths" if len(spans) > 1 else spans[0]["source"],
        "spans": spans,
        "booster_gain_db": booster,
        "preamp_gain_db": preamp,
        "baseline": bundled_run() if len(points) == 2 and (not reference or customized) else None,
    }


def quality_check(channels, limits):
    if limits is None:
        return {"status": "Not evaluated", "reason": "Enter a GSNR planning threshold at signal bandwidth."}
    if not isinstance(limits, dict):
        raise ValueError("Provide a GSNR threshold and reserves in dB.")
    threshold, reserve, warning = (limits.get(key) for key in ("threshold", "reserve", "warning"))
    if any(type(value) not in (int, float) or not -100 <= value <= 100
           for value in (threshold, reserve, warning)) or min(reserve, warning) < 0:
        raise ValueError("Enter a finite GSNR threshold and nonnegative reserves in dB.")
    channel = min(channels, key=lambda row: row["gsnr_db"])
    margin = round(channel["gsnr_db"] - threshold - reserve, 6)
    action = (
        "ASE-side noise is the larger modeled contribution at the limiting channel. Review amplifier noise figure, "
        "unnecessary stages and passive loss ahead of gain."
        if channel["osnr_ase_db"] <= channel["snr_nli_db"] else
        "Nonlinear interference is the larger modeled contribution at the limiting channel. "
        "Test lower span launch power and rerun to check the ASE trade-off."
    )
    return {
        "status": "Fail" if margin < 0 else "Review" if margin < warning else "Pass",
        "channel": channel["channel"], "frequency_thz": channel["frequency_thz"],
        "gsnr_db": channel["gsnr_db"], "threshold_db": threshold, "reserve_db": reserve,
        "warning_db": warning, "remaining_db": margin,
        "scope": "User-entered GSNR planning check at signal bandwidth",
        "action": action if margin < warning else "",
    }

def ase_check(channels, threshold, warning=1):
    if threshold is None:
        return {"status": "Not evaluated"}
    if type(threshold) not in (int, float) or not -100 <= threshold <= 100:
        raise ValueError("Enter a finite ASE OSNR threshold in dB.")
    if type(warning) not in (int, float) or not 0 <= warning <= 100:
        raise ValueError("Enter a nonnegative margin review band in dB.")
    channel = min(channels, key=lambda row: row["osnr_ase_db"])
    margin = round(channel["osnr_ase_db"] - threshold, 6)
    return {"status": "Fail" if margin < 0 else "Review" if margin < warning else "Pass", "channel": channel["channel"],
            "frequency_thz": channel["frequency_thz"], "osnr_ase_db": channel["osnr_ase_db"],
            "threshold_db": threshold, "remaining_db": margin, "reference_bandwidth": "signal",
            "review_band_db": warning,
            "action": "Review amplifier noise figure, passive loss ahead of gain, and unnecessary gain stages." if margin < warning else ""}


def catalog_checks(result, profile_id, rate):
    profiles = json.loads((ROOT / "equipment_catalog.json").read_bytes())["profiles"]
    profile = next((entry for entry in profiles if entry["id"] == profile_id), None)
    if profile is None:
        raise ValueError("Select an equipment catalog entry.")
    if profile["status"] == "simulation_reference":
        return []
    checks = [{"check": "Vendor optical feasibility", "status": "Not evaluated",
               "detail": "A validated operating mode and required signal-quality threshold are missing."}]
    spectrum = result["spectrum"]
    if "published_tuning_range_thz" in profile:
        low, high = profile["published_tuning_range_thz"]
        frequencies = [channel["frequency_thz"] for channel in result["channels"]]
        checks.append({"check": "Carrier tuning", "status": "Pass" if low <= min(frequencies) <= max(frequencies) <= high else "Fail",
                       "detail": f"{min(frequencies):.5f}–{max(frequencies):.5f} THz versus published {low}–{high} THz."})
    if "published_symbol_rate_range_gbaud" in profile:
        low, high = profile["published_symbol_rate_range_gbaud"]
        baud = spectrum["baud_rate"] / 1e9
        checks.append({"check": "Symbol rate range", "status": "Pass" if low <= baud <= high else "Fail",
                       "detail": f"{baud:g} GBd modeled versus published {low}–{high} GBd."})
    sensitivity = profile.get("published_rx_sensitivity_dbm", {}).get(f"{rate}_gbps")
    if sensitivity is not None:
        weakest = min(result["channels"], key=lambda row: row["power_dbm"])
        delta = weakest["power_dbm"] - sensitivity
        checks.append({"check": "Receive power comparison", "status": "Reference only",
                       "detail": f"Channel {weakest['channel']}: {weakest['power_dbm']:.2f} dBm against {sensitivity:g} dBm at {rate} Gb/s ({delta:+.2f} dB). The carrier was propagated with generic parameters."})
    spacing = profile.get("published_typical_channel_spacing_ghz", profile.get("published_fixed_grid_ghz"))
    if spacing is not None:
        checks.append({"check": "Published spacing reference", "status": "Reference only",
                       "detail": f"{spectrum['spacing'] / 1e9:g} GHz modeled versus {spacing:g} GHz published spacing reference."})
    return checks


def workbook(result):
    output = BytesIO()
    with xlsxwriter.Workbook(output, {"in_memory": True, "strings_to_formulas": False}) as book:
        heading = book.add_format({"bold": True, "bg_color": "#15364D", "font_color": "#FFFFFF"})
        alert = book.add_format({"bold": True, "font_color": "#9C0006", "bg_color": "#FFC7CE"})
        frequency = book.add_format({"num_format": "0.00000"})
        measurement = book.add_format({"num_format": "0.00"})
        summary = book.add_worksheet("Run Summary")
        summary.set_column("A:A", 34)
        summary.set_column("B:B", 75)
        summary.write_row(0, 0, ("Input", "Value"), heading)
        details = [
            ("Project name", result.get("route_name", "Reference run")),
            ("Project ID", result.get("project_id")),
            ("Project revision", result.get("revision")),
            ("GNPy version", result["engine_version"]),
            ("Path", " → ".join(result["site_names"])),
            ("Site A name", result["site_names"][0]),
            ("Site B name", result["site_names"][1]),
            ("Topology", result["topology"]),
            ("Topology SHA-256", result["topology_sha256"]),
            ("Equipment", result["equipment"]),
            ("Equipment SHA-256", result["equipment_sha256"]),
            ("Length source", result["length_source"]),
            ("Terminal B requested preamp gain (dB)", result.get("preamp_gain_db")),
            ("Amplifier design mode", "Gain mode" if result.get("manual_gain_mode") else "Power mode"),
            ("Simulation length (km)", result["span_length_km"]),
            ("Map estimate (km)", result["map_estimate_km"]),
            ("Channel reference bandwidth", "Signal bandwidth"),
        ]
        spectrum = result["spectrum"]
        details.extend([
            ("Spectrum start (THz)", spectrum["f_min"] / 1e12),
            ("Spectrum end (THz)", spectrum["f_max"] / 1e12),
            ("Channel spacing (GHz)", spectrum["spacing"] / 1e9),
            ("Baud rate (GBd)", spectrum["baud_rate"] / 1e9),
            ("Transmitter output (dBm/channel)", spectrum["tx_power_dbm"]),
            ("Span design reference (dBm/channel)", spectrum["power_dbm"]),
            ("Transmitter OSNR (dB)", spectrum["tx_osnr"]),
            ("Roll-off", spectrum["roll_off"]),
        ])
        baseline = result["baseline"]
        if baseline:
            details.extend([
                ("Baseline length (km)", baseline["span_length_km"]),
                ("Baseline topology SHA-256", baseline["topology_sha256"]),
            ])
        details.extend(("External passive budget · " + key.replace("_", " "), value)
                       for key, value in result.get("passive_budget", {}).items())
        for index, row in enumerate(details, 1):
            summary.write_row(index, 0, row)
        if result.get("booster_gain_db") is not None:
            summary.write_row(len(details) + 1, 0, ("Terminal A requested booster gain (dB)", result["booster_gain_db"]))
        for index, (key, value) in enumerate(result.get("quality_check", {}).items(), len(details) + 2):
            summary.write_row(index, 0, ("GSNR check · " + key.replace("_", " "), value),
                              alert if result["quality_check"]["status"] in ("Fail", "Review") else None)
        if result.get("catalog_checks"):
            catalog = book.add_worksheet("Equipment Checks")
            catalog.set_column("A:B", 30)
            catalog.set_column("C:C", 100)
            catalog.write_row(0, 0, ("Check", "Status", "Evidence"), heading)
            catalog.write(1, 0, result["catalog_profile"])
            for index, check in enumerate(result["catalog_checks"], 2):
                catalog.write_row(index, 0, [check["check"], check["status"], check["detail"]],
                                  alert if check["status"] in ("Fail", "Review") else None)
        for index, (key, value) in enumerate(result.get("ase_check", {}).items(), len(details) + 15):
            summary.write_row(index, 0, ("ASE OSNR check · " + key.replace("_", " "), value),
                              alert if result["ase_check"]["status"] in ("Fail", "Review") else None)
        summary.write_row(len(details) + 25, 0, ("FEC margin", "Not evaluated · Requires a validated modem mode"))
        if "spans" in result:
            spans = book.add_worksheet("Route Spans")
            spans.set_column("A:L", 25)
            spans.write_row(0, 0, ("From", "To", "Geodesic (km)", "Simulation (km)", "Length source",
                                    "Individual splices (dB)", "Splice total (dB)", "Connector loss (dB)", "Passive budget (dB)",
                                    "Midpoint EDFA target (dB)", "Over-80 km warning", "Marine screening"), heading)
            for index, span in enumerate(result["spans"], 1):
                spans.write_row(index, 0, [
                    span["from"], span["to"], span["geodesic_km"], span["simulation_km"], span["source"],
                    ", ".join(str(loss) for loss in span["splice_losses_db"]),
                    span["splice_total_db"], span["connector_loss_db"], span["passive_loss_db"],
                    span["inline_gain_db"],
                ])
                if span["amplifier_warning"]:
                    spans.write(index, 10, "Review amplification", alert)
                if span["marine_screening"]:
                    spans.write(index, 11, "Potential ocean crossing · review cable armor", alert)
            start = len(result["spans"]) + 3
            spans.write_row(start, 0, ("Site", "Latitude", "Longitude"), heading)
            for index, (name, point) in enumerate(zip(result["site_names"], result["points"]), start + 1):
                spans.write_row(index, 0, [name, *point])
        channels = book.add_worksheet("Channel Results")
        headers = ["Channel", "Frequency (THz)", *METRICS.values()]
        if baseline:
            headers.extend(f"Bundled {label}" for label in METRICS.values())
            headers.extend(f"Delta {label.replace('(dBm)', '(dB)')}" for label in METRICS.values())
        channels.write_row(0, 0, headers, heading)
        channels.set_column("A:A", 12)
        channels.set_column("B:B", 18, frequency)
        for column, label in enumerate(headers[2:], 2):
            channels.set_column(column, column, len(label) + 2, measurement)
        channels.freeze_panes(1, 2)
        channels.autofilter(0, 0, len(result["channels"]), len(headers) - 1)
        for index, row in enumerate(result["channels"], 1):
            values = [row[key] for key in METRICS]
            if baseline:
                reference = [baseline["channels"][index - 1][key] for key in METRICS]
                values.extend(reference + [round(row[key] - value, 2) for key, value in zip(METRICS, reference)])
            channels.write_row(index, 0, [row["channel"], row["frequency_thz"], *values])
        report = book.add_worksheet("GNPy Details")
        report.set_column("A:A", 96)
        report.write(0, 0, "Completed run · GNPy transmission report", heading)
        lines = result["report"].splitlines()
        for index, line in enumerate(lines, 1):
            report.write_string(index, 0, line)
        if baseline:
            report.set_column("B:B", 96)
            report.write(0, 1, "Bundled run · GNPy transmission report", heading)
            for index, line in enumerate(baseline["report"].splitlines(), 1):
                report.write_string(index, 1, line)
        if "engineering" in result:
            quantities = book.add_worksheet("Equipment Summary")
            quantities.set_column("A:C", 28)
            quantities.set_column("D:D", 55)
            quantities.set_column("E:G", 20)
            quantities.write_row(0, 0, ("Stable ID", "Site", "Kind", "Equipment", "Quantity", "Unit", "Price status"), heading)
            inventory = result["equipment_summary"]["bom"]
            for index, item in enumerate(inventory, 1):
                quantities.write_row(index, 0, [item["id"], item.get("site_id"), item["kind"], item["description"],
                                                item["quantity"], item["unit"], "Estimator pricing pending"])
            geometry = book.add_worksheet("Route Geometry")
            geometry.set_column("A:D", 23)
            geometry.write_row(0, 0, ("Span ID", "Vertex", "Latitude", "Longitude"), heading)
            row = 1
            for span in result["spans"]:
                for vertex, point in enumerate(span["route_vertices"], 1):
                    geometry.write_row(row, 0, [span["id"], vertex, *point])
                    row += 1
            findings = book.add_worksheet("Design Checks")
            findings.set_column("A:C", 24)
            findings.set_column("D:E", 90)
            findings.write_row(0, 0, ("Location", "Check", "Status", "Finding", "Corrective action"), heading)
            for index, issue in enumerate(result["engineering"]["issues"], 1):
                findings.write_row(index, 0, [issue.get("node_id"), issue["check"], issue["status"],
                                                issue.get("reason", ""), issue.get("action", "")],
                                   alert if issue["status"] in ("Fail", "Review") else None)
            zones = book.add_worksheet("Zones Screening")
            zones.set_column("A:C", 25)
            zones.set_column("D:E", 90)
            zones.write_row(0, 0, ("Span", "Zone", "Status", "Reason", "Source"), heading)
            zones.write_row(1, 0, ["", "Source coverage", "Review", result["zones"]["coverage"],
                                    json.dumps(result["zones"]["source"], ensure_ascii=False)], alert)
            for index, finding in enumerate(result["zones"]["findings"], 2):
                zones.write_row(index, 0, [finding["span_index"] + 1, finding["name"], finding["status"],
                                            finding["reason"], finding["source"]], alert)
    return output.getvalue()


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, kind, body, filename=None):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def json_response(self, status, value):
        self.respond(status, "application/json", json.dumps(value).encode())

    def do_GET(self):
        if self.path == "/api/zones":
            from zones_screening import get_zones
            self.json_response(200, get_zones())
            return
        if self.path in STATIC:
            filename, kind = STATIC[self.path]
            self.respond(200, kind, (ROOT / filename).read_bytes())
            return
        if self.path.startswith("/api/workbook/"):
            with RUNS_LOCK:
                result = RUNS.get(self.path.removeprefix("/api/workbook/"))
            if result is not None:
                self.respond(200, XLSX, workbook(result), "hyperion-run.xlsx")
                return
            self.json_response(404, {"error": "This run expired. Run the simulation again to export."})
            return
        for prefix in ("/api/evidence/", "/api/estimator/"):
            if self.path.startswith(prefix):
                with RUNS_LOCK:
                    result = RUNS.get(self.path.removeprefix(prefix))
                if result is None:
                    self.json_response(404, {"error": "Run expired. Rerun the design."})
                else:
                    value = result if prefix == "/api/evidence/" else {
                        "routes": result.get("equipment_summary", result.get("engineering", {})).get("quantity_export"),
                        "equipment": result.get("equipment_summary", result.get("engineering", {})).get("estimator_equipment"),
                        "network_equipment": result.get("equipment_summary"),
                    }
                    self.respond(200, "application/json", json.dumps(value, ensure_ascii=False).encode(),
                                 "hyperion-run.json" if prefix == "/api/evidence/" else "hyperion-quantities.json")
                return
        self.send_error(404)

    def do_POST(self):
        if self.path not in ("/api/run", "/api/distances", "/api/preview"):
            self.send_error(404)
            return
        if self.headers.get_content_type() != "application/json":
            self.json_response(415, {"error": "Expected a JSON simulation request."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 250000:
                raise ValueError("Invalid simulation request size.")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("Invalid simulation inputs.")
            if self.path == "/api/preview":
                self.json_response(200, network_preview(payload))
                return
            if self.path == "/api/distances":
                points = payload["coordinates"]
                self.json_response(200, {"km": geographic_spans(points), "marine": marine_screening(points)})
                return
            result = simulation(payload)
            result["quality_check"] = quality_check(result["channels"], payload.get("quality_limits"))
            result["ase_check"] = ase_check(result["channels"], payload.get("ase_threshold_db"), payload.get("ase_warning_db", 1))
            result["catalog_profile"] = payload.get("catalog_profile", "generic-gnpy-reference")
            result["catalog_checks"] = catalog_checks(result, result["catalog_profile"], payload.get("catalog_rate"))
        except (ValueError, KeyError, TypeError) as error:
            self.json_response(400, {"error": str(error)})
        except Exception as error:
            self.log_error("%s", error)
            self.json_response(500, {"error": str(error)})
        else:
            run_id = uuid4().hex
            with RUNS_LOCK:
                RUNS[run_id] = result
                if len(RUNS) > 32:
                    RUNS.popitem(last=False)
            self.json_response(200, {**result, "workbook_url": f"/api/workbook/{run_id}",
                                     "evidence_url": f"/api/evidence/{run_id}",
                                     "estimator_url": f"/api/estimator/{run_id}"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        print(f"Hyperion Routes is ready at http://127.0.0.1:{server.server_port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
