"""Verify twenty-site routing while keeping map bends outside the site count."""

from route_geometry import MAX_SITES, resolve_network, segmented_route


def main():
    assert MAX_SITES == 20
    nodes = [{"id": str(index), "name": f"Site {index}", "lat": 21 + index * 0.01, "lon": -158}
             for index in range(20)]
    links = [{"id": f"span-{index}", "from": str(index), "to": str(index + 1),
              "bends": [[21 + index * 0.01 + 0.005, -157.999]]} for index in range(19)]
    project = {"network": {"nodes": nodes, "links": links,
                           "services": [{"id": "service", "source": "0", "target": "19"}]}}
    resolved = resolve_network(project)
    assert len(resolved["nodes"]) == 20 and len(resolved["links"]) == 19
    geometry = segmented_route(resolved["coordinates"], resolved["span_bends"])
    assert len(geometry["km"]) == 19 and all(len(path) == 3 for path in geometry["paths"])
    links[0].update(inline_gain=15, inline_position_fraction=0.2)
    project["network"]["services"][0].update(source="19", target="0")
    reverse = resolve_network(project)
    assert reverse["links"][-1]["inline_position_fraction"] == 0.8
    assert links[0]["inline_position_fraction"] == 0.2
    nodes.append({"id": "20", "name": "Too many", "lat": 22, "lon": -158})
    try:
        resolve_network(project)
    except ValueError as error:
        assert "20" in str(error)
    else:
        raise AssertionError("A twenty-first site was accepted")
    print("Passed twenty-site service, nineteen bent spans and twenty-first-site rejection.")


if __name__ == "__main__":
    main()
