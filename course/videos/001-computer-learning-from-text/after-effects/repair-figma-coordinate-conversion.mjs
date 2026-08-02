import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const manifestPath = path.join(scriptDirectory, "figma-scenes.json");
const builderPath = path.join(scriptDirectory, "build-video-001.jsx");
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));

const translatedRightAlignedX = {
  TXT_Text_100_47: 1319,
  DATA_Text_102_98: 1069,
  MODEL_Text_I102_166_97_64: 1509.44,
  DATA_Text_104_98: 1517,
  DATA_Text_104_102: 1517,
  DATA_Text_104_106: 1517,
  LOSS_Text_I104_188_97_67: 1259,
  PROG_Text_104_219: 1257,
  TXT_Text_105_186: 367,
  DATA_Text_105_190: 1367,
  TXT_Text_105_193: 367,
  DATA_Text_105_197: 1367,
  TXT_Text_105_200: 367,
  DATA_Text_105_204: 1367,
};

for (const shot of manifest.shots) {
  for (const element of shot.elements) {
    if (Object.hasOwn(translatedRightAlignedX, element.name)) {
      element.x = translatedRightAlignedX[element.name];
    }

    if (
      element.kind === "text"
      && element.text.includes("→")
      && element.font.startsWith("Sora:")
    ) {
      element.font = "Inter:Medium";
    }

    if (element.name.startsWith("DATA_IndexLink_")) {
      element.kind = "line";
      element.width = 2;
      element.fill = manifest.palette.fixed;
      element.stroke = null;
      element.strokeWidth = 0;
      element.radius = 0;
    }
  }
}

fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);

const builderSource = fs.readFileSync(builderPath, "utf8");
const embeddedPattern = /(var EMBEDDED_MANIFEST = )\{.*\}(;\n\s*var scriptFile =)/s;
if (!embeddedPattern.test(builderSource)) {
  throw new Error("Could not locate the embedded manifest in build-video-001.jsx");
}
const synchronizedBuilder = builderSource.replace(
  embeddedPattern,
  `$1${JSON.stringify(manifest)}$2`,
);
fs.writeFileSync(builderPath, synchronizedBuilder);
