"use strict";

const assert = require("node:assert/strict");
const {insertSite, copySettings, distanceKm} = require("./project_editing.js");

function fixture() {
  return {
    project_id: "m06-editing", revision: 1,
    network: {
      nodes: [{id: "A", name: "A", lat: 0, lon: 0}, {id: "B", name: "B", lat: 0, lon: 4}],
      links: [{id: "ab", from: "A", to: "B", bends: [[1, 1], [1, 3]], override: 500,
        connector_in_db: 0.3, connector_out_db: 0.7, splices: [0.1, 0.2], inline_gain: 12,
        fiber: {type_variety: "SSMF", loss_coef: 0.2}}],
      services: [{id: "s", source: "A", target: "B", via: []}],
    },
    equipment: {vendor: "generic", nodes: {
      A: {id: "A", role: "terminal", panel: {connector_loss_db: 0.4}, manual_gain_override: 9,
        booster_gain_db: 12},
      B: {id: "B", role: "terminal", panel: {connector_loss_db: 0.8}, manual_gain_override: 15,
        booster_gain_db: 10},
    }},
  };
}

function routeLength(project, link) {
  const node = id => project.network.nodes.find(item => item.id === id);
  const from = node(link.from), to = node(link.to);
  const points = [[from.lat, from.lon], ...link.bends, [to.lat, to.lon]];
  return points.slice(1).reduce((sum, point, index) => sum + distanceKm(points[index], point), 0);
}

const original = fixture(), snapshot = JSON.stringify(original);
const draft = insertSite(original, "ab", [0.5, 0.5]);
assert.equal(JSON.stringify(original), snapshot, "Draft insertion mutated the original, so cancel cannot be safe");
assert.equal(draft.insertedNodeId, "C");
assert.equal(draft.project.network.nodes.length, 3);
const [left, right] = draft.project.network.links;
assert.equal(left.override + right.override, 500);
assert.equal(left.connector_in_db, 0.3);
assert.equal(right.connector_out_db, 0.7);
assert.equal(left.connector_out_db, undefined);
assert.equal(right.connector_in_db, undefined);
assert.deepEqual(left.splices, []);
assert.deepEqual(right.splices, [0.1, 0.2]);
assert.deepEqual(right.bends, [[1, 1], [1, 3]]);
assert.equal(left.inline_gain, null);
assert.equal(right.inline_gain, 12);
const oldDistance = routeLength(original, original.network.links[0]) / 2;
const retainedDistance = routeLength(draft.project, left) +
  routeLength(draft.project, right) * right.inline_position_fraction;
assert(Math.abs(oldDistance - retainedDistance) < 0.01, "Existing amplifier changed geographic location");
assert(draft.project.edit_reviews.some(review => /splices/.test(review.message)));
assert(draft.review.some(message => /engineered/.test(message)));
const plain = fixture();
plain.network.links[0].override = null;
plain.network.links[0].inline_gain = null;
const geographic = insertSite(plain, "ab", [0.5, 0.5]);
assert(geographic.project.network.links.every(link => link.override === null));
assert.equal(geographic.project.equipment.nodes.C.role, "pass-through");

const moved = fixture();
moved.network.nodes.push({id: "C", name: "Existing C", lat: 2, lon: 2});
moved.equipment.nodes.C = {panel: {enabled: false}};
const beforeMove = JSON.stringify(moved);
const insertedExisting = insertSite(moved, "ab", [0.5, 0.5], "roadm", "C");
assert.equal(insertedExisting.project.network.nodes.length, 3);
assert.equal(insertedExisting.project.network.nodes[2].name, "Existing C");
assert.equal(JSON.stringify(moved), beforeMove);
assert.equal(insertedExisting.project.equipment.nodes.C.panel.enabled, false);
moved.network.links.push({id: "ac", from: "A", to: "C", bends: []});
assert.throws(() => insertSite(moved, "ab", [0.5, 0.5], "roadm", "C"), /loop/);
assert.throws(() => insertSite(original, "ab", [0, 0]), /one metre/);
assert.throws(() => insertSite(original, "ab", [NaN, 0]), /latitude/);
assert.equal(insertSite(original, "ab", [0.5, 0.5], "oeo").project.equipment.nodes.C.role, "oeo");
assert.equal(insertSite(original, "ab", [0.5, 0.5], "regenerator").project.equipment.nodes.C.role, "oeo");

const crowded = fixture();
for (let index = 2; index < 20; index++) crowded.network.nodes.push({id: "site" + index, name: "Site", lat: 2, lon: index});
assert.throws(() => insertSite(crowded, "ab", [0.5, 0.5]), /20 sites/);
crowded.network.nodes.pop();
assert.equal(insertSite(crowded, "ab", [0.5, 0.5]).project.network.nodes.length, 20);

const copied = copySettings(original, "A", ["B"]);
assert.equal(JSON.stringify(original), snapshot);
assert.equal(copied.network.nodes[1].id, "B");
assert.equal(copied.network.nodes[1].lon, 4);
assert.equal(copied.equipment.nodes.B.id, "B");
assert.equal(copied.equipment.nodes.B.panel.connector_loss_db, 0.4);
assert.equal(copied.equipment.nodes.B.manual_gain_override, 15);
assert.equal(copied.equipment.nodes.B.booster_gain_db, 10);
assert.equal(copySettings(original, "A", ["B"], {preserveAmplifierOverrides: false})
  .equipment.nodes.B.booster_gain_db, 12);
assert.throws(() => copySettings(original, "A", ["missing"]), /exist/);
assert(Math.abs(distanceKm([0, 0], [0, 2]) - 222.638982) < 0.000001);
assert(distanceKm([0, 179.9], [0, -179.9]) < 23);
console.log("Passed M06 immutable insert/cancel, bend partition, engineered length, connector/splice loss, amplifier position, 20-site limit, loop rejection and copy settings checks.");
