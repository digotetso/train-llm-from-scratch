import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import test from "node:test";
import { join } from "node:path";
import { spawn } from "node:child_process";
import type { PathLike } from "node:fs";
import { ProfileRegistry } from "../src/bridge/profile-registry.ts";
import { exporterPaths } from "../src/bridge/paths.ts";
import { parseProfileCli, runProfileCli, type ProfileCliIo } from "../src/cli/profile-cli.ts";
import { realProfileCliRuntimeFilesystem, writeNewProfileJson } from "../src/cli/profile-cli-runtime-internal.ts";
import { PROFILE_LIMITS } from "../src/shared/limits.ts";
import { validateProjectProfile } from "../src/shared/project-profile.ts";
import { makeFixtureProfile } from "./helpers/profile.ts";

interface ScriptedIo extends ProfileCliIo {
  readonly stdoutLines: string[];
  readonly stderrLines: string[];
  readonly prompts: string[];
  readonly files: Map<string, unknown>;
}

function scriptedIo(answers: readonly string[], files = new Map<string, unknown>()): ScriptedIo {
  const remaining = [...answers];
  const stdoutLines: string[] = [];
  const stderrLines: string[] = [];
  const prompts: string[] = [];
  return {
    stdoutLines,
    stderrLines,
    prompts,
    files,
    async readLine(prompt: string): Promise<string> {
      prompts.push(prompt);
      const answer = remaining.shift();
      if (answer === undefined) throw Object.assign(new Error("stdin closed"), { code: "EOF" });
      return answer;
    },
    stdout(value: string): void { stdoutLines.push(value); },
    stderr(value: string): void { stderrLines.push(value); },
    async readJson(path: string): Promise<unknown> {
      if (!files.has(path)) throw Object.assign(new Error("missing file"), { code: "ENOENT" });
      return structuredClone(files.get(path));
    },
    async writeNewJson(path: string, value: unknown): Promise<void> {
      if (files.has(path)) throw Object.assign(new Error("already exists"), { code: "EEXIST" });
      files.set(path, structuredClone(value));
    }
  };
}

async function registryFixture(): Promise<ProfileRegistry> {
  return new ProfileRegistry(exporterPaths(await mkdtemp("/private/tmp/video001-profile-cli-")));
}

async function childExit(command: string, args: readonly string[]): Promise<{ code: number | null; stdout: string; stderr: string }> {
  const child = spawn(command, args, { stdio: ["ignore", "pipe", "pipe"] });
  let stdout = "";
  let stderr = "";
  child.stdout.setEncoding("utf8").on("data", (value: string) => { stdout += value; });
  child.stderr.setEncoding("utf8").on("data", (value: string) => { stderr += value; });
  const code = await new Promise<number | null>((resolve, reject) => {
    child.once("error", reject);
    child.once("exit", resolve);
  });
  return { code, stdout, stderr };
}

test("parses the exact profile command grammar", () => {
  assert.deepEqual(parseProfileCli(["init", "--output", "new.json"]), { kind: "init", output: "new.json" });
  assert.deepEqual(parseProfileCli(["validate", "input.json", "--json"]), { kind: "validate", file: "input.json", json: true });
  assert.deepEqual(parseProfileCli(["inspect", "input.json"]), { kind: "inspect", file: "input.json", json: false });
  assert.deepEqual(parseProfileCli(["install", "input.json", "--json"]), { kind: "install", file: "input.json", json: true });
  assert.deepEqual(parseProfileCli(["list", "--json"]), { kind: "list", json: true });
});

test("rejects unknown and incomplete profile command arguments", () => {
  for (const argv of [
    [], ["init"], ["init", "--output"], ["init", "--output", "--json"], ["init", "--output", "--output"],
    ["init", "--output", "profile.json", "--output", "other.json"], ["validate"], ["validate", "--json"],
    ["validate", "--output"], ["validate", "profile.json", "--json", "--json"], ["list", "unexpected"], ["unknown"]
  ]) {
    assert.throws(() => parseProfileCli(argv), /profile command/i);
  }
});

