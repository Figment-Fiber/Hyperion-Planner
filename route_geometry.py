"""Validate segmented spans and calculate WGS84 lengths in route order."""

import math

from geographiclib.geodesic import Geodesic


MAX_BENDS_PER_SPAN = 50
MAX_SITES = 6


def validate_coordinate(point):
    """Accept the application's latitude/longitude JSON representation."""
    if (
        not isinstance(point, list)
        or len(point) != 2
        or any(type(value) not in (int, float) or not math.isfinite(value) for value in point)
        or not -90 <= point[0] <= 90
        or not -180 <= point[1] <= 180
    ):
        raise ValueError("Provide finite latitude/longitude pairs within their geographic bounds.")


def segmented_route(points, bends=None, marine_screen=None):
    """Return per-span paths, cumulative distances and optional water screening.

    `points` contains two to six ordered equipment sites.
    `bends` contains one array of intermediate geographic vertices per span.
    Marine screening is called with each entire polyline and returns one flag
    per segment, matching Hyperion's existing screening function.
    """
    if not isinstance(points, list) or not 2 <= len(points) <= MAX_SITES:
        raise ValueError(f"Provide two to {MAX_SITES} route sites.")
    for point in points:
        validate_coordinate(point)
    if bends is None:
        bends = [[] for _ in points[1:]]
    if (
        not isinstance(bends, list)
        or len(bends) != len(points) - 1
        or any(not isinstance(vertices, list) or len(vertices) > MAX_BENDS_PER_SPAN for vertices in bends)
    ):
        raise ValueError(f"Provide up to {MAX_BENDS_PER_SPAN} bends for each route span.")

    paths = []
    span_distances = []
    segment_distances = []
    marine = []
    for start, vertices, end in zip(points, bends, points[1:]):
        for vertex in vertices:
            validate_coordinate(vertex)
        path = [list(point) for point in [start, *vertices, end]]
        distances = [
            Geodesic.WGS84.Inverse(*left, *right)["s12"] / 1000
            for left, right in zip(path, path[1:])
        ]
        paths.append(path)
        span_distances.append(round(math.fsum(distances), 6))
        segment_distances.append([round(distance, 6) for distance in distances])
        if marine_screen is not None:
            flags = marine_screen(path)
            if not isinstance(flags, list) or len(flags) != len(path) - 1:
                raise ValueError("Marine screening did not return a result for every route segment.")
            marine.append(any(flags))
    return {
        "paths": paths,
        "km": span_distances,
        "segment_km": segment_distances,
        "marine": marine if marine_screen is not None else None,
    }


