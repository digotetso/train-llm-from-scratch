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
const changedPackagePath = path.join(rawDir, "shot-32-changed-package.video001-ae.json");
const resultPath = path.join(rawDir, "shot-32-final-result.json");
const beforePath = path.join(rawDir, "shot-32-v001-before.json");
const afterPath = path.join(rawDir, "shot-32-v001-after.json");
const v002Path = path.join(rawDir, "shot-32-v002.json");
const timingPath = path.join(rawDir, "shot-32-timing.json");
const metricsPath = path.join(rawDir, "shot-32-image-metrics.json");
const liveImportReportPath = path.join(rawDir, "shot-32-live-import-report.json");
const liveV002ImportReportPath = path.join(rawDir, "shot-32-live-v002-import-report.json");
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

function hierarchyUsesDuration(hierarchy, durationSeconds, durationFrames) {
  return hierarchy.durationSeconds === durationSeconds &&
    hierarchy.durationFrames === durationFrames &&
    hierarchy.duration === undefined &&
    hierarchy.children.every((child) =>
      child.warning === "cyclic precomp reference" ||
      hierarchyUsesDuration(child, durationSeconds, durationFrames)
    );
}

function findNode(nodes, nodeId) {
  for (const node of nodes) {
    if (node.id === nodeId) return node;
    const child = findNode(node.children ?? [], nodeId);
    if (child) return child;
  }
  return null;
}

function contentHashFor(packageValue) {
  const fingerprintValue = { ...packageValue, exportedAt: "", contentHash: "" };
  return sha256Bytes(Buffer.from(canonicalJson(fingerprintValue), "utf8"));
}

