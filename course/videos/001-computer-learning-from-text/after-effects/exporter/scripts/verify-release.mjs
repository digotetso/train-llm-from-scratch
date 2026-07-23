import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { basename, dirname, isAbsolute, join, posix, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { inflateRawSync } from "node:zlib";

const RELEASE_VERSION = "0.2.0";
const RELEASE_ARCHIVE_NAME = `video001-figma-ae-exporter-${RELEASE_VERSION}.tar.gz`;
const RELEASE_CHECKSUM_NAME = `video001-figma-ae-exporter-${RELEASE_VERSION}.sha256`;
const RELEASE_MTIME = Math.floor(Date.parse("2026-07-23T00:00:00Z") / 1000);
const TAR_BLOCK_SIZE = 512;
const CANONICAL_GZIP_HEADER = Buffer.from([0x1f, 0x8b, 8, 0, 0, 0, 0, 0, 2, 255]);
const rootFromScript = dirname(dirname(fileURLToPath(import.meta.url)));
const EXPECTED_MEMBERS = new Set([
  "LICENSE",
  "NOTICE",
  "PROVENANCE.md",
  "README.md",
  "config/video001-figma-scenes.json",
  "dist/ae/Video001-Figma-AE-Exporter.jsx",
  "dist/ae/audit-export.jsx",
  "dist/ae/audit-full-lesson.jsx",
  "dist/ae/figma-scenes.json",
  "dist/bridge/video001-bridge.mjs",
  "dist/figma/code.js",
  "dist/figma/manifest.json",
  "dist/figma/ui.html",
  "package-lock.json",
  "package.json",
  "scripts/build-release.mjs",
  "scripts/build.mjs",
  "scripts/generate-figma-manifest.mjs",
  "scripts/verify-release.mjs",
  "src/ae/audit-export.jsx",
  "src/ae/audit-full-lesson.jsx",
  "src/ae/import-core.jsxinc",
  "src/ae/importer.jsxinc",
  "src/ae/panel.jsx",
  "src/bridge/auth.ts",
  "src/bridge/cli.ts",
  "src/bridge/ownership.ts",
  "src/bridge/paths.ts",
  "src/bridge/queue.ts",
  "src/bridge/server.ts",
  "src/bridge/streaming-package.ts",
  "src/bridge/work-control.ts",
  "src/figma/controller.ts",
  "src/figma/serializer.ts",
  "src/figma/ui.html",
  "src/figma/ui.ts",
  "src/shared/canonical-json.ts",
  "src/shared/contract.ts",
  "src/shared/figma-network.d.mts",
  "src/shared/figma-network.mjs",
  "src/shared/limits.ts",
  "src/shared/sha256.ts",
  "src/shared/utf8.ts",
  "tsconfig.controller.json",
  "tsconfig.json"
]);

function stringField(block, offset, length) {
  const bytes = block.subarray(offset, offset + length);
  const nul = bytes.indexOf(0);
  return bytes.subarray(0, nul === -1 ? bytes.length : nul).toString("utf8");
}

function octalField(block, offset, length, label) {
  const value = stringField(block, offset, length).trim();
  if (!/^[0-7]+$/u.test(value)) throw new Error(`${label} is not canonical octal`);
  const parsed = Number.parseInt(value, 8);
  if (!Number.isSafeInteger(parsed)) throw new Error(`${label} exceeds the safe integer range`);
  return parsed;
}

function writeString(block, offset, length, value, label) {
  const bytes = Buffer.from(value, "utf8");
  if (bytes.length > length) throw new RangeError(`${label} does not fit in its ustar field`);
  bytes.copy(block, offset);
}

function writeOctal(block, offset, length, value, label) {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new TypeError(`${label} must be a non-negative integer`);
  }
  const octal = value.toString(8);
  if (octal.length > length - 1) throw new RangeError(`${label} does not fit in its ustar field`);
  writeString(block, offset, length, `${octal.padStart(length - 1, "0")}\0`, label);
}

