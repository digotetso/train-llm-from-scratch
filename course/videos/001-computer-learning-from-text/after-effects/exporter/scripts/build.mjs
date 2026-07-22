import { build as esbuild, version as esbuildVersion } from "esbuild";
import { access, mkdir, mkdtemp, readFile, rename, rm, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { generateFigmaManifest, readPluginId } from "./generate-figma-manifest.mjs";

const REQUIRED_ESBUILD_VERSION = "0.28.1";
const EXPECTED_FILE_KEY = "fFTux3sx2AzVQtoya67f95";
const EXPECTED_PAGE_ID = "90:2";
const EXPECTED_PAGE_NAME = "02 Video 001 - AE Assets";
const EXPECTED_SHOT_COUNT = 48;
const DOCUMENTED_EXAMPLE_ID = "1661000000000000000";
const SCRIPT_MARKER = "<!-- FIGMA_PLUGIN_SCRIPT -->";
const rootFromScript = dirname(dirname(fileURLToPath(import.meta.url)));

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
    expectedStart += duration;
    return { index, nodeId, name, duration };
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
  return resolve(projectRoot, "..", "figma-scenes.json");
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

export async function buildPlugin({ projectRoot, outDir, pluginIdFile, environment = process.env } = {}) {
  if (esbuildVersion !== REQUIRED_ESBUILD_VERSION) {
    throw new Error(`Expected esbuild ${REQUIRED_ESBUILD_VERSION}, found ${esbuildVersion}`);
  }
  const root = resolve(projectRoot ?? rootFromScript);
  const destination = resolve(outDir ?? join(root, "dist", "figma"));
  const idFile = resolve(pluginIdFile ?? join(root, ".figma-plugin-id"));

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

  const destinationParent = dirname(destination);
  await mkdir(destinationParent, { recursive: true });
  const temporary = await mkdtemp(join(destinationParent, ".figma-build-"));
  try {
    await writeFile(join(temporary, "code.js"), controllerJavaScript, { encoding: "utf8", mode: 0o600 });
    await writeFile(join(temporary, "ui.html"), uiHtml, { encoding: "utf8", mode: 0o600 });
    await generateFigmaManifest({ root, outDir: temporary, pluginIdFile: idFile });
    await access(join(temporary, "manifest.json"));
    await rm(destination, { recursive: true, force: true });
    await rename(temporary, destination);
  } catch (error) {
    await rm(temporary, { recursive: true, force: true });
    throw error;
  }
  return { destination, scenesPath };
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
    await buildPlugin(parseArguments(process.argv.slice(2)));
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}
