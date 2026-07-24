import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { adaptLegacyVideo001Package, legacyVideo001ProfileReference } from "../src/shared/legacy-video001.ts";
import { validatePackage } from "../src/shared/contract.ts";
import { hashProjectProfile } from "../src/shared/project-profile.ts";
import { makeFixtureProfile } from "./helpers/profile.ts";
import { installedVideo001, makeValidPackage } from "./helpers/package.ts";

function legacyVideo001Package(): Record<string, unknown> {
  const value = makeValidPackage();
  const { project: _project, ...legacy } = value;
  return { ...legacy, schemaVersion: "2.0.0" };
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
  assert.throws(
    () => adaptLegacyVideo001Package(wrongSource, installedVideo001()),
    /source does not match/i
  );
});
