import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import {
  cp,
  mkdtemp,
  readFile,
  readdir,
  rm,
  symlink,
  writeFile
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, posix, relative } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { gunzipSync } from "node:zlib";

const projectRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const fixedMtime = Math.floor(Date.parse("2026-07-23T00:00:00Z") / 1000);
const buildModule = await import(new URL("../scripts/build-release.mjs", import.meta.url).href) as unknown as {
  RELEASE_VERSION: string;
  buildRelease(options: {
    projectRoot: string;
    outputDirectory: string;
  }): Promise<{
    archivePath: string;
    checksumPath: string;
    sha256: string;
    members: string[];
  }>;
  createUstar(entries: Array<{ path: string; bytes: Buffer }>): Buffer;
};
const verifyModule = await import(new URL("../scripts/verify-release.mjs", import.meta.url).href) as unknown as {
  verifyRelease(options: {
    archivePath: string;
    checksumPath: string;
  }): Promise<{ sha256: string; members: string[] }>;
};
const { RELEASE_VERSION, buildRelease, createUstar } = buildModule;
const { verifyRelease } = verifyModule;
const required = [
  "README.md",
  "LICENSE",
  "PROVENANCE.md",
  "package.json",
  "package-lock.json",
  "config/video001-figma-scenes.json",
  "dist/figma/manifest.json",
  "dist/figma/code.js",
  "dist/figma/ui.html",
  "dist/bridge/video001-bridge.mjs",
  "dist/ae/Video001-Figma-AE-Exporter.jsx",
  "dist/ae/audit-export.jsx",
  "dist/ae/audit-full-lesson.jsx",
  "dist/ae/figma-scenes.json"
] as const;

interface TarMember {
  name: string;
  mode: number;
  uid: number;
  gid: number;
  size: number;
  mtime: number;
  checksum: number;
  calculatedChecksum: number;
  type: number;
  linkName: string;
  userName: string;
  groupName: string;
  payload: Buffer;
  padding: Buffer;
}

function stringField(block: Buffer, offset: number, length: number): string {
  const field = block.subarray(offset, offset + length);
  const end = field.indexOf(0);
  return field.subarray(0, end === -1 ? field.length : end).toString("utf8");
}

function octalField(block: Buffer, offset: number, length: number): number {
  const value = stringField(block, offset, length).trim();
  assert.match(value, /^[0-7]+$/);
  return Number.parseInt(value, 8);
}

function readTar(archive: Buffer): TarMember[] {
  const tar = gunzipSync(archive);
  assert.equal(tar.length % 512, 0);
  const members: TarMember[] = [];
  let offset = 0;
  while (offset < tar.length) {
    const block = tar.subarray(offset, offset + 512);
    if (block.every((byte) => byte === 0)) break;
    const prefix = stringField(block, 345, 155);
    const name = [prefix, stringField(block, 0, 100)].filter(Boolean).join("/");
    const size = octalField(block, 124, 12);
    const checksum = octalField(block, 148, 8);
    const checksumBlock = Buffer.from(block);
    checksumBlock.fill(0x20, 148, 156);
    const calculatedChecksum = checksumBlock.reduce((sum, byte) => sum + byte, 0);
    const payloadStart = offset + 512;
    const paddedSize = Math.ceil(size / 512) * 512;
    members.push({
      name,
      mode: octalField(block, 100, 8),
      uid: octalField(block, 108, 8),
      gid: octalField(block, 116, 8),
      size,
      mtime: octalField(block, 136, 12),
      checksum,
      calculatedChecksum,
      type: block[156]!,
      linkName: stringField(block, 157, 100),
      userName: stringField(block, 265, 32),
      groupName: stringField(block, 297, 32),
      payload: tar.subarray(payloadStart, payloadStart + size),
      padding: tar.subarray(payloadStart + size, payloadStart + paddedSize)
    });
    offset = payloadStart + paddedSize;
  }
  assert.equal(tar.subarray(offset).length, 1024);
  assert.ok(tar.subarray(offset).every((byte) => byte === 0));
  return members;
}

async function copyReleaseFixture(destination: string): Promise<void> {
  await cp(projectRoot, destination, {
    recursive: true,
    preserveTimestamps: true,
    filter(source) {
      const path = relative(projectRoot, source);
      if (path === "") return true;
      const first = path.split(/[\\/]/u)[0];
      return !new Set([".figma-plugin-id", ".git", "node_modules", "release", "evidence", "docs"]).has(first!);
    }
  });
}

