"""Screen route polylines against a configured, versioned Zones GeoJSON feed."""

from datetime import datetime, timezone
import ipaddress
import json
import math
import os
from pathlib import Path
from threading import Lock
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from geographiclib.geodesic import Geodesic


MAX_BYTES = 5 * 1024 * 1024
MAX_FEATURES = 10000
REFRESH_SECONDS = 300
_LOCK = Lock()
_CACHE = {}


def _bundled():
    path = Path(__file__).parent / "assets" / "zones-v0.6.geojson"
    try:
        data = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None, {"status": "Unavailable", "source": "Bundled Zones snapshot v0.6",
                      "detail": "The bundled screening snapshot could not be read."}
    return data, {"status": "Bundled snapshot", "source": "Hyperion Zones v0.6 bundled snapshot",
                  "version": str(data.get("version", "0.6")),
                  "detail": "Cached reference coverage. Set HYPERION_ZONES_URL for a current polygon feed.",
                  "publication": "https://github.com/Figment-Fiber/Hyperion-Zones/releases/tag/v0.6"}


def _approved_url(url):
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.fragment or not parsed.hostname:
        raise ValueError("Zones URL must have a host and contain no credentials or fragment.")
    loopback = parsed.hostname.lower() == "localhost"
    try:
        loopback = loopback or ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        pass
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        raise ValueError("Zones requires HTTPS, or a local loopback HTTP feed.")
    return url


class _SameOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        before, after = urlsplit(request.full_url), urlsplit(new_url)
        if (before.scheme, before.hostname, before.port) != (after.scheme, after.hostname, after.port):
            raise ValueError("Zones feed redirected to another origin.")
        return super().redirect_request(request, fp, code, message, headers, new_url)


def _fetch(url):
    request = Request(_approved_url(url), headers={
        "Accept": "application/geo+json, application/json",
        "User-Agent": "Hyperion-Routes-M05/1.0",
    })
    with build_opener(_SameOriginRedirect()).open(request, timeout=8) as response:
        content = response.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError("Zones feed exceeds the 5 MiB limit.")
    data = json.loads(content)
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        raise ValueError("Zones feed must be a GeoJSON FeatureCollection.")
    features = data.get("features")
    if not isinstance(features, list) or len(features) > MAX_FEATURES:
        raise ValueError("Zones feed must contain at most 10,000 features.")
    return data


def load_feed():
    """Return the configured feed and freshness metadata, retaining a last-good copy."""
    url = os.environ.get("HYPERION_ZONES_URL", "").strip()
    if not url:
        return _bundled()
    now = time.time()
    with _LOCK:
        entry = _CACHE.get(url)
        if entry and now - entry["attempted"] < REFRESH_SECONDS:
            return entry["data"], dict(entry["metadata"])
        try:
            data = _fetch(url)
            metadata = {"status": "Live", "source": url,
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        "version": str(data.get("version", data.get("revision", "Unspecified")))[:100],
                        "detail": "Route screening uses polygon boundaries supplied by this source."}
        except Exception as error:
            metadata = {"status": "Stale" if entry and entry["data"] else "Unavailable",
                        "source": url, "detail": str(error)[:300]}
            data = entry["data"] if entry else None
            if data is None:
                data, fallback = _bundled()
                metadata.update({"status": "Bundled snapshot", "fallback_source": fallback["source"],
                                 "version": fallback.get("version", "Unknown")})
            if data is not None:
                if entry:
                    metadata.update({key: entry["metadata"][key] for key in ("retrieved_at", "version")
                                     if key in entry["metadata"]})
        _CACHE[url] = {"data": data, "attempted": now, "metadata": metadata}
        return data, dict(metadata)


def get_zones():
    """Return polygon and reference geometry with an explicit feed-status record."""
    data, metadata = load_feed()
    return {"geojson": data, "source": metadata}


def _coordinate(point):
    if (not isinstance(point, (list, tuple)) or len(point) < 2
            or any(type(value) not in (int, float) or not math.isfinite(value) for value in point[:2])
            or not -180 <= point[0] <= 180 or not -90 <= point[1] <= 90):
        raise ValueError("Zones contains an invalid longitude/latitude coordinate.")
    return point[0], point[1]


def _ring(points, anchor):
    if not isinstance(points, list) or not 4 <= len(points) <= 200000:
        raise ValueError("Zones polygon ring must have 4–200,000 coordinates.")
    coordinates = [_coordinate(point) for point in points]
    if coordinates[0] != coordinates[-1]:
        raise ValueError("Zones polygon ring is not closed.")
    unwrapped = []
    previous = anchor
    for longitude, latitude in coordinates:
        longitude += 360 * round((previous - longitude) / 360)
        unwrapped.append((longitude, latitude))
        previous = longitude
    center = sum(point[0] for point in unwrapped) / len(unwrapped)
    shift = 360 * round((anchor - center) / 360)
    return [(longitude + shift, latitude) for longitude, latitude in unwrapped]


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, point):
    return (abs(_cross(a, b, point)) <= 1e-10
            and min(a[0], b[0]) - 1e-10 <= point[0] <= max(a[0], b[0]) + 1e-10
            and min(a[1], b[1]) - 1e-10 <= point[1] <= max(a[1], b[1]) + 1e-10)


