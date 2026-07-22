import assert from "node:assert/strict";
import test from "node:test";
import {
  canonicalJson,
  contentFingerprintInput,
  type ExporterPackage,
  validatePackage
} from "../src/shared/contract.ts";

const valid: ExporterPackage = {
  schemaVersion: "1.0.0",
  exporterVersion: "0.1.0",
  exportedAt: "2026-07-22T00:00:00.000Z",
  contentHash: "a".repeat(64),
  source: { fileKey: "fFTux3sx2AzVQtoya67f95", pageId: "90:2" },
  target: { width: 1920, height: 1080, fps: 30 },
  frames: [{
    nodeId: "95:44",
    name: "S001_SH32_Repo_PreparationNotLearning",
    width: 1920,
    height: 1080,
    duration: 28,
    children: [{
      id: "text-1",
      kind: "text",
      name: "MODEL_Parameters",
      x: 100,
      y: 100,
      width: 300,
      height: 200,
      rotation: 0,
      opacity: 1,
      text: "θ · →",
      textBox: { width: 300, height: 200 },
      paragraph: { align: "LEFT", lineHeightPx: 76, letterSpacingPx: 0 },
      runs: [{ start: 0, end: 5, fontFamily: "Sora", fontStyle: "Bold", fontSize: 64, color: "#F5F7FB" }]
    }],
    warnings: []
  }],
  assets: []
};

test("accepts UTF-8 text without changing paragraph geometry", () => {
  const result = validatePackage(valid);
  const node = result.frames[0]?.children[0];
  assert.ok(node);
  assert.equal(node.kind, "text");
  if (node.kind !== "text") throw new Error("expected text");
  assert.equal(node.text, "θ · →");
  assert.deepEqual(node.textBox, { width: 300, height: 200 });
});

test("rejects an unknown schema major version", () => {
  assert.throws(() => validatePackage({ ...valid, schemaVersion: "2.0.0" }), /schema major/i);
});

test("canonical JSON sorts object keys but preserves array order", () => {
  assert.equal(canonicalJson({ z: 1, a: [3, 2, 1] }), '{"a":[3,2,1],"z":1}');
});

test("content fingerprints ignore export time and the fingerprint field", () => {
  const first = contentFingerprintInput(valid);
  const second = contentFingerprintInput({
    ...valid,
    exportedAt: "2026-07-23T00:00:00.000Z",
    contentHash: "b".repeat(64)
  });
  assert.equal(first, second);
});
