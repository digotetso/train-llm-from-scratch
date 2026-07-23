import { build as esbuild, version as esbuildVersion } from "esbuild";
import { access, lstat, mkdir, mkdtemp, readFile, rename, rm, writeFile } from "node:fs/promises";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { generateFigmaManifest, readPluginId } from "./generate-figma-manifest.mjs";
import { FIGMA_BRIDGE_ORIGIN } from "../src/shared/figma-network.mjs";

const REQUIRED_ESBUILD_VERSION = "0.28.1";
const EXPECTED_FILE_KEY = "fFTux3sx2AzVQtoya67f95";
const EXPECTED_PAGE_ID = "90:2";
const EXPECTED_PAGE_NAME = "02 Video 001 - AE Assets";
const EXPECTED_SHOT_COUNT = 48;
const EXPECTED_SECTIONS = [
  { firstShot: 1, lastShot: 4, timingName: "Hook", sectionId: "90:5", sectionName: "02 Shots 01-04 — Hook" },
  { firstShot: 5, lastShot: 9, timingName: "Direct Explanation", sectionId: "90:6", sectionName: "03 Shots 05-09 — Direct Explanation" },
  { firstShot: 10, lastShot: 17, timingName: "Technical Meaning", sectionId: "90:7", sectionName: "04 Shots 10-17 — Technical Meaning" },
  { firstShot: 18, lastShot: 25, timingName: "Tiny Example", sectionId: "90:8", sectionName: "05 Shots 18-25 — Tiny Example" },
  { firstShot: 26, lastShot: 32, timingName: "Repository Walkthrough", sectionId: "90:9", sectionName: "06 Shots 26-32 — Repository Walkthrough" },
  { firstShot: 33, lastShot: 39, timingName: "Live Mini-Lab", sectionId: "90:10", sectionName: "07 Shots 33-39 — Live Mini-Lab" },
  { firstShot: 40, lastShot: 43, timingName: "Common Mistake", sectionId: "90:11", sectionName: "08 Shots 40-43 — Common Mistake" },
  { firstShot: 44, lastShot: 48, timingName: "Recap and Exercise", sectionId: "90:12", sectionName: "09 Shots 44-48 — Recap & Exercise" }
];
const DOCUMENTED_EXAMPLE_ID = "1661000000000000000";
const SCRIPT_MARKER = "<!-- FIGMA_PLUGIN_SCRIPT -->";
export const BUILD_OWNERSHIP_MARKER = ".video001-figma-build-owned";
const BUILD_OWNERSHIP_VALUE = "video001-figma-exporter-build-v1\n";
const rootFromScript = dirname(dirname(fileURLToPath(import.meta.url)));

function isWithin(parent, child) {
  const path = relative(parent, child);
  return path === "" || (!isAbsolute(path) && path !== ".." && !path.startsWith(`..${sep}`));
}

export function validateBuildDestination({ projectRoot, outDir }) {
  const root = resolve(projectRoot);
  const destination = resolve(outDir);
  if (isWithin(destination, root)) {
    throw new TypeError("Build output must not be the project root or one of its ancestors");
  }
  const defaultDestination = join(root, "dist", "figma");
  if (isWithin(root, destination) && destination !== defaultDestination) {
    throw new TypeError("Build output inside the project must be exactly dist/figma");
  }
  if (basename(destination) !== "figma" || basename(dirname(destination)) !== "dist") {
    throw new TypeError("Build output must use a dedicated dist/figma directory");
  }
  return destination;
}

async function pathExists(path) {
  try {
    await lstat(path);
    return true;
  } catch (error) {
    if (error !== null && typeof error === "object" && error.code === "ENOENT") return false;
    throw error;
  }
}

