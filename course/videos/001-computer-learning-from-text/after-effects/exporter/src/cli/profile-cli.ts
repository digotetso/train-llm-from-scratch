import { open, readFile } from "node:fs/promises";
import { stdin, stdout, stderr } from "node:process";
import { createInterface } from "node:readline/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { ProfileRegistry } from "../bridge/profile-registry.ts";
import { exporterPaths } from "../bridge/paths.ts";
import { hashProjectProfile, validateProjectProfile, type ProjectProfile, type ProfileSummary } from "../shared/project-profile.ts";

export interface ProfileCliIo {
  readLine(prompt: string): Promise<string>;
  stdout(value: string): void;
  stderr(value: string): void;
  readJson(path: string): Promise<unknown>;
  writeNewJson(path: string, value: unknown): Promise<void>;
}

export type ProfileCommand =
  | { kind: "init"; output: string }
  | { kind: "validate"; file: string; json: boolean }
  | { kind: "inspect"; file: string; json: boolean }
  | { kind: "install"; file: string; json: boolean }
  | { kind: "list"; json: boolean };

export interface CliResult {
  status: "ok" | "error";
  code: string;
  project?: { id: string; displayName: string; revision: number; profileSha256: string };
  message: string;
}

class ProfileCliError extends Error {
  constructor(readonly code: string, message: string) {
    super(message);
  }
}

function invalidCommand(): never {
  throw new TypeError("Invalid profile command. Use init, validate, inspect, install, or list.");
}

function profileFileCommand(kind: "validate" | "inspect" | "install", argv: readonly string[]): ProfileCommand {
  const [file, ...flags] = argv;
  if (file === undefined || file.length === 0 || file.startsWith("--") || (flags.length !== 0 && (flags.length !== 1 || flags[0] !== "--json"))) {
    return invalidCommand();
  }
  return { kind, file, json: flags[0] === "--json" };
}

export function parseProfileCli(argv: readonly string[]): ProfileCommand {
  const [kind, ...rest] = argv;
  if (kind === "init") {
    if (rest.length !== 2 || rest[0] !== "--output" || rest[1] === undefined || rest[1].length === 0) return invalidCommand();
    return { kind, output: rest[1] };
  }
  if (kind === "validate" || kind === "inspect" || kind === "install") return profileFileCommand(kind, rest);
  if (kind === "list") {
    if (rest.length !== 0 && (rest.length !== 1 || rest[0] !== "--json")) return invalidCommand();
    return { kind, json: rest[0] === "--json" };
  }
  return invalidCommand();
}

function cliProject(value: ReturnType<typeof hashProjectProfile>): NonNullable<CliResult["project"]> {
  return {
    id: value.profile.project.id,
    displayName: value.profile.project.displayName,
    revision: value.profile.project.revision,
    profileSha256: value.profileSha256
  };
}

function summaryProject(value: ProfileSummary): NonNullable<CliResult["project"]> {
  return {
    id: value.projectId,
    displayName: value.displayName,
    revision: value.revision,
    profileSha256: value.profileSha256
  };
}

function emit(io: ProfileCliIo, json: boolean, result: CliResult): void {
  const destination = result.status === "ok" ? io.stdout : io.stderr;
  if (json) {
    destination(`${JSON.stringify(result)}\n`);
    return;
  }
  const project = result.project === undefined
    ? ""
    : ` project=${result.project.id} revision=${result.project.revision} sha256=${result.project.profileSha256}`;
  destination(`status=${result.status} code=${result.code}${project} message=${result.message}\n`);
}

function errorCode(error: unknown, fallback: string): string {
  if (error instanceof ProfileCliError) return error.code;
  if (error !== null && typeof error === "object" && "code" in error && typeof error.code === "string") {
    if (error.code === "EEXIST") return "PROFILE_OUTPUT_EXISTS";
    if (fallback === "PROFILE_INVALID" && (error.code === "EACCES" || error.code === "ENOENT" || error.code === "EPERM")) {
      return "PROFILE_READ_FAILED";
    }
    if (error.code.startsWith("PROFILE_")) return error.code;
  }
  return fallback;
}

function errorMessage(code: string): string {
  if (code === "PROFILE_OUTPUT_EXISTS") return "Refusing to overwrite an existing profile";
  if (code === "PROFILE_INIT_CANCELLED") return "Profile initialization was cancelled";
  if (code === "PROFILE_INIT_TTY_REQUIRED") return "Profile initialization requires an interactive terminal";
  if (code === "PROFILE_INVALID") return "Profile is invalid";
  if (code === "PROFILE_READ_FAILED") return "Profile could not be read";
  if (code.startsWith("PROFILE_REGISTRY_") || code === "PROFILE_REVISION_CONFLICT" || code === "PROFILE_NOT_FOUND") {
    return "Profile registry operation failed";
  }
  return "Profile command failed";
}

