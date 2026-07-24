import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

export function readProfile(relativePath: string): unknown {
  return JSON.parse(readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)), "utf8"));
}

export function makeVideo001Profile(): Record<string, unknown> {
  return structuredClone(readProfile("../../config/profiles/video-001.figma-ae-project.json") as Record<string, unknown>);
}

export function makeFixtureProfile(): Record<string, unknown> {
  return structuredClone(readProfile("../fixtures/profiles/fixture-two.figma-ae-project.json") as Record<string, unknown>);
}

export function reorderKeysDeep(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(reorderKeysDeep);
  if (value !== null && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return Object.fromEntries(Object.keys(record).sort().reverse().map((key) => [key, reorderKeysDeep(record[key])]));
  }
  return value;
}
