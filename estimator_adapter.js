"use strict";

// Import the equipment summary embedded by Routes into its saved project.
// Pricing stays in the consuming Estimator. Reimport creates a new draft revision.
const fs = require("node:fs");

function requireValue(condition, message) {
  if (!condition) throw new Error(message);
}

function validId(value) {
  return typeof value === "string" && /^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$/.test(value);
}

function stableJSON(value) {
  if (Array.isArray(value)) return "[" + value.map(stableJSON).join(",") + "]";
  if (value && typeof value === "object") {
    return "{" + Object.keys(value).sort().map(key => JSON.stringify(key) + ":" + stableJSON(value[key])).join(",") + "}";
  }
  return JSON.stringify(value);
}

function importRoutesProject(project) {
  const summary = project?.equipment_summary;
  requireValue(project?.version === 2 && project.network &&
    summary?.schema === "hyperion.equipment-summary/1",
  "Save a version 2 Routes project with its equipment summary first.");
  requireValue(validId(project.project_id) && summary.project_id === project.project_id,
    "Equipment summary project ID does not match the saved project.");
  requireValue(String(summary.revision) === String(project.revision),
    "Equipment summary is stale. Save the project again before importing.");
  const source = Object.fromEntries(Object.entries(project).filter(([key]) => key !== "equipment_summary"));
  requireValue(summary.source_snapshot && stableJSON(summary.source_snapshot) === stableJSON(source),
    "Equipment summary inputs changed. Save the project again before importing.");
  requireValue(summary.project_name === project.route_name,
    "Equipment summary route name does not match the saved project.");
  const nodes = new Map(project.network.nodes.map(node => [node.id, node]));
  const segments = new Set(project.network.links.map(link => link.id));
  requireValue(Array.isArray(summary.sites) && summary.sites.length === nodes.size &&
    summary.sites.every(site => nodes.get(site.id)?.name === site.name),
  "Equipment summary sites do not match the saved network.");
  requireValue(Array.isArray(summary.bom), "Equipment summary has no quantity list.");
  const seen = new Set();
  const quantities = summary.bom.map(item => {
    requireValue(typeof item.id === "string" && item.id && !seen.has(item.id),
      "Equipment source IDs must be present and unique.");
    requireValue(item.unit === "each" && Number.isSafeInteger(item.quantity) && item.quantity >= 0,
      "Equipment quantities must be nonnegative whole counts.");
    requireValue(typeof item.description === "string" && item.description.trim(),
      "Equipment descriptions must be present.");
    requireValue(item.site_id == null || nodes.has(item.site_id), "Equipment references an unknown site.");
    requireValue(item.segment_id == null || segments.has(item.segment_id), "Equipment references an unknown span.");
    seen.add(item.id);
    return {
      sourceObjectId: item.id,
      sourceApplication: "routes",
      sourceRevision: String(project.revision),
      siteId: item.site_id ?? null,
      segmentId: item.segment_id ?? null,
      kind: item.kind,
      itemKey: item.catalog_id ?? null,
      description: item.description,
      quantity: item.quantity,
      unit: "each",
      verificationStatus: item.status,
      unitPrice: null,
      currency: null,
      priceSource: null,
      extendedCost: null,
    };
  });
  return {
    schema: "hyperion.estimator-equipment/1",
    projectId: project.project_id,
    projectName: project.route_name,
    revision: String(project.revision),
    status: "draft",
    sites: summary.sites.map(site => ({id: site.id, name: site.name})),
    segments: structuredClone(summary.quantity_export?.segments ?? []),
    quantities,
    actualServiceAmplifiers: structuredClone(summary.actual_service_amplifiers ?? []),
    sourceIssues: structuredClone(summary.issues ?? []),
    assumptions: [
      "Equipment quantities are supplied by the Routes design and require engineering verification.",
      "Unit prices, quotes and approved estimates belong to Estimator.",
      "Actual service amplifier findings are recorded separately from planned physical equipment.",
    ],
  };
}

function reconcileRoutesImport(existingEstimate, project) {
  const next = importRoutesProject(project);
  requireValue(existingEstimate?.schema === "hyperion.estimator-equipment/1" &&
    existingEstimate.projectId === next.projectId, "Reimport requires the same Estimator project.");
  const oldRows = new Map(existingEstimate.quantities.map(row => [row.sourceObjectId, row]));
  const newRows = new Map(next.quantities.map(row => [row.sourceObjectId, row]));
  const changes = [];
  for (const row of next.quantities) {
    const previous = oldRows.get(row.sourceObjectId);
    if (!previous) {
      changes.push({sourceObjectId: row.sourceObjectId, change: "added", quantity: row.quantity});
      continue;
    }
    if (previous.quantity !== row.quantity || previous.itemKey !== row.itemKey) {
      changes.push({sourceObjectId: row.sourceObjectId, change: "changed",
        previousQuantity: previous.quantity, quantity: row.quantity,
        previousItemKey: previous.itemKey, itemKey: row.itemKey});
    }
    if (previous.itemKey === row.itemKey) {
      row.unitPrice = previous.unitPrice;
      row.currency = previous.currency;
      row.priceSource = previous.priceSource;
      row.extendedCost = Number.isFinite(row.unitPrice) ? row.quantity * row.unitPrice : null;
    }
  }
  for (const previous of existingEstimate.quantities) {
    if (!newRows.has(previous.sourceObjectId)) {
      changes.push({sourceObjectId: previous.sourceObjectId, change: "removed", previousQuantity: previous.quantity});
    }
  }
  return {...next, previousRevision: existingEstimate.revision, changes};
}

if (require.main === module) {
  try {
    const project = JSON.parse(fs.readFileSync(process.argv[2], "utf8").replace(/^\uFEFF/, ""));
    process.stdout.write(JSON.stringify(importRoutesProject(project), null, 2) + "\n");
  } catch (error) {
    process.stderr.write("Equipment import failed. " + error.message + "\n");
    process.exitCode = 1;
  }
}

module.exports = {importRoutesProject, reconcileRoutesImport};
