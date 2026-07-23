import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const rootArgumentIndex = process.argv.indexOf("--root");
const exporterDir = rootArgumentIndex >= 0
  ? path.resolve(process.argv[rootArgumentIndex + 1])
  : fileURLToPath(new URL("../", import.meta.url));
const evidenceDir = path.join(exporterDir, "evidence");
const rawDir = path.join(evidenceDir, "raw");
const referencePath = path.join(exporterDir, "tests/fixtures/shot-32-reference.json");
const auditPath = path.join(evidenceDir, "shot-32-audit.json");
const comparisonPath = path.join(evidenceDir, "shot-32-comparison.json");
const manifestPath = path.join(rawDir, "shot-32-evidence-manifest.json");

const packagePath = path.join(rawDir, "shot-32-package.video001-ae.json");
const resultPath = path.join(rawDir, "shot-32-final-result.json");
const beforePath = path.join(rawDir, "shot-32-v001-before.json");
const afterPath = path.join(rawDir, "shot-32-v001-after.json");
const timingPath = path.join(rawDir, "shot-32-timing.json");
const metricsPath = path.join(rawDir, "shot-32-image-metrics.json");
const figmaPath = path.join(evidenceDir, "shot-32-figma.png");
const aePath = path.join(evidenceDir, "shot-32-ae.png");

function readJson(filePath) {
  return JSON.parse(readFileSync(filePath, "utf8"));
}

function sha256Bytes(value) {
  return createHash("sha256").update(value).digest("hex");
}

function sha256File(filePath) {
  return sha256Bytes(readFileSync(filePath));
}

function canonicalJson(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map(canonicalJson).join(",") + "]";
  return "{" + Object.keys(value).sort().map((key) => JSON.stringify(key) + ":" + canonicalJson(value[key])).join(",") + "}";
}

function jsonBytes(value) {
  return Buffer.from(JSON.stringify(value, null, 2) + "\n", "utf8");
}

function pngDimensions(filePath) {
  const value = readFileSync(filePath);
  if (value.subarray(0, 8).toString("hex") !== "89504e470d0a1a0a" || value.subarray(12, 16).toString("ascii") !== "IHDR") {
    throw new Error(path.basename(filePath) + " is not a PNG with an IHDR header");
  }
  return { width: value.readUInt32BE(16), height: value.readUInt32BE(20) };
}

const nodeFields = [
  "id",
  "name",
  "kind",
  "x",
  "y",
  "width",
  "height",
  "rotation",
  "opacity",
  "text",
  "textBox",
  "paragraph",
  "runs",
  "fill",
  "stroke",
  "strokeWidth",
  "radius",
  "assetHash"
];

function flattenNodes(nodes, parentPath = []) {
  const flattened = [];
  nodes.forEach((node, index) => {
    const entry = { path: [...parentPath, index], zIndex: index };
    nodeFields.forEach((field) => {
      if (node[field] !== null && node[field] !== undefined) entry[field] = node[field];
    });
    flattened.push(entry);
    flattened.push(...flattenNodes(node.children ?? [], [...parentPath, index]));
  });
  return flattened;
}

function stableAudit(value) {
  return {
    comp: value.comp,
    layers: value.layers,
    precompHierarchy: value.precompHierarchy,
    contentHash: value.contentHash,
    missingFonts: value.missingFonts,
    rasterFallbacks: value.rasterFallbacks,
    warnings: value.warnings
  };
}

function sourceRectFitsBox(check) {
  const tolerance = 0.01;
  const [boxWidth, boxHeight] = check.boxTextSize;
  const [boxLeft, boxTop] = check.boxTextPos;
  const rect = check.sourceRect;
  return rect.left >= boxLeft - tolerance &&
    rect.top >= boxTop - tolerance &&
    rect.left + rect.width <= boxLeft + boxWidth + tolerance &&
    rect.top + rect.height <= boxTop + boxHeight + tolerance;
}