test("keeps profile command operands from being interpreted as flags", async () => {
  const executable = join(process.cwd(), "dist", "cli", "figma-ae.mjs");
  const build = await childExit(process.execPath, [join(process.cwd(), "scripts", "build.mjs")]);
  assert.deepEqual(build, { code: 0, stdout: "", stderr: "" });
  try {
    const valid = await childExit(process.execPath, [executable, "profile", "validate", "config/profiles/video-001.figma-ae-project.json"]);
    assert.equal(valid.code, 0);
    assert.match(valid.stdout, /^status=ok code=PROFILE_VALID project=video-001 revision=1 sha256=[0-9a-f]{64} message=Profile is valid\n$/);
    assert.equal(valid.stderr, "");

    const result = await childExit(process.execPath, [executable, "profile", "init", "--output", "--json"]);
    assert.deepEqual(result, {
      code: 2,
      stdout: "",
      stderr: "status=error code=PROFILE_COMMAND_INVALID message=Invalid profile command\n"
    });
  } finally {
    await rm(join(process.cwd(), "dist", "cli"), { recursive: true, force: true });
  }
});

test("validates a profile without changing its source and emits a machine-readable result", async () => {
  const registry = await registryFixture();
  const source = makeFixtureProfile();
  const io = scriptedIo([], new Map([["fixture.json", source]]));

  assert.equal(await runProfileCli({ kind: "validate", file: "fixture.json", json: true }, { io, registry }), 0);
  assert.deepEqual(io.files.get("fixture.json"), source);
  assert.deepEqual(JSON.parse(io.stdoutLines.join("")), {
    status: "ok",
    code: "PROFILE_VALID",
    project: {
      id: "fixture-two",
      displayName: "Fixture Two",
      revision: 2,
      profileSha256: "508d602330f01141e2f9f012267b9d1b555cffda9129b51a63cf0f3ea0e8c4eb"
    },
    message: "Profile is valid"
  });
  assert.deepEqual(io.stderrLines, []);
});

