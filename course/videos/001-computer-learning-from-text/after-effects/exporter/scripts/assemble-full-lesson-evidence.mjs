import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync
} from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptRoot = fileURLToPath(new URL("../", import.meta.url));

function parseArguments(argv) {
  let mode;
  let root = scriptRoot;
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--write" || argument === "--verify") {
      if (mode !== undefined) throw new Error("Choose exactly one of --write or --verify");
      mode = argument;
    } else if (argument === "--root") {
      const value = argv[index + 1];
      if (value === undefined || value.startsWith("--")) {
        throw new Error("--root requires a path");
      }
      root = path.resolve(value);
      index += 1;
    } else {
      throw new Error("Unknown argument " + argument);
    }
  }
  if (mode === undefined) {
    throw new Error("Usage: node scripts/assemble-full-lesson-evidence.mjs --write|--verify [--root PATH]");
  }
  return { mode, root };
}

const options = parseArguments(process.argv.slice(2));
const exporterRoot = options.root;
const evidenceDirectory = path.join(exporterRoot, "evidence", "full-lesson");
const rawDirectory = path.join(evidenceDirectory, "raw");
const rawPaths = {
  package: path.join(rawDirectory, "full-lesson-package.video001-ae.json"),
  importReport: path.join(rawDirectory, "full-lesson-import-report.json"),
  aeAudit: path.join(rawDirectory, "full-lesson-ae-audit.json"),
  liveSession: path.join(rawDirectory, "full-lesson-live-session.json"),
  bridgeLog: path.join(rawDirectory, "full-lesson-bridge-log.jsonl")
};
const derivedPaths = {
  audit: path.join(evidenceDirectory, "audit.json"),
  summary: path.join(evidenceDirectory, "summary.json"),
  manifest: path.join(evidenceDirectory, "manifest.json")
};
const isolatedTimingPath = path.join(exporterRoot, "config", "video001-figma-scenes.json");
const timingPath = existsSync(isolatedTimingPath)
  ? isolatedTimingPath
  : path.join(scriptRoot, "config", "video001-figma-scenes.json");

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function sha256File(filePath) {
  return sha256(readFileSync(filePath));
}

function canonicalJson(value) {
  if (value === null || typeof value !== "object") {
    const serialized = JSON.stringify(value);
    if (serialized === undefined) throw new Error("Cannot canonicalize a non-JSON value");
    return serialized;
  }
  if (Array.isArray(value)) return "[" + value.map(canonicalJson).join(",") + "]";
  return "{" + Object.keys(value).sort().map((key) =>
    JSON.stringify(key) + ":" + canonicalJson(value[key])
  ).join(",") + "}";
}

function jsonBytes(value) {
  return Buffer.from(JSON.stringify(value, null, 2) + "\n", "utf8");
}

function readJson(filePath, label) {
  try {
    return JSON.parse(readFileSync(filePath, "utf8"));
  } catch (error) {
    throw new Error("Cannot read " + label + " JSON from " + filePath + ": " + error.message);
  }
}

function object(value, label) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(label + " must be an object");
  }
  return value;
}

function array(value, label) {
  if (!Array.isArray(value)) throw new Error(label + " must be an array");
  return value;
}

function finiteNumber(value, label) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(label + " must be a finite number");
  }
  return value;
}

function string(value, label) {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(label + " must be a non-empty string");
  }
  return value;
}

