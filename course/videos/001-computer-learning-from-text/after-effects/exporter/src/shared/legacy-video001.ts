import {
  canonicalJson,
  EXTERNAL_ASSET_DATA,
  validatePackage,
  validatePackageWithVerifiedAssets,
  validatePackageAgainstProfile,
  type ExternalAssetDescriptor,
  type ExporterPackage
} from "./contract.ts";
import {
  hashProjectProfile,
  profileReference,
  type InstalledProfile,
  type ProfileReference,
  type ProjectProfile
} from "./project-profile.ts";
import { sha256Hex } from "./sha256.ts";
import { encodeUtf8 } from "./utf8.ts";

export type LegacyVideo001Package = Omit<ExporterPackage, "schemaVersion" | "project"> & {
  schemaVersion: "2.0.0";
};

/** A schema-2 package after asset bytes have been held outside the manifest. */
export interface LegacyVideo001ExternalPackage extends Omit<LegacyVideo001Package, "assets"> {
  assets: ExternalAssetDescriptor[];
}

type UnknownRecord = Record<string, unknown>;

export const legacyVideo001SchemaVersion = "2.0.0";
export const legacyVideo001ExportMediaType = "application/vnd.video001.figma-ae+json";
export const legacyVideo001PackageSuffix = ".video001-ae.json";
export const legacyVideo001MaxFrames = 48;
const BUNDLED_VIDEO001_REFERENCE = Object.freeze({
  projectId: "video-001",
  profileRevision: 1,
  profileSha256: "632a156d68b4245c1985b16069276842c5dcdc9306726c88e139fdabf40b2479"
});

/** The schema-3 reference used only while the Video 001 producer remains legacy-bound. */
export function legacyVideo001ProfileReference(): ProfileReference {
  return { ...BUNDLED_VIDEO001_REFERENCE };
}

export function isLegacyVideo001Package(value: unknown): value is { schemaVersion: "2.0.0" } {
  return value !== null && typeof value === "object" && !Array.isArray(value) &&
    (value as UnknownRecord).schemaVersion === legacyVideo001SchemaVersion;
}

function recordAt(value: unknown, path: string): UnknownRecord {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError(`Invalid legacy Video 001 package at ${path}: expected an object`);
  }
  return value as UnknownRecord;
}

function exactKeys(record: UnknownRecord, keys: readonly string[], path: string): void {
  const allowed = new Set(keys);
  for (const key of Object.keys(record)) {
    if (!allowed.has(key)) throw new TypeError(`Invalid legacy Video 001 package at ${path}.${key}: unknown field`);
  }
  for (const key of keys) {
    if (!Object.prototype.hasOwnProperty.call(record, key)) {
      throw new TypeError(`Invalid legacy Video 001 package at ${path}.${key}: missing required field`);
    }
  }
}

function legacyFingerprintInput(value: LegacyVideo001Package): string {
  return canonicalJson({ ...value, exportedAt: "", contentHash: "" });
}

export function legacyVideo001ContentFingerprintInput(value: unknown): string {
  return legacyFingerprintInput(validateLegacyPackage(value, true));
}

export function finalizeLegacyVideo001Package(value: unknown): LegacyVideo001Package {
  const legacy = validateLegacyPackage(value, true);
  return { ...legacy, contentHash: sha256Hex(encodeUtf8(legacyFingerprintInput(legacy))) };
}

export function createLegacyVideo001Package(
  value: Omit<LegacyVideo001Package, "schemaVersion" | "contentHash">
): LegacyVideo001Package {
  return { ...value, schemaVersion: legacyVideo001SchemaVersion, contentHash: "" };
}

export function validateLegacyVideo001Package(value: unknown): LegacyVideo001Package {
  return validateLegacyPackage(value, false);
}

function validateLegacyPackage(value: unknown, allowEmptyContentHash: boolean): LegacyVideo001Package {
  const record = recordAt(value, "$");
  assertLegacyVideo001Envelope(record, allowEmptyContentHash);
  const candidate = {
    ...record,
    schemaVersion: "3.0.0",
    contentHash: record.contentHash === "" ? "0".repeat(64) : record.contentHash,
    project: legacyVideo001ProfileReference()
  };
  const generic = validatePackage(candidate);
  const legacy: LegacyVideo001Package = {
    schemaVersion: legacyVideo001SchemaVersion,
    exporterVersion: generic.exporterVersion,
    exportedAt: generic.exportedAt,
    contentHash: record.contentHash as string,
    source: generic.source,
    target: generic.target,
    frames: generic.frames,
    assets: generic.assets
  };
  if (!allowEmptyContentHash || legacy.contentHash !== "") {
    const expected = sha256Hex(encodeUtf8(legacyFingerprintInput(legacy)));
    if (legacy.contentHash !== expected) {
      throw new TypeError("Invalid legacy Video 001 package at $.contentHash: does not match the canonical legacy fingerprint");
    }
  }
  return legacy;
}

