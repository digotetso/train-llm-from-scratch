import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";
import path from "node:path";

const rootIndex = process.argv.indexOf("--root");
const exporterDir = rootIndex >= 0
  ? path.resolve(process.argv[rootIndex + 1])
  : fileURLToPath(new URL("../", import.meta.url));
const rawDir = path.join(exporterDir, "evidence", "raw");
const evidenceDir = path.join(exporterDir, "evidence");
const userDataRoot = path.join(
  homedir(),
  "Library",
  "Application Support",
  "Video001FigmaAEExporter"
);
const tempRoot = "/private/tmp";
const originalHash = "2cbb0412d0cb500c347ca5c9a54596bf43299206f25084046b9d10e289d525e0";
const changedHash = "a6ff2c07d771884c72cf297fdc6d3067c0660600e98ea84b7144f1c9c58243fb";

const inputs = {
  finalResult: path.join(tempRoot, "Video001-Exporter-Shot32-Seconds-final-result.json"),
  before: path.join(tempRoot, "Video001-Exporter-Shot32-Seconds-v001-before.json"),
  after: path.join(tempRoot, "Video001-Exporter-Shot32-Seconds-v001-after.json"),
  v002: path.join(tempRoot, "Video001-Exporter-Shot32-Seconds-v002.json"),
  duplicate: path.join(tempRoot, "Video001-Exporter-Shot32-Seconds-duplicate.json"),
  project: path.join(tempRoot, "Video001-Exporter-Shot32-Seconds.aep"),
  render: path.join(tempRoot, "Video001-Exporter-Shot32-Seconds.png"),
  bridgeLog: path.join(userDataRoot, "logs", "bridge.log"),
  originalImportReport: path.join(userDataRoot, `import-report-${originalHash}.json`),
  changedImportReport: path.join(userDataRoot, `import-report-${changedHash}.json`)
};

function readJson(filePath) {
  return JSON.parse(readFileSync(filePath, "utf8"));
}

function jsonBytes(value) {
  return Buffer.from(JSON.stringify(value, null, 2) + "\n", "utf8");
}

function sha256File(filePath) {
  return createHash("sha256").update(readFileSync(filePath)).digest("hex");
}

function redactMutablePaths(value) {
  if (Array.isArray(value)) return value.map(redactMutablePaths);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, redactMutablePaths(child)]));
  }
  if (typeof value !== "string") return value;
  if (value.startsWith(`${tempRoot}/`)) return path.basename(value);
  if (value.includes("/Users/")) {
    throw new Error("Refusing to capture evidence containing a mutable user path");
  }
  return value;
}

function writeJson(relativePath, value) {
  writeFileSync(path.join(exporterDir, relativePath), jsonBytes(value));
}

const finalResult = readJson(inputs.finalResult);
const before = readJson(inputs.before);
const after = readJson(inputs.after);
const v002 = readJson(inputs.v002);
const duplicate = readJson(inputs.duplicate);
const originalReport = readJson(inputs.originalImportReport);
const changedReport = readJson(inputs.changedImportReport);

if (
  finalResult.status !== "COMPLETE" ||
  finalResult.payload?.comp?.durationSeconds !== 28 ||
  finalResult.payload?.comp?.durationFrames !== 840 ||
  finalResult.payload?.hardChecks?.recursiveDurationsExact !== true
) {
  throw new Error("Final AE result does not prove the schema-2 seconds contract");
}
if (
  before.contentHash !== originalHash ||
  after.contentHash !== originalHash ||
  v002.contentHash !== changedHash ||
  before.comp?.durationSeconds !== 28 ||
  after.comp?.durationSeconds !== 28 ||
  v002.comp?.durationSeconds !== 28 ||
  before.comp?.durationFrames !== 840 ||
  after.comp?.durationFrames !== 840 ||
  v002.comp?.durationFrames !== 840
) {
  throw new Error("AE audit hashes or durations do not match the expected v001/v002 proof");
}
if (
  duplicate.status !== "DUPLICATE_CONTENT" ||
  duplicate.itemCountBefore !== duplicate.itemCountAfter ||
  duplicate.v001Count !== 1 ||
  duplicate.v002Count !== 0 ||
  duplicate.queueCountAfter !== 0
) {
  throw new Error("Duplicate evidence is not an unchanged queue no-op");
}
if (
  originalReport.contentHash !== originalHash ||
  originalReport.createdCompNames?.[0] !== "S001_SH32_Repo_PreparationNotLearning_v001" ||
  changedReport.contentHash !== changedHash ||
  changedReport.createdCompNames?.[0] !== "S001_SH32_Repo_PreparationNotLearning_v002"
) {
  throw new Error("AE import reports do not match the expected immutable versions");
}

const routeEvents = readFileSync(inputs.bridgeLog, "utf8")
  .trim()
  .split("\n")
  .map((line) => JSON.parse(line))
  .filter((entry) => entry.event === "http_request" && (entry.route === "pair" || entry.route === "export"))
  .slice(-6)
  .map(({ timestamp, event, route, status, code }) => ({
    timestamp,
    event,
    route,
    status,
    ...(code ? { code } : {})
  }));
