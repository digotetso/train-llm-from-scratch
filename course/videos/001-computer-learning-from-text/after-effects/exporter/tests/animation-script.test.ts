import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

function extractFunction(source: string, name: string): string {
  const start = source.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} must remain discoverable`);
  const bodyStart = source.indexOf("{", start);
  assert.notEqual(bodyStart, -1);
  let depth = 0;
  for (let index = bodyStart; index < source.length; index += 1) {
    if (source[index] === "{") depth += 1;
    if (source[index] === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(start, index + 1);
    }
  }
  throw new Error(`unterminated function ${name}`);
}

const visualProvenanceUrl = new URL(
  "../../scripts/lib/video001-motion-provenance.jsxinc",
  import.meta.url
);

function makeLeaf(matchName: string, value: unknown) {
  return {
    name: matchName,
    matchName,
    value,
    numKeys: 0,
    numProperties: 0,
    canSetExpression: false,
    expression: "",
  };
}

function makeGroup(matchName: string, children: Array<ReturnType<typeof makeLeaf> | any>) {
  return {
    name: matchName,
    matchName,
    numKeys: 0,
    numProperties: children.length,
    canSetExpression: false,
    expression: "",
    property(value: string | number) {
      if (typeof value === "number") return children[value - 1] ?? null;
      return children.find((child) => child.matchName === value) ?? null;
    },
  };
}

function transformGroup({
  anchor = [50, 10],
  position = [60, 30],
  scale = [100, 100],
  rotation = 0,
  opacity = 100,
} = {}) {
  return makeGroup("ADBE Transform Group", [
    makeLeaf("ADBE Anchor Point", anchor),
    makeLeaf("ADBE Position", position),
    makeLeaf("ADBE Scale", scale),
    makeLeaf("ADBE Rotate Z", rotation),
    makeLeaf("ADBE Opacity", opacity),
  ]);
}

test("animation easing uses AE property-value cardinality for spatial and non-spatial properties", () => {
  const sourceUrl = new URL("../../scripts/animate-full-lesson.jsx", import.meta.url);
  const source = readFileSync(sourceUrl, "utf8");
  const functionSource = extractFunction(source, "easeArrayForProperty");
  const propertyValueType = {
    OneD: "OneD",
    TwoD: "TwoD",
    ThreeD: "ThreeD",
    TwoD_SPATIAL: "TwoD_SPATIAL",
    ThreeD_SPATIAL: "ThreeD_SPATIAL",
  };
  const context = {
    PropertyValueType: propertyValueType,
    KeyframeEase: class {
      constructor(
        readonly speed: number,
        readonly influence: number
      ) {}
    },
    result: undefined as undefined | ((property: { propertyValueType: string }, influence: number) => unknown[]),
  };

  vm.runInNewContext(`${functionSource}\nresult = easeArrayForProperty;`, context);
  assert.ok(context.result);
  const easeArrayForProperty = context.result;
  const expected = new Map([
    [propertyValueType.OneD, 1],
    [propertyValueType.TwoD, 2],
    [propertyValueType.ThreeD, 3],
    [propertyValueType.TwoD_SPATIAL, 1],
    [propertyValueType.ThreeD_SPATIAL, 1],
  ]);
  for (const [valueType, cardinality] of expected) {
    const eases = easeArrayForProperty({ propertyValueType: valueType }, 82);
    assert.equal(eases.length, cardinality, valueType);
    for (const ease of eases as Array<{ speed: number; influence: number }>) {
      assert.equal(ease.speed, 0);
      assert.equal(ease.influence, 82);
    }
  }
});

test("reveal order follows original Figma order and chooses the first semantic hero", () => {
  const sourceUrl = new URL("../../scripts/animate-full-lesson.jsx", import.meta.url);
  const source = readFileSync(sourceUrl, "utf8");
  const functionNames = [
    "isBackgroundLayer",
    "revealPriority",
    "isHeroCandidate",
    "layerArea",
    "collectRevealLayers",
    "selectHero",
  ];
  const context = {
    collect: undefined as undefined | ((comp: unknown) => Array<{ layer: { name: string } }>),
    select: undefined as undefined | ((layers: unknown[]) => { layer: { name: string } } | null),
  };
  vm.runInNewContext(
    functionNames.map((name) => extractFunction(source, name)).join("\n") +
      "\ncollect = collectRevealLayers; select = selectHero;",
    context
  );
  assert.ok(context.collect);
  assert.ok(context.select);
  const collectRevealLayers = context.collect;
  const selectHero = context.select;

  const transform = {};
  const layers = [
    { index: 1, name: "BG_Base", enabled: true, area: 999999 },
    { index: 2, name: "TXT_Detail", enabled: true, area: 100 },
    { index: 3, name: "DATA_Secondary", enabled: true, area: 999999 },
    { index: 4, name: "DATA_Primary", enabled: true, area: 100 },
    { index: 5, name: "TXT_Title", enabled: true, area: 100 },
  ].map((layer) => ({
    ...layer,
    source: null,
    property(name: string) {
      if (name === "ADBE Transform Group") return transform;
      if (name === "ADBE Text Properties") {
        return layer.name.startsWith("TXT_") ? {} : null;
      }
      return null;
    },
    sourceRectAtTime() {
      return { width: layer.area, height: 1 };
    },
  }));
  const comp = {
    numLayers: layers.length,
    layer(index: number) {
      return layers[index - 1];
    },
  };

  const revealLayers = collectRevealLayers(comp);
  assert.equal(
    JSON.stringify(revealLayers.map((entry) => entry.layer.name)),
    JSON.stringify(["TXT_Title", "DATA_Primary", "DATA_Secondary", "TXT_Detail"])
  );
  assert.equal(selectHero(revealLayers)?.layer.name, "DATA_Primary");
});

test("animation audit requires exact unique coverage of every eligible foreground layer", () => {
  const sourceUrl = new URL("../../scripts/audit-animated-full-lesson.jsx", import.meta.url);
  const source = readFileSync(sourceUrl, "utf8");
  const context = {
    requireObject: undefined,
    verify: undefined as undefined | ((comp: unknown, entries: unknown[], expected: unknown[]) => void),
  };
  vm.runInNewContext(
    [
      extractFunction(source, "requireObject"),
      extractFunction(source, "assertExactAnimatedLayerCoverage"),
      "verify = assertExactAnimatedLayerCoverage;",
    ].join("\n"),
    context
  );
  assert.ok(context.verify);
  const verifyCoverage = context.verify;
  const comp = { name: "SHOT" };
  const expected = [
    { layer: { index: 4, name: "TXT_Title" } },
    { layer: { index: 3, name: "DATA_Main" } },
  ];
  const exact = [
    { layerIndex: 4, layerName: "TXT_Title" },
    { layerIndex: 3, layerName: "DATA_Main" },
  ];

  assert.doesNotThrow(() => verifyCoverage(comp, exact, expected));
  assert.throws(
    () => verifyCoverage(comp, exact.slice(0, 1), expected),
    /omits or adds/
  );
  assert.throws(
    () => verifyCoverage(comp, [exact[0], exact[0]], expected),
    /duplicated, omitted, or reordered/
  );
});

test("animation audit rejects unreported keyframes and expressions anywhere on a layer", () => {
  const sourceUrl = new URL("../../scripts/audit-animated-full-lesson.jsx", import.meta.url);
  const source = readFileSync(sourceUrl, "utf8");
  const context = {
    inspect: undefined as undefined | ((group: unknown, allowed: unknown[], label: string) => void),
  };
  vm.runInNewContext(
    [
      extractFunction(source, "propertyIsAllowed"),
      extractFunction(source, "hasNonEmptyExpression"),
      extractFunction(source, "assertNoUnexpectedAnimation"),
      "inspect = assertNoUnexpectedAnimation;",
    ].join("\n"),
    context
  );
  assert.ok(context.inspect);
  const inspectUnexpectedAnimation = context.inspect;
  const keyed = {
    name: "Effect Amount",
    numKeys: 1,
    numProperties: 0,
    canSetExpression: true,
    expressionEnabled: false,
  };
  const expressed = {
    name: "Effect Toggle",
    numKeys: 0,
    numProperties: 0,
    canSetExpression: true,
    expressionEnabled: true,
    expression: "time",
  };
  const disabledExpression = {
    name: "Disabled Expression",
    numKeys: 0,
    numProperties: 0,
    canSetExpression: true,
    expressionEnabled: false,
    expression: "wiggle(1, 1)",
  };
  const group = {
    numProperties: 3,
    property(index: number) {
      if (index === 1) return keyed;
      return index === 2 ? expressed : disabledExpression;
    },
  };

  assert.throws(() => inspectUnexpectedAnimation(group, [], "Layer"), /unexpected keyframes/);
  assert.throws(
    () => inspectUnexpectedAnimation(group, [keyed], "Layer"),
    /expression/
  );
  assert.throws(
    () => inspectUnexpectedAnimation(group, [keyed, expressed], "Layer"),
    /expression/
  );
  assert.throws(
    () => inspectUnexpectedAnimation(group, [keyed, expressed, disabledExpression], "Layer"),
    /expression/
  );
  const disabledOnlyGroup = {
    numProperties: 1,
    property() {
      return disabledExpression;
    },
  };
  assert.throws(
    () => inspectUnexpectedAnimation(disabledOnlyGroup, [disabledExpression], "Layer"),
    /expression/
  );
});

test("animation audit requires the exact saved AEP and rejects dirty in-memory state", () => {
  const sourceUrl = new URL("../../scripts/audit-animated-full-lesson.jsx", import.meta.url);
  const source = readFileSync(sourceUrl, "utf8");
  const context = {
    verify: undefined as undefined | ((project: unknown, expectedPath: string) => void),
  };
  vm.runInNewContext(
    `${extractFunction(source, "assertPersistedProject")}\nverify = assertPersistedProject;`,
    context
  );
  assert.ok(context.verify);
  const verifyPersisted = context.verify;
  const expectedPath = "/deliverables/video-001-figma-exported-animated.aep";

  assert.doesNotThrow(() =>
    verifyPersisted(
      {
        file: { fsName: expectedPath, exists: true, length: 1024, alias: false },
        dirty: false,
      },
      expectedPath
    )
  );
  assert.throws(
    () =>
      verifyPersisted(
        {
          file: { fsName: expectedPath, exists: true, length: 1024, alias: false },
          dirty: true,
        },
        expectedPath
      ),
    /unsaved/
  );
  assert.throws(
    () =>
      verifyPersisted(
        {
          file: { fsName: expectedPath, exists: false, length: 0, alias: false },
          dirty: false,
        },
        expectedPath
      ),
    /persisted/
  );
});

test("source provenance rejects a wrong shot hash or changed exported node content", () => {
  const sourceUrl = new URL("../../scripts/animate-full-lesson.jsx", import.meta.url);
  const source = readFileSync(sourceUrl, "utf8");
  class CompItemMock {}
  class AVLayerMock {}
  const context = {
    CompItem: CompItemMock,
    AVLayer: AVLayerMock,
    canonicalJson: JSON.stringify,
    verify: undefined as undefined | ((
      comp: unknown,
      shot: unknown,
      trustedShot: unknown,
      expectedContentHash: string
    ) => unknown),
  };
  vm.runInNewContext(
    [
      extractFunction(source, "approximately"),
      extractFunction(source, "requireExactContentHash"),
      extractFunction(source, "parseExporterNodeComment"),
      extractFunction(source, "appendUniqueNativeNode"),
      extractFunction(source, "collectSourceProvenance"),
      extractFunction(source, "assertSourceCompMatchesTrusted"),
      "verify = assertSourceCompMatchesTrusted;",
    ].join("\n"),
    context
  );
  assert.ok(context.verify);
  const verifySource = context.verify;
  const hash = "a".repeat(64);
  const nativeLayer = Object.assign(new AVLayerMock(), {
    name: "TXT_Title",
    comment: "Figma native text 94:3",
    source: null,
  });
  const comp = Object.assign(new CompItemMock(), {
    name: "S001_SH01_v001",
    comment: `Video001Export sha256:${hash}`,
    width: 1920,
    height: 1080,
    frameRate: 30,
    duration: 8,
    numLayers: 1,
    layer() {
      return nativeLayer;
    },
  });
  const shot = {
    index: 1,
    nodeId: "94:2",
    name: "S001_SH01",
    duration: 8,
  };
  const trustedShot = {
    index: 1,
    nodeId: "94:2",
    configuredName: "S001_SH01",
    name: "S001_SH01_v001",
    contentHash: hash,
    width: 1920,
    height: 1080,
    fps: 30,
    durationSeconds: 8,
    durationFrames: 240,
    nativeCount: 1,
    nativeNodeIds: ["94:3"],
    rasterCount: 0,
    rasterFallbacks: [],
  };

  assert.doesNotThrow(() => verifySource(comp, shot, trustedShot, hash));
  comp.comment = `Video001Export sha256:${"b".repeat(64)}`;
  assert.throws(
    () => verifySource(comp, shot, trustedShot, hash),
    /content hash/
  );
  comp.comment = `Video001Export sha256:${hash}`;
  nativeLayer.comment = "Figma native text 94:999";
  assert.throws(
    () => verifySource(comp, shot, trustedShot, hash),
    /provenance/
  );
});

test("visual provenance hashes canonical UTF-8 identically to SHA-256", () => {
  const source = readFileSync(visualProvenanceUrl, "utf8");
  const context = {
    hash: undefined as undefined | ((value: string) => string),
  };
  vm.runInNewContext(
    [
      extractFunction(source, "utf8Bytes"),
      extractFunction(source, "rotateRight"),
      extractFunction(source, "paddedHex"),
      extractFunction(source, "sha256Utf8"),
      "hash = sha256Utf8;",
    ].join("\n"),
    context
  );
  assert.ok(context.hash);
  const value = '{"lesson":"θ · cat","emoji":"🐈"}';
  assert.equal(
    context.hash(value),
    createHash("sha256").update(value, "utf8").digest("hex")
  );
});

test("visual provenance rejects changed Source Text and static transforms", () => {
  const source = readFileSync(visualProvenanceUrl, "utf8");
  const interFont = {
    postScriptName: "Inter-Regular",
    styleName: "Regular",
    isSubstitute: false,
    hasGlyphsFor: () => true,
  };
  const context = {
    app: {
      fonts: {
        allFonts: [[interFont]],
        getFontsByPostScriptName(name: string) {
          return name === "Inter-Regular" ? [interFont] : [];
        },
      },
    },
    ParagraphJustification: {
      LEFT_JUSTIFY: "LEFT",
      CENTER_JUSTIFY: "CENTER",
      RIGHT_JUSTIFY: "RIGHT",
    },
    verify: undefined as undefined | ((layer: unknown, node: unknown, motion: unknown) => unknown),
  };
  vm.runInNewContext(
    [
      extractFunction(source, "isArrayValue"),
      extractFunction(source, "approximately"),
      extractFunction(source, "assertNumber"),
      extractFunction(source, "copyArray"),
      extractFunction(source, "assertArray"),
      extractFunction(source, "hexToRgb"),
      extractFunction(source, "clamp"),
      extractFunction(source, "expectedPosition"),
      extractFunction(source, "requireProperty"),
      extractFunction(source, "directPropertiesByMatchName"),
      extractFunction(source, "optionalUniqueProperty"),
      extractFunction(source, "propertyBaseValue"),
      extractFunction(source, "normalizeTextDocument"),
      extractFunction(source, "assertDefaultTextDocumentState"),
      extractFunction(source, "fontCandidates"),
      extractFunction(source, "textFont"),
      extractFunction(source, "fontHasGlyphs"),
      extractFunction(source, "fontObjectHasBoldStyle"),
      extractFunction(source, "resolveExpectedRunFont"),
      extractFunction(source, "assertRunFont"),
      extractFunction(source, "sameColor"),
      extractFunction(source, "validateTextRuns"),
      extractFunction(source, "assertTransformMatchesNode"),
      extractFunction(source, "assertTextMatchesNode"),
      "verify = assertTextMatchesNode;",
    ].join("\n"),
    context
  );
  assert.ok(context.verify);
  const documentValue = {
    text: "cat",
    boxTextSize: [100, 20],
    boxTextPos: [0, 0],
    font: "Inter-Regular",
    fontSize: 20,
    fillColor: [1, 1, 1],
    leading: 24,
    tracking: 0,
    applyFill: true,
    applyStroke: false,
    autoLeading: false,
    fauxBold: false,
    fauxItalic: false,
    allCaps: false,
    smallCaps: false,
    superscript: false,
    subscript: false,
    baselineShift: 0,
    horizontalScale: 100,
    verticalScale: 100,
    tsume: 0,
    noBreak: false,
    autoHyphenate: false,
    hangingRoman: false,
    startIndent: 0,
    endIndent: 0,
    firstLineIndent: 0,
    spaceBefore: 0,
    spaceAfter: 0,
    justification: "LEFT",
  };
  const textProperties = makeGroup("ADBE Text Properties", [
    makeLeaf("ADBE Text Document", documentValue),
    makeGroup("ADBE Text Animators", []),
  ]);
  let transform = transformGroup();
  const layer = {
    name: "TXT_Word",
    property(matchName: string) {
      if (matchName === "ADBE Text Properties") return textProperties;
      if (matchName === "ADBE Transform Group") return transform;
      return null;
    },
  };
  const node = {
    id: "99:5",
    name: "TXT_Word",
    kind: "text",
    x: 10,
    y: 20,
    width: 100,
    height: 20,
    rotation: 0,
    opacity: 1,
    text: "cat",
    textBox: { width: 100, height: 20 },
    paragraph: { align: "LEFT", lineHeightPx: 24, letterSpacingPx: 0 },
    runs: [{
      start: 0,
      end: 3,
      fontFamily: "Inter",
      fontStyle: "Regular",
      fontSize: 20,
      color: "#FFFFFF",
    }],
  };

  assert.doesNotThrow(() => context.verify?.(layer, node, null));
  documentValue.text = "dog";
  assert.throws(() => context.verify?.(layer, node, null), /Source Text/);
  documentValue.text = "cat";
  transform = transformGroup({ position: [61, 30] });
  assert.throws(() => context.verify?.(layer, node, null), /static position/);
  transform = transformGroup();
  documentValue.fauxItalic = true;
  assert.throws(
    () => context.verify?.(layer, node, null),
    /default text style/
  );
});

test("visual provenance rejects a fallback when an intended run font is installed", () => {
  const source = readFileSync(visualProvenanceUrl, "utf8");
  const jetBrains = {
    postScriptName: "JetBrainsMono-Medium",
    styleName: "Medium",
    isSubstitute: false,
    hasGlyphsFor: () => true,
  };
  const inter = {
    postScriptName: "Inter-Regular",
    styleName: "Regular",
    isSubstitute: false,
    hasGlyphsFor: () => true,
  };
  const context = {
    app: {
      fonts: {
        allFonts: [[inter], [jetBrains]],
        getFontsByPostScriptName(name: string) {
          if (name === "JetBrainsMono-Medium") return [jetBrains];
          if (name === "Inter-Regular") return [inter];
          return [];
        },
      },
    },
    verify: undefined as undefined | ((
      value: unknown,
      run: unknown,
      runText: string,
      label: string
    ) => string),
  };
  vm.runInNewContext(
    [
      extractFunction(source, "fontCandidates"),
      extractFunction(source, "textFont"),
      extractFunction(source, "fontHasGlyphs"),
      extractFunction(source, "fontObjectHasBoldStyle"),
      extractFunction(source, "resolveExpectedRunFont"),
      extractFunction(source, "assertRunFont"),
      "verify = assertRunFont;",
    ].join("\n"),
    context
  );
  assert.ok(context.verify);
  const run = {
    fontFamily: "JetBrains Mono",
    fontStyle: "Medium",
  };
  assert.equal(
    context.verify(
      { font: "JetBrainsMono-Medium", fauxBold: false },
      run,
      "cat",
      "run"
    ),
    "JetBrainsMono-Medium"
  );
  assert.throws(
    () =>
      context.verify?.(
        { font: "Inter-Regular", fauxBold: false },
        run,
        "cat",
        "run"
      ),
    /deterministic import/
  );
});

test("visual provenance rejects a removed font-only mixed-run animator", () => {
  const source = readFileSync(visualProvenanceUrl, "utf8");
  const inter = {
    postScriptName: "Inter-Regular",
    styleName: "Regular",
    isSubstitute: false,
    hasGlyphsFor: () => true,
  };
  const jetBrains = {
    postScriptName: "JetBrainsMono-Medium",
    styleName: "Medium",
    isSubstitute: false,
    hasGlyphsFor: () => true,
  };
  const context = {
    app: {
      fonts: {
        allFonts: [[inter], [jetBrains]],
        getFontsByPostScriptName(name: string) {
          if (name === "Inter-Regular") return [inter];
          if (name === "JetBrainsMono-Medium") return [jetBrains];
          return [];
        },
      },
    },
    verify: undefined as undefined | ((...values: unknown[]) => void),
  };
  vm.runInNewContext(
    [
      extractFunction(source, "approximately"),
      extractFunction(source, "hexToRgb"),
      extractFunction(source, "fontCandidates"),
      extractFunction(source, "textFont"),
      extractFunction(source, "fontHasGlyphs"),
      extractFunction(source, "fontObjectHasBoldStyle"),
      extractFunction(source, "resolveExpectedRunFont"),
      extractFunction(source, "assertRunFont"),
      extractFunction(source, "sameColor"),
      extractFunction(source, "requireProperty"),
      extractFunction(source, "validateTextRuns"),
      "verify = validateTextRuns;",
    ].join("\n"),
    context
  );
  assert.ok(context.verify);
  const runs = [
    {
      start: 0,
      end: 1,
      fontFamily: "Inter",
      fontStyle: "Regular",
      fontSize: 20,
      color: "#FFFFFF",
    },
    {
      start: 1,
      end: 2,
      fontFamily: "JetBrains Mono",
      fontStyle: "Medium",
      fontSize: 20,
      color: "#FFFFFF",
    },
  ];
  const documentValue = {
    font: "Inter-Regular",
    fauxBold: false,
    characterRange(start: number) {
      return start === 0
        ? { font: "Inter-Regular", fauxBold: false }
        : { font: "JetBrainsMono-Medium", fauxBold: false };
    },
  };
  const textProperties = makeGroup("ADBE Text Properties", [
    makeGroup("ADBE Text Animators", []),
  ]);
  assert.throws(
    () =>
      context.verify?.(
        textProperties,
        documentValue,
        runs,
        0,
        runs[0],
        "Inter-Regular",
        "ab",
        "TXT_Mixed"
      ),
    /animator count/
  );
});

test("visual provenance rejects changed vector fill and geometry", () => {
  const source = readFileSync(visualProvenanceUrl, "utf8");
  const context = {
    verify: undefined as undefined | ((layer: unknown, node: unknown, motion: unknown) => unknown),
  };
  vm.runInNewContext(
    [
      extractFunction(source, "isArrayValue"),
      extractFunction(source, "approximately"),
      extractFunction(source, "assertNumber"),
      extractFunction(source, "copyArray"),
      extractFunction(source, "assertArray"),
      extractFunction(source, "hexToRgb"),
      extractFunction(source, "clamp"),
      extractFunction(source, "expectedPosition"),
      extractFunction(source, "requireProperty"),
      extractFunction(source, "directPropertiesByMatchName"),
      extractFunction(source, "optionalUniqueProperty"),
      extractFunction(source, "propertyBaseValue"),
      extractFunction(source, "normalizeTextDocument"),
      extractFunction(source, "normalizePropertyValue"),
      extractFunction(source, "propertyTreeFingerprint"),
      extractFunction(source, "assertTransformMatchesNode"),
      extractFunction(source, "assertShapeMatchesNode"),
      "verify = assertShapeMatchesNode;",
    ].join("\n"),
    context
  );
  assert.ok(context.verify);
  const rectSize = makeLeaf("ADBE Vector Rect Size", [100, 20]);
  const rectPosition = makeLeaf("ADBE Vector Rect Position", [0, 0]);
  const rect = makeGroup("ADBE Vector Shape - Rect", [
    rectSize,
    rectPosition,
    makeLeaf("ADBE Vector Rect Roundness", 4),
  ]);
  const fillColor = makeLeaf("ADBE Vector Fill Color", [1, 0, 0]);
  const fill = makeGroup("ADBE Vector Graphic - Fill", [
    fillColor,
    makeLeaf("ADBE Vector Fill Opacity", 100),
  ]);
  const strokeOpacity = makeLeaf("ADBE Vector Stroke Opacity", 100);
  const strokeLineCap = makeLeaf("ADBE Vector Stroke Line Cap", 1);
  const strokeLineJoin = makeLeaf("ADBE Vector Stroke Line Join", 1);
  const strokeMiterLimit = makeLeaf("ADBE Vector Stroke Miter Limit", 4);
  const strokeDashes = makeGroup("ADBE Vector Stroke Dashes", []);
  const stroke = makeGroup("ADBE Vector Graphic - Stroke", [
    makeLeaf("ADBE Vector Stroke Color", [0, 0, 0]),
    makeLeaf("ADBE Vector Stroke Width", 2),
    strokeOpacity,
    strokeLineCap,
    strokeLineJoin,
    strokeMiterLimit,
    strokeDashes,
  ]);
  const contents = makeGroup("ADBE Root Vectors Group", [rect, fill, stroke]);
  const layer = {
    name: "DATA_Box",
    property(matchName: string) {
      if (matchName === "ADBE Root Vectors Group") return contents;
      if (matchName === "ADBE Transform Group") {
        return transformGroup({ anchor: [0, 0] });
      }
      return null;
    },
  };
  const node = {
    id: "99:6",
    name: "DATA_Box",
    kind: "rect",
    x: 10,
    y: 20,
    width: 100,
    height: 20,
    rotation: 0,
    opacity: 1,
    fill: "#FF0000",
    stroke: "#000000",
    strokeWidth: 2,
    radius: 4,
  };

  assert.doesNotThrow(() => context.verify?.(layer, node, null));
  fillColor.value = [0, 1, 0];
  assert.throws(() => context.verify?.(layer, node, null), /vector fill/);
  fillColor.value = [1, 0, 0];
  rectSize.value = [101, 20];
  assert.throws(() => context.verify?.(layer, node, null), /geometry/);
  rectSize.value = [100, 20];
  rectPosition.value = [25, 0];
  assert.throws(
    () => context.verify?.(layer, node, null),
    /internal position/
  );
  rectPosition.value = [0, 0];
  strokeOpacity.value = 50;
  assert.throws(
    () => context.verify?.(layer, node, null),
    /stroke opacity/
  );
  strokeOpacity.value = 100;
  strokeLineJoin.value = 2;
  assert.throws(
    () => context.verify?.(layer, node, null),
    /stroke line join/
  );
  strokeLineJoin.value = 1;
  strokeDashes.numProperties = 1;
  assert.throws(
    () => context.verify?.(layer, node, null),
    /stroke dashes/
  );
});

test("visual provenance rejects changed raster interpretation", () => {
  const source = readFileSync(visualProvenanceUrl, "utf8");
  class CompItemMock {}
  const context = {
    AlphaMode: {
      IGNORE: "IGNORE",
      STRAIGHT: "STRAIGHT",
      PREMULTIPLIED: "PREMULTIPLIED",
    },
    CompItem: CompItemMock,
    sha256File: () => "a".repeat(64),
    verify: undefined as undefined | ((layer: unknown) => unknown),
  };
  vm.runInNewContext(
    [
      extractFunction(source, "approximately"),
      extractFunction(source, "rasterFile"),
      extractFunction(source, "assertRasterInterpretation"),
      extractFunction(source, "sourceIdentity"),
      "verify = sourceIdentity;",
    ].join("\n"),
    context
  );
  assert.ok(context.verify);
  const mainSource = {
    file: { fsName: "/tmp/raster.png" },
    isStill: true,
    hasAlpha: true,
    alphaMode: "STRAIGHT",
    invertAlpha: false,
  };
  const layer = {
    source: {
      name: "raster.png",
      width: 100,
      height: 50,
      pixelAspect: 1,
      mainSource,
    },
  };

  assert.doesNotThrow(() => context.verify?.(layer));
  mainSource.alphaMode = "PREMULTIPLIED";
  assert.throws(
    () => context.verify?.(layer),
    /raster interpretation/i
  );
  mainSource.alphaMode = "STRAIGHT";
  mainSource.invertAlpha = true;
  assert.throws(
    () => context.verify?.(layer),
    /raster interpretation/i
  );
});

test("visual provenance rejects an animated layer rebound to another source item", () => {
  const source = readFileSync(visualProvenanceUrl, "utf8");
  const context = {
    verify: undefined as undefined | ((layer: unknown, sourceLayer: unknown) => void),
  };
  vm.runInNewContext(
    `${extractFunction(source, "assertSameSourceIdentity")}\nverify = assertSameSourceIdentity;`,
    context
  );
  assert.ok(context.verify);
  const trustedSource = {};
  assert.doesNotThrow(() =>
    context.verify?.({ source: trustedSource }, { source: trustedSource })
  );
  assert.throws(
    () => context.verify?.({ source: {} }, { source: trustedSource }),
    /Animated-layer source/
  );
});

test("visual provenance rejects disabled or retimed package layers", () => {
  const source = readFileSync(visualProvenanceUrl, "utf8");
  const context = {
    verify: undefined as undefined | ((layer: unknown, frame: unknown) => void),
  };
  vm.runInNewContext(
    [
      extractFunction(source, "approximately"),
      extractFunction(source, "assertDefaultLayerState"),
      "verify = assertDefaultLayerState;",
    ].join("\n"),
    context
  );
  assert.ok(context.verify);
  const frame = { duration: 8 };
  const layer = {
    name: "TXT_Title",
    enabled: true,
    startTime: 0,
    inPoint: 0,
    outPoint: 8,
    stretch: 100,
    parent: null,
  };
  assert.doesNotThrow(() => context.verify?.(layer, frame));
  layer.enabled = false;
  assert.throws(() => context.verify?.(layer, frame), /disabled/);
  layer.enabled = true;
  layer.outPoint = 7;
  assert.throws(() => context.verify?.(layer, frame), /out point/);
});

test("animation audit validates Bézier interpolation, influence, speed, and AE ease cardinality", () => {
  const sourceUrl = new URL("../../scripts/audit-animated-full-lesson.jsx", import.meta.url);
  const source = readFileSync(sourceUrl, "utf8");
  const propertyValueType = {
    TwoD: "TwoD",
    ThreeD: "ThreeD",
    TwoD_SPATIAL: "TwoD_SPATIAL",
  };
  const interpolation = { BEZIER: "BEZIER", LINEAR: "LINEAR" };
  const context = {
    PropertyValueType: propertyValueType,
    KeyframeInterpolationType: interpolation,
    EASE_INFLUENCE: 82,
    inspect: undefined as undefined | ((property: unknown, label: string) => void),
  };
  vm.runInNewContext(
    [
      extractFunction(source, "approximately"),
      extractFunction(source, "expectedEaseCount"),
      extractFunction(source, "assertBezierEase"),
      "inspect = assertBezierEase;",
    ].join("\n"),
    context
  );
  assert.ok(context.inspect);
  const inspectBezierEase = context.inspect;
  function makeProperty(
    valueType: string,
    cardinality: number,
    interpolationType = interpolation.BEZIER,
    influence = 82
  ) {
    const ease = Array.from(
      { length: cardinality },
      () => ({ speed: 0, influence })
    );
    return {
      propertyValueType: valueType,
      numKeys: 2,
      keyInInterpolationType: () => interpolationType,
      keyOutInterpolationType: () => interpolationType,
      keyInTemporalEase: () => ease,
      keyOutTemporalEase: () => ease,
    };
  }

  assert.doesNotThrow(() =>
    inspectBezierEase(makeProperty(propertyValueType.TwoD_SPATIAL, 1), "Position")
  );
  assert.doesNotThrow(() =>
    inspectBezierEase(makeProperty(propertyValueType.TwoD, 2), "Scale")
  );
  assert.throws(
    () => inspectBezierEase(makeProperty(propertyValueType.TwoD_SPATIAL, 2), "Position"),
    /cardinality/
  );
  assert.throws(
    () => inspectBezierEase(makeProperty(propertyValueType.TwoD, 2, interpolation.LINEAR), "Scale"),
    /Bézier/
  );
  assert.throws(
    () => inspectBezierEase(makeProperty(propertyValueType.TwoD, 2, interpolation.BEZIER, 50), "Scale"),
    /wrong temporal ease/
  );
});

test("animation rollback restores in reverse and never overwrites the input after an incomplete project rollback", () => {
  const sourceUrl = new URL("../../scripts/animate-full-lesson.jsx", import.meta.url);
  const source = readFileSync(sourceUrl, "utf8");

  function makeHarness(failCreatedItem: boolean) {
    const events: string[] = [];
    class FileMock {
      alias = false;
      exists = true;
      constructor(readonly fsName: string) {}
      remove() {
        events.push(`remove-file:${this.fsName}`);
        this.exists = false;
        return true;
      }
    }
    const project = {
      file: new FileMock("/output/source.aep"),
      save(file: FileMock) {
        events.push(`save:${file.fsName}`);
        this.file = file;
      },
    };
    const context = {
      EXPECTED_INPUT_PROJECT: "/private/tmp/Video001-Exporter-Full-Lesson.aep",
      transactionOpen: true,
      File: FileMock,
      app: {
        project,
        endUndoGroup() {
          events.push("end-undo");
        },
      },
      canonicalJson: JSON.stringify,
      sourceSnapshot: () => ({ source: "unchanged" }),
      rollback: undefined as undefined | ((state: unknown) => void),
    };
    vm.runInNewContext(
      [
        extractFunction(source, "restoreRelinkedAssets"),
        extractFunction(source, "removeCreatedItems"),
        extractFunction(source, "removeCreatedOutput"),
        extractFunction(source, "rollbackBuild"),
        "rollback = rollbackBuild;",
      ].join("\n"),
      context
    );
    assert.ok(context.rollback);
    const rollback = context.rollback;

    const makeItem = (name: string, shouldFail = false) => ({
      name,
      remove() {
        events.push(`remove-item:${name}`);
        if (shouldFail) throw new Error(`cannot remove ${name}`);
      },
    });
    const makeFootage = (name: string) => ({
      replace(file: FileMock) {
        events.push(`relink:${name}:${file.fsName}`);
      },
    });
    const makeFolder = (name: string) => ({
      fsName: name,
      alias: false,
      exists: true,
      getFiles: () => [],
      remove() {
        events.push(`remove-folder:${name}`);
        this.exists = false;
        return true;
      },
    });
    const state = {
      createdItems: [
        makeItem("folder"),
        makeItem("shot", failCreatedItem),
        makeItem("master"),
      ],
      relinkedAssets: [
        { item: makeFootage("one"), originalFile: new FileMock("/original/one.png") },
        { item: makeFootage("two"), originalFile: new FileMock("/original/two.png") },
      ],
      createdFiles: [
        new FileMock("/output/asset.png"),
        new FileMock("/output/source.aep"),
      ],
      createdFolders: [
        makeFolder("/output"),
        makeFolder("/output/assets"),
      ],
      sourceMaster: {},
      sourceComps: [],
      sourceSnapshot: { source: "unchanged" },
    };
    return { rollback, events, state };
  }

  const successful = makeHarness(false);
  successful.rollback(successful.state);
  assert.equal(
    JSON.stringify(successful.events),
    JSON.stringify([
      "end-undo",
      "remove-item:master",
      "remove-item:shot",
      "remove-item:folder",
      "relink:two:/original/two.png",
      "relink:one:/original/one.png",
      "save:/private/tmp/Video001-Exporter-Full-Lesson.aep",
      "remove-file:/output/source.aep",
      "remove-file:/output/asset.png",
      "remove-folder:/output/assets",
      "remove-folder:/output",
    ])
  );

  const incomplete = makeHarness(true);
  assert.throws(
    () => incomplete.rollback(incomplete.state),
    /Partial outputs were retained for recovery/
  );
  assert.ok(incomplete.events.includes("relink:two:/original/two.png"));
  assert.equal(
    incomplete.events.some((event) => event.startsWith("save:")),
    false
  );
  assert.equal(
    incomplete.events.some((event) => event.startsWith("remove-file:")),
    false
  );
});

test("direct validation importer refuses saved projects and retains the prior disposable AEP", () => {
  const sourceUrl = new URL(
    "../../scripts/import-full-lesson-validation.jsx",
    import.meta.url
  );
  const source = readFileSync(sourceUrl, "utf8");

  assert.match(
    source,
    /app\.project\.file !== null[\s\S]*app\.project\.numItems !== 0/
  );
  assert.match(
    source,
    /The direct importer refuses every saved or non-empty project/
  );
  assert.match(
    source,
    /Video001-Exporter-Full-Lesson\.pre-refresh-/
  );
  assert.match(
    source,
    /target\.fsName !== EXPECTED_TARGET/
  );
  assert.doesNotMatch(
    source,
    /target\.parent\.fsName !== Folder\.temp\.fsName/
  );
  assert.match(
    source,
    /Video001ExporterImporter\.importPackageFile/
  );
  assert.match(
    source,
    /e00533e4bb05140b2c4b6a8de4635f726722e84c2e33c4a6466b0364a88cb97f/
  );
  assert.match(
    source,
    /Folder\.userData\.fsName \+ "\/Video001FigmaAEExporter"/
  );
  assert.match(
    source,
    /incomingRoot\.fsName \+ "\/" \+[\s\S]*EXPECTED_CONTENT_HASH \+[\s\S]*"\.video001-ae\.json"/
  );
  assert.match(
    source,
    /sha256File\(packageFile\) !== EXPECTED_PACKAGE_SHA256/
  );
  assert.match(
    source,
    /importPackageFile\(\s*queuePackage,/
  );
  assert.match(
    source,
    /removeAfterReport:\s*true/
  );
  assert.match(
    source,
    /result\.report\.createdCompNames\.length !== 48/
  );
  assert.match(
    source,
    /result\.report\.createdMasterCompName !==[\s\S]*"VIDEO001_MASTER_v001"/
  );
  assert.doesNotMatch(
    source,
    /video-001-what-ai-models-actually-do\.aep/
  );
  assert.doesNotMatch(source, /app\.open\s*\(/);
});