function splitUstarPath(path) {
  if (Buffer.byteLength(path, "utf8") <= 100) return { name: path, prefix: "" };
  const slashPositions = [...path.matchAll(/\//gu)].map((match) => match.index);
  for (let index = slashPositions.length - 1; index >= 0; index -= 1) {
    const split = slashPositions[index];
    const prefix = path.slice(0, split);
    const name = path.slice(split + 1);
    if (Buffer.byteLength(prefix, "utf8") <= 155 && Buffer.byteLength(name, "utf8") <= 100) {
      return { name, prefix };
    }
  }
  throw new RangeError(`${path} does not fit in a POSIX ustar name`);
}

function canonicalUstarHeader(path, size) {
  const { name, prefix } = splitUstarPath(path);
  const block = Buffer.alloc(TAR_BLOCK_SIZE);
  writeString(block, 0, 100, name, "name");
  writeOctal(block, 100, 8, 0o644, "mode");
  writeOctal(block, 108, 8, 0, "uid");
  writeOctal(block, 116, 8, 0, "gid");
  writeOctal(block, 124, 12, size, "size");
  writeOctal(block, 136, 12, RELEASE_MTIME, "mtime");
  block.fill(0x20, 148, 156);
  block[156] = "0".charCodeAt(0);
  writeString(block, 257, 6, "ustar\0", "magic");
  writeString(block, 263, 2, "00", "version");
  writeString(block, 265, 32, "root", "owner");
  writeString(block, 297, 32, "root", "group");
  writeString(block, 345, 155, prefix, "prefix");
  const checksum = block.reduce((sum, byte) => sum + byte, 0);
  writeString(block, 148, 8, `${checksum.toString(8).padStart(6, "0")}\0 `, "checksum");
  return block;
}

function assertSafeMemberName(name) {
  if (
    name.length === 0 ||
    name.includes("\\") ||
    name.includes("\0") ||
    isAbsolute(name) ||
    posix.isAbsolute(name) ||
    posix.normalize(name) !== name ||
    name.split("/").some((part) => part === "" || part === "." || part === "..")
  ) {
    throw new Error(`Archive member ${JSON.stringify(name)} is an unsafe path`);
  }
  const lower = name.toLowerCase();
  const base = posix.basename(lower);
  if (
    lower.includes(".figma-plugin-id") ||
    lower.split("/").includes("evidence") ||
    lower.endsWith(".aep") ||
    [".env", ".npmrc", "auth.json", "credentials.json", "secrets.json", "state.json"].includes(base)
  ) {
    throw new Error(`Archive contains prohibited mutable or credential path ${name}`);
  }
}

function assertSafeContent(name, bytes) {
  const text = bytes.toString("utf8");
  for (const [description, pattern] of [
    [
      "mutable user path",
      /\/Users\/[^/\s]+|\/home\/[^/\s]+|\/private\/(?:tmp|var\/folders)\/[^/\s]+|[A-Za-z]:\\Users\\[^\\\s]+/u
    ],
    ["private key credential", /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/u],
    ["bearer credential", /\bBearer [A-Za-z0-9._~-]{12,}\b/u],
    ["cloud credential", /\b(?:AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9_-]{16,}|gh[op]_[A-Za-z0-9]{20,}|figd_[A-Za-z0-9_-]{16,})\b/u],
    [
      "credential literal",
      /\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password)\b\s*[:=]\s*["'][^"'\r\n]{8,}["']/iu
    ]
  ]) {
    if (pattern.test(text)) throw new Error(`${name} contains a prohibited ${description}`);
  }
}