test("builds byte-identical deterministic releases in separate temporary directories", async (t) => {
  const firstRoot = await mkdtemp(join(tmpdir(), "video001-release-first-"));
  const secondRoot = await mkdtemp(join(tmpdir(), "video001-release-second-"));
  t.after(async () => {
    await Promise.all([
      rm(firstRoot, { recursive: true, force: true }),
      rm(secondRoot, { recursive: true, force: true })
    ]);
  });
  const firstProject = join(firstRoot, "exporter");
  const secondProject = join(secondRoot, "exporter");
  await Promise.all([
    copyReleaseFixture(firstProject),
    copyReleaseFixture(secondProject)
  ]);
  const firstOutput = join(firstRoot, "release");
  const secondOutput = join(secondRoot, "release");

  const first = await buildRelease({ projectRoot: firstProject, outputDirectory: firstOutput });
  const second = await buildRelease({ projectRoot: secondProject, outputDirectory: secondOutput });
  const firstBytes = await readFile(first.archivePath);
  const secondBytes = await readFile(second.archivePath);
  const calculated = createHash("sha256").update(firstBytes).digest("hex");

  assert.deepEqual(firstBytes, secondBytes);
  assert.equal(first.sha256, second.sha256);
  assert.equal(first.sha256, calculated);
  assert.match(first.sha256, /^[0-9a-f]{64}$/);
  assert.equal(
    await readFile(first.checksumPath, "utf8"),
    `${first.sha256}  video001-figma-ae-exporter-0.2.0.tar.gz\n`
  );
  assert.deepEqual(
    (await readdir(firstOutput)).sort(),
    [
      "video001-figma-ae-exporter-0.2.0.sha256",
      "video001-figma-ae-exporter-0.2.0.tar.gz"
    ]
  );
});

test("archive contains the approved source and dist files with fixed safe ustar metadata", async (t) => {
  const outputDirectory = await mkdtemp(join(tmpdir(), "video001-release-members-"));
  t.after(() => rm(outputDirectory, { recursive: true, force: true }));
  const release = await buildRelease({ projectRoot, outputDirectory });
  const archive = await readFile(release.archivePath);
  const members = readTar(archive);
  const names = members.map(({ name }) => name);

  for (const path of required) assert.ok(names.includes(path), `missing ${path}`);
  assert.equal(names.includes("dist/ae/audit-report.json"), false);
  assert.equal(new Set(names).size, names.length);
  for (const member of members) {
    assert.equal(posix.isAbsolute(member.name), false);
    assert.equal(member.name.includes("\\"), false);
    assert.equal(member.name.split("/").some((part) => part === "" || part === "." || part === ".."), false);
    assert.equal(member.type, "0".charCodeAt(0));
    assert.equal(member.linkName, "");
    assert.equal(member.mode, 0o644);
    assert.equal(member.uid, 0);
    assert.equal(member.gid, 0);
    assert.equal(member.userName, "root");
    assert.equal(member.groupName, "root");
    assert.equal(member.mtime, fixedMtime);
    assert.equal(member.checksum, member.calculatedChecksum);
    assert.ok(member.padding.every((byte) => byte === 0));
  }
  assert.equal(archive[0], 0x1f);
  assert.equal(archive[1], 0x8b);
  assert.equal(archive[3], 0);
  assert.deepEqual([...archive.subarray(4, 8)], [0, 0, 0, 0]);
  assert.equal(archive[8], 2);
  assert.equal(archive[9], 255);
});

test("release excludes mutable state, evidence, AEPs, credentials, and user paths", async (t) => {
  const outputDirectory = await mkdtemp(join(tmpdir(), "video001-release-security-"));
  t.after(() => rm(outputDirectory, { recursive: true, force: true }));
  const release = await buildRelease({ projectRoot, outputDirectory });
  const members = readTar(await readFile(release.archivePath));

  for (const member of members) {
    const lowerName = member.name.toLowerCase();
    const baseName = posix.basename(lowerName);
    assert.equal(lowerName.includes(".figma-plugin-id"), false);
    assert.equal(lowerName.split("/").includes("evidence"), false);
    assert.equal(lowerName.endsWith(".aep"), false);
    assert.equal(
      [".env", ".npmrc", "auth.json", "credentials.json", "secrets.json", "state.json"].includes(baseName),
      false
    );
    const text = member.payload.toString("utf8");
    assert.doesNotMatch(
      text,
      /\/Users\/[^/\s]+|\/home\/[^/\s]+|\/private\/(?:tmp|var\/folders)\/[^/\s]+|[A-Za-z]:\\Users\\[^\\\s]+/u
    );
    assert.doesNotMatch(text, /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/u);
    assert.doesNotMatch(text, /\bBearer [A-Za-z0-9._~-]{12,}\b/u);
  }
});

