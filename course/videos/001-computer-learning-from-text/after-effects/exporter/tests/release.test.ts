import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import {
  cp,
  mkdtemp,
  readFile,
  readdir,
  rm,
  symlink,
  utimes,
  writeFile
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, posix, relative } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { gzipSync, gunzipSync } from "node:zlib";

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
};
const verifyModule = await import(new URL("../scripts/verify-release.mjs", import.meta.url).href) as unknown as {
  verifyRelease(options: {
    archivePath: string;
    checksumPath: string;
  }): Promise<{ sha256: string; members: string[] }>;
};
const { RELEASE_VERSION, buildRelease } = buildModule;
const { verifyRelease } = verifyModule;
const archiveName = "video001-figma-ae-exporter-0.2.0.tar.gz";
const checksumName = "video001-figma-ae-exporter-0.2.0.sha256";
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

interface AdversarialEntry {
  name: string;
  payload: Buffer;
  mode?: number;
  uid?: number;
  gid?: number;
  mtime?: number;
  type?: string;
  linkName?: string;
  magic?: string;
  version?: string;
  paddingByte?: number;
  checksumStyle?: "canonical" | "space-padded";
  mutateHeader?: (header: Buffer) => void;
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

function writeAdversarialString(
  header: Buffer,
  offset: number,
  length: number,
  value: string
): void {
  const bytes = Buffer.from(value, "utf8");
  assert.ok(bytes.length <= length);
  bytes.copy(header, offset);
}

function writeAdversarialOctal(
  header: Buffer,
  offset: number,
  length: number,
  value: number
): void {
  writeAdversarialString(
    header,
    offset,
    length,
    `${value.toString(8).padStart(length - 1, "0")}\0`
  );
}

function setAdversarialChecksum(
  header: Buffer,
  style: "canonical" | "space-padded" = "canonical"
): void {
  header.fill(0x20, 148, 156);
  const checksum = header.reduce((sum, byte) => sum + byte, 0);
  const encoded = style === "canonical"
    ? `${checksum.toString(8).padStart(6, "0")}\0 `
    : `${checksum.toString(8).padStart(7, " ")}\0`;
  writeAdversarialString(header, 148, 8, encoded);
}

function adversarialHeader(entry: AdversarialEntry): Buffer {
  assert.ok(Buffer.byteLength(entry.name, "utf8") <= 100, "test member name must fit the name field");
  const header = Buffer.alloc(512);
  writeAdversarialString(header, 0, 100, entry.name);
  writeAdversarialOctal(header, 100, 8, entry.mode ?? 0o644);
  writeAdversarialOctal(header, 108, 8, entry.uid ?? 0);
  writeAdversarialOctal(header, 116, 8, entry.gid ?? 0);
  writeAdversarialOctal(header, 124, 12, entry.payload.length);
  writeAdversarialOctal(header, 136, 12, entry.mtime ?? fixedMtime);
  header[156] = (entry.type ?? "0").charCodeAt(0);
  writeAdversarialString(header, 157, 100, entry.linkName ?? "");
  writeAdversarialString(header, 257, 6, entry.magic ?? "ustar\0");
  writeAdversarialString(header, 263, 2, entry.version ?? "00");
  writeAdversarialString(header, 265, 32, "root");
  writeAdversarialString(header, 297, 32, "root");
  entry.mutateHeader?.(header);
  setAdversarialChecksum(header, entry.checksumStyle);
  return header;
}

function adversarialTar(entries: readonly AdversarialEntry[]): Buffer {
  const blocks: Buffer[] = [];
  for (const entry of entries) {
    blocks.push(adversarialHeader(entry), entry.payload);
    const paddingLength = (512 - (entry.payload.length % 512)) % 512;
    if (paddingLength > 0) blocks.push(Buffer.alloc(paddingLength, entry.paddingByte ?? 0));
  }
  blocks.push(Buffer.alloc(1024));
  return Buffer.concat(blocks);
}

function adversarialGzip(tar: Buffer): Buffer {
  const gzip = gzipSync(tar, { level: 9 });
  gzip.writeUInt32LE(0, 4);
  gzip[9] = 255;
  return gzip;
}

function cloneAdversarialEntries(entries: readonly AdversarialEntry[]): AdversarialEntry[] {
  return entries.map((entry) => ({ ...entry, payload: Buffer.from(entry.payload) }));
}

async function writeRecomputedRelease(outputDirectory: string, archive: Buffer): Promise<{
  archivePath: string;
  checksumPath: string;
}> {
  const archivePath = join(outputDirectory, archiveName);
  const checksumPath = join(outputDirectory, checksumName);
  const sha256 = createHash("sha256").update(archive).digest("hex");
  await writeFile(archivePath, archive);
  await writeFile(checksumPath, `${sha256}  ${archiveName}\n`, "ascii");
  return { archivePath, checksumPath };
}

async function expectVerifierRejects(
  outputDirectory: string,
  archive: Buffer,
  pattern: RegExp
): Promise<void> {
  const paths = await writeRecomputedRelease(outputDirectory, archive);
  await assert.rejects(verifyRelease(paths), pattern);
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

test("release builder rejects allowlisted source symlinks", async (t) => {
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

test("release builder rejects a manually modified newer dist artifact", async (t) => {
  const fixtureParent = await mkdtemp(join(tmpdir(), "video001-release-dist-drift-"));
  const fixtureRoot = join(fixtureParent, "exporter");
  const outputDirectory = join(fixtureParent, "out");
  t.after(() => rm(fixtureParent, { recursive: true, force: true }));
  await copyReleaseFixture(fixtureRoot);
  const controllerBundle = join(fixtureRoot, "dist/figma/code.js");
  await writeFile(
    controllerBundle,
    `${await readFile(controllerBundle, "utf8")}\n/* manual newer dist mutation */\n`,
    "utf8"
  );
  const newer = new Date(Date.now() + 60_000);
  await utimes(controllerBundle, newer, newer);

  await assert.rejects(
    buildRelease({ projectRoot: fixtureRoot, outputDirectory }),
    /captured|deterministic|fresh build|does not match/i
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

test("verifier rejects non-canonical gzip framing and trailers with matching checksums", async (t) => {
  const outputDirectory = await mkdtemp(join(tmpdir(), "video001-release-gzip-framing-"));
  t.after(() => rm(outputDirectory, { recursive: true, force: true }));
  const release = await buildRelease({ projectRoot, outputDirectory });
  const validArchive = await readFile(release.archivePath);

  await expectVerifierRejects(
    outputDirectory,
    Buffer.concat([validArchive, Buffer.from([0])]),
    /gzip|single|trailing|member/i
  );
  await expectVerifierRejects(
    outputDirectory,
    Buffer.concat([validArchive, adversarialGzip(Buffer.alloc(0))]),
    /gzip|single|trailing|member/i
  );
  const invalidCrc = Buffer.from(validArchive);
  invalidCrc[invalidCrc.length - 8] = invalidCrc[invalidCrc.length - 8]! ^ 1;
  await expectVerifierRejects(outputDirectory, invalidCrc, /gzip|trailer|crc/i);
  const invalidSize = Buffer.from(validArchive);
  invalidSize[invalidSize.length - 4] = invalidSize[invalidSize.length - 4]! ^ 1;
  await expectVerifierRejects(outputDirectory, invalidSize, /gzip|trailer|size/i);
});

test("verifier requires byte-canonical ustar headers after checksum recomputation", async (t) => {
  const outputDirectory = await mkdtemp(join(tmpdir(), "video001-release-ustar-adversarial-"));
  t.after(() => rm(outputDirectory, { recursive: true, force: true }));
  const release = await buildRelease({ projectRoot, outputDirectory });
  const baseEntries = readTar(await readFile(release.archivePath)).map(({ name, payload }) => ({
    name,
    payload: Buffer.from(payload)
  }));
  const canonicalArchive = adversarialGzip(adversarialTar(baseEntries));
  const canonicalPaths = await writeRecomputedRelease(outputDirectory, canonicalArchive);
  await verifyRelease(canonicalPaths);

  const cases: Array<{
    name: string;
    mutate(entry: AdversarialEntry): void;
  }> = [
    {
      name: "space-padded numeric field",
      mutate(entry) {
        entry.mutateHeader = (header) => {
          Buffer.from("  00644\0", "ascii").copy(header, 100);
        };
      }
    },
    {
      name: "space-padded checksum field",
      mutate(entry) {
        entry.checksumStyle = "space-padded";
      }
    },
    {
      name: "malformed base-256 numeric field",
      mutate(entry) {
        entry.mutateHeader = (header) => {
          header[124] = 0x80;
        };
      }
    },
    {
      name: "non-zero byte after a NUL terminator",
      mutate(entry) {
        entry.mutateHeader = (header) => {
          header[270] = 0x78;
        };
      }
    },
    {
      name: "non-zero device field padding",
      mutate(entry) {
        entry.mutateHeader = (header) => {
          header[329] = 0x31;
        };
      }
    },
    {
      name: "non-zero prefix padding",
      mutate(entry) {
        entry.mutateHeader = (header) => {
          header[346] = 0x78;
        };
      }
    },
    {
      name: "non-zero reserved header byte",
      mutate(entry) {
        entry.mutateHeader = (header) => {
          header[500] = 0x01;
        };
      }
    },
    {
      name: "wrong magic",
      mutate(entry) {
        entry.magic = "xstar\0";
      }
    },
    {
      name: "wrong version",
      mutate(entry) {
        entry.version = "01";
      }
    },
    {
      name: "wrong fixed mode",
      mutate(entry) {
        entry.mode = 0o600;
      }
    },
    {
      name: "wrong fixed uid",
      mutate(entry) {
        entry.uid = 1;
      }
    },
    {
      name: "wrong fixed gid",
      mutate(entry) {
        entry.gid = 1;
      }
    },
    {
      name: "wrong fixed mtime",
      mutate(entry) {
        entry.mtime = fixedMtime + 1;
      }
    },
    {
      name: "link type and link metadata",
      mutate(entry) {
        entry.type = "2";
        entry.linkName = "README.md";
      }
    }
  ];

  for (const scenario of cases) {
    await t.test(scenario.name, async () => {
      const entries = cloneAdversarialEntries(baseEntries);
      scenario.mutate(entries[0]!);
      await expectVerifierRejects(
        outputDirectory,
        adversarialGzip(adversarialTar(entries)),
        /canonical|ustar|header|checksum|metadata|type|link/i
      );
    });
  }
});

test("verifier reaches every adversarial member and payload branch with a matching outer checksum", async (t) => {
  const outputDirectory = await mkdtemp(join(tmpdir(), "video001-release-member-adversarial-"));
  t.after(() => rm(outputDirectory, { recursive: true, force: true }));
  const release = await buildRelease({ projectRoot, outputDirectory });
  const baseEntries = readTar(await readFile(release.archivePath)).map(({ name, payload }) => ({
    name,
    payload: Buffer.from(payload)
  }));

  const memberCases: Array<{
    name: string;
    entries(): AdversarialEntry[];
    pattern: RegExp;
  }> = [
    {
      name: "duplicate member",
      entries: () => [...cloneAdversarialEntries(baseEntries), { ...baseEntries[0]!, payload: Buffer.from(baseEntries[0]!.payload) }],
      pattern: /duplicate/i
    },
    ...["/absolute.txt", "../escape.txt", "back\\slash.txt"].map((unsafeName) => ({
      name: `unsafe path ${unsafeName}`,
      entries: () => {
        const entries = cloneAdversarialEntries(baseEntries);
        entries[0]!.name = unsafeName;
        return entries;
      },
      pattern: /unsafe path/i
    })),
    {
      name: "missing member",
      entries: () => cloneAdversarialEntries(baseEntries).slice(0, -1),
      pattern: /allowlist|missing/i
    },
    {
      name: "extra member",
      entries: () => [
        ...cloneAdversarialEntries(baseEntries),
        { name: "extra.txt", payload: Buffer.from("extra\n") }
      ],
      pattern: /allowlist|extra/i
    },
    {
      name: "prohibited content",
      entries: () => {
        const entries = cloneAdversarialEntries(baseEntries);
        const readme = entries.find((entry) => entry.name === "README.md")!;
        readme.payload = Buffer.from("-----BEGIN PRIVATE KEY-----\n");
        return entries;
      },
      pattern: /private key|credential|prohibited/i
    },
    {
      name: "non-zero payload padding",
      entries: () => {
        const entries = cloneAdversarialEntries(baseEntries);
        const entry = entries.find(({ payload }) => payload.length % 512 !== 0)!;
        entry.paddingByte = 1;
        return entries;
      },
      pattern: /padding/i
    },
    {
      name: "runtime version drift",
      entries: () => {
        const entries = cloneAdversarialEntries(baseEntries);
        const bundle = entries.find((entry) => entry.name === "dist/figma/code.js")!;
        const source = bundle.payload.toString("utf8");
        const drifted = source.replace('"0.2.0"', '"0.2.1"');
        assert.notEqual(drifted, source);
        bundle.payload = Buffer.from(drifted);
        return entries;
      },
      pattern: /runtime|bundle|version|0\.2\.0/i
    }
  ];

  for (const scenario of memberCases) {
    await t.test(scenario.name, async () => {
      await expectVerifierRejects(
        outputDirectory,
        adversarialGzip(adversarialTar(scenario.entries())),
        scenario.pattern
      );
    });
  }

  const validTar = adversarialTar(baseEntries);
  const nonZeroEndBlock = Buffer.from(validTar);
  nonZeroEndBlock[nonZeroEndBlock.length - 1] = 1;
  await expectVerifierRejects(
    outputDirectory,
    adversarialGzip(nonZeroEndBlock),
    /zero|end|ustar|header/i
  );
  await expectVerifierRejects(
    outputDirectory,
    adversarialGzip(Buffer.concat([validTar, Buffer.alloc(512)])),
    /zero|end|trailing|ustar/i
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
