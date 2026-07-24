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

test("rejects prohibited declarative bypass values with field-addressable errors", () => {
  const cases: Array<[string, string, (value: Record<string, unknown>) => void]> = [
    ["path", "$.naming.importFolder", (value) => { (value.naming as Record<string, unknown>).importFolder = "relative/path"; }],
    ["URL including mailto", "$.source.pageName", (value) => { (value.source as Record<string, unknown>).pageName = "mailto:someone@example.test"; }],
    ["script source", "$.source.pageName", (value) => { (value.source as Record<string, unknown>).pageName = "const profile = 1;"; }],
    ["command", "$.project.displayName", (value) => { (value.project as Record<string, unknown>).displayName = "curl attacker.example"; }],
    ["port", "$.timeline.shots[0].nodeId", (value) => { fixtureTimeline(value).shots[0]!.nodeId = "host:3000"; }],
    ["credentials", "$.source.fileKey", (value) => { (value.source as Record<string, unknown>).fileKey = "user:secret"; }],
    ["permission change", "$.naming.importFolder", (value) => { (value.naming as Record<string, unknown>).importFolder = "chmod 777"; }]
  ];
  for (const [label, path, mutate] of cases) {
    const value = makeFixtureProfile();
    mutate(value);
    assert.throws(() => validateProjectProfile(value), new RegExp(`${path.replace(/[.$[\]]/g, "\\$&")}: unsafe value`), label);
  }
});

test("accepts current profile values through each field-specific grammar", () => {
  const value = makeFixtureProfile();
  const timeline = fixtureTimeline(value);
  (value.project as Record<string, unknown>).displayName = "Video 001 - What AI Models Actually Do";
  (value.source as Record<string, unknown>).fileKey = "fFTux3sx2AzVQtoya67f95";
  (value.source as Record<string, unknown>).pageId = "90:2";
  (value.source as Record<string, unknown>).pageName = "02 Video 001 - AE Assets";
  (value.naming as Record<string, unknown>).shotPrefix = "S001";
  (value.naming as Record<string, unknown>).masterCompBase = "VIDEO001_MASTER";
  (value.naming as Record<string, unknown>).importFolder = "Video 001";
  timeline.sections[0]!.id = "repository-walkthrough";
  timeline.sections[0]!.name = "Repository Walkthrough";
  for (const shot of timeline.shots) shot.sectionId = "repository-walkthrough";
  timeline.shots[0]!.nodeId = "95:44";
  timeline.shots[0]!.compName = "S001_SH32_Repo_PreparationNotLearning";
  timeline.shots[0]!.sectionParentNodeId = "700:1";
  ((value.fontPolicy as Record<string, unknown>).required as Array<Record<string, unknown>>)[0]!.family = "JetBrains_Mono";
  ((value.fontPolicy as Record<string, unknown>).required as Array<Record<string, unknown>>)[0]!.style = "SemiBold";
  assert.doesNotThrow(() => validateProjectProfile(value));
});

test("accepts normalized Unicode human names and conventional font identities", () => {
  const cases: Array<[string, (value: Record<string, unknown>) => void]> = [
    ["lowercase human name", (value) => { (value.project as Record<string, unknown>).displayName = "my project"; }],
    ["apostrophe", (value) => { (value.source as Record<string, unknown>).pageName = "What's new"; }],
    ["ampersand", (value) => { fixtureTimeline(value).sections[0]!.name = "R&D overview"; }],
    ["diacritics", (value) => { (value.naming as Record<string, unknown>).importFolder = "café overview"; }],
    ["Open Sans", (value) => { ((value.fontPolicy as Record<string, unknown>).required as Array<Record<string, unknown>>)[0]!.family = "Open Sans"; }],
    ["IBM Plex Mono", (value) => { ((value.fontPolicy as Record<string, unknown>).required as Array<Record<string, unknown>>)[0]!.family = "IBM Plex Mono"; }],
    ["Noto Sans CJK", (value) => { ((value.fontPolicy as Record<string, unknown>).required as Array<Record<string, unknown>>)[0]!.family = "Noto Sans CJK"; }],
    ["Semi Bold", (value) => { ((value.fontPolicy as Record<string, unknown>).required as Array<Record<string, unknown>>)[0]!.style = "Semi Bold"; }]
  ];
  for (const [label, mutate] of cases) {
    const value = makeFixtureProfile();
    mutate(value);
    assert.doesNotThrow(() => validateProjectProfile(value), label);
  }
});

