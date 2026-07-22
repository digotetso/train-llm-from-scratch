import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const ID_PATTERN = /^[0-9]{10,30}$/;
const DOCUMENTED_EXAMPLE_ID = "1661000000000000000";

export function parsePluginId(raw) {
  if (typeof raw !== "string") throw new TypeError("Figma plugin ID must be text");
  const id = raw.trim();
  if (!ID_PATTERN.test(id)) {
    throw new TypeError(".figma-plugin-id must contain only a 10-30 digit Figma-assigned plugin ID");
  }
  if (id === DOCUMENTED_EXAMPLE_ID) {
    throw new TypeError("The documented example plugin ID is not a Figma-assigned development plugin ID");
  }
  return id;
}

export function figmaManifest(id) {
  return {
    name: "Video 001 → After Effects",
    id,
    api: "1.0.0",
    main: "code.js",
    ui: "ui.html",
    editorType: ["figma"],
    documentAccess: "dynamic-page",
    networkAccess: {
      allowedDomains: ["none"],
      devAllowedDomains: ["http://127.0.0.1:3456"],
      reasoning: "Transfers selected lesson frames to the local After Effects bridge."
    }
  };
}

export async function readPluginId(pluginIdFile) {
  let raw;
  try {
    raw = await readFile(pluginIdFile, "utf8");
  } catch (error) {
    if (error && typeof error === "object" && error.code === "ENOENT") {
      throw new Error(`Missing ${pluginIdFile}. Register the development plugin in Figma first.`);
    }
    throw error;
  }
  return parsePluginId(raw);
}

export async function generateFigmaManifest({ root, outDir, pluginIdFile } = {}) {
  const resolvedRoot = resolve(root ?? process.cwd());
  const resolvedOutDir = resolve(outDir ?? join(resolvedRoot, "dist", "figma"));
  const resolvedPluginIdFile = resolve(pluginIdFile ?? join(resolvedRoot, ".figma-plugin-id"));
  const id = await readPluginId(resolvedPluginIdFile);
  await mkdir(resolvedOutDir, { recursive: true });
  const manifestPath = join(resolvedOutDir, "manifest.json");
  await writeFile(manifestPath, `${JSON.stringify(figmaManifest(id), null, 2)}\n`, {
    encoding: "utf8",
    mode: 0o600
  });
  return { id, manifestPath };
}

function parseArguments(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    const value = argv[index + 1];
    if (value === undefined || value.startsWith("--")) throw new TypeError(`Missing value for ${argument}`);
    if (argument === "--root") options.root = value;
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
    await generateFigmaManifest(parseArguments(process.argv.slice(2)));
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}