async function assertOwnedBuildDirectory(destination) {
  const directory = await lstat(destination);
  if (!directory.isDirectory() || directory.isSymbolicLink()) {
    throw new Error(`Build output ${destination} is not an owned regular directory`);
  }
  const markerPath = join(destination, BUILD_OWNERSHIP_MARKER);
  let marker;
  try {
    marker = await lstat(markerPath);
  } catch (error) {
    if (error !== null && typeof error === "object" && error.code === "ENOENT") {
      throw new Error(`Build output ${destination} has no ownership marker`);
    }
    throw error;
  }
  if (!marker.isFile() || marker.isSymbolicLink()) {
    throw new Error(`Build output ${destination} has an invalid ownership marker`);
  }
  if (await readFile(markerPath, "utf8") !== BUILD_OWNERSHIP_VALUE) {
    throw new Error(`Build output ${destination} has an invalid ownership marker`);
  }
}

function record(value, path) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError(`${path} must be an object`);
  }
  return value;
}

function positiveNumber(value, path) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    throw new TypeError(`${path} must be a positive number`);
  }
  return value;
}

function nonEmptyString(value, path) {
  if (typeof value !== "string" || value.length === 0) throw new TypeError(`${path} must be a non-empty string`);
  return value;
}

export function validateVideo001Scenes(value) {
  const root = record(value, "$timing");
  const source = record(root.source, "$timing.source");
  const canvas = record(root.canvas, "$timing.canvas");
  if (source.figmaFileKey !== EXPECTED_FILE_KEY) throw new TypeError("Timing source has the wrong Video 001 Figma file key");
  if (source.figmaPageNodeId !== EXPECTED_PAGE_ID) throw new TypeError("Timing source has the wrong Video 001 page ID");
  if (source.figmaPageName !== EXPECTED_PAGE_NAME) throw new TypeError("Timing source has the wrong Video 001 page name");
  const target = {
    width: positiveNumber(canvas.width, "$timing.canvas.width"),
    height: positiveNumber(canvas.height, "$timing.canvas.height"),
    fps: positiveNumber(canvas.fps, "$timing.canvas.fps")
  };
  if (target.width !== 1920 || target.height !== 1080 || target.fps !== 30) {
    throw new TypeError("Timing source target must be exactly 1920×1080 at 30 fps");
  }
  if (canvas.duration !== 840) throw new TypeError("Timing source canvas duration must be exactly 840 frames");
  if (!Array.isArray(root.sections) || root.sections.length !== EXPECTED_SECTIONS.length) {
    throw new TypeError(`Timing source must contain exactly ${EXPECTED_SECTIONS.length} approved sections`);
  }
  const sections = root.sections.map((rawSection, index) => {
    const section = record(rawSection, `$timing.sections[${index}]`);
    const expected = EXPECTED_SECTIONS[index];
    if (
      section.name !== expected.timingName ||
      section.firstShot !== expected.firstShot ||
      section.lastShot !== expected.lastShot
    ) {
      throw new TypeError(
        `$timing.sections[${index}] must be ${expected.timingName} for Shots ${expected.firstShot}-${expected.lastShot}`
      );
    }
    return expected;
  });
  if (!Array.isArray(root.shots) || root.shots.length !== EXPECTED_SHOT_COUNT) {
    throw new TypeError(`Timing source must contain exactly ${EXPECTED_SHOT_COUNT} shots`);
  }
  const ids = new Set();
  const names = new Set();
  let expectedStart = 0;
  const shots = root.shots.map((rawShot, position) => {
    const shot = record(rawShot, `$timing.shots[${position}]`);
    const index = shot.index;
    if (!Number.isSafeInteger(index) || index !== position + 1) {
      throw new TypeError(`$timing.shots[${position}].index must be exactly ${position + 1}`);
    }
    const nodeId = nonEmptyString(shot.figmaNodeId, `$timing.shots[${position}].figmaNodeId`);
    if (!/^\d+:\d+$/.test(nodeId) || ids.has(nodeId)) {
      throw new TypeError(`$timing.shots[${position}].figmaNodeId must be a unique Figma node ID`);
    }
    ids.add(nodeId);
    const name = nonEmptyString(shot.name, `$timing.shots[${position}].name`);
    const shotNumber = String(index).padStart(2, "0");
    if (!name.startsWith(`S001_SH${shotNumber}_`) || names.has(name) || /[\u0000-\u001f\u007f/\\]/.test(name)) {
      throw new TypeError(`$timing.shots[${position}].name is not the unique safe name for Shot ${shotNumber}`);
    }
    names.add(name);
    const duration = positiveNumber(shot.duration, `$timing.shots[${position}].duration`);
    if (!Number.isSafeInteger(duration)) throw new TypeError(`$timing.shots[${position}].duration must be whole frames`);
    if (shot.start !== expectedStart) {
      throw new TypeError(`$timing.shots[${position}].start must preserve continuous deterministic timing`);
    }
    const section = sections.find(({ firstShot, lastShot }) => index >= firstShot && index <= lastShot);
    if (section === undefined) throw new TypeError(`Shot ${index} has no approved section mapping`);
    expectedStart += duration;
    return {
      index,
      nodeId,
      name,
      duration,
      sectionId: section.sectionId,
      sectionName: section.sectionName
    };
  });
  if (expectedStart !== 840) throw new TypeError("Shot durations must fill the exact 840-frame canvas");
  const shot32 = shots[31];
  if (
    shot32?.nodeId !== "95:44" ||
    shot32.name !== "S001_SH32_Repo_PreparationNotLearning" ||
    shot32.duration !== 28
  ) {
    throw new TypeError("Shot 32 timing identity must remain 95:44 / S001_SH32_Repo_PreparationNotLearning / 28");
  }
  return {
    source: { fileKey: EXPECTED_FILE_KEY, pageId: EXPECTED_PAGE_ID },
    target,
    shots
  };
}

