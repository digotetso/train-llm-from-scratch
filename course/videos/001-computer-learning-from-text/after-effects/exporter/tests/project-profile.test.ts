import assert from "node:assert/strict";
import test from "node:test";
import {
  canonicalProfileJson,
  hashProjectProfile,
  profileReference,
  profileSummary,
  publicProfileProjection,
  validateProjectProfile
} from "../src/shared/project-profile.ts";
import { PROFILE_LIMITS } from "../src/shared/limits.ts";
import { makeFixtureProfile, makeVideo001Profile, reorderKeysDeep } from "./helpers/profile.ts";

function fixtureTimeline(value: Record<string, unknown>): { shots: Array<Record<string, unknown>>; sections: Array<Record<string, unknown>> } {
  return (value.timeline as { shots: Array<Record<string, unknown>>; sections: Array<Record<string, unknown>> });
}

test("accepts the declared Video 001 profile without changing fidelity timing", () => {
  const profile = validateProjectProfile(makeVideo001Profile());
  assert.equal(profile.project.id, "video-001");
  assert.equal(profile.timeline.shots.length, 48);
  assert.equal(profile.timeline.shots[31]?.compName, "S001_SH32_Repo_PreparationNotLearning");
  assert.equal(profile.timeline.shots.at(-1)?.start, 834);
  assert.equal(profile.timeline.shots.at(-1)?.duration, 6);
  assert.equal(profile.naming.masterCompBase, "VIDEO001_MASTER");
});

test("accepts the independent second profile fixture", () => {
  const profile = validateProjectProfile(makeFixtureProfile());
  assert.equal(profile.project.id, "fixture-two");
  assert.deepEqual(profile.target, { width: 1280, height: 720, fps: 24, timeUnit: "seconds" });
  assert.equal(profile.timeline.shots.length, 3);
  assert.equal(profile.timeline.shots.reduce((total, shot) => total + shot.duration, 0), 6);
  assert.notEqual(profile.naming.masterCompBase, "VIDEO001_MASTER");
});

test("rejects unknown fields at every profile object boundary", () => {
  const cases: Array<[string, (value: Record<string, unknown>) => void]> = [
    ["profile", (value) => { value.url = "https://invalid.example"; }],
    ["project", (value) => { (value.project as Record<string, unknown>).script = "alert(1)"; }],
    ["shot", (value) => { fixtureTimeline(value).shots[0]!.path = "/tmp/out"; }],
    ["font fallback", (value) => { ((value.fontPolicy as Record<string, unknown>).fallbacks as Array<Record<string, unknown>>)[0]!.command = "open"; }]
  ];
  for (const [label, mutate] of cases) {
    const value = makeFixtureProfile();
    mutate(value);
    assert.throws(() => validateProjectProfile(value), /Invalid project profile at .*unknown field/, label);
  }
});

test("rejects unsafe project identifiers and unsafe profile strings", () => {
  const cases: Array<[string, (value: Record<string, unknown>) => void, RegExp]> = [
    ["unsafe ID", (value) => { (value.project as Record<string, unknown>).id = "../escape"; }, /\$\.project\.id: unsafe project ID/],
    ["URL page name", (value) => { (value.source as Record<string, unknown>).pageName = "https://example.test/page"; }, /\$\.source\.pageName: unsafe value/],
    ["path comp name", (value) => { fixtureTimeline(value).shots[0]!.compName = "../escape"; }, /\$\.timeline\.shots\[0\]\.compName: unsafe value/],
    ["script URL font family", (value) => { ((value.fontPolicy as Record<string, unknown>).required as Array<Record<string, unknown>>)[0]!.family = "javascript:alert(1)"; }, /\$\.fontPolicy\.required\[0\]\.family: unsafe value/],
    ["script source font family", (value) => { ((value.fontPolicy as Record<string, unknown>).required as Array<Record<string, unknown>>)[0]!.family = "function execute() {}"; }, /\$\.fontPolicy\.required\[0\]\.family: unsafe value/]
  ];
  for (const [label, mutate, expected] of cases) {
    const value = makeFixtureProfile();
    mutate(value);
    assert.throws(() => validateProjectProfile(value), expected, label);
  }
});

