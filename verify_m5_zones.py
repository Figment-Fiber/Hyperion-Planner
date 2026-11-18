"""Regression cases for polygon screening, route bends and Zones feed fallback."""

from copy import deepcopy
import json
import os
from unittest.mock import patch

import zones_screening as zones


def feature(kind, coordinates, name="Restricted fixture"):
    return {"type": "Feature", "id": "fixture", "properties": {"name": name, "source": "https://example.test/source"},
            "geometry": {"type": kind, "coordinates": coordinates}}


def collection(*features):
    return {"type": "FeatureCollection", "version": "test-1", "features": list(features)}


def main():
    square = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
    feed = collection(feature("Polygon", [square]), feature("Point", [.5, .5]))
    crossing = zones.screen_routes([[[.5, -1], [.5, 2]]], feed)
    assert len(crossing["findings"]) == 1
    assert crossing["findings"][0]["span_index"] == 0
    assert crossing["ignored_reference_features"] == 1
    assert not zones.screen_routes([[[2, -1], [2, 2]]], feed)["findings"]
    assert not zones.screen_routes([[[.5, -1], [2, -1], [2, 2], [.5, 2]]], feed)["findings"]
    assert zones.screen_routes([[[0, -1], [0, 2]]], feed)["findings"]
    hole = [[.2, .2], [.8, .2], [.8, .8], [.2, .8], [.2, .2]]
    holed = collection(feature("Polygon", [square, hole]))
    assert not zones.screen_routes([[[.4, .4], [.6, .6]]], holed)["findings"]
    assert zones.screen_routes([[[.5, .5], [.5, 2]]], holed)["findings"]
    multi = collection(feature("MultiPolygon", [[square]]))
    assert len(zones.screen_routes([[[.5, -1], [.5, 2]], [[2, -1], [2, 2]]], multi)["findings"]) == 1
    bad = collection(feature("Polygon", [[[0, 0], [1, 0], [1, 1]]]))
    assert zones.screen_routes([[[.5, -1], [.5, 2]]], bad)["invalid_features"] == 1
    dateline = collection(feature("Polygon", [[[179, -1], [-179, -1], [-179, 1], [179, 1], [179, -1]]]))
    assert zones.screen_routes([[[0, 178], [0, -178]]], dateline)["findings"]
    with patch.dict(os.environ, {"HYPERION_ZONES_URL": ""}):
        fallback = zones.get_zones()
        assert fallback["source"]["status"] == "Bundled snapshot"
        assert fallback["geojson"]["version"] == "0.6"
        assert any(item["geometry"]["type"] == "Polygon" for item in fallback["geojson"]["features"])
    with patch.dict(os.environ, {"HYPERION_ZONES_URL": "https://example.test/zones.geojson"}):
        zones._CACHE.clear()
        with patch.object(zones, "_fetch", return_value=deepcopy(feed)) as fetch:
            first = zones.get_zones()
            assert first["source"]["status"] == "Live"
            assert zones.get_zones()["geojson"] == feed
            assert fetch.call_count == 1
        zones._CACHE["https://example.test/zones.geojson"]["attempted"] = 0
        with patch.object(zones, "_fetch", side_effect=OSError("upstream unavailable")):
            stale = zones.get_zones()
            assert stale["source"]["status"] == "Stale" and stale["geojson"] == feed
        zones._CACHE.clear()
        with patch.object(zones, "_fetch", side_effect=OSError("upstream unavailable")):
            assert zones.get_zones()["source"]["status"] == "Bundled snapshot"
    for url in ("ftp://example.test/zones", "http://example.test/zones", "https://user:password@example.test/zones"):
        try:
            zones._approved_url(url)
        except ValueError:
            pass
        else:
            raise AssertionError("Unsafe feed URL accepted")
    print("Zones passed: full-segment crossing, bent reroute, holes, boundary touch, multi-span, dateline, invalid data, reference points, live/cache/stale/fallback and URL checks.")


if __name__ == "__main__":
    main()