/**
 * Validates fields that are available before a streaming reader has retained
 * the asset bytes. The canonical schema-2 fingerprint is checked separately
 * against those files before any verified-asset validation is performed.
 */
export function validateLegacyVideo001StreamingEnvelope(value: unknown): void {
  assertLegacyVideo001Envelope(recordAt(value, "$"), false);
}

function assertLegacyVideo001Envelope(record: UnknownRecord, allowEmptyContentHash: boolean): void {
  exactKeys(record, ["schemaVersion", "exporterVersion", "exportedAt", "contentHash", "source", "target", "frames", "assets"], "$");
  if (record.schemaVersion !== legacyVideo001SchemaVersion) {
    throw new TypeError(`Invalid legacy Video 001 package at $.schemaVersion: expected ${JSON.stringify(legacyVideo001SchemaVersion)}`);
  }
  if (!Array.isArray(record.frames) || record.frames.length > legacyVideo001MaxFrames) {
    throw new TypeError(`Invalid legacy Video 001 package at $.frames: exceeds the ${legacyVideo001MaxFrames}-frame limit`);
  }
  if (typeof record.contentHash !== "string" || (!allowEmptyContentHash && record.contentHash.length === 0)) {
    throw new TypeError("Invalid legacy Video 001 package at $.contentHash: expected a content hash");
  }
}

export function validateLegacyVideo001PackageWithVerifiedAssets(
  value: unknown,
  evidence: ReadonlyArray<{ byteLength: number; hash: string }>,
  byteCounts: { bodyBytes: number; manifestBytes: number },
  canonicalContentHash: string
): LegacyVideo001ExternalPackage {
  const record = recordAt(value, "$");
  assertLegacyVideo001Envelope(record, false);
  if (record.contentHash !== canonicalContentHash) {
    throw new TypeError("Invalid legacy Video 001 package at $.contentHash: does not match the canonical legacy fingerprint");
  }
  const candidate = {
    ...record,
    schemaVersion: "3.0.0",
    project: legacyVideo001ProfileReference(),
    assets: Array.isArray(record.assets) ? record.assets.map((asset) => ({ ...(asset as UnknownRecord), dataBase64: EXTERNAL_ASSET_DATA })) : record.assets
  };
  const validated = validatePackageWithVerifiedAssets(candidate, evidence, byteCounts);
  return {
    schemaVersion: legacyVideo001SchemaVersion,
    exporterVersion: validated.exporterVersion,
    exportedAt: validated.exportedAt,
    contentHash: validated.contentHash,
    source: validated.source,
    target: validated.target,
    frames: validated.frames,
    assets: validated.assets
  };
}

function assertBundledVideo001Profile(installed: InstalledProfile): ProjectProfile {
  const canonicalInstalled = hashProjectProfile(installed.profile);
  const reference = profileReference(canonicalInstalled);
  if (
    installed.profileSha256 !== canonicalInstalled.profileSha256 ||
    reference.projectId !== BUNDLED_VIDEO001_REFERENCE.projectId ||
    reference.profileRevision !== BUNDLED_VIDEO001_REFERENCE.profileRevision ||
    reference.profileSha256 !== BUNDLED_VIDEO001_REFERENCE.profileSha256
  ) {
    throw new TypeError("Legacy Video 001 conversion requires the exact bundled Video 001 profile");
  }
  return canonicalInstalled.profile;
}

function assertLegacyMatchesProfile(legacy: LegacyVideo001Package, profile: ProjectProfile): void {
  const source = recordAt(legacy.source, "$.source");
  const target = recordAt(legacy.target, "$.target");
  if (source.fileKey !== profile.source.fileKey || source.pageId !== profile.source.pageId) {
    throw new TypeError("Legacy Video 001 package source does not match the bundled profile");
  }
  if (
    target.width !== profile.target.width ||
    target.height !== profile.target.height ||
    target.fps !== profile.target.fps ||
    target.timeUnit !== profile.target.timeUnit
  ) {
    throw new TypeError("Legacy Video 001 package target does not match the bundled profile");
  }
}

/** Converts only the historical Video 001 schema-2 package into schema 3. */
export function adaptLegacyVideo001Package(value: unknown, installedVideo001: InstalledProfile): ExporterPackage {
  assertBundledVideo001Profile(installedVideo001);
  const legacy = validateLegacyPackage(value, false);
  assertLegacyMatchesProfile(legacy, installedVideo001.profile);
  return validatePackageAgainstProfile({
    ...legacy,
    schemaVersion: "3.0.0",
    project: profileReference(installedVideo001)
  }, installedVideo001);
}
