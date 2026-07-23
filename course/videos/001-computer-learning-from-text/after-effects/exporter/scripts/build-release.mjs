import { createHash, randomBytes } from "node:crypto";
import {
  constants,
  lstat,
  mkdir,
  mkdtemp,
  open,
  rename,
  rm,
  writeFile
} from "node:fs/promises";
import { dirname, isAbsolute, join, posix, relative, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { gzipSync } from "node:zlib";

export const RELEASE_VERSION = "0.2.0";
export const RELEASE_BASENAME = `video001-figma-ae-exporter-${RELEASE_VERSION}`;
export const RELEASE_ARCHIVE_NAME = `${RELEASE_BASENAME}.tar.gz`;
export const RELEASE_CHECKSUM_NAME = `${RELEASE_BASENAME}.sha256`;
export const RELEASE_MTIME = Math.floor(Date.parse("2026-07-23T00:00:00Z") / 1000);

const rootFromScript = dirname(dirname(fileURLToPath(import.meta.url)));
const TAR_BLOCK_SIZE = 512;
const BUILD_OWNERSHIP_MARKER = "dist/figma/.video001-figma-build-owned";
const BUILD_OWNERSHIP_VALUE = "video001-figma-exporter-build-v1\n";

export const RELEASE_SOURCE_FILES = Object.freeze([
  "LICENSE",
  "NOTICE",
  "PROVENANCE.md",
  "README.md",
  "config/video001-figma-scenes.json",
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

export const RELEASE_DIST_FILES = Object.freeze([
  "dist/ae/Video001-Figma-AE-Exporter.jsx",
  "dist/ae/audit-export.jsx",
  "dist/ae/audit-full-lesson.jsx",
  "dist/ae/figma-scenes.json",
  "dist/bridge/video001-bridge.mjs",
  "dist/figma/code.js",
  "dist/figma/manifest.json",
  "dist/figma/ui.html"
]);

const RELEASE_FILES = Object.freeze([...RELEASE_SOURCE_FILES, ...RELEASE_DIST_FILES].sort());
const BUILD_INPUTS = Object.freeze([
  "config/video001-figma-scenes.json",
  "package-lock.json",
  "package.json",
  "scripts/build.mjs",
  "scripts/generate-figma-manifest.mjs",
  ...RELEASE_SOURCE_FILES.filter((path) => path.startsWith("src/"))
]);

function safeRelativePosixPath(value) {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.includes("\\") ||
    value.includes("\0") ||
    isAbsolute(value) ||
    posix.isAbsolute(value) ||
    posix.normalize(value) !== value ||
    value.split("/").some((part) => part === "" || part === "." || part === "..") ||
    /[\u0000-\u001f\u007f]/u.test(value)
  ) {
    throw new TypeError(`${JSON.stringify(value)} is not a safe relative POSIX path`);
  }
  return value;
}

function sourcePath(projectRoot, relativePath) {
  const safePath = safeRelativePosixPath(relativePath);
  const nativePath = join(projectRoot, ...safePath.split("/"));
  const fromRoot = relative(projectRoot, nativePath);
  if (fromRoot === "" || isAbsolute(fromRoot) || fromRoot === ".." || fromRoot.startsWith(`..${sep}`)) {
    throw new TypeError(`${JSON.stringify(relativePath)} escapes the project root`);
  }
  return nativePath;
}

async function assertDirectoryComponents(projectRoot, relativePath) {
  const parts = safeRelativePosixPath(relativePath).split("/");
  let current = projectRoot;
  const rootStat = await lstat(current);
  if (!rootStat.isDirectory() || rootStat.isSymbolicLink()) {
    throw new Error(`Project root ${current} must be a regular directory, not a symlink`);
  }
  for (const part of parts.slice(0, -1)) {
    current = join(current, part);
    const value = await lstat(current);
    if (!value.isDirectory() || value.isSymbolicLink()) {
      throw new Error(`${relativePath} has a symlink or non-directory path component`);
    }
  }
}

async function readRegularFile(projectRoot, relativePath) {
  await assertDirectoryComponents(projectRoot, relativePath);
  const path = sourcePath(projectRoot, relativePath);
  const before = await lstat(path, { bigint: true });
  if (!before.isFile() || before.isSymbolicLink()) {
    throw new Error(`${relativePath} must be a regular file, not a symlink`);
  }
  const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const opened = await handle.stat({ bigint: true });
    if (!opened.isFile() || opened.dev !== before.dev || opened.ino !== before.ino) {
      throw new Error(`${relativePath} changed identity while it was opened`);
    }
    const bytes = await handle.readFile();
    const after = await handle.stat({ bigint: true });
    if (
      after.dev !== opened.dev ||
      after.ino !== opened.ino ||
      after.size !== opened.size ||
      after.mtimeNs !== opened.mtimeNs ||
      BigInt(bytes.byteLength) !== after.size
    ) {
      throw new Error(`${relativePath} changed while it was read`);
    }
    return { bytes };
  } finally {
    await handle.close();
  }
}

function assertSafeReleaseContent(path, bytes) {
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
    if (pattern.test(text)) throw new Error(`${path} contains a prohibited ${description}`);
  }
}