function scanRedaction(filePath) {
  const value = readFileSync(filePath, "utf8");
  const findings = [
    ["/Users/", /\/Users\//],
    ["pairing credential", /pairingCode/i],
    ["authorization credential", /authorization/i],
    ["token credential", /"(?:token|accessToken|refreshToken|password|secret)"\s*:/i],
    ["Bearer credential", /Bearer\s+[A-Za-z0-9._~-]+/i]
  ];
  for (const [label, pattern] of findings) {
    if (pattern.test(value)) {
      throw new Error(path.basename(filePath) + " contains prohibited " + label + " or mutable user path");
    }
  }
}

function validateTiming() {
  const timing = object(readJson(timingPath, "canonical timing"), "Canonical timing");
  const canvas = object(timing.canvas, "Canonical timing canvas");
  const source = object(timing.source, "Canonical timing source");
  if (
    canvas.width !== 1920 ||
    canvas.height !== 1080 ||
    canvas.fps !== 30 ||
    canvas.timeUnit !== "seconds" ||
    canvas.duration !== 840
  ) {
    throw new Error("Canonical timing must be 1920x1080, 30 fps, seconds, and 840 seconds");
  }
  const shots = array(timing.shots, "Canonical timing shots");
  if (shots.length !== 48) throw new Error("Canonical timing must contain exactly 48 shots");
  let expectedStart = 0;
  const normalized = shots.map((rawShot, index) => {
    const shot = object(rawShot, "Canonical timing shot " + String(index + 1));
    if (shot.index !== index + 1) throw new Error("Canonical timing shot order is invalid");
    if (shot.start !== expectedStart) throw new Error("Canonical timing contains a gap or overlap");
    const duration = finiteNumber(shot.duration, "Canonical shot duration");
    const normalizedShot = {
      index: index + 1,
      nodeId: string(shot.figmaNodeId, "Canonical shot node ID"),
      name: string(shot.name, "Canonical shot name"),
      start: shot.start,
      duration
    };
    expectedStart += duration;
    return normalizedShot;
  });
  if (expectedStart !== 840) throw new Error("Canonical timing does not cover exactly 840 seconds");
  return {
    source: {
      fileKey: string(source.figmaFileKey, "Canonical source file key"),
      pageId: string(source.figmaPageNodeId, "Canonical source page ID")
    },
    target: { width: 1920, height: 1080, fps: 30, timeUnit: "seconds" },
    shots: normalized
  };
}

function flattenNodes(nodes, values = []) {
  for (const rawNode of array(nodes, "Frame children")) {
    const node = object(rawNode, "Frame child");
    values.push(node);
    flattenNodes(node.children ?? [], values);
  }
  return values;
}

function contentHashFor(packageValue) {
  const fingerprint = { ...packageValue, exportedAt: "", contentHash: "" };
  return sha256(Buffer.from(canonicalJson(fingerprint), "utf8"));
}

function collectContentHashes(value, output) {
  if (value === null || typeof value !== "object") return;
  if (Array.isArray(value)) {
    for (const entry of value) collectContentHashes(entry, output);
    return;
  }
  for (const [key, entry] of Object.entries(value)) {
    if (key === "contentHash") output.push(entry);
    collectContentHashes(entry, output);
  }
}

function requireTiedHash(value, expectedHash, label) {
  const hashes = [];
  collectContentHashes(value, hashes);
  if (hashes.length === 0) throw new Error(label + " contains no contentHash");
  for (const hash of hashes) {
    if (hash !== expectedHash) throw new Error(label + " contains the wrong content hash");
  }
}

function rasterFallbackIds(values, label) {
  const ids = [];
  for (const rawValue of array(values, label)) {
    const value = object(rawValue, label + " entry");
    if (value.type === "raster-fallback") {
      ids.push(string(value.nodeId, label + " raster node ID"));
    }
  }
  return ids.sort();
}

function hierarchyDurationsExact(hierarchyValue, duration, fps, label) {
  const hierarchy = object(hierarchyValue, label);
  if (hierarchy.warning !== undefined) {
    throw new Error(label + " contains a cyclic recursive precomp reference");
  }
  if (
    hierarchy.durationSeconds !== duration ||
    hierarchy.durationFrames !== Math.round(duration * fps)
  ) {
    throw new Error(label + " recursive precomp duration does not match its shot");
  }
  for (const [index, child] of array(hierarchy.children, label + " children").entries()) {
    hierarchyDurationsExact(child, duration, fps, label + " child " + String(index + 1));
  }
}

function derive() {
  for (const filePath of Object.values(rawPaths)) scanRedaction(filePath);
  const timing = validateTiming();
  const packageValue = object(readJson(rawPaths.package, "full-lesson package"), "Full-lesson package");
  const importReport = object(readJson(rawPaths.importReport, "full-lesson import report"), "Import report");
  const aeAudit = object(readJson(rawPaths.aeAudit, "full-lesson AE audit"), "AE audit");
  const liveSession = object(readJson(rawPaths.liveSession, "full-lesson live session"), "Live session");
  const bridgeEvents = readFileSync(rawPaths.bridgeLog, "utf8")
    .split(/\r?\n/)
    .filter((line) => line.length > 0)
    .map((line, index) => {
      try {
        return JSON.parse(line);
      } catch (error) {
        throw new Error("Bridge log line " + String(index + 1) + " is not JSON: " + error.message);
      }
    });

  if (packageValue.schemaVersion !== "2.0.0") {
    throw new Error("Full-lesson package must use schemaVersion 2.0.0");
  }
  const target = object(packageValue.target, "Package target");
  if (
    target.timeUnit !== "seconds" ||
    target.width !== timing.target.width ||
    target.height !== timing.target.height ||
    target.fps !== timing.target.fps
  ) {
    throw new Error('Full-lesson package target must use 1920x1080, 30 fps, and timeUnit "seconds"');
  }
  const source = object(packageValue.source, "Package source");
  if (source.fileKey !== timing.source.fileKey || source.pageId !== timing.source.pageId) {
    throw new Error("Full-lesson package source does not match canonical timing");
  }
  const computedHash = contentHashFor(packageValue);
  if (packageValue.contentHash !== computedHash) {
    throw new Error("Full-lesson package contentHash is not canonical; expected " + computedHash);
  }
  const frames = array(packageValue.frames, "Package frames");
  if (frames.length !== 48) throw new Error("Full-lesson package must contain exactly 48 frames");

  let expectedStart = 0;
  let packageNativeCount = 0;
  let packageRasterCount = 0;
  const packageRasterIds = [];
  const packageWarningRasterIds = [];
  frames.forEach((rawFrame, index) => {
    const frame = object(rawFrame, "Package frame " + String(index + 1));
    const shot = timing.shots[index];
    if (frame.nodeId !== shot.nodeId) {
      throw new Error("Full-lesson package node IDs must preserve canonical order");
    }
    if (
      frame.name !== shot.name ||
      frame.width !== timing.target.width ||
      frame.height !== timing.target.height
    ) {
      throw new Error("Full-lesson package frame identity or dimensions are not canonical");
    }
    if (frame.duration !== shot.duration || shot.start !== expectedStart) {
      throw new Error("Full-lesson package durations and starts must cover the canonical timeline without a gap or overlap");
    }
    expectedStart += frame.duration;
    for (const node of flattenNodes(frame.children)) {
      if (node.kind === "raster") {
        packageRasterCount += 1;
        packageRasterIds.push(string(node.id, "Raster node ID"));
        string(node.assetHash, "Raster asset hash");
      } else {
        packageNativeCount += 1;
      }
    }
    for (const rawWarning of array(frame.warnings, "Package frame warnings")) {
      const warning = object(rawWarning, "Package frame warning");
      if (warning.fallback !== "png") {
        throw new Error("Package raster fallback warning must use png");
      }
      packageWarningRasterIds.push(string(warning.nodeId, "Package raster warning node ID"));
    }
  });
  if (expectedStart !== 840) {
    throw new Error("Full-lesson package durations and starts must cover exactly 840 seconds");
  }
  packageRasterIds.sort();
  packageWarningRasterIds.sort();
  if (canonicalJson(packageRasterIds) !== canonicalJson(packageWarningRasterIds)) {
    throw new Error("Package raster nodes and raster fallback warnings do not match exactly");
  }

  if (importReport.contentHash !== computedHash) {
    throw new Error("Import report content hash does not match the package");
  }
  const importedMasterName = string(
    importReport.createdMasterCompName,
    "Import report master comp name"
  );
  if (!/^VIDEO001_MASTER_v[0-9]{3}$/.test(importedMasterName) || /_v000$/.test(importedMasterName)) {
    throw new Error("Import report must identify one VIDEO001_MASTER_vNNN comp");
  }
  const createdCompNames = array(importReport.createdCompNames, "Import report created comp names");
  if (createdCompNames.length !== 48) {
    throw new Error("Import report must identify exactly 48 created shot comps");
  }
  if (
    importReport.nativeCount !== packageNativeCount ||
    importReport.rasterCount !== packageRasterCount
  ) {
    throw new Error("Import report native/raster counts do not match the full package");
  }

  if (
    aeAudit.auditSchemaVersion !== 1 ||
    aeAudit.contentHash !== computedHash ||
    aeAudit.itemCountBefore !== aeAudit.itemCountAfter ||
    aeAudit.projectStateUnchanged !== true
  ) {
    throw new Error("AE audit schema, content hash, or read-only project-state proof is invalid");
  }
  const master = object(aeAudit.master, "AE audit master");
  if (
    master.name !== importedMasterName ||
    master.width !== 1920 ||
    master.height !== 1080 ||
    master.fps !== 30 ||
    master.durationSeconds !== 840 ||
    master.durationFrames !== 25_200
  ) {
    throw new Error("AE master must match VIDEO001_MASTER_vNNN at 1920x1080, 30 fps, 840 seconds, and 25200 frames");
  }
  const masterLayers = array(master.layers, "AE master layers");
  const auditedShots = array(aeAudit.shots, "AE audited shots");
  if (masterLayers.length !== 48 || auditedShots.length !== 48) {
    throw new Error("AE audit must contain exactly 48 master layers and 48 shots");
  }
  let auditedNativeCount = 0;
  let auditedRasterCount = 0;
  const auditedRasterIds = [];
  for (let index = 0; index < timing.shots.length; index += 1) {
    const timingShot = timing.shots[index];
    const layer = object(masterLayers[index], "Master layer " + String(index + 1));
    const shot = object(auditedShots[index], "Audited shot " + String(index + 1));
    const expectedCompPattern = new RegExp(
      "^" + timingShot.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "_v[0-9]{3}$"
    );
    if (
      layer.index !== timingShot.index ||
      layer.nodeId !== timingShot.nodeId ||
      !expectedCompPattern.test(layer.sourceComp) ||
      layer.name !== layer.sourceComp ||
      shot.name !== layer.sourceComp ||
      createdCompNames[index] !== layer.sourceComp
    ) {
      throw new Error("Master layer " + String(index + 1) + " has the wrong exact source comp");
    }
    if (
      layer.startTime !== timingShot.start ||
      layer.inPoint !== timingShot.start
    ) {
      if (layer.startTime > timingShot.start || layer.inPoint > timingShot.start) {
        throw new Error("Master layer " + String(index + 1) + " introduces a timing gap");
      }
      throw new Error("Master layer " + String(index + 1) + " introduces a timing overlap");
    }
    if (layer.outPoint !== timingShot.start + timingShot.duration) {
      throw new Error("Master layer " + String(index + 1) + " has the wrong out point");
    }
    if (
      shot.index !== timingShot.index ||
      shot.nodeId !== timingShot.nodeId ||
      shot.configuredName !== timingShot.name ||
      shot.contentHash !== computedHash ||
      shot.width !== 1920 ||
      shot.height !== 1080 ||
      shot.fps !== 30 ||
      shot.durationSeconds !== timingShot.duration ||
      shot.durationFrames !== timingShot.duration * 30
    ) {
      throw new Error("Audited shot " + String(index + 1) + " does not match canonical timing");
    }
    hierarchyDurationsExact(
      shot.hierarchy,
      timingShot.duration,
      30,
      "Audited shot " + String(index + 1)
    );
    auditedNativeCount += finiteNumber(shot.nativeCount, "Audited native count");
    auditedRasterCount += finiteNumber(shot.rasterCount, "Audited raster count");
    for (const rawRaster of array(shot.rasterFallbacks, "Audited raster fallbacks")) {
      const raster = object(rawRaster, "Audited raster fallback");
      auditedRasterIds.push(string(raster.nodeId, "Audited raster node ID"));
      if (!/^[0-9a-f]{64}$/.test(string(raster.assetHash, "Audited raster asset hash"))) {
        throw new Error("Audited raster fallback has an invalid asset hash");
      }
    }
  }
  auditedRasterIds.sort();
  if (
    auditedNativeCount !== packageNativeCount ||
    auditedRasterCount !== packageRasterCount ||
    canonicalJson(auditedRasterIds) !== canonicalJson(packageRasterIds)
  ) {
    throw new Error("AE audit contains an unexpected raster fallback or native/raster count");
  }
  const importRasterIds = rasterFallbackIds(importReport.fallbacks, "Import report fallbacks");
  const auditFallbackRasterIds = rasterFallbackIds(aeAudit.fallbacks, "AE audit fallbacks");
  if (
    canonicalJson(importRasterIds) !== canonicalJson(packageRasterIds) ||
    canonicalJson(auditFallbackRasterIds) !== canonicalJson(packageRasterIds)
  ) {
    throw new Error("Package, import report, and AE audit raster fallback evidence do not match");
  }
  if (
    canonicalJson(array(aeAudit.missingFonts, "AE audit missing fonts")) !==
      canonicalJson(array(importReport.missingFonts, "Import report missing fonts")) ||
    canonicalJson(array(aeAudit.fallbacks, "AE audit fallbacks")) !==
      canonicalJson(array(importReport.fallbacks, "Import report fallbacks")) ||
    canonicalJson(array(aeAudit.warnings, "AE audit warnings")) !==
      canonicalJson(array(importReport.warnings, "Import report warnings"))
  ) {
    throw new Error("AE audit fallback, font, or warning evidence does not match the import report");
  }

  requireTiedHash(liveSession, computedHash, "Live session");
  requireTiedHash(bridgeEvents, computedHash, "Bridge log");

  const derivedAudit = {
    evidenceSchemaVersion: 1,
    contentHash: computedHash,
    timingSha256: sha256File(timingPath),
    packageSha256: sha256File(rawPaths.package),
    importReportSha256: sha256File(rawPaths.importReport),
    aeAuditSha256: sha256File(rawPaths.aeAudit),
    source: packageValue.source,
    target: packageValue.target,
    itemCountBefore: aeAudit.itemCountBefore,
    itemCountAfter: aeAudit.itemCountAfter,
    projectStateUnchanged: aeAudit.projectStateUnchanged,
    master,
    shots: auditedShots,
    nativeCount: auditedNativeCount,
    rasterCount: auditedRasterCount,
    missingFonts: aeAudit.missingFonts,
    fallbacks: aeAudit.fallbacks,
    warnings: aeAudit.warnings
  };
  if (liveSession.fixture === "synthetic-test-only") {
    derivedAudit.fixture = "synthetic-test-only";
  }
  const summary = {
    status: "PASS",
    shotCount: 48,
    durationSeconds: 840,
    durationFrames: 25_200,
    nativeCount: auditedNativeCount,
    rasterCount: auditedRasterCount,
    missingFontCount: aeAudit.missingFonts.length,
    fallbackCount: aeAudit.fallbacks.length,
    contentHash: computedHash
  };
  return { audit: derivedAudit, summary };
}

const manifestRelativePaths = [
  "evidence/full-lesson/raw/full-lesson-package.video001-ae.json",
  "evidence/full-lesson/raw/full-lesson-import-report.json",
  "evidence/full-lesson/raw/full-lesson-ae-audit.json",
  "evidence/full-lesson/raw/full-lesson-live-session.json",
  "evidence/full-lesson/raw/full-lesson-bridge-log.jsonl",
  "evidence/full-lesson/audit.json",
  "evidence/full-lesson/summary.json"
];

function artifactManifest() {
  return {
    schemaVersion: 1,
    generatedBy: "scripts/assemble-full-lesson-evidence.mjs",
    sha256: Object.fromEntries(manifestRelativePaths.map((relativePath) => [
      relativePath,
      sha256File(path.join(exporterRoot, relativePath))
    ]))
  };
}

function writeDerived(derived) {
  mkdirSync(evidenceDirectory, { recursive: true });
  writeFileSync(derivedPaths.audit, jsonBytes(derived.audit));
  writeFileSync(derivedPaths.summary, jsonBytes(derived.summary));
  writeFileSync(derivedPaths.manifest, jsonBytes(artifactManifest()));
}

function verifyFile(filePath, value) {
  const expected = jsonBytes(value);
  const actual = readFileSync(filePath);
  if (!actual.equals(expected)) {
    throw new Error(
      path.relative(exporterRoot, filePath) + " is not the deterministic assembler output"
    );
  }
}

function verifyDerived(derived) {
  verifyFile(derivedPaths.audit, derived.audit);
  verifyFile(derivedPaths.summary, derived.summary);
  verifyFile(derivedPaths.manifest, artifactManifest());
  for (const filePath of Object.values(derivedPaths)) scanRedaction(filePath);
}

const derived = derive();
if (options.mode === "--write") {
  writeDerived(derived);
  process.stdout.write("Full-lesson evidence assembled\n");
} else {
  verifyDerived(derived);
  process.stdout.write("Full-lesson evidence verified\n");
}