function isCancelled(error: unknown): boolean {
  return error instanceof ProfileCliError && error.code === "PROFILE_INIT_CANCELLED";
}

async function answer(io: ProfileCliIo, prompt: string, optional = false): Promise<string | undefined> {
  let value: string;
  try {
    value = await io.readLine(prompt);
  } catch (error) {
    if (error instanceof ProfileCliError) throw error;
    throw new ProfileCliError("PROFILE_INIT_CANCELLED", "Profile initialization was cancelled");
  }
  if (value.length === 0) {
    if (optional) return undefined;
    throw new ProfileCliError("PROFILE_INIT_CANCELLED", "Profile initialization was cancelled");
  }
  return value;
}

async function required(io: ProfileCliIo, prompt: string): Promise<string> {
  return (await answer(io, prompt))!;
}

function sectionName(id: string): string {
  return id.split("-").map((part) => `${part[0]!.toUpperCase()}${part.slice(1)}`).join(" ");
}

function derivedSections(shots: ProjectProfile["timeline"]["shots"]): ProjectProfile["timeline"]["sections"] {
  if (shots.every((shot) => shot.sectionId === undefined)) return [];
  if (shots.some((shot) => shot.sectionId === undefined)) {
    throw new ProfileCliError("PROFILE_INVALID", "Profile is invalid");
  }
  const sections: ProjectProfile["timeline"]["sections"] = [];
  const completed = new Set<string>();
  for (const shot of shots) {
    const id = shot.sectionId!;
    const current = sections.at(-1);
    if (current?.id === id) {
      current.lastShot = shot.index;
      continue;
    }
    if (completed.has(id)) throw new ProfileCliError("PROFILE_INVALID", "Profile is invalid");
    if (current !== undefined) completed.add(current.id);
    sections.push({ id, name: sectionName(id), firstShot: shot.index, lastShot: shot.index });
  }
  return sections;
}

async function wizardProfile(io: ProfileCliIo): Promise<ProjectProfile> {
  const projectId = await required(io, "Project ID: ");
  const displayName = await required(io, "Project display name: ");
  const revision = Number(await required(io, "Profile revision: "));
  const fileKey = await required(io, "Figma file key: ");
  const pageId = await required(io, "Figma page ID: ");
  const pageName = await required(io, "Figma page name: ");
  const width = Number(await required(io, "Target width: "));
  const height = Number(await required(io, "Target height: "));
  const fps = Number(await required(io, "Target fps: "));
  const shotPrefix = await required(io, "Shot prefix: ");
  const masterCompBase = await required(io, "Master composition base: ");
  const importFolder = await required(io, "Import folder: ");
  const requiredFontCount = Number(await required(io, "Required font count: "));
  if (!Number.isSafeInteger(requiredFontCount) || requiredFontCount < 0) {
    throw new ProfileCliError("PROFILE_INVALID", "Profile is invalid");
  }
  const fonts: Array<{ family: string; style: string }> = [];
  for (let index = 0; index < requiredFontCount; index += 1) {
    fonts.push({
      family: await required(io, `Required font ${index + 1} family: `),
      style: await required(io, `Required font ${index + 1} style: `)
    });
  }
  const shotCount = Number(await required(io, "Shot count: "));
  if (!Number.isSafeInteger(shotCount) || shotCount <= 0) {
    throw new ProfileCliError("PROFILE_INVALID", "Profile is invalid");
  }
  const shots: ProjectProfile["timeline"]["shots"] = [];
  for (let index = 0; index < shotCount; index += 1) {
    const nodeId = await required(io, `Shot ${index + 1} Figma node ID: `);
    const compName = await required(io, `Shot ${index + 1} composition name: `);
    const start = Number(await required(io, `Shot ${index + 1} start seconds: `));
    const duration = Number(await required(io, `Shot ${index + 1} duration seconds: `));
    const sectionId = await answer(io, `Shot ${index + 1} section ID (optional): `, true);
    const sectionParentNodeId = await answer(io, `Shot ${index + 1} section parent node ID (optional): `, true);
    shots.push({
      index: index + 1,
      nodeId,
      compName,
      start,
      duration,
      ...(sectionId === undefined ? {} : { sectionId }),
      ...(sectionParentNodeId === undefined ? {} : { sectionParentNodeId })
    });
  }
  return validateProjectProfile({
    schemaVersion: "1.0.0",
    project: { id: projectId, displayName, revision },
    source: { fileKey, pageId, pageName },
    target: { width, height, fps, timeUnit: "seconds" },
    naming: { shotPrefix, masterCompBase, importFolder },
    timeline: { sections: derivedSections(shots), shots },
    fontPolicy: { required: fonts, fallbacks: [] },
    limits: { maxFrames: shotCount, maxAssets: 1 }
  });
}

