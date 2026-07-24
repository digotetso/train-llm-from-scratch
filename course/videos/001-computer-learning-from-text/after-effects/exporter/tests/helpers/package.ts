import type { ExporterPackage } from "../../src/shared/contract.ts";
import { hashProjectProfile, profileReference, type InstalledProfile } from "../../src/shared/project-profile.ts";
import { makeVideo001Profile } from "./profile.ts";

export function installedVideo001(): InstalledProfile {
  return hashProjectProfile(makeVideo001Profile());
}

const valid: ExporterPackage = {
  schemaVersion: "3.0.0",
  exporterVersion: "0.2.0",
  exportedAt: "2026-07-22T00:00:00.000Z",
  contentHash: "a".repeat(64),
  project: profileReference(installedVideo001()),
  source: { fileKey: "fFTux3sx2AzVQtoya67f95", pageId: "90:2" },
  target: { width: 1920, height: 1080, fps: 30, timeUnit: "seconds" },
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

export function makeValidPackage(): ExporterPackage {
  return structuredClone(valid);
}