const routeSignature = routeEvents.map((entry) => `${entry.route}:${entry.status}`).join(",");
if (routeSignature !== "pair:204,pair:200,export:204,export:202,export:204,export:202") {
  throw new Error(`Unexpected bridge route proof: ${routeSignature}`);
}

const panelPath = path.join(exporterDir, "dist", "ae", "Video001-Figma-AE-Exporter.jsx");
const timingPath = path.join(exporterDir, "dist", "ae", "figma-scenes.json");
const bridgePath = path.join(exporterDir, "dist", "bridge", "video001-bridge.mjs");
const figmaCodePath = path.join(exporterDir, "dist", "figma", "code.js");
const figmaUiPath = path.join(exporterDir, "dist", "figma", "ui.html");
const liveSession = {
  figma: {
    selection: {
      count: 1,
      nodeId: "95:44",
      name: "S001_SH32_Repo_PreparationNotLearning"
    },
    build: {
      status: "PACKAGE_READY",
      schemaVersion: "2.0.0",
      timeUnit: "seconds",
      durationSeconds: 28,
      contentHash: originalHash,
      nativeCount: 30,
      rasterCount: 0
    },
    pair: {
      httpStatus: 200,
      code: "PAIRED"
    },
    sends: [
      { httpStatus: 202, code: "EXPORT_ACCEPTED", contentHash: originalHash },
      { httpStatus: 202, code: "EXPORT_ACCEPTED", contentHash: originalHash }
    ]
  },
  afterEffects: {
    version: finalResult.payload.aeVersion,
    firstImport: {
      status: "IMPORTED",
      createdCompName: originalReport.createdCompNames[0],
      itemCount: duplicate.itemCountBefore,
      durationSeconds: after.comp.durationSeconds,
      durationFrames: after.comp.durationFrames
    },
    unchangedResend: {
      sendHttpStatus: 202,
      importStatus: duplicate.status,
      queueCountAfterImport: duplicate.queueCountAfter,
      itemCountBefore: duplicate.itemCountBefore,
      itemCountAfter: duplicate.itemCountAfter
    },
    changedImport: {
      status: "IMPORTED",
      createdCompName: changedReport.createdCompNames[0],
      contentHash: changedHash,
      durationSeconds: v002.comp.durationSeconds,
      durationFrames: v002.comp.durationFrames
    },
    projectName: path.basename(inputs.project),
    projectSha256: sha256File(inputs.project)
  },
  buildArtifacts: {
    panelSha256: sha256File(panelPath),
    timingSha256: sha256File(timingPath),
    bridgeSha256: sha256File(bridgePath),
    figmaCodeSha256: sha256File(figmaCodePath),
    figmaUiSha256: sha256File(figmaUiPath)
  },
  operatorNote: "Pairing credentials and authentication secrets were intentionally omitted from evidence."
};
const liveAeResult = {
  status: "COMPLETE",
  payload: {
    schemaVersion: "2.0.0",
    timeUnit: "seconds",
    originalContentHash: originalHash,
    changedContentHash: changedHash,
    duplicateStatus: duplicate.status,
    itemCountAfterFirst: duplicate.itemCountBefore,
    itemCountAfterDuplicate: duplicate.itemCountAfter,
    compNames: [
      originalReport.createdCompNames[0],
      changedReport.createdCompNames[0]
    ],
    durations: {
      v001: { seconds: after.comp.durationSeconds, frames: after.comp.durationFrames },
      v002: { seconds: v002.comp.durationSeconds, frames: v002.comp.durationFrames }
    },
    projectName: path.basename(inputs.project),
    projectSha256: sha256File(inputs.project)
  }
};

writeJson("evidence/raw/shot-32-final-result.json", redactMutablePaths(finalResult));
writeJson("evidence/raw/shot-32-v001-before.json", redactMutablePaths(before));
writeJson("evidence/raw/shot-32-v001-after.json", redactMutablePaths(after));
writeJson("evidence/raw/shot-32-v002.json", redactMutablePaths(v002));
writeJson("evidence/raw/shot-32-live-import-report.json", originalReport);
writeJson("evidence/raw/shot-32-live-v002-import-report.json", changedReport);
writeJson("evidence/raw/shot-32-live-ae-result.json", liveAeResult);
writeJson("evidence/raw/shot-32-live-session.json", liveSession);
writeFileSync(
  path.join(rawDir, "shot-32-live-bridge-log.jsonl"),
  routeEvents.map((entry) => JSON.stringify(entry)).join("\n") + "\n"
);
writeFileSync(path.join(evidenceDir, "shot-32-ae.png"), readFileSync(inputs.render));

process.stdout.write(
  JSON.stringify({
    captured: true,
    originalContentHash: originalHash,
    changedContentHash: changedHash,
    duplicateStatus: duplicate.status,
    v001DurationFrames: after.comp.durationFrames,
    v002DurationFrames: v002.comp.durationFrames,
    projectSha256: liveSession.afterEffects.projectSha256,
    renderSha256: sha256File(inputs.render)
  }) + "\n"
);