function snapshotBytes(snapshot, path) {
  const bytes = snapshot.get(path);
  if (bytes === undefined) throw new Error(`Captured release snapshot is missing ${path}`);
  return bytes;
}

async function captureReleaseSnapshot(projectRoot) {
  const snapshot = new Map();
  for (const path of [...RELEASE_FILES, BUILD_OWNERSHIP_MARKER]) {
    const bytes = (await readRegularFile(projectRoot, path)).bytes;
    if (path !== BUILD_OWNERSHIP_MARKER) assertSafeReleaseContent(path, bytes);
    snapshot.set(path, bytes);
  }
  return snapshot;
}

function validateProjectVersion(snapshot) {
  const packageBytes = snapshotBytes(snapshot, "package.json");
  const lockBytes = snapshotBytes(snapshot, "package-lock.json");
  const controllerBytes = snapshotBytes(snapshot, "src/figma/controller.ts");
  const packageValue = JSON.parse(packageBytes.toString("utf8"));
  const lockValue = JSON.parse(lockBytes.toString("utf8"));
  if (
    packageValue.version !== RELEASE_VERSION ||
    lockValue.version !== RELEASE_VERSION ||
    lockValue.packages?.[""]?.version !== RELEASE_VERSION ||
    !controllerBytes.toString("utf8").includes(`const EXPORTER_VERSION = "${RELEASE_VERSION}";`)
  ) {
    throw new Error(`Package, lockfile, runtime, and release version must all be ${RELEASE_VERSION}`);
  }
}

async function validateCleanBuild(snapshot) {
  const marker = snapshotBytes(snapshot, BUILD_OWNERSHIP_MARKER).toString("utf8");
  if (marker !== BUILD_OWNERSHIP_VALUE) {
    throw new Error("dist/figma has an invalid build ownership marker");
  }
  const sourceTiming = snapshotBytes(snapshot, "config/video001-figma-scenes.json");
  const builtTiming = snapshotBytes(snapshot, "dist/ae/figma-scenes.json");
  if (!sourceTiming.equals(builtTiming)) {
    throw new Error("dist/ae/figma-scenes.json is stale; run npm run build");
  }
  const manifestBytes = snapshotBytes(snapshot, "dist/figma/manifest.json");
  const manifest = JSON.parse(manifestBytes.toString("utf8"));
  if (
    !/^[0-9]{10,30}$/u.test(manifest.id) ||
    manifest.main !== "code.js" ||
    manifest.ui !== "ui.html"
  ) {
    throw new Error("dist/figma/manifest.json is not a valid fresh development-plugin manifest");
  }

  const temporaryRoot = await mkdtemp(join(rootFromScript, ".release-rebuild-"));
  try {
    for (const path of BUILD_INPUTS) {
      const destination = sourcePath(temporaryRoot, path);
      await mkdir(dirname(destination), { recursive: true, mode: 0o700 });
      await writeFile(destination, snapshotBytes(snapshot, path), { mode: 0o600 });
    }
    const pluginIdFile = join(temporaryRoot, ".figma-plugin-id");
    await writeFile(pluginIdFile, `${manifest.id}\n`, { encoding: "ascii", mode: 0o600 });
    const buildModule = await import(
      `${pathToFileURL(join(temporaryRoot, "scripts", "build.mjs")).href}?snapshot=1`
    );
    await buildModule.buildExporter({
      projectRoot: temporaryRoot,
      pluginIdFile,
      environment: {}
    });
    for (const path of [...RELEASE_DIST_FILES, BUILD_OWNERSHIP_MARKER]) {
      const rebuilt = (await readRegularFile(temporaryRoot, path)).bytes;
      if (!rebuilt.equals(snapshotBytes(snapshot, path))) {
        throw new Error(
          `${path} does not match a fresh deterministic build from the captured release sources`
        );
      }
    }
  } finally {
    await rm(temporaryRoot, { recursive: true, force: true });
  }
}

function writeString(block, offset, length, value, label) {
  const bytes = Buffer.from(value, "utf8");
  if (bytes.length > length) throw new RangeError(`${label} does not fit in its ustar field`);
  bytes.copy(block, offset);
}