test("rejects revisions outside positive safe integer bounds", () => {
  for (const revision of [0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1]) {
    const value = makeFixtureProfile();
    (value.project as Record<string, unknown>).revision = revision;
    assert.throws(() => validateProjectProfile(value), /\$\.project\.revision: expected a positive safe integer/, String(revision));
  }
});

test("rejects sections that do not exactly map the ordered shots", () => {
  const value = makeFixtureProfile();
  fixtureTimeline(value).sections[0]!.lastShot = 1;
  assert.throws(() => validateProjectProfile(value), /\$\.timeline\.sections\[0\]\.lastShot: expected contiguous section ranges/);
});

test("rejects duplicate shot node IDs", () => {
  const value = makeFixtureProfile();
  const timeline = fixtureTimeline(value);
  timeline.shots[1]!.nodeId = timeline.shots[0]!.nodeId;
  assert.throws(() => validateProjectProfile(value), /\$\.timeline\.shots\[1\]\.nodeId: duplicate node ID/);
});

test("rejects a timing gap before returning a profile", () => {
  const value = makeFixtureProfile();
  const target = value.target as { fps: number };
  fixtureTimeline(value).shots[1]!.start = 2 + 1 / target.fps;
  assert.throws(
    () => validateProjectProfile(value),
    /Invalid project profile at \$\.timeline\.shots\[1\]\.start: expected continuous timing/
  );
});

test("rejects fractional frame timing", () => {
  const value = makeFixtureProfile();
  fixtureTimeline(value).shots[0]!.duration = 1 / 25;
  assert.throws(() => validateProjectProfile(value), /\$\.timeline\.shots\[0\]\.duration: expected whole-frame timing/);
});

test("rejects limits outside the generic ceilings or below the declared timeline", () => {
  const excessive = makeFixtureProfile();
  (excessive.limits as Record<string, unknown>).maxFrames = PROFILE_LIMITS.maxFrames + 1;
  assert.throws(() => validateProjectProfile(excessive), /\$\.limits\.maxFrames: exceeds the 256-frame limit/);

  const tooSmall = makeFixtureProfile();
  (tooSmall.limits as Record<string, unknown>).maxFrames = 2;
  assert.throws(() => validateProjectProfile(tooSmall), /\$\.limits\.maxFrames: must cover all declared shots/);

  const assets = makeFixtureProfile();
  (assets.limits as Record<string, unknown>).maxAssets = PROFILE_LIMITS.maxAssets + 1;
  assert.throws(() => validateProjectProfile(assets), /\$\.limits\.maxAssets: exceeds the 2048-asset limit/);
});

test("hashes a validated profile canonically and independently of key order", () => {
  const first = makeVideo001Profile();
  const reordered = reorderKeysDeep(first);
  const left = hashProjectProfile(first);
  const right = hashProjectProfile(reordered);
  assert.equal(left.profileSha256, right.profileSha256);
  assert.deepEqual(left.profile, right.profile);
  assert.equal(canonicalProfileJson(first), canonicalProfileJson(reordered));
});

test("returns an intentionally redacted profile summary", () => {
  const installed = hashProjectProfile(makeFixtureProfile());
  assert.deepEqual(profileSummary(installed), {
    projectId: "fixture-two",
    displayName: "Fixture Two",
    revision: 2,
    profileSha256: installed.profileSha256,
    sourcePageName: "Fixture Two Assets",
    target: { width: 1280, height: 720, fps: 24 }
  });
});

test("returns a public projection with a stable reference and no project object", () => {
  const installed = hashProjectProfile(makeFixtureProfile());
  const projection = publicProfileProjection(installed);
  assert.deepEqual(projection.reference, profileReference(installed));
  assert.equal("project" in projection, false);
  assert.deepEqual(projection.source, installed.profile.source);
  assert.deepEqual(projection.timeline, installed.profile.timeline);
  projection.timeline.shots[0]!.compName = "mutated";
  assert.notEqual(installed.profile.timeline.shots[0]!.compName, "mutated");
});