test("release builder rejects traversal names and allowlisted source symlinks", async (t) => {
  assert.throws(
    () => createUstar([{ path: "../secret.txt", bytes: Buffer.from("secret") }]),
    /safe relative POSIX path/i
  );
  assert.throws(
    () => createUstar([{ path: "/absolute.txt", bytes: Buffer.from("secret") }]),
    /safe relative POSIX path/i
  );

  const fixtureParent = await mkdtemp(join(tmpdir(), "video001-release-symlink-"));
  const fixtureRoot = join(fixtureParent, "exporter");
  const outputDirectory = join(fixtureParent, "out");
  t.after(() => rm(fixtureParent, { recursive: true, force: true }));
  await copyReleaseFixture(fixtureRoot);
  const external = join(fixtureParent, "external-secret.txt");
  await writeFile(external, "do not archive\n", "utf8");
  await rm(join(fixtureRoot, "README.md"));
  await symlink(external, join(fixtureRoot, "README.md"));

  await assert.rejects(
    buildRelease({ projectRoot: fixtureRoot, outputDirectory }),
    /symlink|regular file/i
  );
});

test("release builder rejects credentials and mutable user paths in allowlisted files", async (t) => {
  const fixtureParent = await mkdtemp(join(tmpdir(), "video001-release-secret-"));
  const fixtureRoot = join(fixtureParent, "exporter");
  const outputDirectory = join(fixtureParent, "out");
  t.after(() => rm(fixtureParent, { recursive: true, force: true }));
  await copyReleaseFixture(fixtureRoot);
  await writeFile(
    join(fixtureRoot, "README.md"),
    "-----BEGIN PRIVATE KEY-----\nBearer leaked-release-token-123456\n/Users/example/exporter\n",
    "utf8"
  );

  await assert.rejects(
    buildRelease({ projectRoot: fixtureRoot, outputDirectory }),
    /credential|private key|mutable user path/i
  );
});

test("independent verifier validates the release and rejects tampering", async (t) => {
  const outputDirectory = await mkdtemp(join(tmpdir(), "video001-release-verify-"));
  t.after(() => rm(outputDirectory, { recursive: true, force: true }));
  const release = await buildRelease({ projectRoot, outputDirectory });

  const verified = await verifyRelease({
    archivePath: release.archivePath,
    checksumPath: release.checksumPath
  });
  assert.equal(verified.sha256, release.sha256);
  assert.ok(verified.members.includes("README.md"));

  const archive = await readFile(release.archivePath);
  archive[archive.length - 1] = archive[archive.length - 1]! ^ 0xff;
  await writeFile(release.archivePath, archive);
  await assert.rejects(
    verifyRelease({ archivePath: release.archivePath, checksumPath: release.checksumPath }),
    /checksum|gzip|archive/i
  );
});

test("release and runtime versions cannot drift", async () => {
  const packageValue = JSON.parse(await readFile(join(projectRoot, "package.json"), "utf8")) as {
    version: string;
  };
  const lockValue = JSON.parse(await readFile(join(projectRoot, "package-lock.json"), "utf8")) as {
    version: string;
    packages: { "": { version: string } };
  };
  const controller = await readFile(join(projectRoot, "src/figma/controller.ts"), "utf8");

  assert.equal(RELEASE_VERSION, "0.2.0");
  assert.equal(packageValue.version, RELEASE_VERSION);
  assert.equal(lockValue.version, RELEASE_VERSION);
  assert.equal(lockValue.packages[""].version, RELEASE_VERSION);
  assert.match(controller, /const EXPORTER_VERSION = "0\.2\.0";/u);
});

test("historical Shot 32 evidence keeps its captured 0.1.0 exporter identity", async () => {
  const reference = JSON.parse(
    await readFile(join(projectRoot, "tests/fixtures/shot-32-reference.json"), "utf8")
  ) as { exporterVersion: string };

  assert.equal(reference.exporterVersion, "0.1.0");
  assert.notEqual(reference.exporterVersion, RELEASE_VERSION);
});