function derive() {
  const packageValue = readJson(packagePath);
  const result = readJson(resultPath);
  const before = readJson(beforePath);
  const after = readJson(afterPath);
  const timing = readJson(timingPath);
  const metrics = readJson(metricsPath);
  const payload = result.payload;
  const frame = packageValue.frames[0];
  const timingShot = timing.shots.find((shot) => shot.figmaNodeId === frame.nodeId);
  const nodes = flattenNodes(frame.children);
  const nativeCount = nodes.filter((node) => node.kind !== "raster").length;
  const rasterCount = nodes.filter((node) => node.kind === "raster").length;
  const fingerprintValue = { ...packageValue, exportedAt: "", contentHash: "" };
  const contentHash = sha256Bytes(Buffer.from(canonicalJson(fingerprintValue), "utf8"));
  if (contentHash !== packageValue.contentHash) throw new Error("raw package contentHash is not canonical");
  if (result.status !== "COMPLETE") throw new Error("raw final wrapper result is not COMPLETE");
  if (readFileSync(resultPath, "utf8").includes("/Users/")) throw new Error("raw result contains a mutable user path");
  if (timing.source.figmaFileKey !== packageValue.source.fileKey || timing.source.figmaPageNodeId !== packageValue.source.pageId) {
    throw new Error("raw timing source does not match the package source");
  }
  if (!timingShot || timingShot.name !== frame.name || timingShot.duration !== frame.duration) {
    throw new Error("raw timing does not approve the exported frame");
  }

  const expected = {
    TXT_Title: {
      text: "The stored record crosses a separate boundary before model updates.",
      lineCount: 2
    },
    MODEL_Parameters: {
      text: "θ",
      requestedFont: "Sora-Bold",
      fallbackFont: "Inter-Regular",
      fauxBold: true
    },
    TXT_Caveat: {
      text: "PYTHON len() REPORTS STRING LENGTH · NOT ALWAYS VISIBLE-SYMBOL COUNT"
    }
  };
  const reference = {
    schemaVersion: packageValue.schemaVersion,
    exporterVersion: packageValue.exporterVersion,
    source: packageValue.source,
    target: packageValue.target,
    contentHash,
    packageSha256: sha256File(packagePath),
    timingSha256: sha256File(timingPath),
    frame: {
      nodeId: frame.nodeId,
      name: frame.name,
      width: frame.width,
      height: frame.height,
      duration: frame.duration,
      rootNodeCount: frame.children.length,
      nativeNodeCount: nativeCount,
      rasterNodeCount: rasterCount,
      warnings: frame.warnings,
      nodes
    },
    expected
  };

  const beforeStable = stableAudit(before);
  const afterStable = stableAudit(after);
  const beforeStableHash = sha256Bytes(Buffer.from(canonicalJson(beforeStable), "utf8"));
  const afterStableHash = sha256Bytes(Buffer.from(canonicalJson(afterStable), "utf8"));
  const v001Immutable = beforeStableHash === afterStableHash;
  const titleCheck = payload.textChecks.TXT_Title;
  const thetaCheck = payload.textChecks.MODEL_Parameters;
  const deckCheck = payload.textChecks.TXT_Deck;
  const caveatCheck = payload.textChecks.TXT_Caveat;
  const hardChecks = {
    thetaExact: thetaCheck.text === expected.MODEL_Parameters.text,
    middleDotExact: caveatCheck.text === expected.TXT_Caveat.text,
    titleExact: titleCheck.text === expected.TXT_Title.text,
    titleLineCount: titleCheck.lineCount,
    titleFullRangeExact: titleCheck.fullRangeText === titleCheck.text,
    titleNoClipping: sourceRectFitsBox(titleCheck),
    thetaFullRangeExact: thetaCheck.fullRangeText === expected.MODEL_Parameters.text,
    interThetaCoverage: payload.fonts["Inter-Regular"].theta === true,
    soraBoldThetaCoverage: payload.fonts["Sora-Bold"].theta === true,
    thetaResolvedFont: thetaCheck.font,
    thetaFauxBold: thetaCheck.fauxBold === true,
    ordinaryInterNotFauxBold: deckCheck.fauxBold === false,
    nativeCount,
    rasterCount,
    duplicateNoOp: payload.duplicate.status === "DUPLICATE_CONTENT" &&
      payload.duplicate.itemCountBefore === payload.duplicate.itemCountAfter,
    v001Immutable
  };
  // This check intentionally records the observed negative coverage instead of converting it to a pass boolean.
  hardChecks.soraBoldThetaCoverage = payload.fonts["Sora-Bold"].theta;

  const figmaDimensions = pngDimensions(figmaPath);
  const aeDimensions = pngDimensions(aePath);
  if (figmaDimensions.width !== aeDimensions.width || figmaDimensions.height !== aeDimensions.height) {
    throw new Error("reference and AE render dimensions differ");
  }
  const imageArtifacts = {
    figmaScreenshot: {
      file: "shot-32-figma.png",
      sha256: sha256File(figmaPath),
      ...figmaDimensions
    },
    afterEffectsRender: {
      file: "shot-32-ae.png",
      sha256: sha256File(aePath),
      ...aeDimensions
    }
  };
  const { projectPath: _discardedProjectPath, ...redactedAfter } = after;
  const audit = {
    ...redactedAfter,
    evidenceSchemaVersion: 2,
    environment: {
      afterEffectsVersion: payload.aeVersion,
      freshProjectBeforeImport: payload.freshProjectBeforeImport,
      sourceFileKey: packageValue.source.fileKey,
      sourcePageId: packageValue.source.pageId,
      sourceFrameId: frame.nodeId
    },
    reference: expected,
    fonts: payload.fonts,
    textChecks: payload.textChecks,
    original: payload.original,
    duplicate: payload.duplicate,
    changed: payload.changed,
    v001Immutable,
    v001StableHashes: { before: beforeStableHash, after: afterStableHash },
    mutatedPreexistingItems: payload.mutatedPreexistingItems,
    hardChecks,
    artifacts: imageArtifacts
  };
  const comparison = {
    status: Object.values(metrics.visualReview).filter((value) => typeof value === "string").every((value) => value === "PASS") ? "PASS" : "FAIL",
    dimensions: figmaDimensions,
    figma: imageArtifacts.figmaScreenshot,
    afterEffects: imageArtifacts.afterEffectsRender,
    visualReview: metrics.visualReview,
    pixelDiagnostics: metrics.pixelDiagnostics,
    rawMetrics: metrics.raw,
    metricTool: metrics.tool
  };
  return { reference, audit, comparison };
}

