import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

interface ImportReportOptions {
  contentHash: string;
  createdCompNames: string[];
  layerCount: number;
  nativeCount: number;
  rasterCount: number;
  missingFonts: string[];
  fallbacks: Array<{ nodeId: string; property: string }>;
  warnings: string[];
  elapsedMs: number;
}

interface Video001ExporterCore {
  nextVersionName(existingNames: string[], baseName: string): string;
  scaleRect(
    rect: { x: number; y: number; width: number; height: number },
    sourceWidth: number,
    sourceHeight: number,
    targetWidth: number,
    targetHeight: number
  ): { x: number; y: number; width: number; height: number };
  sanitizeAeName(name: string): string;
  isDuplicateHash(items: Array<{ comment?: string }>, contentHash: string): boolean;
  makeImportReport(options: ImportReportOptions): ImportReportOptions;
}

function loadCore(): Video001ExporterCore {
  const sourceUrl = new URL("../src/ae/import-core.jsxinc", import.meta.url);
  const source = readFileSync(sourceUrl, "utf8");
  const context: { Video001ExporterCore?: Video001ExporterCore } = {};
  vm.runInNewContext(source, context, { filename: sourceUrl.pathname });
  assert.ok(context.Video001ExporterCore, "core must export one Video001ExporterCore global");
  return context.Video001ExporterCore;
}

function fromVmRealm<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

test("selects the first three-digit version for a new comp", () => {
  const core = loadCore();
  assert.equal(
    core.nextVersionName([], "S001_SH32_Repo_PreparationNotLearning"),
    "S001_SH32_Repo_PreparationNotLearning_v001"
  );
});

test("increments the highest exact three-digit version", () => {
  const core = loadCore();
  assert.equal(
    core.nextVersionName(
      [
        "S001_SH32_Repo_PreparationNotLearning_v001",
        "S001_SH32_Repo_PreparationNotLearning_v009"
      ],
      "S001_SH32_Repo_PreparationNotLearning"
    ),
    "S001_SH32_Repo_PreparationNotLearning_v010"
  );
});

test("ignores partial matches and escapes regex characters in the base name", () => {
  const core = loadCore();
  assert.equal(
    core.nextVersionName(
      [
        "ShotX1_v009",
        "Shot.1_v002_extra",
        "prefix_Shot.1_v007",
        "Shot.1_v003"
      ],
      "Shot.1"
    ),
    "Shot.1_v004"
  );
});

test("refuses to create a version beyond v999", () => {
  const core = loadCore();
  assert.throws(
    () => core.nextVersionName(["Shot_v999"], "Shot"),
    /cannot create version beyond Shot_v999/i
  );
});

test("scales rectangles independently on both axes", () => {
  const core = loadCore();
  assert.deepEqual(
    fromVmRealm(core.scaleRect({ x: 10, y: 20, width: 30, height: 40 }, 1920, 1080, 3840, 2160)),
    { x: 20, y: 40, width: 60, height: 80 }
  );
  assert.deepEqual(
    fromVmRealm(core.scaleRect({ x: 10, y: 20, width: 30, height: 40 }, 100, 200, 200, 100)),
    { x: 20, y: 10, width: 60, height: 20 }
  );
});

test("sanitizes only the final path segment and caps AE names at 120 characters", () => {
  const core = loadCore();
  assert.equal(core.sanitizeAeName("../bad:name"), "bad_name");
  assert.equal(core.sanitizeAeName("folder\\nested/Valid name-v001.aep"), "Valid name-v001.aep");
  assert.equal(core.sanitizeAeName("x".repeat(121)), "x".repeat(120));
});

test("detects only an exact exporter hash comment", () => {
  const core = loadCore();
  const hash = "a".repeat(64);
  assert.equal(core.isDuplicateHash([{ comment: "Video001Export sha256:" + hash }], hash), true);
  assert.equal(core.isDuplicateHash([{ comment: "prefix Video001Export sha256:" + hash }], hash), false);
  assert.equal(core.isDuplicateHash([{ comment: "Video001Export sha256:" + hash + " suffix" }], hash), false);
});

test("creates an isolated import report with the required audit fields", () => {
  const core = loadCore();
  const options: ImportReportOptions = {
    contentHash: "b".repeat(64),
    createdCompNames: ["S001_SH32_Repo_PreparationNotLearning_v001"],
    layerCount: 8,
    nativeCount: 7,
    rasterCount: 1,
    missingFonts: ["Missing Font"],
    fallbacks: [{ nodeId: "95:44", property: "gradient" }],
    warnings: ["θ remains UTF-8"],
    elapsedMs: 125
  };

  const report = core.makeImportReport(options);

  assert.deepEqual(fromVmRealm(report), options);
  assert.notStrictEqual(report, options);
  assert.notStrictEqual(report.createdCompNames, options.createdCompNames);
  assert.notStrictEqual(report.missingFonts, options.missingFonts);
  assert.notStrictEqual(report.fallbacks, options.fallbacks);
  assert.notStrictEqual(report.warnings, options.warnings);
});
