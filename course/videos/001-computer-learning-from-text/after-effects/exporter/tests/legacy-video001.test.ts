import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  adaptLegacyVideo001Package,
  finalizeLegacyVideo001Package,
  legacyVideo001ProfileReference,
  validateLegacyVideo001Package
} from "../src/shared/legacy-video001.ts";
import { validatePackage } from "../src/shared/contract.ts";
import { hashProjectProfile } from "../src/shared/project-profile.ts";
import { makeFixtureProfile } from "./helpers/profile.ts";
import { installedVideo001, makeValidPackage } from "./helpers/package.ts";

function legacyVideo001Package(): Record<string, unknown> {
  const value = makeValidPackage();
  const { project: _project, ...legacy } = value;
  return finalizeLegacyVideo001Package({ ...legacy, schemaVersion: "2.0.0", contentHash: "" }) as unknown as Record<string, unknown>;
}

test("converts an exact Video 001 schema 2 package through the isolated adapter", () => {
  const adapted = adaptLegacyVideo001Package(legacyVideo001Package(), installedVideo001());
  assert.equal(adapted.schemaVersion, "3.0.0");
  assert.deepEqual(validatePackage(adapted), adapted);
  assert.deepEqual(adapted.project, makeValidPackage().project);
});

test("exposes the exact bundled Video 001 reference only from the legacy adapter", () => {
  assert.deepEqual(legacyVideo001ProfileReference(), makeValidPackage().project);
});

test("keeps schema-2 and Video 001 media literals out of the generic contract and controller", () => {
  const contractSource = readFileSync(fileURLToPath(new URL("../src/shared/contract.ts", import.meta.url)), "utf8");
  const controllerSource = readFileSync(fileURLToPath(new URL("../src/figma/controller.ts", import.meta.url)), "utf8");
  const adapterSource = readFileSync(fileURLToPath(new URL("../src/shared/legacy-video001.ts", import.meta.url)), "utf8");
  assert.doesNotMatch(contractSource, /2\.0\.0|video001/i);
  assert.doesNotMatch(controllerSource, /schemaVersion:\s*"2\.0\.0"|application\/vnd\.video001/i);
  assert.match(adapterSource, /2\.0\.0/);
  assert.match(adapterSource, /application\/vnd\.video001/);
});

test("rejects legacy data when the installed profile is not the exact bundled Video 001 profile", () => {
  assert.throws(
    () => adaptLegacyVideo001Package(legacyVideo001Package(), hashProjectProfile(makeFixtureProfile())),
    /exact bundled Video 001 profile/i
  );
});

test("rejects legacy assumptions that do not exactly match Video 001", () => {
  const wrongSource = legacyVideo001Package();
  (wrongSource.source as { fileKey: string }).fileKey = "other-file";
  const restamped = finalizeLegacyVideo001Package({ ...wrongSource, contentHash: "" });
  assert.throws(
    () => adaptLegacyVideo001Package(restamped, installedVideo001()),
    /source does not match/i
  );
});

test("rejects malformed nested legacy fields and a noncanonical legacy content hash at the adapter boundary", () => {
  const nested = legacyVideo001Package();
  (nested.frames as Array<Record<string, unknown>>)[0]!.duration = "wrong";
  assert.throws(() => validateLegacyVideo001Package(nested), /duration.*finite number/i);
  const tampered = legacyVideo001Package();
  tampered.contentHash = "a".repeat(64);
  assert.throws(() => adaptLegacyVideo001Package(tampered, installedVideo001()), /canonical legacy fingerprint/i);
});

test("rejects an altered profile sharing the bundled Video 001 ID and revision", () => {
  const profile = installedVideo001();
  profile.profile = structuredClone(profile.profile);
  profile.profile.target.width = 1280;
  assert.throws(() => adaptLegacyVideo001Package(legacyVideo001Package(), profile), /exact bundled Video 001 profile/i);
});
