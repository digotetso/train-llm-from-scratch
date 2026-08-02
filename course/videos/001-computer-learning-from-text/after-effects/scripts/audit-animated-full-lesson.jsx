/*
 * Read-only project audit for the Video 001 animated lesson.
 *
 * The script reads project properties, validates the motion and timing
 * contract, writes an external JSON report, and proves the project state did
 * not change during inspection.
 */

(function () {
    var DELIVERY_CONFIG_PATH =
        "/private/tmp/video001-animation-delivery.json";
    var SOURCE_MASTER_NAME = "VIDEO001_MASTER_v001";
    var ANIMATED_MASTER_NAME = "VIDEO001_ANIMATED_MASTER_v001";
    var ANIMATED_SUFFIX = "_ANIM_v001";
    var ANIMATED_AEP_NAME =
        "video-001-figma-exported-animated.aep";
    var OUTPUT_SUFFIX =
        "/deliverables/video-001-figma-exported-animated";
    var TRUSTED_EVIDENCE_SHA256 =
        "b4f9cc4ff18e6d31b402578e33aac977b66b8e9b12f675740dc3d4ac41a4cdeb";
    var TRUSTED_CONTENT_HASH =
        "da8c7f9d1100e3a415034f8c486a128e6f99bbd66c86caecb65101d63130e831";
    var TRUSTED_PACKAGE_SHA256 =
        "e00533e4bb05140b2c4b6a8de4635f726722e84c2e33c4a6466b0364a88cb97f";
    var MAX_TRAVEL_PX = 24;
    var MAX_OVERSHOOT_PERCENT = 102;
    var MIN_ENTRY_SCALE_PERCENT = 96;
    var EASE_INFLUENCE = 82;
    var TRANSITION_SECONDS = 12 / 30;
    var STAGGER_SECONDS = 0.06;
    var scriptFile = new File($.fileName);
    var afterEffectsRoot = scriptFile.parent.parent;
    var timingFile = new File(
        afterEffectsRoot.fsName +
        "/exporter/config/video001-figma-scenes.json"
    );
    var trustedEvidenceFile = new File(
        afterEffectsRoot.fsName +
        "/exporter/evidence/full-lesson/audit.json"
    );
    var trustedPackageFile = new File(
        afterEffectsRoot.fsName +
        "/exporter/evidence/full-lesson/raw/" +
        "full-lesson-package.video001-ae.json"
    );
    var provenanceLibraryFile = new File(
        scriptFile.parent.fsName +
        "/lib/video001-motion-provenance.jsxinc"
    );
    var deliveryConfigFile = new File(DELIVERY_CONFIG_PATH);

    File.encoding = "UTF-8";

    function readUtf8(file, label) {
        var value;
        file.encoding = "UTF-8";
        if (!file.exists || !file.open("r")) {
            throw new Error("Cannot open " + label);
        }
        try {
            value = file.read();
        } finally {
            file.close();
        }
        return value;
    }

    function requireObject(value, label) {
        if (value === null || typeof value !== "object" || value instanceof Array) {
            throw new Error(label + " must be an object");
        }
        return value;
    }

    function requireArray(value, label) {
        if (!(value instanceof Array)) {
            throw new Error(label + " must be an array");
        }
        return value;
    }

    function requireString(value, label) {
        if (typeof value !== "string" || value.length === 0) {
            throw new Error(label + " must be a non-empty string");
        }
        return value;
    }

    function ownKeyCount(value) {
        var count = 0;
        var key;
        for (key in value) {
            if (value.hasOwnProperty(key)) {
                count += 1;
            }
        }
        return count;
    }

    function assertSafeOutputAncestors(outputRoot, expectedOutputRoot) {
        var cursor = afterEffectsRoot;
        var previous = "";
        var deliverablesFolder = new Folder(
            afterEffectsRoot.fsName + "/deliverables"
        );
        if (
            outputRoot.fsName !== expectedOutputRoot ||
            !outputRoot.exists ||
            outputRoot.alias === true
        ) {
            throw new Error(
                "Animation output root is not the exact safe deliverable"
            );
        }
        while (
            cursor !== null &&
            cursor.fsName !== previous
        ) {
            if (!cursor.exists || cursor.alias === true) {
                throw new Error(
                    "Animation output ancestor is missing or aliased: " +
                    cursor.fsName
                );
            }
            previous = cursor.fsName;
            cursor = cursor.parent;
        }
        if (
            !deliverablesFolder.exists ||
            deliverablesFolder.alias === true
        ) {
            throw new Error(
                "Animation deliverables folder is unavailable or aliased"
            );
        }
    }

    function approximately(left, right) {
        return Math.abs(left - right) <= 0.000001;
    }

    function propertyValue(value) {
        var result = [];
        var index;
        if (value instanceof Array) {
            for (index = 0; index < value.length; index += 1) {
                result[result.length] = value[index];
            }
            return result;
        }
        return value;
    }

    function canonicalJson(value) {
        var keys = [];
        var parts = [];
        var key;
        var index;
        var serialized;
        if (value === null || typeof value !== "object") {
            serialized = JSON.stringify(value);
            if (serialized === undefined) {
                throw new Error("Cannot canonicalize a non-JSON value");
            }
            return serialized;
        }
        if (value instanceof Array) {
            for (index = 0; index < value.length; index += 1) {
                parts[parts.length] = canonicalJson(value[index]);
            }
            return "[" + parts.join(",") + "]";
        }
        for (key in value) {
            if (value.hasOwnProperty(key)) {
                keys[keys.length] = key;
            }
        }
        keys.sort();
        for (index = 0; index < keys.length; index += 1) {
            parts[parts.length] =
                JSON.stringify(keys[index]) + ":" +
                canonicalJson(value[keys[index]]);
        }
        return "{" + parts.join(",") + "}";
    }

    function quoteShellArgument(value) {
        return "'" + String(value).replace(/'/g, "'\\''") + "'";
    }

    function sha256File(file) {
        var output;
        var match;
        if (!file.exists || file.alias === true) {
            throw new Error("Trusted evidence file is unavailable or aliased");
        }
        output = system.callSystem(
            "/usr/bin/shasum -a 256 " +
            quoteShellArgument(file.fsName)
        );
        match = /^([0-9a-f]{64})\b/.exec(String(output));
        if (match === null) {
            throw new Error("Cannot verify trusted evidence SHA-256");
        }
        return match[1];
    }

    function loadTrustedSourceEvidence() {
        var value;
        if (sha256File(trustedEvidenceFile) !== TRUSTED_EVIDENCE_SHA256) {
            throw new Error("Trusted full-lesson evidence SHA-256 is invalid");
        }
        value = requireObject(
            JSON.parse(readUtf8(
                trustedEvidenceFile,
                "trusted full-lesson evidence"
            )),
            "Trusted full-lesson evidence"
        );
        if (
            value.contentHash !== TRUSTED_CONTENT_HASH ||
            value.projectStateUnchanged !== true ||
            requireArray(
                value.shots,
                "Trusted full-lesson evidence shots"
            ).length !== 48
        ) {
            throw new Error("Trusted full-lesson evidence is invalid");
        }
        return value;
    }

    function loadTrustedPackage() {
        var value;
        if (sha256File(trustedPackageFile) !== TRUSTED_PACKAGE_SHA256) {
            throw new Error("Trusted Figma package SHA-256 is invalid");
        }
        value = requireObject(
            JSON.parse(readUtf8(
                trustedPackageFile,
                "trusted Figma package"
            )),
            "Trusted Figma package"
        );
        if (
            value.contentHash !== TRUSTED_CONTENT_HASH ||
            requireArray(value.frames, "Trusted Figma frames").length !== 48
        ) {
            throw new Error("Trusted Figma package is invalid");
        }
        return value;
    }

    function loadProvenanceLibrary() {
        if (
            !provenanceLibraryFile.exists ||
            provenanceLibraryFile.alias === true
        ) {
            throw new Error("Visual provenance library is unavailable");
        }
        $.evalFile(provenanceLibraryFile);
        if (
            typeof Video001MotionProvenance !== "object" ||
            typeof Video001MotionProvenance.assertCompMatchesFrame !==
                "function"
        ) {
            throw new Error("Visual provenance library did not initialize");
        }
        return Video001MotionProvenance;
    }

    function assertPersistedProject(project, expectedPath) {
        if (
            project === null ||
            project.file === null ||
            project.file.fsName !== expectedPath ||
            !project.file.exists ||
            project.file.alias === true ||
            project.file.length <= 0
        ) {
            throw new Error(
                "Animation audit requires the exact persisted AEP"
            );
        }
        if (
            typeof project.dirty !== "boolean" ||
            project.dirty !== false
        ) {
            throw new Error(
                "Animation audit refuses unsaved in-memory project changes"
            );
        }
    }

    function propertyFingerprint(property) {
        var values = [];
        var index;
        if (property === null) {
            return null;
        }
        for (index = 1; index <= property.numKeys; index += 1) {
            values[values.length] = {
                time: property.keyTime(index),
                value: propertyValue(property.keyValue(index))
            };
        }
        return {
            numKeys: property.numKeys,
            value: propertyValue(property.value),
            expressionEnabled: property.canSetExpression
                ? property.expressionEnabled
                : false,
            keys: values
        };
    }

    function layerFingerprint(layer) {
        var transform = layer.property("ADBE Transform Group");
        return {
            index: layer.index,
            name: String(layer.name),
            enabled: layer.enabled,
            locked: layer.locked,
            sourceName: layer.source === null ||
                layer.source === undefined
                ? null
                : String(layer.source.name),
            inPoint: layer.inPoint,
            outPoint: layer.outPoint,
            startTime: layer.startTime,
            opacity: transform === null
                ? null
                : propertyFingerprint(transform.property("ADBE Opacity")),
            position: transform === null
                ? null
                : propertyFingerprint(transform.property("ADBE Position")),
            scale: transform === null
                ? null
                : propertyFingerprint(transform.property("ADBE Scale")),
            rotation: transform === null
                ? null
                : propertyFingerprint(transform.property("ADBE Rotate Z"))
        };
    }

    function compFingerprint(comp) {
        var layers = [];
        var index;
        for (index = 1; index <= comp.numLayers; index += 1) {
            layers[layers.length] = layerFingerprint(comp.layer(index));
        }
        return {
            name: comp.name,
            width: comp.width,
            height: comp.height,
            duration: comp.duration,
            frameRate: comp.frameRate,
            layerCount: comp.numLayers,
            layers: layers
        };
    }

    function projectFingerprint() {
        var items = [];
        var index;
        var item;
        for (index = 1; index <= app.project.numItems; index += 1) {
            item = app.project.item(index);
            items[items.length] = {
                index: index,
                name: String(item.name),
                type: item instanceof CompItem
                    ? "comp"
                    : item instanceof FootageItem
                        ? "footage"
                        : item instanceof FolderItem
                            ? "folder"
                            : "other",
                comp: item instanceof CompItem
                    ? compFingerprint(item)
                    : null
            };
        }
        return {
            itemCount: app.project.numItems,
            items: items
        };
    }

    function findUniqueComp(name) {
        var result = null;
        var count = 0;
        var index;
        var item;
        for (index = 1; index <= app.project.numItems; index += 1) {
            item = app.project.item(index);
            if (item instanceof CompItem && item.name === name) {
                result = item;
                count += 1;
            }
        }
        if (count !== 1) {
            throw new Error("Expected exactly one composition named " + name);
        }
        return result;
    }

    function contentHashFromMaster(master) {
        var match = /^Video001Export sha256:([0-9a-f]{64})$/.exec(
            String(master.comment || "")
        );
        if (match === null) {
            throw new Error(
                "Source master has no validated exporter content hash"
            );
        }
        return match[1];
    }

    function contentHashFromAnimatedMaster(master) {
        var match = /Video001 animated master sha256:([0-9a-f]{64})/.exec(
            String(master.comment || "")
        );
        if (match === null) {
            throw new Error(
                "Animated master has no validated exporter content hash"
            );
        }
        return match[1];
    }

    function requireExactContentHash(item, expectedHash, label) {
        var match = /^Video001Export sha256:([0-9a-f]{64})$/.exec(
            String(item.comment || "")
        );
        if (match === null || match[1] !== expectedHash) {
            throw new Error(label + " content hash is invalid");
        }
        return match[1];
    }

    function parseExporterNodeComment(comment, label) {
        var value = String(comment || "");
        var match = /^Figma native text ([^ ]+)$/.exec(value);
        if (match !== null) {
            return { type: "native", nodeId: match[1] };
        }
        match = /^Figma native vector ([^ ]+) (rect|ellipse)$/.exec(value);
        if (match !== null) {
            return { type: "native", nodeId: match[1] };
        }
        match = /^Figma group precomp ([^ ]+)$/.exec(value);
        if (match !== null) {
            return { type: "group", nodeId: match[1] };
        }
        match = /^Figma raster fallback ([^ ]+) sha256:([0-9a-f]{64})$/.exec(
            value
        );
        if (match !== null) {
            return {
                type: "raster",
                nodeId: match[1],
                assetHash: match[2]
            };
        }
        throw new Error(
            "Source provenance is missing for " + String(label || "")
        );
    }

    function appendUniqueNativeNode(stats, nodeId) {
        var index;
        for (index = 0; index < stats.nativeNodeIds.length; index += 1) {
            if (stats.nativeNodeIds[index] === nodeId) {
                throw new Error(
                    "Source provenance contains duplicate node " + nodeId
                );
            }
        }
        stats.nativeNodeIds[stats.nativeNodeIds.length] = nodeId;
        stats.nativeCount += 1;
    }

    function collectSourceProvenance(comp, stack, stats) {
        var nextStack = [];
        var index;
        var stackIndex;
        var layer;
        var parsed;
        var alreadyVisited;
        for (stackIndex = 0; stackIndex < stack.length; stackIndex += 1) {
            nextStack[nextStack.length] = stack[stackIndex];
        }
        nextStack[nextStack.length] = comp;
        for (index = 1; index <= comp.numLayers; index += 1) {
            layer = comp.layer(index);
            parsed = parseExporterNodeComment(layer.comment, layer.name);
            if (parsed.type === "group") {
                if (
                    !(layer instanceof AVLayer) ||
                    !(layer.source instanceof CompItem)
                ) {
                    throw new Error(
                        "Source provenance group has the wrong source type"
                    );
                }
                appendUniqueNativeNode(stats, parsed.nodeId);
                alreadyVisited = false;
                for (
                    stackIndex = 0;
                    stackIndex < nextStack.length;
                    stackIndex += 1
                ) {
                    if (nextStack[stackIndex] === layer.source) {
                        alreadyVisited = true;
                        break;
                    }
                }
                if (!alreadyVisited) {
                    collectSourceProvenance(
                        layer.source,
                        nextStack,
                        stats
                    );
                }
            } else if (parsed.type === "raster") {
                if (
                    !(layer instanceof AVLayer) ||
                    layer.source instanceof CompItem
                ) {
                    throw new Error(
                        "Source provenance raster has the wrong source type"
                    );
                }
                stats.rasterFallbacks[
                    stats.rasterFallbacks.length
                ] = {
                    nodeId: parsed.nodeId,
                    assetHash: parsed.assetHash
                };
                stats.rasterCount += 1;
            } else {
                appendUniqueNativeNode(stats, parsed.nodeId);
            }
        }
        return stats;
    }

    function assertSourceCompMatchesTrusted(
        comp,
        shot,
        trustedShot,
        expectedContentHash
    ) {
        var shotNodeId = shot.figmaNodeId || shot.nodeId;
        var stats = collectSourceProvenance(comp, [], {
            nativeCount: 0,
            nativeNodeIds: [],
            rasterCount: 0,
            rasterFallbacks: []
        });
        requireExactContentHash(
            comp,
            expectedContentHash,
            "Source shot " + comp.name
        );
        if (
            trustedShot.index !== shot.index ||
            trustedShot.nodeId !== shotNodeId ||
            trustedShot.configuredName !== shot.name ||
            trustedShot.name !== comp.name ||
            trustedShot.contentHash !== expectedContentHash ||
            trustedShot.width !== comp.width ||
            trustedShot.height !== comp.height ||
            trustedShot.fps !== comp.frameRate ||
            !approximately(
                trustedShot.durationSeconds,
                comp.duration
            ) ||
            trustedShot.durationFrames !==
                Math.round(comp.duration * comp.frameRate)
        ) {
            throw new Error(
                "Source shot identity does not match trusted evidence: " +
                comp.name
            );
        }
        if (
            trustedShot.nativeCount !== stats.nativeCount ||
            trustedShot.rasterCount !== stats.rasterCount ||
            canonicalJson(trustedShot.nativeNodeIds) !==
                canonicalJson(stats.nativeNodeIds) ||
            canonicalJson(trustedShot.rasterFallbacks) !==
                canonicalJson(stats.rasterFallbacks)
        ) {
            throw new Error(
                "Source shot provenance does not match trusted evidence: " +
                comp.name
            );
        }
        return stats;
    }

    function sourceSnapshot(master, sourceComps) {
        var shots = [];
        var index;
        for (index = 0; index < sourceComps.length; index += 1) {
            shots[shots.length] = compFingerprint(sourceComps[index]);
        }
        return {
            master: compFingerprint(master),
            shots: shots
        };
    }

    function isBackgroundLayer(layer) {
        var name = String(layer.name).toUpperCase();
        return (
            name.indexOf("ROOT_SOLID_BACKGROUND") >= 0 ||
            name.indexOf("BG_") === 0 ||
            name.indexOf("__BG_") >= 0
        );
    }

    function revealPriority(layer) {
        var name = String(layer.name).toUpperCase();
        if (
            name.indexOf("EYEBROW") >= 0 ||
            name.indexOf("CAPTION") >= 0
        ) {
            return 0;
        }
        if (
            name.indexOf("TITLE") >= 0 ||
            name.indexOf("WORD") >= 0 ||
            name.indexOf("OBJECTIVE") >= 0
        ) {
            return 1;
        }
        if (
            name.indexOf("DECK") >= 0 ||
            name.indexOf("SUBTITLE") >= 0 ||
            name.indexOf("QUESTION") >= 0
        ) {
            return 2;
        }
        if (isHeroCandidate(layer)) {
            return 3;
        }
        return 4;
    }

    function isHeroCandidate(layer) {
        var name = String(layer.name).toUpperCase();
        if (
            layer.property("ADBE Text Properties") !== null ||
            name.indexOf("TXT_") === 0 ||
            name.indexOf("__TXT_") >= 0
        ) {
            return false;
        }
        return (
            name.indexOf("DATA_") >= 0 ||
            name.indexOf("MODEL_") >= 0 ||
            name.indexOf("LOSS_") >= 0 ||
            name.indexOf("PROG_") >= 0 ||
            name.indexOf("CODE_") >= 0 ||
            name.indexOf("FX_") >= 0
        );
    }

    function discoverExpectedRevealLayers(comp) {
        var values = [];
        var index;
        var layer;
        for (index = 1; index <= comp.numLayers; index += 1) {
            layer = comp.layer(index);
            if (
                !isBackgroundLayer(layer) &&
                layer.enabled &&
                layer.property("ADBE Transform Group") !== null
            ) {
                values[values.length] = {
                    layer: layer,
                    priority: revealPriority(layer),
                    index: layer.index
                };
            }
        }
        values.sort(function (left, right) {
            if (left.priority !== right.priority) {
                return left.priority - right.priority;
            }
            return right.index - left.index;
        });
        return values;
    }

    function selectExpectedHero(expected) {
        var index;
        for (index = 0; index < expected.length; index += 1) {
            if (isHeroCandidate(expected[index].layer)) {
                return expected[index].layer;
            }
        }
        return null;
    }

    function assertExactAnimatedLayerCoverage(comp, entries, expected) {
        var seen = {};
        var index;
        var entry;
        var key;
        if (entries.length !== expected.length) {
            throw new Error(
                comp.name + " build report omits or adds animated layers"
            );
        }
        for (index = 0; index < entries.length; index += 1) {
            entry = requireObject(entries[index], "Animated layer entry");
            key = String(entry.layerIndex);
            if (
                seen[key] === true ||
                entry.layerIndex !== expected[index].layer.index ||
                entry.layerName !== String(expected[index].layer.name)
            ) {
                throw new Error(
                    comp.name +
                    " animated layer coverage is duplicated, omitted, or reordered"
                );
            }
            seen[key] = true;
        }
    }

    function propertyIsAllowed(property, allowedProperties) {
        var index;
        for (index = 0; index < allowedProperties.length; index += 1) {
            if (property === allowedProperties[index]) {
                return true;
            }
        }
        return false;
    }

    function hasNonEmptyExpression(property) {
        var expressionValue;
        if (!property.canSetExpression) {
            return false;
        }
        try {
            expressionValue = String(property.expression || "");
        } catch (expressionError) {
            throw new Error(
                "Cannot inspect expression on " +
                String(property.name || property.matchName)
            );
        }
        return expressionValue.length > 0;
    }

    function assertNoUnexpectedAnimation(
        propertyGroup,
        allowedProperties,
        label
    ) {
        var index;
        var property;
        var hasKeys;
        var hasExpression;
        if (
            propertyGroup === null ||
            propertyGroup === undefined ||
            typeof propertyGroup.numProperties !== "number"
        ) {
            return;
        }
        for (
            index = 1;
            index <= propertyGroup.numProperties;
            index += 1
        ) {
            property = propertyGroup.property(index);
            if (property === null || property === undefined) {
                continue;
            }
            hasKeys =
                typeof property.numKeys === "number" &&
                property.numKeys > 0;
            hasExpression =
                hasNonEmptyExpression(property);
            if (hasExpression) {
                throw new Error(
                    label +
                    " contains an expression on " +
                    String(property.name || property.matchName)
                );
            }
            if (
                hasKeys &&
                !propertyIsAllowed(property, allowedProperties)
            ) {
                throw new Error(
                    label +
                    " contains unexpected keyframes or an expression on " +
                    String(property.name || property.matchName)
                );
            }
            assertNoUnexpectedAnimation(
                property,
                allowedProperties,
                label
            );
        }
    }

    function expectedEaseCount(property) {
        if (property.propertyValueType === PropertyValueType.TwoD) {
            return 2;
        }
        if (property.propertyValueType === PropertyValueType.ThreeD) {
            return 3;
        }
        return 1;
    }

    function assertBezierEase(property, label) {
        var keyIndex;
        var easeIndex;
        var inEase;
        var outEase;
        var expectedCount = expectedEaseCount(property);
        for (
            keyIndex = 1;
            keyIndex <= property.numKeys;
            keyIndex += 1
        ) {
            if (
                property.keyInInterpolationType(keyIndex) !==
                    KeyframeInterpolationType.BEZIER ||
                property.keyOutInterpolationType(keyIndex) !==
                    KeyframeInterpolationType.BEZIER
            ) {
                throw new Error(label + " is not Bézier-interpolated");
            }
            inEase = property.keyInTemporalEase(keyIndex);
            outEase = property.keyOutTemporalEase(keyIndex);
            if (
                inEase.length !== expectedCount ||
                outEase.length !== expectedCount
            ) {
                throw new Error(label + " uses invalid temporal-ease cardinality");
            }
            for (easeIndex = 0; easeIndex < expectedCount; easeIndex += 1) {
                if (
                    !approximately(inEase[easeIndex].speed, 0) ||
                    !approximately(outEase[easeIndex].speed, 0) ||
                    !approximately(
                        inEase[easeIndex].influence,
                        EASE_INFLUENCE
                    ) ||
                    !approximately(
                        outEase[easeIndex].influence,
                        EASE_INFLUENCE
                    )
                ) {
                    throw new Error(label + " uses the wrong temporal ease");
                }
            }
        }
    }

    function requireUnexpressed(property, label) {
        if (
            property === null ||
            hasNonEmptyExpression(property)
        ) {
            throw new Error(label + " is missing or expression-driven");
        }
    }

    function vectorDistance(left, right) {
        var sum = 0;
        var index;
        if (!(left instanceof Array) || !(right instanceof Array) || left.length !== right.length) {
            throw new Error("Position values must be same-length arrays");
        }
        for (index = 0; index < left.length; index += 1) {
            sum += Math.pow(left[index] - right[index], 2);
        }
        return Math.sqrt(sum);
    }

    function scaleExtrema(property, baseValue) {
        var minimum = 1000000;
        var maximum = -1000000;
        var keyIndex;
        var dimensionIndex;
        var keyValue;
        var percent;
        for (keyIndex = 1; keyIndex <= property.numKeys; keyIndex += 1) {
            keyValue = property.keyValue(keyIndex);
            for (dimensionIndex = 0; dimensionIndex < keyValue.length; dimensionIndex += 1) {
                if (baseValue[dimensionIndex] === 0) {
                    throw new Error("Scale base component must be nonzero");
                }
                percent = keyValue[dimensionIndex] /
                    baseValue[dimensionIndex] * 100;
                minimum = Math.min(minimum, percent);
                maximum = Math.max(maximum, percent);
            }
        }
        return {
            minimumPercent: minimum,
            maximumPercent: maximum
        };
    }

    function assertBackgroundsStatic(comp) {
        var index;
        var layer;
        var transform;
        var property;
        var propertyNames = [
            "ADBE Opacity",
            "ADBE Position",
            "ADBE Scale",
            "ADBE Rotate Z"
        ];
        var propertyIndex;
        for (index = 1; index <= comp.numLayers; index += 1) {
            layer = comp.layer(index);
            if (!isBackgroundLayer(layer)) {
                continue;
            }
            assertNoUnexpectedAnimation(
                layer,
                [],
                comp.name + " background layer " + layer.name
            );
            transform = layer.property("ADBE Transform Group");
            if (transform === null) {
                continue;
            }
            for (propertyIndex = 0; propertyIndex < propertyNames.length; propertyIndex += 1) {
                property = transform.property(propertyNames[propertyIndex]);
                if (property !== null && property.numKeys !== 0) {
                    throw new Error(comp.name + " background layer is animated");
                }
            }
        }
    }

    function expectedContainsLayer(expected, layer) {
        var index;
        for (index = 0; index < expected.length; index += 1) {
            if (expected[index].layer === layer) {
                return true;
            }
        }
        return false;
    }

    function auditAnimatedShot(comp, shot, report) {
        var entries = requireArray(report.animatedLayers, "Animated layer report");
        var expected = discoverExpectedRevealLayers(comp);
        var expectedHero = selectExpectedHero(expected);
        var index;
        var entry;
        var layer;
        var transform;
        var opacity;
        var property;
        var travel;
        var extrema;
        var scaleCount = 0;
        if (
            comp.width !== 1920 ||
            comp.height !== 1080 ||
            comp.frameRate !== 30 ||
            !approximately(comp.duration, shot.duration) ||
            entries.length === 0
        ) {
            throw new Error(comp.name + " geometry, duration, or animated-layer inventory is invalid");
        }
        assertBackgroundsStatic(comp);
        assertExactAnimatedLayerCoverage(comp, entries, expected);
        for (index = 0; index < entries.length; index += 1) {
            entry = requireObject(entries[index], "Animated layer entry");
            if (
                !approximately(entry.startTime, index * STAGGER_SECONDS) ||
                !approximately(
                    entry.endTime - entry.startTime,
                    TRANSITION_SECONDS
                )
            ) {
                throw new Error(comp.name + " entry timing violates 12f/60ms motion");
            }
            layer = comp.layer(entry.layerIndex);
            if (layer.name !== entry.layerName || isBackgroundLayer(layer)) {
                throw new Error(comp.name + " animated layer identity is invalid");
            }
            transform = layer.property("ADBE Transform Group");
            opacity = transform.property("ADBE Opacity");
            requireUnexpressed(opacity, layer.name + " opacity");
            if (
                opacity.numKeys !== 2 ||
                !approximately(opacity.keyTime(1), entry.startTime) ||
                !approximately(opacity.keyTime(2), entry.endTime) ||
                !approximately(opacity.keyValue(1), 0) ||
                !approximately(opacity.keyValue(2), entry.opacityBase)
            ) {
                throw new Error(layer.name + " opacity entry is invalid");
            }
            assertBezierEase(opacity, layer.name + " opacity");
            if (
                (
                    expectedHero !== null &&
                    layer === expectedHero &&
                    entry.mode !== "scale"
                ) ||
                (
                    layer !== expectedHero &&
                    entry.mode === "scale"
                )
            ) {
                throw new Error(
                    layer.name + " does not match the deterministic hero mode"
                );
            }
            if (entry.mode === "position") {
                if (entry.position.separated) {
                    property = transform.property("ADBE Position_1");
                    requireUnexpressed(property, layer.name + " Y position");
                } else {
                    property = transform.property("ADBE Position");
                    requireUnexpressed(property, layer.name + " position");
                }
                if (
                    property.numKeys !== 2
                ) {
                    throw new Error(layer.name + " position entry key count is invalid");
                }
                if (entry.position.separated) {
                    travel = Math.abs(
                        property.keyValue(1) - property.keyValue(2)
                    );
                } else {
                    travel = vectorDistance(
                        property.keyValue(1),
                        property.keyValue(2)
                    );
                }
                if (
                    !approximately(property.keyTime(1), entry.startTime) ||
                    !approximately(property.keyTime(2), entry.endTime) ||
                    travel > MAX_TRAVEL_PX + 0.000001 ||
                    (
                        entry.position.separated &&
                        !approximately(
                            property.keyValue(2),
                            entry.position.base
                        )
                    ) ||
                    (
                        !entry.position.separated &&
                        canonicalJson(property.keyValue(2)) !==
                        canonicalJson(entry.position.base)
                    )
                ) {
                    throw new Error(layer.name + " position entry exceeds maxTravelPx");
                }
                assertBezierEase(property, layer.name + " position");
                assertNoUnexpectedAnimation(
                    layer,
                    [opacity, property],
                    comp.name + " layer " + layer.name
                );
            } else if (entry.mode === "scale") {
                scaleCount += 1;
                property = transform.property("ADBE Scale");
                requireUnexpressed(property, layer.name + " scale");
                extrema = scaleExtrema(property, entry.scale.base);
                if (
                    property.numKeys !== 3 ||
                    !approximately(property.keyTime(1), entry.startTime) ||
                    !approximately(
                        property.keyTime(2),
                        entry.scale.overshootTime
                    ) ||
                    !approximately(property.keyTime(3), entry.endTime) ||
                    canonicalJson(property.keyValue(1)) !==
                        canonicalJson(entry.scale.start) ||
                    canonicalJson(property.keyValue(2)) !==
                        canonicalJson(entry.scale.overshoot) ||
                    canonicalJson(property.keyValue(3)) !==
                        canonicalJson(entry.scale.base) ||
                    extrema.minimumPercent < MIN_ENTRY_SCALE_PERCENT - 0.000001 ||
                    extrema.maximumPercent > MAX_OVERSHOOT_PERCENT + 0.000001
                ) {
                    throw new Error(layer.name + " scale entry exceeds maxOvershootPercent or entry minimum");
                }
                assertBezierEase(property, layer.name + " scale");
                assertNoUnexpectedAnimation(
                    layer,
                    [opacity, property],
                    comp.name + " layer " + layer.name
                );
            } else {
                throw new Error(layer.name + " uses an unknown animation mode");
            }
        }
        if (
            scaleCount !==
            (expectedHero === null ? 0 : 1)
        ) {
            throw new Error(
                comp.name + " contains the wrong hero scale entry count"
            );
        }
        for (index = 1; index <= comp.numLayers; index += 1) {
            layer = comp.layer(index);
            if (!expectedContainsLayer(expected, layer)) {
                assertNoUnexpectedAnimation(
                    layer,
                    [],
                    comp.name + " static layer " + layer.name
                );
            }
        }
        return {
            name: comp.name,
            durationSeconds: comp.duration,
            durationFrames: Math.round(comp.duration * comp.frameRate),
            animatedLayerCount: entries.length,
            heroScaleCount: scaleCount
        };
    }

    function assertNoMissingFootageOrV002() {
        var index;
        var item;
        var sourceFile;
        for (index = 1; index <= app.project.numItems; index += 1) {
            item = app.project.item(index);
            if (/_v002$/.test(String(item.name))) {
                throw new Error("Unexpected _v002 project item " + item.name);
            }
            if (item instanceof FootageItem) {
                try {
                    sourceFile = item.mainSource.file;
                } catch (sourceError) {
                    sourceFile = null;
                }
                if (
                    sourceFile !== null &&
                    sourceFile !== undefined &&
                    !sourceFile.exists
                ) {
                    throw new Error("Missing linked footage " + item.name);
                }
            }
        }
    }

    function writeAuditOnce(file, value) {
        var temporary;
        var suffix;
        if (
            file.parent.alias === true ||
            file.alias === true ||
            file.exists
        ) {
            throw new Error("Animation audit output must be a new non-alias file");
        }
        suffix = String(new Date().getTime()) + "-" +
            String(Math.floor(Math.random() * 1000000000));
        temporary = new File(
            file.parent.fsName + "/." + file.name + "." + suffix + ".tmp"
        );
        if (temporary.exists || temporary.alias === true) {
            throw new Error("Cannot reserve animation audit temporary file");
        }
        temporary.encoding = "UTF-8";
        if (!temporary.open("w")) {
            throw new Error("Cannot open animation audit temporary file");
        }
        try {
            if (!temporary.write(JSON.stringify(value, null, 2) + "\n")) {
                throw new Error("Cannot complete animation audit temporary file");
            }
        } finally {
            temporary.close();
        }
        if (file.exists || file.alias === true || !temporary.rename(file.name)) {
            throw new Error("Cannot publish animation audit evidence");
        }
    }

    function main() {
        var projectBefore;
        var projectAfter;
        var deliveryConfig;
        var outputRoot;
        var expectedOutputRoot;
        var expectedProjectFile;
        var evidenceFolder;
        var buildReportFile;
        var buildReport;
        var trustedEvidence;
        var trustedPackage;
        var visualProvenance;
        var timing;
        var sourceMaster;
        var animatedMaster;
        var sourceComps = [];
        var animatedComps = [];
        var shotAudits = [];
        var sourceVisualSnapshot;
        var animatedVisualSnapshot;
        var sourceVisualHash;
        var currentSourceSnapshot;
        var index;
        var shot;
        var masterLayer;
        var auditFile;
        var result;

        if (app.project === null || app.project.file === null) {
            throw new Error("No saved After Effects project is open");
        }
        deliveryConfig = requireObject(
            JSON.parse(readUtf8(deliveryConfigFile, "animation delivery config")),
            "Animation delivery config"
        );
        if (ownKeyCount(deliveryConfig) !== 1) {
            throw new Error(
                "Animation delivery config must contain only outputRoot"
            );
        }
        expectedOutputRoot =
            afterEffectsRoot.fsName + OUTPUT_SUFFIX;
        outputRoot = new Folder(
            requireString(
                deliveryConfig.outputRoot,
                "Animation output root"
            )
        );
        assertSafeOutputAncestors(outputRoot, expectedOutputRoot);
        expectedProjectFile =
            outputRoot.fsName + "/" + ANIMATED_AEP_NAME;
        if (app.project.file.fsName !== expectedProjectFile) {
            throw new Error("Refusing to audit an unexpected After Effects project");
        }
        assertPersistedProject(app.project, expectedProjectFile);
        evidenceFolder = new Folder(outputRoot.fsName + "/evidence");
        if (!evidenceFolder.exists || evidenceFolder.alias === true) {
            throw new Error("Animation evidence folder is unavailable or aliased");
        }
        buildReportFile = new File(
            evidenceFolder.fsName + "/animation-build-report.json"
        );
        buildReport = requireObject(
            JSON.parse(readUtf8(buildReportFile, "animation build report")),
            "Animation build report"
        );
        timing = requireObject(
            JSON.parse(readUtf8(timingFile, "canonical timing")),
            "Canonical timing"
        );
        trustedEvidence = loadTrustedSourceEvidence();
        trustedPackage = loadTrustedPackage();
        visualProvenance = loadProvenanceLibrary();
        if (
            requireArray(timing.shots, "Canonical shots").length !== 48 ||
            buildReport.status !== "PASS" ||
            buildReport.sourceMasterUnchanged !== true ||
            buildReport.contentHash !== TRUSTED_CONTENT_HASH ||
            buildReport.trustedEvidenceSha256 !==
                TRUSTED_EVIDENCE_SHA256 ||
            buildReport.trustedPackageSha256 !==
                TRUSTED_PACKAGE_SHA256 ||
            buildReport.sourceAep !==
                "video-001-figma-exported-source-import.aep" ||
            buildReport.animatedAep !== ANIMATED_AEP_NAME ||
            requireArray(buildReport.shots, "Build report shots").length !==
                48
        ) {
            throw new Error("Animation build report or canonical timing is invalid");
        }

        projectBefore = projectFingerprint();
        sourceMaster = findUniqueComp(SOURCE_MASTER_NAME);
        animatedMaster = findUniqueComp(ANIMATED_MASTER_NAME);
        if (
            contentHashFromMaster(sourceMaster) !== buildReport.contentHash ||
            contentHashFromAnimatedMaster(animatedMaster) !==
                buildReport.contentHash
        ) {
            throw new Error(
                "Animation build report content hash does not match the project"
            );
        }
        if (
            animatedMaster.width !== 1920 ||
            animatedMaster.height !== 1080 ||
            animatedMaster.frameRate !== 30 ||
            !approximately(animatedMaster.duration, 840) ||
            Math.round(animatedMaster.duration * animatedMaster.frameRate) !== 25200 ||
            animatedMaster.numLayers !== 48
        ) {
            throw new Error("Animated master is not 1920x1080, 30 fps, 840 seconds / 25200 frames");
        }

        for (index = 0; index < timing.shots.length; index += 1) {
            shot = timing.shots[index];
            if (
                buildReport.shots[index].index !== shot.index ||
                buildReport.shots[index].sourceComp !==
                    shot.name + "_v001" ||
                buildReport.shots[index].animatedComp !==
                    shot.name + ANIMATED_SUFFIX ||
                !approximately(
                    buildReport.shots[index].start,
                    shot.start
                ) ||
                !approximately(
                    buildReport.shots[index].duration,
                    shot.duration
                )
            ) {
                throw new Error(
                    "Animation build report shot identity is invalid at " +
                    String(index + 1)
                );
            }
            sourceComps[sourceComps.length] =
                findUniqueComp(shot.name + "_v001");
            if (
                buildReport.shots[index].sourceContentHash !==
                    TRUSTED_CONTENT_HASH ||
                canonicalJson(
                    assertSourceCompMatchesTrusted(
                        sourceComps[index],
                        shot,
                        trustedEvidence.shots[index],
                        TRUSTED_CONTENT_HASH
                    )
                ) !==
                    canonicalJson(
                        buildReport.shots[index].sourceProvenance
                    )
            ) {
                throw new Error(
                    "Source shot provenance report is invalid at " +
                    String(index + 1)
                );
            }
            animatedComps[animatedComps.length] =
                findUniqueComp(shot.name + ANIMATED_SUFFIX);
            sourceVisualSnapshot =
                visualProvenance.assertCompMatchesFrame(
                    sourceComps[index],
                    trustedPackage.frames[index],
                    trustedPackage,
                    null,
                    null
                );
            sourceVisualHash = visualProvenance.sha256Utf8(
                visualProvenance.canonicalJson(
                    sourceVisualSnapshot
                )
            );
            if (
                buildReport.shots[index].sourceVisualSha256 !==
                    sourceVisualHash
            ) {
                throw new Error(
                    "Source visual fingerprint is invalid at shot " +
                    String(index + 1)
                );
            }
            animatedVisualSnapshot =
                visualProvenance.assertCompMatchesFrame(
                    animatedComps[index],
                    trustedPackage.frames[index],
                    trustedPackage,
                    buildReport.shots[index],
                    sourceComps[index]
                );
            if (
                visualProvenance.canonicalJson(
                    animatedVisualSnapshot
                ) !==
                visualProvenance.canonicalJson(
                    sourceVisualSnapshot
                )
            ) {
                throw new Error(
                    "Animated shot static visual content differs from " +
                    "its source at shot " + String(index + 1)
                );
            }
            masterLayer = animatedMaster.layer(index + 1);
            if (
                masterLayer.source !== animatedComps[index] ||
                masterLayer.name !== animatedComps[index].name ||
                !approximately(masterLayer.startTime, shot.start) ||
                !approximately(masterLayer.inPoint, shot.start) ||
                !approximately(masterLayer.outPoint, shot.start + shot.duration)
            ) {
                throw new Error("Animated master contains a timing gap, overlap, or wrong source at shot " + String(index + 1));
            }
            shotAudits[shotAudits.length] = auditAnimatedShot(
                animatedComps[index],
                shot,
                buildReport.shots[index]
            );
        }

        currentSourceSnapshot = sourceSnapshot(sourceMaster, sourceComps);
        if (
            canonicalJson(currentSourceSnapshot) !==
            canonicalJson(buildReport.sourceSnapshot)
        ) {
            throw new Error("sourceMasterUnchanged check failed");
        }
        assertNoMissingFootageOrV002();
        projectAfter = projectFingerprint();
        if (canonicalJson(projectBefore) !== canonicalJson(projectAfter)) {
            throw new Error("Audit changed After Effects project state");
        }
        assertPersistedProject(app.project, expectedProjectFile);

        result = {
            auditSchemaVersion: 1,
            status: "PASS",
            generator: "After Effects " + String(app.version),
            contentHash: buildReport.contentHash,
            projectStateUnchanged: true,
            sourceMasterUnchanged: true,
            master: {
                name: animatedMaster.name,
                width: animatedMaster.width,
                height: animatedMaster.height,
                frameRate: animatedMaster.frameRate,
                durationSeconds: animatedMaster.duration,
                durationFrames: 25200,
                layerCount: animatedMaster.numLayers
            },
            motionLimits: {
                transitionFrames: 12,
                staggerSeconds: STAGGER_SECONDS,
                maxTravelPx: MAX_TRAVEL_PX,
                entryScalePercent: MIN_ENTRY_SCALE_PERCENT,
                maxOvershootPercent: MAX_OVERSHOOT_PERCENT
            },
            shots: shotAudits
        };
        auditFile = new File(
            evidenceFolder.fsName + "/animation-audit.json"
        );
        writeAuditOnce(auditFile, result);
        alert(
            "Video 001 animation audit PASS.\n" +
            "48 shots, 840 seconds, 25200 frames; projectStateUnchanged."
        );
    }

    try {
        main();
    } catch (error) {
        alert("Video 001 animation audit failed:\n" + error.toString());
        throw error;
    }
}());
