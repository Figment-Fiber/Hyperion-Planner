"""Local HTTP entry point for Hyperion Planner M1."""

import argparse
from collections import OrderedDict
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import math
from pathlib import Path
from threading import Lock
from uuid import uuid4

import xlsxwriter
from geographiclib.geodesic import Geodesic

from gnpy_reference import run_reference


ROOT = Path(__file__).resolve().parent
STATIC = {
    "/": ("hyperion.html", "text/html; charset=utf-8"),
    "/app.js": ("hyperion.js", "text/javascript; charset=utf-8"),
    "/app.css": ("hyperion.css", "text/css; charset=utf-8"),
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


def simulation(payload):
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


def geographic_simulation(payload):
    points = payload["coordinates"]
    estimates = geographic_spans(points)
    names = payload.get("site_names")
    if (not isinstance(names, list) or len(names) != len(points)
        or any(not isinstance(name, str) or not name.strip() or len(name) > 60 for name in names)):
        raise ValueError("Enter a name of up to 60 characters for each site.")
    overrides = payload.get("span_overrides", [None] * len(estimates))
    if not isinstance(overrides, list) or len(overrides) != len(estimates):
        raise ValueError("Provide one length setting per span.")
    reference = len(points) == 2 and payload.get("bundled") is True and overrides == [None]
    lengths = [estimate if override is None else override for estimate, override in zip(estimates, overrides)]
    result = bundled_run() if reference else run_reference(*lengths)
    spans = [
        {"from": names[index], "to": names[index + 1], "geodesic_km": estimate,
         "simulation_km": result["span_lengths_km"][index],
         "source": "Bundled topology" if reference else "WGS84 geodesic" if overrides[index] is None else "Engineered override"}
        for index, estimate in enumerate(estimates)
    ]
    return {
        **result,
        "points": points,
        "site_names": [name.strip() for name in names],
        "map_estimate_km": sum(estimates),
        "length_source": "Per-span lengths" if len(spans) > 1 else spans[0]["source"],
        "spans": spans,
        "baseline": bundled_run() if len(points) == 2 and not reference else None,
    }


def workbook(result):
    output = BytesIO()
    with xlsxwriter.Workbook(output, {"in_memory": True, "strings_to_formulas": False}) as book:
        heading = book.add_format({"bold": True, "bg_color": "#15364D", "font_color": "#FFFFFF"})
        frequency = book.add_format({"num_format": "0.00000"})
        measurement = book.add_format({"num_format": "0.00"})
        summary = book.add_worksheet("Run Summary")
        summary.set_column("A:A", 34)
        summary.set_column("B:B", 75)
        summary.write_row(0, 0, ("Input", "Value"), heading)
        details = [
            ("GNPy version", result["engine_version"]),
            ("Path", " → ".join(result["site_names"])),
            ("Site A name", result["site_names"][0]),
            ("Site B name", result["site_names"][1]),
            ("Topology", result["topology"]),
            ("Topology SHA-256", result["topology_sha256"]),
            ("Equipment", result["equipment"]),
            ("Equipment SHA-256", result["equipment_sha256"]),
            ("Length source", result["length_source"]),
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
            ("Launch power (dBm)", spectrum["power_dbm"]),
            ("Transmitter OSNR (dB)", spectrum["tx_osnr"]),
            ("Roll-off", spectrum["roll_off"]),
        ])
        baseline = result["baseline"]
        if baseline:
            details.extend([
                ("Baseline length (km)", baseline["span_length_km"]),
                ("Baseline topology SHA-256", baseline["topology_sha256"]),
            ])
        for index, row in enumerate(details, 1):
            summary.write_row(index, 0, row)
        if "spans" in result:
            spans = book.add_worksheet("Route Spans")
            spans.set_column("A:E", 25)
            spans.write_row(0, 0, ("From", "To", "Geodesic (km)", "Simulation (km)", "Length source"), heading)
            for index, span in enumerate(result["spans"], 1):
                spans.write_row(index, 0, list(span.values()))
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
        self.send_error(404)

    def do_POST(self):
        if self.path not in ("/api/run", "/api/distances"):
            self.send_error(404)
            return
        if self.headers.get_content_type() != "application/json":
            self.json_response(415, {"error": "Expected a JSON simulation request."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 4096:
                raise ValueError("Invalid simulation request size.")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("Invalid simulation inputs.")
            if self.path == "/api/distances":
                self.json_response(200, geographic_spans(payload["coordinates"]))
                return
            result = simulation(payload)
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
            self.json_response(200, {**result, "workbook_url": f"/api/workbook/{run_id}"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        print(f"Hyperion Planner is ready at http://127.0.0.1:{server.server_port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
