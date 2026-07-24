import { canonicalJson } from "./canonical-json.ts";
import { PROFILE_LIMITS } from "./limits.ts";
import { sha256Hex } from "./sha256.ts";
import { encodeUtf8, utf8ByteLength } from "./utf8.ts";

export interface ProjectProfile {
  schemaVersion: "1.0.0";
  project: { id: string; displayName: string; revision: number };
  source: { fileKey: string; pageId: string; pageName: string };
  target: { width: number; height: number; fps: number; timeUnit: "seconds" };
  naming: { shotPrefix: string; masterCompBase: string; importFolder: string };
  timeline: { sections: ProfileSection[]; shots: ProfileShot[] };
  fontPolicy: { required: FontIdentity[]; fallbacks: FontFallback[] };
  limits: { maxFrames: number; maxAssets: number };
}

export interface ProfileSection {
  id: string;
  name: string;
  firstShot: number;
  lastShot: number;
}

export interface ProfileShot {
  index: number;
  nodeId: string;
  compName: string;
  start: number;
  duration: number;
  sectionId?: string;
  sectionParentNodeId?: string;
}

export interface FontIdentity {
  family: string;
  style: string;
}

export interface FontFallback {
  source: FontIdentity;
  fallback: FontIdentity;
}

export interface InstalledProfile {
  profile: ProjectProfile;
  profileSha256: string;
}

export interface ProfileReference {
  projectId: string;
  profileRevision: number;
  profileSha256: string;
}

export interface ProfileSummary {
  projectId: string;
  displayName: string;
  revision: number;
  profileSha256: string;
  sourcePageName: string;
  target: { width: number; height: number; fps: number };
}

export interface ProfileProjection {
  reference: ProfileReference;
  source: ProjectProfile["source"];
  target: ProjectProfile["target"];
  naming: ProjectProfile["naming"];
  timeline: ProjectProfile["timeline"];
  fontPolicy: ProjectProfile["fontPolicy"];
  limits: ProjectProfile["limits"];
}

type UnknownRecord = Record<string, unknown>;