function timingSourcePath(projectRoot, environment) {
  const override = environment.VIDEO001_FIGMA_SCENES;
  if (override !== undefined) {
    if (!isAbsolute(override)) throw new TypeError("VIDEO001_FIGMA_SCENES must be an absolute path");
    return override;
  }
  return resolve(projectRoot, "config", "video001-figma-scenes.json");
}

function browserBuildOptions(entryPoint) {
  return {
    entryPoints: [entryPoint],
    bundle: true,
    charset: "utf8",
    format: "iife",
    legalComments: "none",
    minify: true,
    platform: "browser",
    sourcemap: false,
    target: ["chrome126"],
    treeShaking: true,
    write: false
  };
}

function singleOutput(result, label) {
  const output = result.outputFiles?.find((file) => file.path.endsWith(".js")) ?? result.outputFiles?.[0];
  if (output === undefined) throw new Error(`esbuild produced no ${label} output`);
  return output.text;
}

function assertBrowserBundle(value, label) {
  const forbidden = [
    "node:fs",
    "node:path",
    "node:crypto",
    "node:http",
    "node:https",
    "node:net",
    "node:tls",
    "node:child_process",
    "require(",
    "process.",
    "child_process",
    "readFileSync",
    "writeFileSync"
  ];
  for (const token of forbidden) {
    if (value.includes(token)) throw new Error(`${label} browser bundle contains forbidden Node capability ${token}`);
  }
  if (/console\.(?:log|debug|info)\s*\(/.test(value)) {
    throw new Error(`${label} browser bundle contains a forbidden data logging call`);
  }
  if (value.includes(DOCUMENTED_EXAMPLE_ID)) throw new Error(`${label} contains the documented fake plugin ID`);
}

function assertExtendScriptBundle(value, label) {
  const prohibitedPatterns = [
    ["let declarations", /\blet\s+[$A-Za-z_]/],
    ["const declarations", /\bconst\s+[$A-Za-z_]/],
    ["arrow functions", /=>/],
    ["classes", /\bclass\s+[$A-Za-z_]/],
    ["template literals", /`/],
    ["optional chaining", /\?\./],
    ["nullish coalescing", /\?\?/],
    ["Node globals", /\b(?:require|module|exports|process|Buffer)\b|(?:^|[^.$A-Za-z0-9_])global\b/m],
    ["Array prototype additions", /Array\.prototype\./]
  ];
  for (const [description, pattern] of prohibitedPatterns) {
    if (pattern.test(value)) throw new Error(`${label} contains forbidden ${description}`);
  }
  for (const destructive of ["app.project.close", "app.project.save", "app.quit"]) {
    if (value.includes(destructive)) throw new Error(`${label} contains prohibited project mutation ${destructive}`);
  }
}

export async function buildBridge({ projectRoot } = {}) {
  const root = resolve(projectRoot ?? rootFromScript);
  const destination = join(root, "dist", "bridge");
  const result = await esbuild({
    entryPoints: [join(root, "src", "bridge", "cli.ts")],
    bundle: true,
    charset: "utf8",
    format: "esm",
    legalComments: "none",
    minify: false,
    outfile: "video001-bridge.mjs",
    platform: "node",
    sourcemap: false,
    target: ["node20"],
    treeShaking: true,
    write: false
  });
  const bridgeJavaScript = singleOutput(result, "bridge");
  await mkdir(destination, { recursive: true });
  await writeFile(join(destination, "video001-bridge.mjs"), bridgeJavaScript, { encoding: "utf8", mode: 0o600 });
  return { destination };
}

export async function buildAfterEffects({ projectRoot, environment = process.env } = {}) {
  const root = resolve(projectRoot ?? rootFromScript);
  const sourceDirectory = join(root, "src", "ae");
  const destination = join(root, "dist", "ae");
  const scenesPath = timingSourcePath(root, environment);
  const sourceNames = ["import-core.jsxinc", "importer.jsxinc", "panel.jsx"];
  const sourceParts = [];
  let timingSource;
  try {
    timingSource = await readFile(scenesPath, "utf8");
    validateVideo001Scenes(JSON.parse(timingSource));
  } catch (error) {
    throw new Error(`Unable to package valid Video 001 timings from ${scenesPath}`, { cause: error });
  }
  for (const sourceName of sourceNames) {
    sourceParts.push(await readFile(join(sourceDirectory, sourceName), "utf8"));
  }
  const panel = `${sourceParts.join("\n\n")}\n`;
  const audit = await readFile(join(sourceDirectory, "audit-export.jsx"), "utf8");
  assertExtendScriptBundle(panel, "After Effects panel");
  assertExtendScriptBundle(audit, "After Effects audit");
  await mkdir(destination, { recursive: true });
  await writeFile(join(destination, "Video001-Figma-AE-Exporter.jsx"), panel, { encoding: "utf8", mode: 0o600 });
  await writeFile(join(destination, "audit-export.jsx"), audit, { encoding: "utf8", mode: 0o600 });
  await writeFile(join(destination, "figma-scenes.json"), timingSource, { encoding: "utf8", mode: 0o600 });
  return { destination, scenesPath };
}

export async function buildPlugin({ projectRoot, outDir, pluginIdFile, environment = process.env } = {}) {
  if (esbuildVersion !== REQUIRED_ESBUILD_VERSION) {
    throw new Error(`Expected esbuild ${REQUIRED_ESBUILD_VERSION}, found ${esbuildVersion}`);
  }
  const root = resolve(projectRoot ?? rootFromScript);
  const destination = validateBuildDestination({
    projectRoot: root,
    outDir: outDir ?? join(root, "dist", "figma")
  });
  const idFile = resolve(pluginIdFile ?? join(root, ".figma-plugin-id"));
  const replacingExistingDestination = await pathExists(destination);
  if (replacingExistingDestination) await assertOwnedBuildDirectory(destination);

  await readPluginId(idFile);
  const scenesPath = timingSourcePath(root, environment);
  let parsedScenes;
  try {
    parsedScenes = JSON.parse(await readFile(scenesPath, "utf8"));
  } catch (error) {
    throw new Error(`Unable to read valid Video 001 timings from ${scenesPath}`, { cause: error });
  }
  const embeddedConfig = validateVideo001Scenes(parsedScenes);
  const templatePath = join(root, "src", "figma", "ui.html");
  const template = await readFile(templatePath, "utf8");
  if (template.split(SCRIPT_MARKER).length !== 2) {
    throw new Error(`UI template must contain exactly one ${SCRIPT_MARKER} marker`);
  }

  const uiResult = await esbuild({
    ...browserBuildOptions(join(root, "src", "figma", "ui.ts")),
    outfile: "ui.js"
  });
  const uiJavaScript = singleOutput(uiResult, "UI");
  assertBrowserBundle(uiJavaScript, "UI");
  if (/crypto\.subtle|globalThis\.crypto|SubtleCrypto/.test(uiJavaScript)) {
    throw new Error("UI bundle contains Web Crypto unavailable in Figma's null-origin iframe");
  }
  const uiHtml = template.replace(SCRIPT_MARKER, `<script>${uiJavaScript.replaceAll("</script", "<\\/script")}</script>`);
  if (/https?:\/\//.test(uiHtml)) throw new Error("UI output contains a remote asset or URL");

  const controllerResult = await esbuild({
    ...browserBuildOptions(join(root, "src", "figma", "controller.ts")),
    define: {
      __VIDEO001_CONFIG__: JSON.stringify(embeddedConfig)
    },
    outfile: "code.js"
  });
  const controllerJavaScript = singleOutput(controllerResult, "controller");
  assertBrowserBundle(controllerJavaScript, "Controller");
  if (/TextEncoder|crypto\.subtle|globalThis\.crypto/.test(controllerJavaScript)) {
    throw new Error("Controller bundle contains browser-only UTF-8 or Web Crypto APIs");
  }
  if (/\.headers\.get\(|\.body(?:\?\.|\.)getReader\(/.test(controllerJavaScript)) {
    throw new Error("Controller bundle contains DOM Response APIs unavailable in the Figma main sandbox");
  }
  if (!controllerJavaScript.includes(FIGMA_BRIDGE_ORIGIN) || controllerJavaScript.includes("http://127.0.0.1:3456")) {
    throw new Error("Controller bundle and Figma manifest development origins do not match");
  }

  const destinationParent = dirname(destination);
  await mkdir(destinationParent, { recursive: true });
  const temporary = await mkdtemp(join(destinationParent, ".figma-build-"));
  const previous = `${temporary}-previous`;
  let previousMoved = false;
  let installed = false;
  try {
    await writeFile(join(temporary, "code.js"), controllerJavaScript, { encoding: "utf8", mode: 0o600 });
    await writeFile(join(temporary, "ui.html"), uiHtml, { encoding: "utf8", mode: 0o600 });
    await generateFigmaManifest({ root, outDir: temporary, pluginIdFile: idFile });
    await access(join(temporary, "manifest.json"));
    await writeFile(join(temporary, BUILD_OWNERSHIP_MARKER), BUILD_OWNERSHIP_VALUE, {
      encoding: "utf8",
      mode: 0o600
    });
    if (replacingExistingDestination) {
      await assertOwnedBuildDirectory(destination);
      await rename(destination, previous);
      previousMoved = true;
    }
    await rename(temporary, destination);
    installed = true;
    if (previousMoved) {
      await assertOwnedBuildDirectory(previous);
      await rm(previous, { recursive: true, force: false });
      previousMoved = false;
    }
  } catch (error) {
    if (!installed) {
      if (previousMoved && !(await pathExists(destination))) {
        await rename(previous, destination);
        previousMoved = false;
      }
      await rm(temporary, { recursive: true, force: true });
    }
    throw error;
  }
  return { destination, scenesPath };
}

export async function buildExporter(options = {}) {
  const plugin = await buildPlugin(options);
  const bridge = await buildBridge(options);
  const afterEffects = await buildAfterEffects(options);
  return { plugin, bridge, afterEffects };
}

function parseArguments(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    const value = argv[index + 1];
    if (value === undefined || value.startsWith("--")) throw new TypeError(`Missing value for ${argument}`);
    if (argument === "--project-root") options.projectRoot = value;
    else if (argument === "--out-dir") options.outDir = value;
    else if (argument === "--plugin-id-file") options.pluginIdFile = value;
    else throw new TypeError(`Unknown argument ${argument}`);
    index += 1;
  }
  return options;
}

const isMain = process.argv[1] !== undefined && fileURLToPath(import.meta.url) === resolve(process.argv[1]);
if (isMain) {
  try {
    await buildExporter(parseArguments(process.argv.slice(2)));
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}