def resolve_network(payload):
    """Resolve a selected service through a small undirected physical graph.

    Source and destination establish the direction of propagation. Optional via
    sites constrain the route in order. Link settings are returned intact with
    bend order corrected when the service traverses a physical link backwards.
    Parallel links are rejected until the UI can select one explicitly.
    """
    network = payload.get("network")
    if not isinstance(network, dict):
        raise ValueError("Provide a network with sites, links and services.")
    nodes = network.get("nodes")
    links = network.get("links")
    services = network.get("services")
    if not isinstance(nodes, list) or not 2 <= len(nodes) <= MAX_SITES:
        raise ValueError(f"A network must have two to {MAX_SITES} sites.")
    if not isinstance(links, list) or len(links) > MAX_SITES * (MAX_SITES - 1) // 2:
        raise ValueError("Provide valid physical links for the network.")
    if not isinstance(services, list) or not services:
        raise ValueError("Provide at least one service with source and destination sites.")
    node_by_id = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("Every site must be a named object with geographic coordinates.")
        site_id = node.get("id")
        name = node.get("name")
        if not isinstance(site_id, str) or not site_id or site_id in node_by_id:
            raise ValueError("Every site needs a unique nonempty ID.")
        if not isinstance(name, str) or not name.strip() or len(name) > 60:
            raise ValueError("Enter a site name of up to 60 characters.")
        validate_coordinate([node.get("lat"), node.get("lon")])
        node_by_id[site_id] = node
    adjacency = {site_id: [] for site_id in node_by_id}
    link_ids = set()
    pairs = set()
    for link in links:
        if not isinstance(link, dict):
            raise ValueError("Every span must have an ID and endpoint sites.")
        link_id = link.get("id")
        left, right = link.get("from"), link.get("to")
        if not isinstance(link_id, str) or not link_id or link_id in link_ids:
            raise ValueError("Every span needs a unique nonempty ID.")
        if left not in node_by_id or right not in node_by_id or left == right:
            raise ValueError("A span must join two different sites in the network.")
        pair = frozenset((left, right))
        if pair in pairs:
            raise ValueError("Parallel spans require explicit route selection and are not supported in M05.")
        bends = link.get("bends", [])
        segmented_route(
            [[node_by_id[left]["lat"], node_by_id[left]["lon"]],
             [node_by_id[right]["lat"], node_by_id[right]["lon"]]],
            [bends],
        )
        override = link.get("override")
        if override is not None and (
            type(override) not in (int, float) or not math.isfinite(override) or override <= 0
        ):
            raise ValueError("An engineered span length must be finite and positive.")
        link_ids.add(link_id)
        pairs.add(pair)
        adjacency[left].append((right, link))
        adjacency[right].append((left, link))
    service_ids = set()
    for service in services:
        if not isinstance(service, dict) or not isinstance(service.get("id"), str) or not service["id"]:
            raise ValueError("Every service needs an ID.")
        if service["id"] in service_ids:
            raise ValueError("Every service needs a unique ID.")
        service_ids.add(service["id"])
        if service.get("source") not in node_by_id or service.get("target") not in node_by_id:
            raise ValueError("Service endpoints must refer to network sites.")
        if service["source"] == service["target"]:
            raise ValueError("A service needs different source and destination sites.")
    active_id = payload.get("active_service", network.get("active_service", services[0]["id"]))
    active = next((service for service in services if service["id"] == active_id), None)
    if active is None:
        raise ValueError("The selected service does not exist.")
    via = active.get("via", [])
    if not isinstance(via, list) or any(site_id not in node_by_id for site_id in via):
        raise ValueError("Service via sites must refer to network sites.")
    waypoints = [active["source"], *via, active["target"]]
    if len(waypoints) != len(set(waypoints)):
        raise ValueError("Service endpoints and via sites must not repeat.")
    route_ids = [waypoints[0]]
    ordered_links = []
    for waypoint_index, destination in enumerate(waypoints[1:], 1):
        source = route_ids[-1]
        blocked = set(route_ids[:-1]) | set(waypoints[waypoint_index + 1:])
        found = _shortest_path(adjacency, source, destination, blocked)
        for left, right, link in found:
            oriented = dict(link)
            oriented["from"], oriented["to"] = left, right
            oriented["bends"] = link.get("bends", []) if link["from"] == left else list(reversed(link.get("bends", [])))
            if link["from"] != left:
                oriented["connector_in_db"] = link.get("connector_out_db")
                oriented["connector_out_db"] = link.get("connector_in_db")
            ordered_links.append(oriented)
            route_ids.append(right)
    return {
        "nodes": [node_by_id[site_id] for site_id in route_ids],
        "links": ordered_links,
        "coordinates": [[node_by_id[site_id]["lat"], node_by_id[site_id]["lon"]] for site_id in route_ids],
        "site_names": [node_by_id[site_id]["name"] for site_id in route_ids],
        "span_bends": [link["bends"] for link in ordered_links],
        "span_overrides": [link.get("override") for link in ordered_links],
        "degrees": {site_id: len(neighbors) for site_id, neighbors in adjacency.items()},
        "service_id": active["id"],
    }


def _shortest_path(adjacency, source, destination, blocked):
    queue = [(source, [])]
    visited = set(blocked) | {source}
    for site_id, path in queue:
        if site_id == destination:
            return path
        for neighbor, link in adjacency[site_id]:
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append((neighbor, [*path, (site_id, neighbor, link)]))
    raise ValueError(f"Service route is disconnected between {source} and {destination}.")