function localProfile(value: unknown): ReturnType<typeof hashProjectProfile> {
  return hashProjectProfile(validateProjectProfile(value));
}

export async function runProfileCli(
  command: ProfileCommand,
  dependencies: { io: ProfileCliIo; registry: ProfileRegistry }
): Promise<number> {
  const { io, registry } = dependencies;
  const json = command.kind !== "init" && command.json;
  try {
    if (command.kind === "init") {
      const profile = await wizardProfile(io);
      await io.writeNewJson(command.output, profile);
      emit(io, false, { status: "ok", code: "PROFILE_INITIALIZED", project: cliProject(hashProjectProfile(profile)), message: "Profile was created" });
      return 0;
    }
    if (command.kind === "validate") {
      const profile = localProfile(await io.readJson(command.file));
      emit(io, command.json, { status: "ok", code: "PROFILE_VALID", project: cliProject(profile), message: "Profile is valid" });
      return 0;
    }
    if (command.kind === "inspect") {
      const profile = localProfile(await io.readJson(command.file));
      emit(io, command.json, { status: "ok", code: "PROFILE_INSPECTED", project: cliProject(profile), message: "Profile inspected" });
      return 0;
    }
    if (command.kind === "install") {
      const profile = localProfile(await io.readJson(command.file));
      const installed = await registry.installValue(profile.profile);
      emit(io, command.json, { status: "ok", code: "PROFILE_INSTALLED", project: cliProject(installed), message: "Profile installed" });
      return 0;
    }
    const summaries = await registry.list();
    if (summaries.length === 0) {
      emit(io, command.json, { status: "ok", code: "PROFILE_LIST_EMPTY", message: "No profiles are installed" });
    } else {
      for (const summary of summaries) {
        emit(io, command.json, { status: "ok", code: "PROFILE_LISTED", project: summaryProject(summary), message: "Installed profile" });
      }
    }
    return 0;
  } catch (error) {
    const fallback = command.kind === "validate" || command.kind === "inspect" || command.kind === "install"
      ? "PROFILE_INVALID"
      : command.kind === "init" && isCancelled(error)
        ? "PROFILE_INIT_CANCELLED"
        : "PROFILE_COMMAND_FAILED";
    const code = errorCode(error, fallback);
    emit(io, json, { status: "error", code, message: errorMessage(code) });
    return 1;
  }
}

function runtimeIo(): ProfileCliIo & { close(): void } {
  let lineReader: ReturnType<typeof createInterface> | undefined;
  const reader = (): ReturnType<typeof createInterface> => {
    lineReader ??= createInterface({ input: stdin, output: stdout, terminal: true });
    return lineReader;
  };
  return {
    async readLine(prompt: string): Promise<string> {
      if (!stdin.isTTY) throw new ProfileCliError("PROFILE_INIT_TTY_REQUIRED", "Profile initialization requires an interactive terminal");
      const activeReader = reader();
      return new Promise<string>((resolve, reject) => {
        const onClose = (): void => reject(new ProfileCliError("PROFILE_INIT_CANCELLED", "Profile initialization was cancelled"));
        activeReader.once("close", onClose);
        void activeReader.question(prompt).then(
          (value) => { activeReader.off("close", onClose); resolve(value); },
          (error: unknown) => { activeReader.off("close", onClose); reject(error); }
        );
      });
    },
    stdout(value: string): void { stdout.write(value); },
    stderr(value: string): void { stderr.write(value); },
    async readJson(path: string): Promise<unknown> { return JSON.parse(await readFile(path, "utf8")); },
    async writeNewJson(path: string, value: unknown): Promise<void> {
      const handle = await open(path, "wx", 0o600);
      try {
        await handle.writeFile(`${JSON.stringify(value, null, 2)}\n`, "utf8");
        await handle.sync();
      } finally {
        await handle.close();
      }
    },
    close(): void { lineReader?.close(); }
  };
}

async function main(argv: readonly string[]): Promise<number> {
  if (argv[0] !== "profile") {
    stderr.write("status=error code=PROFILE_COMMAND_INVALID message=Invalid profile command\n");
    return 2;
  }
  try {
    const io = runtimeIo();
    try {
      return await runProfileCli(parseProfileCli(argv.slice(1)), {
        io,
        registry: new ProfileRegistry(exporterPaths())
      });
    } finally {
      io.close();
    }
  } catch {
    stderr.write("status=error code=PROFILE_COMMAND_INVALID message=Invalid profile command\n");
    return 2;
  }
}

if (process.argv[1] !== undefined && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  process.exitCode = await main(process.argv.slice(2));
}