function parseUstar(tar) {
  if (tar.length % TAR_BLOCK_SIZE !== 0) throw new Error("Archive is not block-aligned ustar");
  const members = [];
  const seen = new Set();
  let offset = 0;
  while (offset < tar.length) {
    const block = tar.subarray(offset, offset + TAR_BLOCK_SIZE);
    if (block.every((byte) => byte === 0)) break;
    if (stringField(block, 257, 6) !== "ustar" || stringField(block, 263, 2) !== "00") {
      throw new Error("Archive member does not use POSIX ustar metadata");
    }
    const prefix = stringField(block, 345, 155);
    const name = [prefix, stringField(block, 0, 100)].filter(Boolean).join("/");
    assertSafeMemberName(name);
    if (seen.has(name)) throw new Error(`Archive contains duplicate member ${name}`);
    seen.add(name);
    const size = octalField(block, 124, 12, `${name} size`);
    const checksum = octalField(block, 148, 8, `${name} checksum`);
    const checksumBlock = Buffer.from(block);
    checksumBlock.fill(0x20, 148, 156);
    const calculated = checksumBlock.reduce((sum, byte) => sum + byte, 0);
    if (checksum !== calculated) throw new Error(`${name} has an invalid ustar header checksum`);
    if (!block.equals(canonicalUstarHeader(name, size))) {
      throw new Error(`${name} does not have a byte-canonical POSIX ustar header`);
    }
    const payloadStart = offset + TAR_BLOCK_SIZE;
    const payloadEnd = payloadStart + size;
    const paddedEnd = payloadStart + Math.ceil(size / TAR_BLOCK_SIZE) * TAR_BLOCK_SIZE;
    if (payloadEnd > tar.length || paddedEnd > tar.length) {
      throw new Error(`${name} extends beyond the archive boundary`);
    }
    const payload = tar.subarray(payloadStart, payloadEnd);
    if (!tar.subarray(payloadEnd, paddedEnd).every((byte) => byte === 0)) {
      throw new Error(`${name} has non-zero ustar payload padding`);
    }
    assertSafeContent(name, payload);
    members.push({ name, payload });
    offset = paddedEnd;
  }
  if (tar.length - offset !== TAR_BLOCK_SIZE * 2 || !tar.subarray(offset).every((byte) => byte === 0)) {
    throw new Error("Archive does not end with canonical zero ustar blocks");
  }
  if (
    seen.size !== EXPECTED_MEMBERS.size ||
    [...seen].some((name) => !EXPECTED_MEMBERS.has(name))
  ) {
    const extra = [...seen].filter((name) => !EXPECTED_MEMBERS.has(name));
    const missing = [...EXPECTED_MEMBERS].filter((name) => !seen.has(name));
    throw new Error(
      `Archive allowlist mismatch (extra: ${extra.join(", ") || "none"}; missing: ${missing.join(", ") || "none"})`
    );
  }
  return members;
}

function memberText(members, name) {
  const member = members.find((candidate) => candidate.name === name);
  if (member === undefined) throw new Error(`Archive is missing ${name}`);
  return member.payload.toString("utf8");
}

function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function inflateCanonicalGzip(archive) {
  if (
    archive.length < CANONICAL_GZIP_HEADER.length + 8 ||
    !archive.subarray(0, CANONICAL_GZIP_HEADER.length).equals(CANONICAL_GZIP_HEADER)
  ) {
    throw new Error("Release archive is not a canonical zero-time gzip stream");
  }
  let result;
  try {
    result = inflateRawSync(archive.subarray(CANONICAL_GZIP_HEADER.length), { info: true });
  } catch (error) {
    throw new Error("Release archive gzip stream is invalid", { cause: error });
  }
  const compressedLength = Number(result.engine.bytesWritten);
  const trailerOffset = CANONICAL_GZIP_HEADER.length + compressedLength;
  if (
    !Number.isSafeInteger(compressedLength) ||
    compressedLength <= 0 ||
    trailerOffset + 8 !== archive.length
  ) {
    throw new Error("Release archive must contain exactly one gzip member with no trailing bytes");
  }
  const tar = result.buffer;
  if (
    archive.readUInt32LE(trailerOffset) !== crc32(tar) ||
    archive.readUInt32LE(trailerOffset + 4) !== (tar.length >>> 0)
  ) {
    throw new Error("Release archive has an invalid gzip trailer");
  }
  return tar;
}

