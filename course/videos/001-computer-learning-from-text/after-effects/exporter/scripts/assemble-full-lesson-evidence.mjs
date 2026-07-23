import { createHash, randomBytes } from "node:crypto";
import {
  closeSync,
  constants,
  fstatSync,
  fsyncSync,
  lstatSync,
  openSync,
  readFileSync,
  realpathSync,
  renameSync,
  unlinkSync,
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
const timingPath = path.join(scriptRoot, "config", "video001-figma-scenes.json");

function isWithin(parent, child) {
  const relativePath = path.relative(parent, child);
  return relativePath === "" || (
    !path.isAbsolute(relativePath) &&
    relativePath !== ".." &&
    !relativePath.startsWith(".." + path.sep)
  );
}

function lstatOrUndefined(filePath) {
  try {
    return lstatSync(filePath);
  } catch (error) {
    if (error !== null && typeof error === "object" && error.code === "ENOENT") return undefined;
    throw error;
  }
}

function assertDirectory(filePath, label) {
  const details = lstatSync(filePath);
  if (!details.isDirectory() || details.isSymbolicLink()) {
    throw new Error(label + " must be a real directory, not a symlink");
  }
}

function assertEvidenceDirectories() {
  const evidenceParent = path.join(exporterRoot, "evidence");
  assertDirectory(exporterRoot, "Evidence exporter root");
  assertDirectory(evidenceParent, "Evidence directory");
  assertDirectory(evidenceDirectory, "Full-lesson evidence root");
  assertDirectory(rawDirectory, "Full-lesson raw evidence directory");
  const exporterRealPath = realpathSync(exporterRoot);
  const evidenceRealPath = realpathSync(evidenceDirectory);
  const rawRealPath = realpathSync(rawDirectory);
  if (
    !isWithin(exporterRealPath, evidenceRealPath) ||
    !isWithin(evidenceRealPath, rawRealPath)
  ) {
    throw new Error("Evidence directory containment is invalid");
  }
  return evidenceRealPath;
}

function assertEvidenceFile(filePath, label) {
  const evidenceRealPath = assertEvidenceDirectories();
  if (!isWithin(path.resolve(evidenceDirectory), path.resolve(filePath))) {
    throw new Error(label + " is outside the full-lesson evidence root");
  }
  const details = lstatSync(filePath);
  if (!details.isFile() || details.isSymbolicLink()) {
    throw new Error(label + " must be a regular file, not a symlink");
  }
  const actualPath = realpathSync(filePath);
  if (!isWithin(evidenceRealPath, actualPath)) {
    throw new Error(label + " resolves outside the full-lesson evidence root");
  }
}

function readEvidenceFile(filePath, label, encoding) {
  assertEvidenceFile(filePath, label);
  const descriptor = openSync(filePath, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    if (!fstatSync(descriptor).isFile()) {
      throw new Error(label + " must remain a regular file while it is read");
    }
    return readFileSync(descriptor, encoding);
  } finally {
    closeSync(descriptor);
  }
}

function validateTrustedTimingSource() {
  const details = lstatSync(timingPath);
  if (!details.isFile() || details.isSymbolicLink()) {
    throw new Error("Committed canonical timing must be a trusted regular file");
  }
  if (path.resolve(isolatedTimingPath) === path.resolve(timingPath)) return;
  const isolatedDetails = lstatOrUndefined(isolatedTimingPath);
  if (isolatedDetails === undefined) return;
  if (!isolatedDetails.isFile() || isolatedDetails.isSymbolicLink()) {
    throw new Error("Root-local timing must be a regular byte-identical copy of committed canonical timing");
  }
  const exporterRealPath = realpathSync(exporterRoot);
  if (!isWithin(exporterRealPath, realpathSync(isolatedTimingPath))) {
    throw new Error("Root-local timing resolves outside the evidence exporter root");
  }
  if (!readFileSync(isolatedTimingPath).equals(readFileSync(timingPath))) {
    throw new Error("Root-local timing is not byte-identical to committed canonical timing");
  }
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function sha256File(filePath) {
  const bytes = isWithin(path.resolve(evidenceDirectory), path.resolve(filePath))
    ? readEvidenceFile(filePath, path.basename(filePath))
    : readFileSync(filePath);
  return sha256(bytes);
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
    const source = isWithin(path.resolve(evidenceDirectory), path.resolve(filePath))
      ? readEvidenceFile(filePath, label, "utf8")
      : readFileSync(filePath, "utf8");
    return JSON.parse(source);
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

function exactKeys(value, expectedKeys, label) {
  const actualKeys = Object.keys(value).sort();
  const expected = [...expectedKeys].sort();
  if (canonicalJson(actualKeys) !== canonicalJson(expected)) {
    throw new Error(label + " has unexpected or missing fields");
  }
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

function prohibitedCredentialKey(key) {
  const normalized = key.toLowerCase().replace(/[^a-z0-9]/g, "");
  return (
    normalized.includes("authorization") ||
    normalized.includes("apikey") ||
    normalized.includes("pairingcode") ||
    normalized.includes("credential") ||
    normalized.includes("password") ||
    normalized.includes("secret") ||
    normalized.includes("token")
  );
}

function scanDecodedString(value, fileLabel) {
  if (/\/Users\//.test(value)) {
    throw new Error(fileLabel + " contains a prohibited mutable user path");
  }
  if (
    /\bBearer\s+[A-Za-z0-9._~+/=-]+/i.test(value) ||
    /\bAuthorization\s*[:=]/i.test(value)
  ) {
    throw new Error(fileLabel + " contains prohibited authorization or bearer material");
  }
}

function scanStructuredEvidence(value, fileLabel) {
  if (typeof value === "string") {
    scanDecodedString(value, fileLabel);
    return;
  }
  if (Array.isArray(value)) {
    for (const child of value) scanStructuredEvidence(child, fileLabel);
    return;
  }
  if (value === null || typeof value !== "object") return;
  for (const [key, child] of Object.entries(value)) {
    if (prohibitedCredentialKey(key)) {
      throw new Error(fileLabel + " contains a prohibited credential field");
    }
    scanStructuredEvidence(child, fileLabel);
  }
}

function scanRedaction(filePath) {
  const fileLabel = path.basename(filePath);
  const source = readEvidenceFile(filePath, fileLabel, "utf8");
  if (/\/Users\//.test(source)) {
    throw new Error(fileLabel + " contains a prohibited mutable user path");
  }
  if (/Bearer\s+[A-Za-z0-9._~-]+/i.test(source)) {
    throw new Error(fileLabel + " contains a prohibited bearer credential");
  }
  let values;
  try {
    values = filePath.endsWith(".jsonl")
      ? source.split(/\r?\n/).filter((line) => line.length > 0).map((line) => JSON.parse(line))
      : [JSON.parse(source)];
  } catch {
    throw new Error(fileLabel + " is not valid structured JSON evidence");
  }
  scanStructuredEvidence(values, fileLabel);
}

function scanGeneratedJsonBytes(bytes, label) {
  const source = bytes.toString("utf8");
  if (/\/Users\//.test(source)) {
    throw new Error(label + " contains a prohibited mutable user path");
  }
  if (/Bearer\s+[A-Za-z0-9._~+/=-]+/i.test(source)) {
    throw new Error(label + " contains prohibited bearer material");
  }
  let value;
  try {
    value = JSON.parse(source);
  } catch {
    throw new Error(label + " is not valid generated JSON evidence");
  }
  scanStructuredEvidence(value, label);
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

function validateRasterAssets(packageValue) {
  const assetByHash = new Map();
  for (const [index, rawAsset] of array(packageValue.assets, "Package assets").entries()) {
    const asset = object(rawAsset, "Package asset " + String(index + 1));
    const hash = string(asset.hash, "Package asset hash");
    if (!/^[0-9a-f]{64}$/.test(hash)) {
      throw new Error("Package asset hash must be lowercase SHA-256");
    }
    if (assetByHash.has(hash)) throw new Error("Package asset hashes must be unique");
    if (asset.mimeType !== "image/png") throw new Error("Package raster assets must use image/png");
    if (!Number.isSafeInteger(asset.byteLength) || asset.byteLength <= 0) {
      throw new Error("Package asset byteLength must be a positive safe integer");
    }
    const dataBase64 = string(asset.dataBase64, "Package asset dataBase64");
    if (
      dataBase64.length % 4 !== 0 ||
      !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(dataBase64)
    ) {
      throw new Error("Package asset dataBase64 is not canonical base64");
    }
    const bytes = Buffer.from(dataBase64, "base64");
    if (
      bytes.byteLength !== asset.byteLength ||
      bytes.toString("base64") !== dataBase64 ||
      sha256(bytes) !== hash
    ) {
      throw new Error("Package raster asset bytes, byteLength, and SHA-256 do not match");
    }
    assetByHash.set(hash, asset);
  }
  return assetByHash;
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

function rasterFallbackMap(values, label) {
  const entries = new Map();
  for (const rawValue of array(values, label)) {
    const value = object(rawValue, label + " entry");
    if (value.type !== "raster-fallback") continue;
    const nodeId = string(value.nodeId, label + " raster node ID");
    if (entries.has(nodeId)) throw new Error(label + " contains a duplicate raster node ID");
    entries.set(nodeId, value);
  }
  return entries;
}

function validateLiveEvidence({
  liveSession,
  bridgeEvents,
  expectedHash,
  importedMasterName
}) {
  if (liveSession.status !== "COMPLETE") {
    throw new Error("Live session must have successful COMPLETE status");
  }
  const sessionId = string(liveSession.sessionId, "Live session ID");
  const requestId = string(liveSession.requestId, "Live request ID");
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(requestId)) {
    throw new Error("Live request ID must be a server UUID");
  }
  if (liveSession.contentHash !== expectedHash) {
    throw new Error("Live session contains the wrong content hash");
  }

  const figma = object(liveSession.figma, "Live Figma evidence");
  const build = object(figma.build, "Live Figma build");
  if (
    build.status !== "PACKAGE_READY" ||
    build.shotCount !== 48 ||
    build.durationSeconds !== 840 ||
    build.contentHash !== expectedHash
  ) {
    throw new Error("Live Figma build is not a complete 48-shot package");
  }
  const exported = object(figma.export, "Live Figma export");
  if (
    exported.sessionId !== sessionId ||
    exported.requestId !== requestId ||
    exported.method !== "POST" ||
    exported.route !== "export" ||
    exported.status !== 202 ||
    exported.code !== "EXPORT_ACCEPTED" ||
    exported.contentHash !== expectedHash
  ) {
    throw new Error("Live Figma export request identity, route, or accepted status is invalid");
  }

  const bridge = object(liveSession.bridge, "Live bridge reference");
  if (bridge.requestId !== requestId || bridge.contentHash !== expectedHash) {
    throw new Error("Live bridge request identity does not match the session");
  }
  const acceptedEvents = bridgeEvents.filter((rawEvent) => {
    const event = object(rawEvent, "Bridge log event");
    return event.event === "export_accepted";
  });
  for (const rawEvent of acceptedEvents) {
    const event = object(rawEvent, "Bridge accepted event");
    exactKeys(event, [
      "timestamp",
      "event",
      "requestId",
      "method",
      "route",
      "status",
      "remoteAddress",
      "remoteFamily",
      "authenticated",
      "contentHash"
    ], "Bridge accepted event");
    if (
      typeof event.timestamp !== "string" ||
      !Number.isFinite(Date.parse(event.timestamp)) ||
      event.method !== "POST" ||
      event.route !== "export" ||
      event.status !== 202 ||
      event.remoteAddress !== "127.0.0.1" ||
      event.remoteFamily !== "IPv4" ||
      event.authenticated !== true ||
      event.contentHash !== expectedHash
    ) {
      throw new Error(
        "Bridge accepted event must prove authenticated POST export status 202 on IPv4 loopback 127.0.0.1"
      );
    }
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      string(event.requestId, "Bridge accepted request ID")
    )) {
      throw new Error("Bridge accepted request ID must be a UUID");
    }
  }
  if (acceptedEvents.filter((event) => event.requestId === requestId).length !== 1) {
    throw new Error("Bridge log must contain exactly one accepted event for the live request identity");
  }

  const afterEffects = object(liveSession.afterEffects, "Live After Effects evidence");
  const imported = object(afterEffects.import, "Live After Effects import");
  if (
    imported.status !== "IMPORTED" ||
    imported.sessionId !== sessionId ||
    imported.requestId !== requestId ||
    imported.contentHash !== expectedHash ||
    imported.createdCompCount !== 48 ||
    imported.createdMasterCompName !== importedMasterName
  ) {
    throw new Error("Live After Effects import or master identity is invalid");
  }
  if (afterEffects.queueCountAfterImport !== 0) {
    throw new Error("Live After Effects queue must be drained after import");
  }
  if (afterEffects.projectPath !== "/private/tmp/Video001-Exporter-Full-Lesson.aep") {
    throw new Error(
      "Live After Effects project path must be /private/tmp/Video001-Exporter-Full-Lesson.aep"
    );
  }
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
  validateTrustedTimingSource();
  assertEvidenceDirectories();
  for (const filePath of Object.values(rawPaths)) scanRedaction(filePath);
  const timing = validateTiming();
  const packageValue = object(readJson(rawPaths.package, "full-lesson package"), "Full-lesson package");
  const importReport = object(readJson(rawPaths.importReport, "full-lesson import report"), "Import report");
  const aeAudit = object(readJson(rawPaths.aeAudit, "full-lesson AE audit"), "AE audit");
  const liveSession = object(readJson(rawPaths.liveSession, "full-lesson live session"), "Live session");
  const bridgeEvents = readEvidenceFile(
    rawPaths.bridgeLog,
    "full-lesson bridge log",
    "utf8"
  )
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
  const packageAssetByHash = validateRasterAssets(packageValue);

  let expectedStart = 0;
  let packageNativeCount = 0;
  let packageRasterCount = 0;
  const packageRasterIds = [];
  const packageWarningRasterIds = [];
  const packageRasterById = new Map();
  const packageWarningById = new Map();
  const packageShotExpectations = [];
  const packageNodeIds = new Set();
  frames.forEach((rawFrame, index) => {
    const frame = object(rawFrame, "Package frame " + String(index + 1));
    const shot = timing.shots[index];
    const frameNativeNodeIds = [];
    const frameRasterById = new Map();
    const frameWarningById = new Map();
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
      const nodeId = string(node.id, "Package node ID");
      if (packageNodeIds.has(nodeId)) throw new Error("Package node IDs must be unique");
      packageNodeIds.add(nodeId);
      if (node.kind === "raster") {
        packageRasterCount += 1;
        const assetHash = string(node.assetHash, "Raster asset hash");
        if (!/^[0-9a-f]{64}$/.test(assetHash) || !packageAssetByHash.has(assetHash)) {
          throw new Error("Raster node references a missing or invalid exact asset SHA-256");
        }
        if (packageRasterById.has(nodeId)) throw new Error("Package raster node IDs must be unique");
        packageRasterIds.push(nodeId);
        packageRasterById.set(nodeId, {
          assetHash,
          name: string(node.name, "Raster node name")
        });
        frameRasterById.set(nodeId, packageRasterById.get(nodeId));
      } else {
        packageNativeCount += 1;
        frameNativeNodeIds.push(nodeId);
      }
    }
    for (const rawWarning of array(frame.warnings, "Package frame warnings")) {
      const warning = object(rawWarning, "Package frame warning");
      if (warning.fallback !== "png") {
        throw new Error("Package raster fallback warning must use png");
      }
      const nodeId = string(warning.nodeId, "Package raster warning node ID");
      if (packageWarningById.has(nodeId)) {
        throw new Error("Package raster warnings must identify each raster node once");
      }
      packageWarningRasterIds.push(nodeId);
      packageWarningById.set(nodeId, warning);
      frameWarningById.set(nodeId, warning);
    }
    const frameRasterIds = [...frameRasterById.keys()].sort();
    const frameWarningIds = [...frameWarningById.keys()].sort();
    if (canonicalJson(frameRasterIds) !== canonicalJson(frameWarningIds)) {
      throw new Error(
        "Package frame " + String(index + 1) +
        " raster nodes and warnings do not match within the same shot"
      );
    }
    packageShotExpectations.push({
      nativeNodeIds: frameNativeNodeIds.sort(),
      rasterById: frameRasterById
    });
  });
  if (expectedStart !== 840) {
    throw new Error("Full-lesson package durations and starts must cover exactly 840 seconds");
  }
  packageRasterIds.sort();
  packageWarningRasterIds.sort();
  if (canonicalJson(packageRasterIds) !== canonicalJson(packageWarningRasterIds)) {
    throw new Error("Package raster nodes and raster fallback warnings do not match exactly");
  }
  const referencedAssetHashes = new Set();
  for (const [nodeId, raster] of packageRasterById) {
    const warning = packageWarningById.get(nodeId);
    if (
      warning === undefined ||
      warning.nodeName !== raster.name ||
      typeof warning.property !== "string" ||
      warning.property.length === 0
    ) {
      throw new Error("Package raster warning identity does not match its raster node");
    }
    referencedAssetHashes.add(raster.assetHash);
  }
  if (
    referencedAssetHashes.size !== packageAssetByHash.size ||
    [...packageAssetByHash.keys()].some((hash) => !referencedAssetHashes.has(hash))
  ) {
    throw new Error("Package asset table must exactly match referenced raster asset hashes");
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
  const auditedRasterById = new Map();
  for (let index = 0; index < timing.shots.length; index += 1) {
    const timingShot = timing.shots[index];
    const packageShot = packageShotExpectations[index];
    const layer = object(masterLayers[index], "Master layer " + String(index + 1));
    const shot = object(auditedShots[index], "Audited shot " + String(index + 1));
    const expectedCompPattern = new RegExp(
      "^" + timingShot.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "_v(?!000)[0-9]{3}$"
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
    const shotNativeCount = finiteNumber(shot.nativeCount, "Audited native count");
    const shotNativeNodeIds = array(
      shot.nativeNodeIds,
      "Audited native node IDs"
    ).map((nodeId) => string(nodeId, "Audited native node ID")).sort();
    if (
      new Set(shotNativeNodeIds).size !== shotNativeNodeIds.length ||
      shotNativeCount !== packageShot.nativeNodeIds.length ||
      canonicalJson(shotNativeNodeIds) !== canonicalJson(packageShot.nativeNodeIds)
    ) {
      throw new Error(
        "Audited shot " + String(index + 1) +
        " native count or node IDs do not match its package frame"
      );
    }
    const shotRasterCount = finiteNumber(shot.rasterCount, "Audited raster count");
    const shotRasterById = new Map();
    auditedNativeCount += shotNativeCount;
    auditedRasterCount += shotRasterCount;
    for (const rawRaster of array(shot.rasterFallbacks, "Audited raster fallbacks")) {
      const raster = object(rawRaster, "Audited raster fallback");
      const nodeId = string(raster.nodeId, "Audited raster node ID");
      const assetHash = string(raster.assetHash, "Audited raster asset hash");
      auditedRasterIds.push(nodeId);
      if (!/^[0-9a-f]{64}$/.test(assetHash)) {
        throw new Error("Audited raster fallback has an invalid asset hash");
      }
      if (auditedRasterById.has(nodeId)) {
        throw new Error("AE audit contains duplicate raster fallback identities");
      }
      if (shotRasterById.has(nodeId)) {
        throw new Error("Audited shot contains duplicate raster fallback identities");
      }
      auditedRasterById.set(nodeId, assetHash);
      shotRasterById.set(nodeId, assetHash);
    }
    if (
      shotRasterCount !== packageShot.rasterById.size ||
      shotRasterById.size !== packageShot.rasterById.size
    ) {
      throw new Error(
        "Audited shot " + String(index + 1) +
        " raster count or node IDs do not match its package frame"
      );
    }
    for (const [nodeId, raster] of packageShot.rasterById) {
      if (shotRasterById.get(nodeId) !== raster.assetHash) {
        throw new Error(
          "Audited shot " + String(index + 1) +
          " raster node ID or asset hash does not match its package frame"
        );
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
  for (const [nodeId, raster] of packageRasterById) {
    if (auditedRasterById.get(nodeId) !== raster.assetHash) {
      throw new Error("AE audited raster asset hash does not match the package raster node");
    }
  }
  const importRasterIds = rasterFallbackIds(importReport.fallbacks, "Import report fallbacks");
  const auditFallbackRasterIds = rasterFallbackIds(aeAudit.fallbacks, "AE audit fallbacks");
  if (
    canonicalJson(importRasterIds) !== canonicalJson(packageRasterIds) ||
    canonicalJson(auditFallbackRasterIds) !== canonicalJson(packageRasterIds)
  ) {
    throw new Error("Package, import report, and AE audit raster fallback evidence do not match");
  }
  const importFallbackById = rasterFallbackMap(
    importReport.fallbacks,
    "Import report fallbacks"
  );
  const auditFallbackById = rasterFallbackMap(aeAudit.fallbacks, "AE audit fallbacks");
  for (const [nodeId, raster] of packageRasterById) {
    const warning = packageWarningById.get(nodeId);
    const importedFallback = importFallbackById.get(nodeId);
    const auditedFallback = auditFallbackById.get(nodeId);
    if (
      importedFallback === undefined ||
      auditedFallback === undefined ||
      importedFallback.nodeName !== raster.name ||
      importedFallback.property !== warning.property ||
      importedFallback.replacement !== warning.fallback ||
      canonicalJson(importedFallback) !== canonicalJson(auditedFallback)
    ) {
      throw new Error(
        "Package warning, import fallback, and AE audit raster identity do not match exactly"
      );
    }
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
  validateLiveEvidence({
    liveSession,
    bridgeEvents,
    expectedHash: computedHash,
    importedMasterName
  });

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

function artifactManifest(byteOverrides = new Map()) {
  return {
    schemaVersion: 1,
    generatedBy: "scripts/assemble-full-lesson-evidence.mjs",
    sha256: Object.fromEntries(manifestRelativePaths.map((relativePath) => [
      relativePath,
      byteOverrides.has(relativePath)
        ? sha256(byteOverrides.get(relativePath))
        : sha256File(path.join(exporterRoot, relativePath))
    ]))
  };
}

function assertSafeOutputPath(filePath, label) {
  const evidenceRealPath = assertEvidenceDirectories();
  if (!isWithin(path.resolve(evidenceDirectory), path.resolve(filePath))) {
    throw new Error(label + " is outside the full-lesson evidence root");
  }
  const details = lstatOrUndefined(filePath);
  if (details === undefined) return;
  if (!details.isFile() || details.isSymbolicLink()) {
    throw new Error(label + " must be a regular output file, not a symlink");
  }
  if (!isWithin(evidenceRealPath, realpathSync(filePath))) {
    throw new Error(label + " resolves outside the full-lesson evidence root");
  }
}

function atomicWriteDerived(filePath, bytes, label) {
  assertSafeOutputPath(filePath, label);
  const temporaryPath = path.join(
    evidenceDirectory,
    "." + path.basename(filePath) + "." + String(process.pid) + "." +
      randomBytes(8).toString("hex") + ".tmp"
  );
  let descriptor;
  try {
    descriptor = openSync(
      temporaryPath,
      constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
      0o600
    );
    writeFileSync(descriptor, bytes);
    fsyncSync(descriptor);
    closeSync(descriptor);
    descriptor = undefined;
    assertSafeOutputPath(filePath, label);
    renameSync(temporaryPath, filePath);
  } finally {
    if (descriptor !== undefined) closeSync(descriptor);
    const temporaryDetails = lstatOrUndefined(temporaryPath);
    if (
      temporaryDetails !== undefined &&
      temporaryDetails.isFile() &&
      !temporaryDetails.isSymbolicLink()
    ) {
      unlinkSync(temporaryPath);
    }
  }
}

function writeDerived(derived) {
  assertEvidenceDirectories();
  const auditBytes = jsonBytes(derived.audit);
  const summaryBytes = jsonBytes(derived.summary);
  const derivedByteOverrides = new Map([
    ["evidence/full-lesson/audit.json", auditBytes],
    ["evidence/full-lesson/summary.json", summaryBytes]
  ]);
  const manifestBytes = jsonBytes(artifactManifest(derivedByteOverrides));
  scanGeneratedJsonBytes(auditBytes, "Derived audit output");
  scanGeneratedJsonBytes(summaryBytes, "Derived summary output");
  scanGeneratedJsonBytes(manifestBytes, "Derived manifest output");
  assertSafeOutputPath(derivedPaths.audit, "Derived audit output");
  assertSafeOutputPath(derivedPaths.summary, "Derived summary output");
  assertSafeOutputPath(derivedPaths.manifest, "Derived manifest output");
  atomicWriteDerived(derivedPaths.audit, auditBytes, "Derived audit output");
  atomicWriteDerived(derivedPaths.summary, summaryBytes, "Derived summary output");
  atomicWriteDerived(
    derivedPaths.manifest,
    manifestBytes,
    "Derived manifest output"
  );
}

function verifyFile(filePath, value) {
  const expected = jsonBytes(value);
  const actual = readEvidenceFile(filePath, path.basename(filePath));
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