function derive() {
  const packageValue = readJson(packagePath);
  const changedPackage = readJson(changedPackagePath);
  const result = readJson(resultPath);
  const before = readJson(beforePath);
  const after = readJson(afterPath);
  const v002 = readJson(v002Path);
  const timing = readJson(timingPath);
  const metrics = readJson(metricsPath);
  const liveImportReport = readJson(liveImportReportPath);
  const liveV002ImportReport = readJson(liveV002ImportReportPath);
  const payload = result.payload;
  const frame = packageValue.frames[0];
  const timingShot = timing.shots.find((shot) => shot.figmaNodeId === frame.nodeId);
  const nodes = flattenNodes(frame.children);
  const nativeCount = nodes.filter((node) => node.kind !== "raster").length;
  const rasterCount = nodes.filter((node) => node.kind === "raster").length;
  const contentHash = contentHashFor(packageValue);
  if (contentHash !== packageValue.contentHash) throw new Error("raw package contentHash is not canonical");
  const changedContentHash = contentHashFor(changedPackage);
  if (changedContentHash !== changedPackage.contentHash) {
    throw new Error("raw changed package contentHash is not canonical");
  }
  if (packageValue.schemaVersion !== "2.0.0") {
    throw new Error("raw package must use exporter schema 2.0.0");
  }
  if (changedPackage.schemaVersion !== packageValue.schemaVersion) {
    throw new Error("raw changed package schema does not match the original package");
  }
  if (result.status !== "COMPLETE") throw new Error("raw final wrapper result is not COMPLETE");
  if (readFileSync(resultPath, "utf8").includes("/Users/")) throw new Error("raw result contains a mutable user path");
  if (timing.source.figmaFileKey !== packageValue.source.fileKey || timing.source.figmaPageNodeId !== packageValue.source.pageId) {
    throw new Error("raw timing source does not match the package source");
  }
  if (timing.canvas.timeUnit !== "seconds" || packageValue.target.timeUnit !== "seconds") {
    throw new Error('raw timing and package target must declare timeUnit "seconds"');
  }
  if (!timingShot || timingShot.name !== frame.name || timingShot.duration !== frame.duration) {
    throw new Error("raw timing does not approve the exported frame");
  }
  const expectedDurationFrames = frame.duration * packageValue.target.fps;
  if (
    before.comp.durationSeconds !== frame.duration ||
    before.comp.durationFrames !== expectedDurationFrames ||
    before.comp.duration !== undefined ||
    !hierarchyUsesDuration(before.precompHierarchy, frame.duration, expectedDurationFrames)
  ) {
    throw new Error("raw v001-before audit does not preserve explicit second/frame durations");
  }
  if (
    after.comp.durationSeconds !== frame.duration ||
    after.comp.durationFrames !== expectedDurationFrames ||
    after.comp.duration !== undefined ||
    !hierarchyUsesDuration(after.precompHierarchy, frame.duration, expectedDurationFrames)
  ) {
    throw new Error("raw After Effects audit does not preserve explicit second/frame durations");
  }
  if (
    v002.comp.name !== "S001_SH32_Repo_PreparationNotLearning_v002" ||
    v002.comp.durationSeconds !== frame.duration ||
    v002.comp.durationFrames !== expectedDurationFrames ||
    v002.comp.duration !== undefined ||
    v002.contentHash !== changedContentHash ||
    !hierarchyUsesDuration(v002.precompHierarchy, frame.duration, expectedDurationFrames)
  ) {
    throw new Error("raw v002 audit does not preserve the changed hash and explicit durations");
  }

  const expectedChangedPackage = JSON.parse(JSON.stringify(packageValue));
  const expectedChangedBackground = findNode(expectedChangedPackage.frames[0].children, "95:45");
  if (
    !expectedChangedBackground ||
    expectedChangedBackground.name !== "BG_Base" ||
    expectedChangedBackground.kind !== "rect" ||
    expectedChangedBackground.opacity !== 1
  ) {
    throw new Error("raw original package lacks the expected BG_Base opacity source");
  }
  expectedChangedBackground.opacity = 0.999999;
  expectedChangedPackage.contentHash = contentHashFor(expectedChangedPackage);
  if (canonicalJson(expectedChangedPackage) !== canonicalJson(changedPackage)) {
    throw new Error("raw changed package contains a delta other than BG_Base opacity and contentHash");
  }
  if (
    liveImportReport.contentHash !== contentHash ||
    liveImportReport.createdCompNames?.[0] !== "S001_SH32_Repo_PreparationNotLearning_v001" ||
    liveV002ImportReport.contentHash !== changedContentHash ||
    liveV002ImportReport.createdCompNames?.[0] !== "S001_SH32_Repo_PreparationNotLearning_v002"
  ) {
    throw new Error("raw live AE import reports do not match v001 and v002");
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
      durationSeconds: frame.duration,
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
    compDurationSeconds: after.comp.durationSeconds === frame.duration,
    compDurationFrames: after.comp.durationFrames === expectedDurationFrames,
    recursiveDurationsExact: hierarchyUsesDuration(
      after.precompHierarchy,
      frame.duration,
      expectedDurationFrames
    ),
    v002DurationSeconds: v002.comp.durationSeconds === frame.duration,
    v002DurationFrames: v002.comp.durationFrames === expectedDurationFrames,
    v002RecursiveDurationsExact: hierarchyUsesDuration(
      v002.precompHierarchy,
      frame.duration,
      expectedDurationFrames
    ),
    changedPackageCanonical: changedPackage.contentHash === changedContentHash,
    changedPackageExactDelta: canonicalJson(expectedChangedPackage) === canonicalJson(changedPackage),
    v002ContentHashExact: v002.contentHash === changedContentHash,
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
    evidenceSchemaVersion: 4,
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
    duplicate: {
      status: payload.duplicate.status,
      itemCountBefore: payload.duplicate.itemCountBefore,
      itemCountAfter: payload.duplicate.itemCountAfter
    },
    duplicateDetails: {
      v001Count: payload.duplicate.v001Count,
      v002CountBeforeChangedImport: payload.duplicate.v002Count,
      queueCountAfter: payload.duplicate.queueCountAfter
    },
    changed: payload.changed,
    changedPackage: {
      contentHash: changedContentHash,
      sha256: sha256File(changedPackagePath),
      delta: {
        nodeId: "95:45",
        nodeName: "BG_Base",
        property: "opacity",
        before: 1,
        after: 0.999999
      }
    },
    v002: {
      comp: v002.comp,
      contentHash: v002.contentHash,
      layerCount: v002.layers.length,
      missingFonts: v002.missingFonts,
      rasterFallbacks: v002.rasterFallbacks,
      warnings: v002.warnings
    },
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
    "evidence/raw/shot-32-changed-package.video001-ae.json",
    "evidence/raw/shot-32-final-result.json",
    "evidence/raw/shot-32-v001-before.json",
    "evidence/raw/shot-32-v001-after.json",
    "evidence/raw/shot-32-v002.json",
    "evidence/raw/shot-32-timing.json",
    "evidence/raw/shot-32-image-metrics.json",
    "evidence/raw/shot-32-live-session.json",
    "evidence/raw/shot-32-live-package.video001-ae.json",
    "evidence/raw/shot-32-live-bridge-log.jsonl",
    "evidence/raw/shot-32-live-import-report.json",
    "evidence/raw/shot-32-live-v002-import-report.json",
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
