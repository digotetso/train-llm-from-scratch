import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

function argumentValue(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) {
    throw new Error(`Missing required ${name} argument`);
  }
  return process.argv[index + 1];
}

function canonicalJson(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
}

function contentHash(packageValue) {
  const fingerprint = { ...packageValue, exportedAt: "", contentHash: "" };
  return createHash("sha256").update(canonicalJson(fingerprint), "utf8").digest("hex");
}

const sourcePath = path.resolve(argumentValue("--source"));
const rootIndex = process.argv.indexOf("--root");
const exporterDir = rootIndex >= 0
  ? path.resolve(process.argv[rootIndex + 1])
  : fileURLToPath(new URL("../", import.meta.url));
const rawDir = path.join(exporterDir, "evidence", "raw");
const sourceBytes = readFileSync(sourcePath);
const sourceText = sourceBytes.toString("utf8");
const packageValue = JSON.parse(sourceText);

if (packageValue.schemaVersion !== "2.0.0") {
  throw new Error(`Expected schemaVersion 2.0.0, received ${String(packageValue.schemaVersion)}`);
}
if (packageValue.target?.timeUnit !== "seconds") {
  throw new Error('Expected target.timeUnit "seconds"');
}
if (packageValue.frames?.length !== 1 || packageValue.frames[0]?.nodeId !== "95:44") {
  throw new Error("Expected the single selected Shot 32 frame (95:44)");
}
if (packageValue.frames[0].duration !== 28) {
  throw new Error(`Expected Shot 32 duration 28 seconds, received ${String(packageValue.frames[0].duration)}`);
}
const computedHash = contentHash(packageValue);
if (packageValue.contentHash !== computedHash) {
  throw new Error(`Package contentHash mismatch: expected ${computedHash}`);
}
if (
  sourceText.includes("/Users/") ||
  /"token"\s*:/i.test(sourceText) ||
  /"pairingCode"\s*:/i.test(sourceText)
) {
  throw new Error("Package contains a mutable user path or pairing credential");
}

for (const fileName of [
  "shot-32-package.video001-ae.json",
  "shot-32-live-package.video001-ae.json"
]) {
  writeFileSync(path.join(rawDir, fileName), sourceBytes);
}

process.stdout.write(
  JSON.stringify({
    captured: true,
    contentHash: computedHash,
    durationSeconds: packageValue.frames[0].duration,
    schemaVersion: packageValue.schemaVersion,
    sourceSha256: createHash("sha256").update(sourceBytes).digest("hex")
  }) + "\n"
);