test("inspects a profile without installing it and redacts source details", async () => {
  const registry = await registryFixture();
  const io = scriptedIo([], new Map([["fixture.json", makeFixtureProfile()]]));

  assert.equal(await runProfileCli({ kind: "inspect", file: "fixture.json", json: false }, { io, registry }), 0);
  assert.equal((await registry.list()).length, 0);
  const output = io.stdoutLines.join("");
  assert.match(output, /fixture-two/);
  assert.doesNotMatch(output, /fixture-file-key|12:34|Fixture Source Page/);
  assert.doesNotMatch(output, /profiles\//);
});

test("installs and lists exact registry summaries in deterministic redacted order", async () => {
  const registry = await registryFixture();
  const first = makeFixtureProfile();
  const second = structuredClone(first);
  (second.project as Record<string, unknown>).id = "alpha-one";
  (second.project as Record<string, unknown>).displayName = "Alpha One";
  (second.project as Record<string, unknown>).revision = 1;
  const io = scriptedIo([], new Map([["fixture.json", first], ["alpha.json", second]]));

  assert.equal(await runProfileCli({ kind: "install", file: "fixture.json", json: true }, { io, registry }), 0);
  assert.equal(await runProfileCli({ kind: "install", file: "alpha.json", json: true }, { io, registry }), 0);
  io.stdoutLines.length = 0;
  assert.equal(await runProfileCli({ kind: "list", json: true }, { io, registry }), 0);

  const results = io.stdoutLines.map((line) => JSON.parse(line) as { project?: { id: string } });
  assert.deepEqual(results.map((result) => result.project?.id), ["alpha-one", "fixture-two"]);
  assert.doesNotMatch(io.stdoutLines.join(""), /profiles\//);
});

test("preserves known registry conflict codes without leaking source details", async () => {
  const registry = await registryFixture();
  const installed = makeFixtureProfile();
  await registry.installValue(installed);
  const conflicting = structuredClone(installed);
  (conflicting.project as Record<string, unknown>).displayName = "Changed Fixture";
  const io = scriptedIo([], new Map([["conflict.json", conflicting]]));

  assert.equal(await runProfileCli({ kind: "install", file: "conflict.json", json: true }, { io, registry }), 1);
  assert.deepEqual(JSON.parse(io.stderrLines.join("")), {
    status: "error",
    code: "PROFILE_REVISION_CONFLICT",
    message: "Profile registry operation failed"
  });
  assert.doesNotMatch(io.stderrLines.join(""), /conflict\.json|profiles\//);
});

test("preserves known registry list errors and redacts unknown failures", async () => {
  const corruptRegistry = { list: async () => { throw new Error("PROFILE_REGISTRY_CORRUPT"); } } as unknown as ProfileRegistry;
  const corruptIo = scriptedIo([]);
  assert.equal(await runProfileCli({ kind: "list", json: false }, { io: corruptIo, registry: corruptRegistry }), 1);
  assert.equal(
    corruptIo.stderrLines.join(""),
    "status=error code=PROFILE_REGISTRY_CORRUPT message=Profile registry operation failed\n"
  );

  const unknownRegistry = { list: async () => { throw new Error("/private/secret profile body"); } } as unknown as ProfileRegistry;
  const unknownIo = scriptedIo([]);
  assert.equal(await runProfileCli({ kind: "list", json: true }, { io: unknownIo, registry: unknownRegistry }), 1);
  assert.deepEqual(JSON.parse(unknownIo.stderrLines.join("")), {
    status: "error",
    code: "PROFILE_COMMAND_FAILED",
    message: "Profile command failed"
  });
  assert.doesNotMatch(unknownIo.stderrLines.join(""), /secret|private/);
});

test("refuses to overwrite an existing init output", async () => {
  const registry = await registryFixture();
  const io = scriptedIo([
    "fixture-project", "Fixture Project", "1", "fixture-file-key", "12:34",
    "AE Assets", "1280", "720", "24", "FX", "FIXTURE_MASTER",
    "Fixture Imports", "0", "1", "12:35", "FX_SH01_Intro", "0", "6", "", ""
  ], new Map([["profile.json", { preserved: true }]]));

  assert.equal(await runProfileCli({ kind: "init", output: "profile.json" }, { io, registry }), 1);
  assert.deepEqual(io.files.get("profile.json"), { preserved: true });
  assert.match(io.stderrLines.join(""), /PROFILE_OUTPUT_EXISTS/);
});

test("creates a validated starter profile from explicit wizard answers", async () => {
  const registry = await registryFixture();
  const profilePath = "fixture-profile.json";
  const io = scriptedIo([
    "fixture-project", "Fixture Project", "1", "fixture-file-key", "12:34",
    "AE Assets", "1280", "720", "24", "FX", "FIXTURE_MASTER",
    "Fixture Imports", "0", "1", "12:35", "FX_SH01_Intro", "0", "6", "", ""
  ]);

  const exitCode = await runProfileCli({ kind: "init", output: profilePath }, { io, registry });
  assert.equal(exitCode, 0);
  assert.equal(validateProjectProfile(await io.readJson(profilePath)).project.id, "fixture-project");
  assert.deepEqual(io.stderrLines, []);
});

test("rejects out-of-range wizard counts before reading entries", async () => {
  const registry = await registryFixture();
  const prefix = [
    "fixture-project", "Fixture Project", "1", "fixture-file-key", "12:34", "AE Assets", "1280", "720", "24",
    "FX", "FIXTURE_MASTER", "Fixture Imports"
  ];
  const fontIo = scriptedIo([...prefix, String(PROFILE_LIMITS.maxRequiredFonts + 1), "must-not-read"]);
  assert.equal(await runProfileCli({ kind: "init", output: "fonts.json" }, { io: fontIo, registry }), 1);
  assert.equal(fontIo.prompts.length, prefix.length + 1);
  assert.match(fontIo.stderrLines.join(""), /PROFILE_INVALID/);

  const shotIo = scriptedIo([...prefix, "0", String(PROFILE_LIMITS.maxFrames + 1), "must-not-read"]);
  assert.equal(await runProfileCli({ kind: "init", output: "shots.json" }, { io: shotIo, registry }), 1);
  assert.equal(shotIo.prompts.length, prefix.length + 2);
  assert.match(shotIo.stderrLines.join(""), /PROFILE_INVALID/);
});

test("publishes runtime profiles atomically without overwriting or leaving failed temporary files", async () => {
  const root = await mkdtemp("/private/tmp/video001-profile-cli-writer-");
  const output = join(root, "profile.json");
  await writeNewProfileJson(output, { value: 1 });
  assert.equal(await readFile(output, "utf8"), '{\n  "value": 1\n}\n');
  await assert.rejects(writeNewProfileJson(output, { value: 2 }), { code: "EEXIST" });
  assert.equal(await readFile(output, "utf8"), '{\n  "value": 1\n}\n');

  const failedOutput = join(root, "failed.json");
  await assert.rejects(
    writeNewProfileJson(failedOutput, { value: 3 }, {
      ...realProfileCliRuntimeFilesystem,
      link: async () => { throw Object.assign(new Error("injected publication failure"), { code: "EIO" }); }
    }),
    { code: "EIO" }
  );
  assert.equal((await readdir(root)).some((entry) => entry.includes("failed.json.tmp-")), false);
  await assert.rejects(readFile(failedOutput, "utf8"), { code: "ENOENT" });
});

test("never unlinks a successor that replaces output after publication", async () => {
  const root = await mkdtemp("/private/tmp/video001-profile-cli-writer-race-");
  const output = join(root, "race.json");
  let replaced = false;
  await assert.rejects(
    writeNewProfileJson(output, { value: 1 }, {
      ...realProfileCliRuntimeFilesystem,
      lstat: (async (path: PathLike) => {
        if (path === output && !replaced) {
          replaced = true;
          await realProfileCliRuntimeFilesystem.unlink(output);
          await writeFile(output, "successor\n", { mode: 0o600 });
        }
        return realProfileCliRuntimeFilesystem.lstat(path);
      }) as unknown as typeof realProfileCliRuntimeFilesystem.lstat
    }),
    /PROFILE_OUTPUT_PUBLICATION_FAILED/
  );
  assert.equal(await readFile(output, "utf8"), "successor\n");
  assert.equal((await readdir(root)).some((entry) => entry.includes("race.json.tmp-")), false);
});

test("derives contiguous declared sections from optional wizard section answers", async () => {
  const registry = await registryFixture();
  const io = scriptedIo([
    "fixture-project", "Fixture Project", "1", "fixture-file-key", "12:34",
    "AE Assets", "1280", "720", "24", "FX", "FIXTURE_MASTER", "Fixture Imports", "0", "2",
    "12:35", "FX_SH01_Intro", "0", "6", "intro", "12:1",
    "12:36", "FX_SH02_Outro", "6", "6", "intro", "12:1"
  ]);

  assert.equal(await runProfileCli({ kind: "init", output: "sections.json" }, { io, registry }), 0);
  assert.deepEqual(validateProjectProfile(await io.readJson("sections.json")).timeline.sections, [
    { id: "intro", name: "Intro", firstShot: 1, lastShot: 2 }
  ]);
});

test("treats blank or EOF wizard input as explicit cancellation without creating output", async () => {
  const registry = await registryFixture();
  const blank = scriptedIo([""]);
  assert.equal(await runProfileCli({ kind: "init", output: "blank.json" }, { io: blank, registry }), 1);
  assert.equal(blank.files.has("blank.json"), false);
  assert.match(blank.stderrLines.join(""), /PROFILE_INIT_CANCELLED/);

  const eof = scriptedIo([]);
  assert.equal(await runProfileCli({ kind: "init", output: "eof.json" }, { io: eof, registry }), 1);
  assert.equal(eof.files.has("eof.json"), false);
  assert.match(eof.stderrLines.join(""), /PROFILE_INIT_CANCELLED/);
});

test("returns a deterministic error result for invalid profile input", async () => {
  const registry = await registryFixture();
  const io = scriptedIo([], new Map([["invalid.json", {}]]));

  assert.equal(await runProfileCli({ kind: "validate", file: "invalid.json", json: true }, { io, registry }), 1);
  assert.deepEqual(JSON.parse(io.stderrLines.join("")), {
    status: "error",
    code: "PROFILE_INVALID",
    message: "Profile is invalid"
  });
});

test("reports an unreadable profile without exposing its path", async () => {
  const registry = await registryFixture();
  const io = scriptedIo([]);

  assert.equal(await runProfileCli({ kind: "inspect", file: "sensitive/missing.json", json: true }, { io, registry }), 1);
  assert.deepEqual(JSON.parse(io.stderrLines.join("")), {
    status: "error",
    code: "PROFILE_READ_FAILED",
    message: "Profile could not be read"
  });
  assert.doesNotMatch(io.stderrLines.join(""), /sensitive/);
});