def _intersects(a, b, c, d):
    if (max(a[0], b[0]) < min(c[0], d[0]) or max(c[0], d[0]) < min(a[0], b[0])
            or max(a[1], b[1]) < min(c[1], d[1]) or max(c[1], d[1]) < min(a[1], b[1])):
        return False
    ab_c, ab_d, cd_a, cd_b = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    return ((ab_c * ab_d < 0 and cd_a * cd_b < 0)
            or _on_segment(a, b, c) or _on_segment(a, b, d)
            or _on_segment(c, d, a) or _on_segment(c, d, b))


def _inside(point, ring):
    inside = False
    for a, b in zip(ring, ring[1:]):
        if _on_segment(a, b, point):
            return True
        if (a[1] > point[1]) != (b[1] > point[1]):
            x = a[0] + (point[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if point[0] < x:
                inside = not inside
    return inside


def _geodesic_path(path):
    """Approximate WGS84 arcs at <=5 km; stored vertices are latitude/longitude."""
    if not isinstance(path, list) or not 2 <= len(path) <= 100:
        raise ValueError("A screened span needs 2–100 route vertices.")
    route = []
    for start, end in zip(path, path[1:]):
        for latitude, longitude in (start, end):
            _coordinate([longitude, latitude])
        line = Geodesic.WGS84.InverseLine(*start, *end)
        intervals = max(1, math.ceil(line.s13 / 5000))
        for index in range(intervals):
            point = line.Position(line.s13 * index / intervals)
            route.append((point["lon2"], point["lat2"]))
    route.append((path[-1][1], path[-1][0]))
    unwrapped = [route[0]]
    for longitude, latitude in route[1:]:
        longitude += 360 * round((unwrapped[-1][0] - longitude) / 360)
        unwrapped.append((longitude, latitude))
    return unwrapped


def _hits_polygon(route, polygon):
    rings = [_ring(points, route[0][0]) for points in polygon]
    if not rings:
        raise ValueError("Zones polygon has no outer ring.")
    west, east = min(point[0] for point in rings[0]), max(point[0] for point in rings[0])
    south, north = min(point[1] for point in rings[0]), max(point[1] for point in rings[0])
    if (max(point[0] for point in route) < west or min(point[0] for point in route) > east
            or max(point[1] for point in route) < south or min(point[1] for point in route) > north):
        return False
    for point in route:
        if _inside(point, rings[0]) and not any(_inside(point, hole) for hole in rings[1:]):
            return True
    return any(_intersects(a, b, c, d) for a, b in zip(route, route[1:])
               for ring in rings for c, d in zip(ring, ring[1:]))


def screen_routes(paths, feed=None, source_metadata=None):
    """Return source health and per-span crossing findings without legal inference."""
    if feed is None:
        feed, metadata = load_feed()
    else:
        metadata = source_metadata or {"status": "Fixture", "source": "Supplied dataset"}
    report = {"source": metadata, "findings": [], "ignored_reference_features": 0,
              "invalid_features": 0, "coverage": "Not evaluated"}
    if feed is None:
        return report
    routes = [_geodesic_path(path) for path in paths]
    boundary_count = 0
    for feature in feed.get("features", []):
        try:
            if not isinstance(feature, dict):
                raise ValueError("Invalid Zones feature.")
            geometry = feature.get("geometry") or {}
            if not isinstance(geometry, dict):
                raise ValueError("Invalid Zones geometry.")
            kind = geometry.get("type")
            if kind not in ("Polygon", "MultiPolygon"):
                report["ignored_reference_features"] += 1
                continue
            polygons = [geometry["coordinates"]] if kind == "Polygon" else geometry["coordinates"]
            boundary_count += 1
            properties = feature.get("properties") or {}
            if not isinstance(properties, dict):
                raise ValueError("Invalid Zones properties.")
            for index, route in enumerate(routes):
                if any(_hits_polygon(route, polygon) for polygon in polygons):
                    report["findings"].append({
                        "span_index": index,
                        "feature_id": str(feature.get("id", properties.get("id", "Unspecified")))[:200],
                        "name": str(properties.get("name", properties.get("title", "Zone crossing")))[:300],
                        "category": str(properties.get("category", "review"))[:100],
                        "reason": str(properties.get("note", properties.get("detail", "Review the supplied boundary and applicable activity restrictions.")))[:1000],
                        "source": str(properties.get("source", metadata.get("source", "")))[:2000],
                        "last_verified": str(properties.get("last_source_review", properties.get("last_verified", "Unknown")))[:100],
                        "geometry_quality": str(properties.get("geometry_quality", "Source polygon; precision unverified"))[:300],
                        "status": "Review",
                    })
        except (KeyError, TypeError, ValueError):
            report["invalid_features"] += 1
    report["coverage"] = "Source polygons screened" if boundary_count else "No polygon boundaries available"
    return report