function runtimeExporterVersion(bundle) {
  const references = [
    ...bundle.matchAll(
      /\bschemaVersion:"2\.0\.0",exporterVersion:([$A-Z_a-z][$\w]*),exportedAt:[$A-Z_a-z][$\w]*\.now\(\)\.toISOString\(\)/gu
    )
  ]
    .map((match) => match[1]);
  const identifiers = new Set(references);
  if (identifiers.size !== 1) {
    throw new Error("Archived Figma runtime bundle has no unambiguous exporterVersion binding");
  }
  const [identifier] = identifiers;
  const escaped = identifier.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
  const assignments = [
    ...bundle.matchAll(new RegExp(`(?:\\bvar\\s+|[,;])${escaped}="([^"]+)"(?=[,;])`, "gu"))
  ].map((match) => match[1]);
  if (assignments.length !== 1) {
    throw new Error("Archived Figma runtime bundle has no unambiguous exporterVersion literal");
  }
  return assignments[0];
}

export async function verifyRelease({
  archivePath = join(rootFromScript, "release", RELEASE_ARCHIVE_NAME),
  checksumPath = join(rootFromScript, "release", RELEASE_CHECKSUM_NAME)
} = {}) {
  if (basename(archivePath) !== RELEASE_ARCHIVE_NAME || basename(checksumPath) !== RELEASE_CHECKSUM_NAME) {
    throw new Error(`Release filenames must be ${RELEASE_ARCHIVE_NAME} and ${RELEASE_CHECKSUM_NAME}`);
  }
  const [archive, checksumLine] = await Promise.all([
    readFile(archivePath),
    readFile(checksumPath, "ascii")
  ]);
  const checksumMatch = /^([0-9a-f]{64})  ([a-z0-9.-]+)\n$/u.exec(checksumLine);
  if (checksumMatch === null || checksumMatch[2] !== RELEASE_ARCHIVE_NAME) {
    throw new Error("Release checksum file is not one lowercase SHA-256 line for the archive");
  }
  const sha256 = createHash("sha256").update(archive).digest("hex");
  if (sha256 !== checksumMatch[1]) throw new Error("Release archive checksum does not match");
  const tar = inflateCanonicalGzip(archive);
  const members = parseUstar(tar);
  const packageValue = JSON.parse(memberText(members, "package.json"));
  const lockValue = JSON.parse(memberText(members, "package-lock.json"));
  const controller = memberText(members, "src/figma/controller.ts");
  const runtimeVersion = runtimeExporterVersion(memberText(members, "dist/figma/code.js"));
  if (
    packageValue.version !== RELEASE_VERSION ||
    lockValue.version !== RELEASE_VERSION ||
    lockValue.packages?.[""]?.version !== RELEASE_VERSION ||
    !controller.includes(`const EXPORTER_VERSION = "${RELEASE_VERSION}";`) ||
    runtimeVersion !== RELEASE_VERSION
  ) {
    throw new Error(
      `Archive package, lockfile, source runtime, and bundled runtime versions must all be ${RELEASE_VERSION}`
    );
  }
  return { sha256, members: members.map(({ name }) => name) };
}

function parseArguments(argv) {
  if (argv.length === 0) return {};
  if (argv.length !== 2) throw new TypeError("Usage: verify-release.mjs [ARCHIVE CHECKSUM]");
  return { archivePath: resolve(argv[0]), checksumPath: resolve(argv[1]) };
}

const isMain = process.argv[1] !== undefined && fileURLToPath(import.meta.url) === resolve(process.argv[1]);
if (isMain) {
  try {
    const result = await verifyRelease(parseArguments(process.argv.slice(2)));
    process.stdout.write(
      `Verified ${RELEASE_ARCHIVE_NAME}\nSHA-256 ${result.sha256}\nMembers ${result.members.length}\n`
    );
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}