test("rejects leading shell and executable command forms in declarative names", () => {
  const cases: Array<[string, (value: Record<string, unknown>) => void]> = [
    ["case-insensitive git status", (value) => { (value.project as Record<string, unknown>).displayName = "GIT status"; }],
    ["ls -la", (value) => { (value.source as Record<string, unknown>).pageName = "ls -la"; }],
    ["echo hello", (value) => { ((value.fontPolicy as Record<string, unknown>).required as Array<Record<string, unknown>>)[0]!.family = "echo hello"; }],
    ["find docs", (value) => { ((value.fontPolicy as Record<string, unknown>).required as Array<Record<string, unknown>>)[0]!.style = "find docs"; }],
    ["umask 077", (value) => { (value.naming as Record<string, unknown>).importFolder = "umask 077"; }],
    ["Python runtime option", (value) => { (value.source as Record<string, unknown>).pageName = "Python -m"; }],
    ["node build", (value) => { (value.project as Record<string, unknown>).displayName = "node build"; }],
    ["bun run", (value) => { (value.project as Record<string, unknown>).displayName = "bun run"; }],
    ["deno task", (value) => { (value.project as Record<string, unknown>).displayName = "deno task"; }],
    ["java Main", (value) => { (value.project as Record<string, unknown>).displayName = "java Main"; }],
    ["python script", (value) => { (value.project as Record<string, unknown>).displayName = "python script"; }],
    ["go test", (value) => { (value.project as Record<string, unknown>).displayName = "go test"; }],
    ["cargo build", (value) => { (value.project as Record<string, unknown>).displayName = "cargo build"; }],
    ["uv run", (value) => { (value.project as Record<string, unknown>).displayName = "uv run"; }],
    ["pip install", (value) => { (value.project as Record<string, unknown>).displayName = "pip install"; }],
    ["npm install", (value) => { (value.project as Record<string, unknown>).displayName = "npm install"; }],
    ["npm install Course", (value) => { (value.project as Record<string, unknown>).displayName = "npm install Course"; }],
    ["python -m Tutorial", (value) => { (value.project as Record<string, unknown>).displayName = "python -m Tutorial"; }],
    ["go test Guide", (value) => { (value.project as Record<string, unknown>).displayName = "go test Guide"; }],
    ["sftp command", (value) => { (value.project as Record<string, unknown>).displayName = "sftp archive"; }],
    ["JavaScript declaration", (value) => { (value.project as Record<string, unknown>).displayName = "const Profile"; }]
  ];
  for (const [label, mutate] of cases) {
    const value = makeFixtureProfile();
    mutate(value);
    assert.throws(() => validateProjectProfile(value), /unsafe value/, label);
  }
});

test("accepts language and runtime names when they are ordinary titles", () => {
  for (const displayName of ["Python Basics", "Node Tutorial", "Java Course"]) {
    const value = makeFixtureProfile();
    (value.project as Record<string, unknown>).displayName = displayName;
    assert.doesNotThrow(() => validateProjectProfile(value), displayName);
  }
});

test("normalizes NFD names to NFC before canonical hashing", () => {
  const nfd = makeFixtureProfile();
  const nfc = makeFixtureProfile();
  (nfd.naming as Record<string, unknown>).importFolder = "cafe\u0301 overview";
  (nfc.naming as Record<string, unknown>).importFolder = "café overview";
  assert.equal(validateProjectProfile(nfd).naming.importFolder, "café overview");
  assert.equal(canonicalProfileJson(nfd), canonicalProfileJson(nfc));
  assert.equal(hashProjectProfile(nfd).profileSha256, hashProjectProfile(nfc).profileSha256);
});

test("normalizes names before enforcing the character limit", () => {
  const nfd = makeFixtureProfile();
  const nfc = makeFixtureProfile();
  const normalizedLimitName = `café${"a".repeat(PROFILE_LIMITS.maxNameCharacters - 4)}`;
  (nfd.naming as Record<string, unknown>).importFolder = `cafe\u0301${"a".repeat(PROFILE_LIMITS.maxNameCharacters - 4)}`;
  (nfc.naming as Record<string, unknown>).importFolder = normalizedLimitName;
  assert.equal(validateProjectProfile(nfd).naming.importFolder, normalizedLimitName);
  assert.equal(canonicalProfileJson(nfd), canonicalProfileJson(nfc));
  assert.equal(hashProjectProfile(nfd).profileSha256, hashProjectProfile(nfc).profileSha256);

  for (const overLimitName of [
    `café${"a".repeat(PROFILE_LIMITS.maxNameCharacters - 3)}`,
    `cafe\u0301${"a".repeat(PROFILE_LIMITS.maxNameCharacters - 3)}`
  ]) {
    const value = makeFixtureProfile();
    (value.naming as Record<string, unknown>).importFolder = overLimitName;
    assert.throws(() => validateProjectProfile(value), /exceeds the 120-character limit/);
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