function artifactManifest() {
  const relativePaths = [
    "evidence/raw/shot-32-package.video001-ae.json",
    "evidence/raw/shot-32-final-result.json",
    "evidence/raw/shot-32-v001-before.json",
    "evidence/raw/shot-32-v001-after.json",
    "evidence/raw/shot-32-timing.json",
    "evidence/raw/shot-32-image-metrics.json",
    "evidence/raw/shot-32-live-session.json",
    "evidence/raw/shot-32-live-package.video001-ae.json",
    "evidence/raw/shot-32-live-bridge-log.jsonl",
    "evidence/raw/shot-32-live-import-report.json",
    "evidence/raw/shot-32-live-ae-result.json",
    "evidence/shot-32-figma.png",
    "evidence/shot-32-ae.png",
    "tests/fixtures/shot-32-reference.json",
    "evidence/shot-32-audit.json",
    "evidence/shot-32-comparison.json"
  ];
  return {
    schemaVersion: 1,
    generatedBy: "scripts/assemble-shot-32-evidence.mjs",
    sha256: Object.fromEntries(relativePaths.map((relativePath) => [
      relativePath,
      sha256File(path.join(exporterDir, relativePath))
    ]))
  };
}

function writeDerived(derived) {
  writeFileSync(referencePath, jsonBytes(derived.reference));
  writeFileSync(auditPath, jsonBytes(derived.audit));
  writeFileSync(comparisonPath, jsonBytes(derived.comparison));
  writeFileSync(manifestPath, jsonBytes(artifactManifest()));
}

function verifyFile(filePath, value) {
  const expected = jsonBytes(value);
  const actual = readFileSync(filePath);
  if (!actual.equals(expected)) {
    throw new Error(path.relative(exporterDir, filePath) + " is not the deterministic assembler output");
  }
}

function verifyDerived(derived) {
  verifyFile(referencePath, derived.reference);
  verifyFile(auditPath, derived.audit);
  verifyFile(comparisonPath, derived.comparison);
  verifyFile(manifestPath, artifactManifest());
}

const mode = process.argv[2];
const derived = derive();
if (mode === "--write") {
  writeDerived(derived);
  process.stdout.write("Shot 32 evidence assembled\n");
} else if (mode === "--verify") {
  verifyDerived(derived);
  process.stdout.write("Shot 32 evidence verified\n");
} else {
  throw new Error("Usage: node scripts/assemble-shot-32-evidence.mjs --write|--verify");
}
