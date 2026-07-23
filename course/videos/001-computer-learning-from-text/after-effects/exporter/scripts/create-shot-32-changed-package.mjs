import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

function canonicalJson(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
}

function packageContentHash(packageValue) {
  const fingerprint = { ...packageValue, exportedAt: "", contentHash: "" };
  return createHash("sha256").update(canonicalJson(fingerprint), "utf8").digest("hex");
}

const rootIndex = process.argv.indexOf("--root");
const exporterDir = rootIndex >= 0
  ? path.resolve(process.argv[rootIndex + 1])
  : fileURLToPath(new URL("../", import.meta.url));
const rawDir = path.join(exporterDir, "evidence", "raw");
const sourcePath = path.join(rawDir, "shot-32-live-package.video001-ae.json");
const outputPath = path.join(rawDir, "shot-32-changed-package.video001-ae.json");
const source = JSON.parse(readFileSync(sourcePath, "utf8"));
const changed = JSON.parse(JSON.stringify(source));

if (
  changed.schemaVersion !== "2.0.0" ||
  changed.target?.timeUnit !== "seconds" ||
  changed.frames?.length !== 1 ||
  changed.frames[0]?.nodeId !== "95:44" ||
  changed.frames[0]?.duration !== 28
) {
  throw new Error("Captured Shot 32 package is not the expected schema-2 seconds fixture");
}
if (source.contentHash !== packageContentHash(source)) {
  throw new Error("Captured Shot 32 source package contentHash is not canonical");
}

const background = changed.frames[0].children.find((node) => node.id === "95:45");
if (!background || background.name !== "BG_Base" || background.kind !== "rect" || background.opacity !== 1) {
  throw new Error("Expected BG_Base opacity source node is missing or changed");
}
background.opacity = 0.999999;
changed.contentHash = packageContentHash(changed);

const sourceWithoutHash = { ...source, contentHash: changed.contentHash };
sourceWithoutHash.frames = JSON.parse(JSON.stringify(source.frames));
const sourceBackground = sourceWithoutHash.frames[0].children.find((node) => node.id === "95:45");
sourceBackground.opacity = 0.999999;
if (canonicalJson(sourceWithoutHash) !== canonicalJson(changed)) {
  throw new Error("Changed package contains a delta other than contentHash and BG_Base opacity");
}

writeFileSync(outputPath, JSON.stringify(changed, null, 2) + "\n");
process.stdout.write(
  JSON.stringify({
    changed: true,
    contentHash: changed.contentHash,
    delta: {
      nodeId: background.id,
      nodeName: background.name,
      property: "opacity",
      before: 1,
      after: background.opacity
    },
    output: path.relative(exporterDir, outputPath)
  }) + "\n"
);