function writeOctal(block, offset, length, value, label) {
  if (!Number.isSafeInteger(value) || value < 0) throw new TypeError(`${label} must be a non-negative integer`);
  const octal = value.toString(8);
  if (octal.length > length - 1) throw new RangeError(`${label} does not fit in its ustar field`);
  writeString(block, offset, length, `${octal.padStart(length - 1, "0")}\0`, label);
}

function splitUstarPath(path) {
  const bytes = Buffer.byteLength(path, "utf8");
  if (bytes <= 100) return { name: path, prefix: "" };
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

function ustarHeader(path, size) {
  const { name, prefix } = splitUstarPath(safeRelativePosixPath(path));
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

export function createUstar(entries) {
  if (!Array.isArray(entries) || entries.length === 0) {
    throw new TypeError("ustar entries must be a non-empty array");
  }
  const seen = new Set();
  const blocks = [];
  for (const entry of entries) {
    const path = safeRelativePosixPath(entry?.path);
    if (seen.has(path)) throw new Error(`Duplicate archive member ${path}`);
    seen.add(path);
    const bytes = Buffer.isBuffer(entry.bytes) ? entry.bytes : Buffer.from(entry.bytes);
    blocks.push(ustarHeader(path, bytes.length), bytes);
    const padding = (TAR_BLOCK_SIZE - (bytes.length % TAR_BLOCK_SIZE)) % TAR_BLOCK_SIZE;
    if (padding > 0) blocks.push(Buffer.alloc(padding));
  }
  blocks.push(Buffer.alloc(TAR_BLOCK_SIZE * 2));
  return Buffer.concat(blocks);
}

function deterministicGzip(tarBytes) {
  const gzip = gzipSync(tarBytes, { level: 9 });
  gzip.writeUInt32LE(0, 4);
  gzip[9] = 255;
  return gzip;
}

async function ensureOutputDirectory(path) {
  await mkdir(path, { recursive: true, mode: 0o700 });
  const value = await lstat(path);
  if (!value.isDirectory() || value.isSymbolicLink()) {
    throw new Error(`Release output ${path} must be a regular directory, not a symlink`);
  }
}

async function atomicWrite(path, bytes) {
  const temporary = join(
    dirname(path),
    `.${posix.basename(path)}.${process.pid}.${randomBytes(8).toString("hex")}.tmp`
  );
  let handle;
  try {
    handle = await open(temporary, "wx", 0o600);
    await handle.writeFile(bytes);
    await handle.sync();
    await handle.close();
    handle = undefined;
    await rename(temporary, path);
  } catch (error) {
    if (handle !== undefined) await handle.close().catch(() => {});
    await rm(temporary, { force: true }).catch(() => {});
    throw error;
  }
}

export async function buildRelease({
  projectRoot = rootFromScript,
  outputDirectory = join(projectRoot, "release")
} = {}) {
  const root = resolve(projectRoot);
  const output = resolve(outputDirectory);
  const snapshot = await captureReleaseSnapshot(root);
  validateProjectVersion(snapshot);
  await validateCleanBuild(snapshot);
  const entries = RELEASE_FILES.map((path) => ({ path, bytes: snapshotBytes(snapshot, path) }));
  const archiveBytes = deterministicGzip(createUstar(entries));
  const sha256 = createHash("sha256").update(archiveBytes).digest("hex");
  const archivePath = join(output, RELEASE_ARCHIVE_NAME);
  const checksumPath = join(output, RELEASE_CHECKSUM_NAME);
  await ensureOutputDirectory(output);
  await atomicWrite(archivePath, archiveBytes);
  await atomicWrite(checksumPath, Buffer.from(`${sha256}  ${RELEASE_ARCHIVE_NAME}\n`, "ascii"));
  return {
    archivePath,
    checksumPath,
    sha256,
    members: entries.map(({ path }) => path)
  };
}

function parseArguments(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    const value = argv[index + 1];
    if (value === undefined || value.startsWith("--")) throw new TypeError(`Missing value for ${argument}`);
    if (argument === "--project-root") options.projectRoot = value;
    else if (argument === "--output-directory") options.outputDirectory = value;
    else throw new TypeError(`Unknown argument ${argument}`);
    index += 1;
  }
  return options;
}

const isMain = process.argv[1] !== undefined && fileURLToPath(import.meta.url) === resolve(process.argv[1]);
if (isMain) {
  try {
    const result = await buildRelease(parseArguments(process.argv.slice(2)));
    process.stdout.write(`${result.sha256}  ${RELEASE_ARCHIVE_NAME}\n`);
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}