const PROJECT_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]{1,62}[a-z0-9])?$/;
const SECTION_ID_PATTERN = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;
const HUMAN_NAME_PATTERN = /^[\p{L}\p{N}](?:[\p{L}\p{M}\p{N}&'’ -]*[\p{L}\p{M}\p{N}])?$/u;
const FIGMA_FILE_KEY_PATTERN = /^(?:[A-Za-z0-9]{16,128}|[a-z][a-z0-9]*(?:-[a-z0-9]+)*)$/;
const FIGMA_NODE_ID_PATTERN = /^\d+:\d+$/;
const PREFIX_PATTERN = /^[A-Z][A-Z0-9]*$/;
const MASTER_COMP_PATTERN = /^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*$/;
const COMP_NAME_PATTERN = /^[A-Z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*$/;
const FONT_NAME_PATTERN = /^[\p{L}\p{N}](?:[\p{L}\p{M}\p{N}&_'’ -]*[\p{L}\p{M}\p{N}])?$/u;
// Defense in depth only: profile values are declarative data and are never executed.
const DECLARATIVE_COMMAND_TOKENS = Object.freeze([
  "alias", "awk", "basename", "bash", "bg", "break", "cat", "cd", "chgrp", "chmod", "chown", "command",
  "cmd", "const", "continue", "cp", "curl", "cut", "dash", "date", "dd", "df", "diff", "dirname", "dirs", "disown", "docker",
  "du", "echo", "env", "eval", "exec", "exit", "export", "fc", "fg", "find", "fish", "function", "getopts", "gh", "git",
  "grep", "hash", "head", "history", "id", "install", "jobs", "kill", "kubectl", "less", "ln", "ls", "make",
  "mkdir", "more", "mount", "mv", "nc", "netcat", "osascript", "pkill",
  "import", "let", "powershell", "ps", "pwd", "pwsh", "read", "readonly", "require", "return", "rm", "rmdir", "scp", "sed", "set",
  "sh", "sha256sum", "shift", "source", "sort", "sftp", "ssh", "stat", "sudo", "suspend", "tail", "tar", "tee", "telnet",
  "terraform", "test", "times", "touch", "tr", "trap", "type", "ulimit", "umask", "unalias", "uname", "uniq", "unset",
  "var", "wait", "wget", "which", "xargs", "zsh"
] as const);
// Runtime/tool-led labels are reserved unless the entire two-token phrase is an educational title.
// Arbitrary command text is otherwise indistinguishable from a plain human-readable label.
const RUNTIME_TOOL_TOKENS = Object.freeze([
  "bun", "cargo", "clang", "deno", "dotnet", "gcc", "go", "java", "node", "npm", "npx", "perl", "php",
  "pip", "pip3", "pnpm", "python", "python3", "ruby", "rustc", "swift", "uv", "yarn"
] as const);
const EDUCATIONAL_TITLE_FINAL_TOKENS = Object.freeze([
  "basics", "course", "fundamentals", "guide", "introduction", "lesson", "overview", "project", "training", "tutorial", "workshop"
] as const);

function invalid(path: string, message: string): never {
  throw new TypeError(`Invalid project profile at ${path}: ${message}`);
}

function recordAt(value: unknown, path: string): UnknownRecord {
  if (value === null || typeof value !== "object" || Array.isArray(value)) invalid(path, "expected an object");
  return value as UnknownRecord;
}

function exactKeys(record: UnknownRecord, keys: readonly string[], path: string): void {
  const allowed = new Set(keys);
  for (const key of Object.keys(record)) {
    if (!allowed.has(key)) invalid(`${path}.${key}`, "unknown field");
  }
  for (const key of keys) {
    if (!Object.prototype.hasOwnProperty.call(record, key)) invalid(`${path}.${key}`, "missing required field");
  }
}

function arrayAt(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) invalid(path, "expected an array");
  return value;
}

function finiteNumberAt(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) invalid(path, "expected a finite number");
  return value;
}

function positiveSafeIntegerAt(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value <= 0) {
    invalid(path, "expected a positive safe integer");
  }
  return value;
}

function characterCount(value: string): number {
  return Array.from(value).length;
}

function boundedStringAt(value: unknown, path: string): string {
  if (typeof value !== "string" || value.length === 0) invalid(path, "expected a non-empty string");
  if (characterCount(value) > PROFILE_LIMITS.maxNameCharacters) {
    invalid(path, `exceeds the ${PROFILE_LIMITS.maxNameCharacters}-character limit`);
  }
  return value;
}

function matchingStringAt(value: unknown, path: string, pattern: RegExp): string {
  const result = boundedStringAt(value, path);
  if (!pattern.test(result)) invalid(path, "unsafe value");
  return result;
}

function isReservedDeclarativeCommand(value: string): boolean {
  const tokens = value.split(" ");
  const firstToken = tokens[0]!.toLowerCase();
  if ((DECLARATIVE_COMMAND_TOKENS as readonly string[]).includes(firstToken)) return true;
  if (!(RUNTIME_TOOL_TOKENS as readonly string[]).includes(firstToken)) return false;
  return tokens.length !== 2 || !(EDUCATIONAL_TITLE_FINAL_TOKENS as readonly string[]).includes(tokens[1]!.toLowerCase());
}

function normalizedNamedStringAt(value: unknown, path: string, pattern: RegExp): string {
  if (typeof value !== "string" || value.length === 0) invalid(path, "expected a non-empty string");
  const normalized = boundedStringAt(value.normalize("NFC"), path);
  if (
    normalized.startsWith(" ") ||
    normalized.endsWith(" ") ||
    normalized.includes("  ") ||
    !pattern.test(normalized) ||
    isReservedDeclarativeCommand(normalized)
  ) invalid(path, "unsafe value");
  return normalized;
}

function humanNameAt(value: unknown, path: string): string {
  return normalizedNamedStringAt(value, path, HUMAN_NAME_PATTERN);
}

function figmaFileKeyAt(value: unknown, path: string): string {
  return matchingStringAt(value, path, FIGMA_FILE_KEY_PATTERN);
}

function figmaNodeIdAt(value: unknown, path: string): string {
  return matchingStringAt(value, path, FIGMA_NODE_ID_PATTERN);
}

function sectionIdAt(value: unknown, path: string): string {
  return matchingStringAt(value, path, SECTION_ID_PATTERN);
}

function prefixAt(value: unknown, path: string): string {
  return matchingStringAt(value, path, PREFIX_PATTERN);
}

function masterCompBaseAt(value: unknown, path: string): string {
  return matchingStringAt(value, path, MASTER_COMP_PATTERN);
}

function compNameAt(value: unknown, path: string): string {
  return matchingStringAt(value, path, COMP_NAME_PATTERN);
}

function fontTokenAt(value: unknown, path: string): string {
  return normalizedNamedStringAt(value, path, FONT_NAME_PATTERN);
}

function projectIdAt(value: unknown, path: string): string {
  if (typeof value !== "string" || !PROJECT_ID_PATTERN.test(value)) invalid(path, "unsafe project ID");
  return value;
}

function exactFrameCount(value: number, fps: number, path: string): number {
  const frames = value * fps;
  const rounded = Math.round(frames);
  if (!Number.isSafeInteger(rounded) || Math.abs(frames - rounded) > 1e-9) {
    invalid(path, "expected whole-frame timing");
  }
  return rounded;
}

function fontIdentityAt(value: unknown, path: string): FontIdentity {
  const record = recordAt(value, path);
  exactKeys(record, ["family", "style"], path);
  return { family: fontTokenAt(record.family, `${path}.family`), style: fontTokenAt(record.style, `${path}.style`) };
}

function fontKey(font: FontIdentity): string {
  return `${font.family}\u0000${font.style}`;
}

function sectionAt(value: unknown, path: string): ProfileSection {
  const record = recordAt(value, path);
  exactKeys(record, ["id", "name", "firstShot", "lastShot"], path);
  const firstShot = positiveSafeIntegerAt(record.firstShot, `${path}.firstShot`);
  const lastShot = positiveSafeIntegerAt(record.lastShot, `${path}.lastShot`);
  if (lastShot < firstShot) invalid(`${path}.lastShot`, "must not precede firstShot");
  return {
    id: sectionIdAt(record.id, `${path}.id`),
    name: humanNameAt(record.name, `${path}.name`),
    firstShot,
    lastShot
  };
}

function shotAt(value: unknown, path: string): ProfileShot {
  const record = recordAt(value, path);
  const allowed = ["index", "nodeId", "compName", "start", "duration", "sectionId", "sectionParentNodeId"];
  for (const key of Object.keys(record)) {
    if (!allowed.includes(key)) invalid(`${path}.${key}`, "unknown field");
  }
  for (const key of ["index", "nodeId", "compName", "start", "duration"]) {
    if (!Object.prototype.hasOwnProperty.call(record, key)) invalid(`${path}.${key}`, "missing required field");
  }
  const start = finiteNumberAt(record.start, `${path}.start`);
  const duration = finiteNumberAt(record.duration, `${path}.duration`);
  if (start < 0) invalid(`${path}.start`, "expected a non-negative number");
  if (duration <= 0) invalid(`${path}.duration`, "expected a positive number");
  const shot: ProfileShot = {
    index: positiveSafeIntegerAt(record.index, `${path}.index`),
    nodeId: figmaNodeIdAt(record.nodeId, `${path}.nodeId`),
    compName: compNameAt(record.compName, `${path}.compName`),
    start,
    duration
  };
  if (Object.prototype.hasOwnProperty.call(record, "sectionId")) shot.sectionId = sectionIdAt(record.sectionId, `${path}.sectionId`);
  if (Object.prototype.hasOwnProperty.call(record, "sectionParentNodeId")) {
    shot.sectionParentNodeId = figmaNodeIdAt(record.sectionParentNodeId, `${path}.sectionParentNodeId`);
  }
  return shot;
}

export function validateProjectProfile(value: unknown): ProjectProfile {
  const root = recordAt(value, "$");
  exactKeys(root, ["schemaVersion", "project", "source", "target", "naming", "timeline", "fontPolicy", "limits"], "$");
  if (root.schemaVersion !== "1.0.0") invalid("$.schemaVersion", "expected \"1.0.0\"");

  const project = recordAt(root.project, "$.project");
  exactKeys(project, ["id", "displayName", "revision"], "$.project");
  const source = recordAt(root.source, "$.source");
  exactKeys(source, ["fileKey", "pageId", "pageName"], "$.source");
  const target = recordAt(root.target, "$.target");
  exactKeys(target, ["width", "height", "fps", "timeUnit"], "$.target");
  const width = positiveSafeIntegerAt(target.width, "$.target.width");
  const height = positiveSafeIntegerAt(target.height, "$.target.height");
  const fps = positiveSafeIntegerAt(target.fps, "$.target.fps");
  if (width < 16 || width > PROFILE_LIMITS.maxDimension) invalid("$.target.width", "must be between 16 and 16384");
  if (height < 16 || height > PROFILE_LIMITS.maxDimension) invalid("$.target.height", "must be between 16 and 16384");
  if (fps > PROFILE_LIMITS.maxFps) invalid("$.target.fps", "exceeds the 120-fps limit");
  if (target.timeUnit !== "seconds") invalid("$.target.timeUnit", "expected \"seconds\"");

  const naming = recordAt(root.naming, "$.naming");
  exactKeys(naming, ["shotPrefix", "masterCompBase", "importFolder"], "$.naming");
  const timeline = recordAt(root.timeline, "$.timeline");
  exactKeys(timeline, ["sections", "shots"], "$.timeline");
  const sectionValues = arrayAt(timeline.sections, "$.timeline.sections");
  const shotValues = arrayAt(timeline.shots, "$.timeline.shots");
  if (shotValues.length === 0) invalid("$.timeline.shots", "expected at least one shot");
  if (shotValues.length > PROFILE_LIMITS.maxFrames) invalid("$.timeline.shots", "exceeds the 256-frame limit");

  const sections = sectionValues.map((entry, index) => sectionAt(entry, `$.timeline.sections[${index}]`));
  const sectionIds = new Set<string>();
  let previousLastShot = 0;
  for (let index = 0; index < sections.length; index += 1) {
    const section = sections[index]!;
    if (sectionIds.has(section.id)) invalid(`$.timeline.sections[${index}].id`, "duplicate section ID");
    sectionIds.add(section.id);
    if (section.firstShot !== previousLastShot + 1) {
      invalid(`$.timeline.sections[${index}].firstShot`, "expected contiguous section ranges");
    }
    previousLastShot = section.lastShot;
  }
  if (sections.length > 0 && previousLastShot !== shotValues.length) {
    invalid(`$.timeline.sections[${sections.length - 1}].lastShot`, "expected contiguous section ranges");
  }

  const shots = shotValues.map((entry, index) => shotAt(entry, `$.timeline.shots[${index}]`));
  const nodeIds = new Set<string>();
  const compNames = new Set<string>();
  let expectedStartFrame = 0;
  for (let position = 0; position < shots.length; position += 1) {
    const shot = shots[position]!;
    const path = `$.timeline.shots[${position}]`;
    if (shot.index !== position + 1) invalid(`${path}.index`, `expected contiguous index ${position + 1}`);
    if (nodeIds.has(shot.nodeId)) invalid(`${path}.nodeId`, "duplicate node ID");
    nodeIds.add(shot.nodeId);
    if (compNames.has(shot.compName)) invalid(`${path}.compName`, "duplicate composition name");
    compNames.add(shot.compName);
    const startFrame = exactFrameCount(shot.start, fps, `${path}.start`);
    const durationFrames = exactFrameCount(shot.duration, fps, `${path}.duration`);
    if (startFrame !== expectedStartFrame) invalid(`${path}.start`, "expected continuous timing");
    expectedStartFrame += durationFrames;
    const matchedSection = sections.find((section) => shot.index >= section.firstShot && shot.index <= section.lastShot);
    if (matchedSection === undefined) {
      if (shot.sectionId !== undefined) invalid(`${path}.sectionId`, "does not match a declared section");
    } else if (shot.sectionId !== matchedSection.id) {
      invalid(`${path}.sectionId`, "does not match the declared section range");
    }
  }
  if (expectedStartFrame / fps > PROFILE_LIMITS.maxDurationSeconds) {
    invalid("$.timeline.shots", "exceeds the six-hour duration limit");
  }

  const fontPolicy = recordAt(root.fontPolicy, "$.fontPolicy");
  exactKeys(fontPolicy, ["required", "fallbacks"], "$.fontPolicy");
  const requiredValues = arrayAt(fontPolicy.required, "$.fontPolicy.required");
  const fallbackValues = arrayAt(fontPolicy.fallbacks, "$.fontPolicy.fallbacks");
  if (requiredValues.length > PROFILE_LIMITS.maxRequiredFonts) invalid("$.fontPolicy.required", "exceeds the 256-font limit");
  if (fallbackValues.length > PROFILE_LIMITS.maxFontFallbacks) invalid("$.fontPolicy.fallbacks", "exceeds the 512-fallback limit");
  const required = requiredValues.map((entry, index) => fontIdentityAt(entry, `$.fontPolicy.required[${index}]`));
  const requiredFonts = new Set<string>();
  for (let index = 0; index < required.length; index += 1) {
    const key = fontKey(required[index]!);
    if (requiredFonts.has(key)) invalid(`$.fontPolicy.required[${index}]`, "duplicate font identity");
    requiredFonts.add(key);
  }
  const fallbacks = fallbackValues.map((entry, index) => {
    const path = `$.fontPolicy.fallbacks[${index}]`;
    const record = recordAt(entry, path);
    exactKeys(record, ["source", "fallback"], path);
    return { source: fontIdentityAt(record.source, `${path}.source`), fallback: fontIdentityAt(record.fallback, `${path}.fallback`) };
  });

  const limits = recordAt(root.limits, "$.limits");
  exactKeys(limits, ["maxFrames", "maxAssets"], "$.limits");
  const maxFrames = positiveSafeIntegerAt(limits.maxFrames, "$.limits.maxFrames");
  const maxAssets = positiveSafeIntegerAt(limits.maxAssets, "$.limits.maxAssets");
  if (maxFrames > PROFILE_LIMITS.maxFrames) invalid("$.limits.maxFrames", "exceeds the 256-frame limit");
  if (maxAssets > PROFILE_LIMITS.maxAssets) invalid("$.limits.maxAssets", "exceeds the 2048-asset limit");
  if (maxFrames < shots.length) invalid("$.limits.maxFrames", "must cover all declared shots");

  const profile: ProjectProfile = {
    schemaVersion: "1.0.0",
    project: {
      id: projectIdAt(project.id, "$.project.id"),
      displayName: humanNameAt(project.displayName, "$.project.displayName"),
      revision: positiveSafeIntegerAt(project.revision, "$.project.revision")
    },
    source: {
      fileKey: figmaFileKeyAt(source.fileKey, "$.source.fileKey"),
      pageId: figmaNodeIdAt(source.pageId, "$.source.pageId"),
      pageName: humanNameAt(source.pageName, "$.source.pageName")
    },
    target: { width, height, fps, timeUnit: "seconds" },
    naming: {
      shotPrefix: prefixAt(naming.shotPrefix, "$.naming.shotPrefix"),
      masterCompBase: masterCompBaseAt(naming.masterCompBase, "$.naming.masterCompBase"),
      importFolder: humanNameAt(naming.importFolder, "$.naming.importFolder")
    },
    timeline: { sections, shots },
    fontPolicy: { required, fallbacks },
    limits: { maxFrames, maxAssets }
  };
  if (utf8ByteLength(canonicalJson(profile)) > PROFILE_LIMITS.maxProfileBytes) {
    invalid("$", "exceeds the profile-byte limit");
  }
  return profile;
}

export function canonicalProfileJson(value: unknown): string {
  return canonicalJson(validateProjectProfile(value));
}

export function hashProjectProfile(value: unknown): InstalledProfile {
  const profile = validateProjectProfile(value);
  const bytes = encodeUtf8(canonicalJson(profile));
  return { profile, profileSha256: sha256Hex(bytes) };
}

export function profileReference(value: InstalledProfile): ProfileReference {
  return {
    projectId: value.profile.project.id,
    profileRevision: value.profile.project.revision,
    profileSha256: value.profileSha256
  };
}

export function profileSummary(value: InstalledProfile): ProfileSummary {
  return {
    projectId: value.profile.project.id,
    displayName: value.profile.project.displayName,
    revision: value.profile.project.revision,
    profileSha256: value.profileSha256,
    sourcePageName: value.profile.source.pageName,
    target: {
      width: value.profile.target.width,
      height: value.profile.target.height,
      fps: value.profile.target.fps
    }
  };
}

export function publicProfileProjection(value: InstalledProfile): ProfileProjection {
  const profile = validateProjectProfile(value.profile);
  return {
    reference: profileReference({ profile, profileSha256: value.profileSha256 }),
    source: { ...profile.source },
    target: { ...profile.target },
    naming: { ...profile.naming },
    timeline: {
      sections: profile.timeline.sections.map((section) => ({ ...section })),
      shots: profile.timeline.shots.map((shot) => ({ ...shot }))
    },
    fontPolicy: {
      required: profile.fontPolicy.required.map((font) => ({ ...font })),
      fallbacks: profile.fontPolicy.fallbacks.map((fallback) => ({
        source: { ...fallback.source },
        fallback: { ...fallback.fallback }
      }))
    },
    limits: { ...profile.limits }
  };
}
