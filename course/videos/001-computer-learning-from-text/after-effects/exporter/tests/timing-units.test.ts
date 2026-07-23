import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

test("canonical Video 001 timing declares seconds and embeds that unit in exporter targets", async () => {
  const projectRoot = new URL("../", import.meta.url);
  const timing = JSON.parse(readFileSync(
    fileURLToPath(new URL("config/video001-figma-scenes.json", projectRoot)),
    "utf8"
  )) as {
    canvas: { duration: number; fps: number; timeUnit?: string };
    shots: Array<{ duration: number }>;
  };
  const buildModule = await import(new URL("../scripts/build.mjs", import.meta.url).href) as unknown as {
    validateVideo001Scenes(value: unknown): {
      target: { width: number; height: number; fps: number; timeUnit?: string };
      shots: Array<{ duration: number }>;
    };
  };

  assert.equal(timing.canvas.timeUnit, "seconds");
  assert.equal(timing.canvas.duration, 840);
  assert.equal(timing.shots.reduce((total, shot) => total + shot.duration, 0), 840);

  const embedded = buildModule.validateVideo001Scenes(timing);
  assert.equal(embedded.target.timeUnit, "seconds");
  assert.equal(embedded.shots[31]?.duration, 28);
  assert.equal(embedded.shots[31]!.duration * embedded.target.fps, 840);

  const missingUnit = structuredClone(timing);
  delete missingUnit.canvas.timeUnit;
  assert.throws(
    () => buildModule.validateVideo001Scenes(missingUnit),
    /canvas\.timeUnit.*seconds/i
  );
});
