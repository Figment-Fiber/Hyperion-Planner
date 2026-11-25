/* Pure project editing operations. Callers apply the returned draft after confirmation. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.ProjectEditing = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";

  const MAX_SITES = 20;
  const clone = value => JSON.parse(JSON.stringify(value));
  const radians = degrees => degrees * Math.PI / 180;
  const wrappedLongitude = longitude => ((longitude + 540) % 360) - 180;
  const finite = value => typeof value === "number" && Number.isFinite(value);

  function coordinate(point) {
    if (!Array.isArray(point) || point.length !== 2 || !point.every(finite) ||
        Math.abs(point[0]) > 90 || Math.abs(point[1]) > 180) {
      throw new Error("Use a valid latitude and longitude for the site.");
    }
    return point;
  }

  function distanceKm(left, right) {
    // Vincenty's inverse solution on WGS84, with a spherical antipodal fallback.
    coordinate(left);
    coordinate(right);
    const a = 6378137, flattening = 1 / 298.257223563, b = (1 - flattening) * a;
    const phi1 = radians(left[0]), phi2 = radians(right[0]);
    const longitude = radians(wrappedLongitude(right[1] - left[1]));
    const reduced1 = Math.atan((1 - flattening) * Math.tan(phi1));
    const reduced2 = Math.atan((1 - flattening) * Math.tan(phi2));
    const sin1 = Math.sin(reduced1), cos1 = Math.cos(reduced1);
    const sin2 = Math.sin(reduced2), cos2 = Math.cos(reduced2);
    let lambda = longitude, sigma, sinSigma, cosSigma, cosSqAlpha, cos2SigmaM;
    let converged = false;
    for (let iteration = 0; iteration < 100; iteration++) {
      const sinLambda = Math.sin(lambda), cosLambda = Math.cos(lambda);
      sinSigma = Math.hypot(cos2 * sinLambda, cos1 * sin2 - sin1 * cos2 * cosLambda);
      if (sinSigma === 0) return 0;
      cosSigma = sin1 * sin2 + cos1 * cos2 * cosLambda;
      sigma = Math.atan2(sinSigma, cosSigma);
      const sinAlpha = cos1 * cos2 * sinLambda / sinSigma;
      cosSqAlpha = 1 - sinAlpha * sinAlpha;
      cos2SigmaM = cosSqAlpha < 1e-15 ? 0 : cosSigma - 2 * sin1 * sin2 / cosSqAlpha;
      const c = flattening / 16 * cosSqAlpha * (4 + flattening * (4 - 3 * cosSqAlpha));
      const previous = lambda;
      lambda = longitude + (1 - c) * flattening * sinAlpha *
        (sigma + c * sinSigma * (cos2SigmaM + c * cosSigma * (-1 + 2 * cos2SigmaM ** 2)));
      if (Math.abs(lambda - previous) < 1e-12) { converged = true; break; }
    }
    if (!converged) {
      const value = Math.sin((phi2 - phi1) / 2) ** 2 +
        Math.cos(phi1) * Math.cos(phi2) * Math.sin(longitude / 2) ** 2;
      return 6371.0088 * 2 * Math.asin(Math.min(1, Math.sqrt(value)));
    }
    const uSquared = cosSqAlpha * (a * a - b * b) / (b * b);
    const coefficientA = 1 + uSquared / 16384 * (4096 + uSquared * (-768 + uSquared * (320 - 175 * uSquared)));
    const coefficientB = uSquared / 1024 * (256 + uSquared * (-128 + uSquared * (74 - 47 * uSquared)));
    const delta = coefficientB * sinSigma * (cos2SigmaM + coefficientB / 4 *
      (cosSigma * (-1 + 2 * cos2SigmaM ** 2) - coefficientB / 6 * cos2SigmaM *
        (-3 + 4 * sinSigma ** 2) * (-3 + 4 * cos2SigmaM ** 2)));
    return b * coefficientA * (sigma - delta) / 1000;
  }

  function nearestSegment(path, point) {
    let best;
    for (let index = 0; index < path.length - 1; index++) {
      const start = path[index], end = path[index + 1];
      const scale = Math.max(1e-6, Math.cos(radians((start[0] + end[0]) / 2)));
      const dx = wrappedLongitude(end[1] - start[1]) * scale;
      const dy = end[0] - start[0];
      const px = wrappedLongitude(point[1] - start[1]) * scale;
      const py = point[0] - start[0];
      const denominator = dx * dx + dy * dy;
      const fraction = denominator === 0 ? 0 : Math.max(0, Math.min(1, (px * dx + py * dy) / denominator));
      const snapped = [start[0] + fraction * dy,
        wrappedLongitude(start[1] + fraction * wrappedLongitude(end[1] - start[1]))];
      const offset = distanceKm(point, snapped);
      if (!best || offset < best.offset) best = {index, fraction, point: snapped, offset};
    }
    return best;
  }

  function pathLength(path) {
    return path.slice(1).reduce((sum, point, index) => sum + distanceKm(path[index], point), 0);
  }

  function uniqueId(items, base) {
    const ids = new Set(items.map(item => item.id));
    if (!ids.has(base)) return base;
    let index = 2;
    while (ids.has(base + "-" + index)) index++;
    return base + "-" + index;
  }

  function connected(links, source, target) {
    const visited = new Set([source]), queue = [source];
    for (const id of queue) {
      if (id === target) return true;
      for (const link of links) {
        const neighbor = link.from === id ? link.to : link.to === id ? link.from : null;
        if (neighbor !== null && !visited.has(neighbor)) { visited.add(neighbor); queue.push(neighbor); }
      }
    }
    return false;
  }

  function insertSite(project, linkId, point, role = "pass-through", existingNodeId = null) {
    coordinate(point);
    if (role === "regenerator") role = "oeo";
    if (!project?.network || !Array.isArray(project.network.nodes) || !Array.isArray(project.network.links)) {
      throw new Error("Open a network project before inserting a site.");
    }
    if (!["pass-through", "roadm", "terminal", "oeo", "amplifier", "splice"].includes(role)) {
      throw new Error("Choose a supported site role.");
    }
    const draft = clone(project), network = draft.network;
    const linkIndex = network.links.findIndex(link => link.id === linkId);
    if (linkIndex < 0) throw new Error("The selected span no longer exists.");
    const link = network.links[linkIndex];
    const from = network.nodes.find(node => node.id === link.from);
    const to = network.nodes.find(node => node.id === link.to);
    if (!from || !to) throw new Error("The selected span has a missing endpoint.");
    const path = [[from.lat, from.lon], ...(link.bends || []), [to.lat, to.lon]];
    path.forEach(coordinate);
    const nearest = nearestSegment(path, point);
    const firstPath = [...path.slice(0, nearest.index + 1), nearest.point];
    const secondPath = [nearest.point, ...path.slice(nearest.index + 1)];
    const firstLength = pathLength(firstPath), secondLength = pathLength(secondPath);
    if (Math.min(firstLength, secondLength) < 0.001) {
      throw new Error("Place the new site at least one metre from the span endpoints.");
    }
    let node;
    if (existingNodeId !== null) {
      node = network.nodes.find(item => item.id === existingNodeId);
      if (!node) throw new Error("The site to move no longer exists.");
      if ([link.from, link.to].includes(node.id)) throw new Error("Choose a site other than the span's endpoint.");
      const remaining = network.links.filter(item => item.id !== linkId);
      if (connected(remaining, node.id, link.from) || connected(remaining, node.id, link.to)) {
        throw new Error("Inserting this connected site would create a loop. Disconnect it before inserting it into this span.");
      }
    } else {
      if (network.nodes.length >= MAX_SITES) throw new Error("This project already has 20 sites.");
      const alphabetic = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("").find(id => !network.nodes.some(item => item.id === id));
      node = {id: alphabetic || uniqueId(network.nodes, "site"), name: "Site " + (alphabetic || network.nodes.length + 1),
        lat: nearest.point[0], lon: nearest.point[1]};
      network.nodes.push(node);
    }
    const review = [];
    if (nearest.offset > 0.001) review.push("The site was snapped to the selected drawn span. Confirm its geographic position.");
    node.lat = nearest.point[0];
    node.lon = nearest.point[1];
    const left = clone(link), right = clone(link);
    left.id = uniqueId(network.links, link.id + "-a");
    right.id = uniqueId([...network.links, left], link.id + "-b");
    left.to = node.id;
    right.from = node.id;
    left.bends = firstPath.slice(1, -1);
    right.bends = secondPath.slice(1, -1);
    if (link.override === null || link.override === undefined) {
      left.override = right.override = null;
    } else {
      if (!finite(link.override) || link.override <= 0) throw new Error("The original engineered length is invalid.");
      left.override = link.override * firstLength / (firstLength + secondLength);
      right.override = link.override - left.override;
      review.push("The engineered length was apportioned by drawn segment length. Confirm both new span lengths.");
    }
    delete left.connector_out_db;
    delete right.connector_in_db;
    left.splices = [];
    right.splices = clone(link.splices || []);
    if (right.splices.length) review.push("Existing splices have no recorded position and remain on the downstream span. Review their allocation.");
    left.inline_gain = right.inline_gain = null;
    delete left.inline_position_fraction;
    delete right.inline_position_fraction;
    if (link.inline_gain !== null && link.inline_gain !== undefined) {
      const oldFraction = link.inline_position_fraction ?? 0.5;
      if (!finite(oldFraction) || oldFraction <= 0 || oldFraction >= 1) throw new Error("The inline amplifier position is invalid.");
      const oldDistance = (firstLength + secondLength) * oldFraction;
      if (Math.abs(oldDistance - firstLength) < 0.001) {
        throw new Error("The insertion coincides with an inline amplifier. Move or remove that amplifier before splitting this span.");
      }
      const child = oldDistance < firstLength ? left : right;
      child.inline_gain = link.inline_gain;
      child.inline_position_fraction = oldDistance < firstLength ? oldDistance / firstLength :
        (oldDistance - firstLength) / secondLength;
      review.push("The inline amplifier retains its original distance along the drawn route. Verify the apportioned engineered lengths if applicable.");
    }
    network.links.splice(linkIndex, 1, left, right);
    draft.equipment ||= {};
    draft.equipment.nodes ||= {};
    draft.equipment.nodes[node.id] = {...(draft.equipment.nodes[node.id] || {}), role};
    draft.reference_case = false;
    if (review.length) {
      const reviews = Array.isArray(draft.edit_reviews) ? draft.edit_reviews : [];
      for (const message of review) {
        reviews.push({id: uniqueId(reviews, node.id + "-insert-review"),
          node_id: node.id, link_ids: [left.id, right.id], status: "Review", message});
      }
      draft.edit_reviews = reviews;
    }
    return {project: draft, review, insertedNodeId: node.id, childLinkIds: [left.id, right.id]};
  }

  function copySettings(project, sourceNodeId, targetIds, options = {}) {
    if (!project?.network || !Array.isArray(targetIds)) throw new Error("Choose a source site and target sites.");
    const ids = new Set(project.network.nodes.map(node => node.id));
    if (!ids.has(sourceNodeId) || targetIds.some(id => !ids.has(id))) throw new Error("All selected sites must exist.");
    const draft = clone(project);
    draft.equipment ||= {};
    draft.equipment.nodes ||= {};
    const source = draft.equipment.nodes[sourceNodeId] || {};
    for (const id of new Set(targetIds)) {
      if (id === sourceNodeId) continue;
      const original = draft.equipment.nodes[id] || {};
      const copied = clone(source);
      for (const key of ["id", "name", "lat", "lon", "degrees"]) {
        delete copied[key];
        if (Object.hasOwn(original, key)) copied[key] = clone(original[key]);
      }
      if (options.preserveAmplifierOverrides !== false) {
        for (const [key, value] of Object.entries(original)) {
          if (/amplifier|booster|preamp|gain_override|manual_gain/i.test(key)) copied[key] = clone(value);
        }
      }
      draft.equipment.nodes[id] = copied;
    }
    return draft;
  }

  // Use map-projected coordinates so the chosen segment matches what is visible
  // on screen. This chooses insertion order only; WGS84 calculates path length.
  function bendSegmentIndex(points, point) {
    let best = Infinity, index = 0;
    for (let i = 1; i < points.length; i++) {
      const a = points[i - 1], b = points[i];
      const dx = b[0] - a[0], dy = b[1] - a[1];
      const t = Math.max(0, Math.min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (dx * dx + dy * dy || 1)));
      const distance = Math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy);
      if (distance < best) { best = distance; index = i - 1; }
    }
    return index;
  }

  return {insertSite, copySettings, distanceKm, bendSegmentIndex};
});
