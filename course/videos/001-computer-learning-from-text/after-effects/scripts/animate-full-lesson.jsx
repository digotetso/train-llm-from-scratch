/*
 * Video 001 full-lesson animation builder.
 *
 * It duplicates the validated Figma-imported shot comps, applies the approved
 * restrained entry system, creates a separate animated master, collects linked
 * raster assets, and saves source-import and animated AEP deliverables.
 */

(function () {
    var EXPECTED_INPUT_PROJECT =
        "/private/tmp/Video001-Exporter-Full-Lesson.aep";
    var DELIVERY_CONFIG_PATH =
        "/private/tmp/video001-animation-delivery.json";
    var SOURCE_MASTER_NAME = "VIDEO001_MASTER_v001";
    var ANIMATED_MASTER_NAME = "VIDEO001_ANIMATED_MASTER_v001";
    var ANIMATED_SUFFIX = "_ANIM_v001";
    var SOURCE_AEP_NAME =
        "video-001-figma-exported-source-import.aep";
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
    var MOTION = {
        transitionFrames: 12,
        staggerSeconds: 0.06,
        maxTravelPx: 24,
        entryScalePercent: 96,
        maxOvershootPercent: 102,
        appliedOvershootPercent: 101.5,
        easeInfluence: 82
    };
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
    var transactionOpen = false;
    var activeBuild = null;

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

    function writeUtf8(file, value, label) {
        file.encoding = "UTF-8";
        if (!file.open("w")) {
            throw new Error("Cannot open " + label + " for writing");
        }
        try {
            if (!file.write(value)) {
                throw new Error("Cannot complete " + label);
            }
        } finally {
            file.close();
        }
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

    function ensureFolder(folder, createdFolders) {
        if (folder.exists) {
            if (folder.alias === true) {
                throw new Error("Refusing aliased output folder " + folder.fsName);
            }
            return;
        }
        if (folder.parent !== null && !folder.parent.exists) {
            ensureFolder(folder.parent, createdFolders);
        }
        if (!folder.create()) {
            throw new Error("Cannot create output folder " + folder.fsName);
        }
        createdFolders[createdFolders.length] = folder;
    }

    function assertSafeOutputAncestors(outputRoot, expectedOutputRoot) {
        var cursor = afterEffectsRoot;
        var previous = "";
        var deliverablesFolder = new Folder(
            afterEffectsRoot.fsName + "/deliverables"
        );
        if (outputRoot.fsName !== expectedOutputRoot) {
            throw new Error("Animation output root is not the exact approved location");
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
            deliverablesFolder.exists &&
            deliverablesFolder.alias === true
        ) {
            throw new Error("Animation deliverables folder is aliased");
        }
        if (outputRoot.exists || outputRoot.alias === true) {
            throw new Error(
                "Refusing to overwrite an existing animation deliverable"
            );
        }
    }

    function writeJsonAtomically(file, value, label, createdFiles) {
        var suffix;
        var temporary;
        if (
            !file.parent.exists ||
            file.parent.alias === true ||
            file.exists ||
            file.alias === true
        ) {
            throw new Error(label + " target is not a new safe file");
        }
        suffix = String(new Date().getTime()) + "-" +
            String(Math.floor(Math.random() * 1000000000));
        temporary = new File(
            file.parent.fsName + "/." + file.name + "." + suffix + ".tmp"
        );
        if (temporary.exists || temporary.alias === true) {
            throw new Error("Cannot reserve " + label + " temporary file");
        }
        try {
            writeUtf8(
                temporary,
                JSON.stringify(value, null, 2) + "\n",
                label + " temporary file"
            );
            if (
                file.exists ||
                file.alias === true ||
                !temporary.rename(file.name)
            ) {
                throw new Error("Cannot atomically publish " + label);
            }
        } catch (error) {
            if (temporary.exists && temporary.alias !== true) {
                temporary.remove();
            }
            throw error;
        }
        createdFiles[createdFiles.length] = file;
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

    function finiteNumber(value, label) {
        if (typeof value !== "number" || !isFinite(value)) {
            throw new Error(label + " must be a finite number");
        }
        return value;
    }

    function approximately(left, right) {
        return Math.abs(left - right) <= 0.000001;
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

    function assertNoItemNamed(name) {
        var index;
        for (index = 1; index <= app.project.numItems; index += 1) {
            if (app.project.item(index).name === name) {
                throw new Error("Refusing to overwrite existing project item " + name);
            }
        }
    }

    function readTiming() {
        var timing = requireObject(
            JSON.parse(readUtf8(timingFile, "canonical timing")),
            "Canonical timing"
        );
        var shots = requireArray(timing.shots, "Canonical shots");
        var canvas = requireObject(timing.canvas, "Canonical canvas");
        var expectedStart = 0;
        var index;
        var shot;
        if (
            shots.length !== 48 ||
            canvas.width !== 1920 ||
            canvas.height !== 1080 ||
            canvas.fps !== 30 ||
            canvas.duration !== 840
        ) {
            throw new Error("Canonical timing must be 48 shots, 1920x1080, 30 fps, and 840 seconds");
        }
        for (index = 0; index < shots.length; index += 1) {
            shot = requireObject(shots[index], "Canonical shot");
            if (
                shot.index !== index + 1 ||
                shot.start !== expectedStart ||
                typeof shot.name !== "string" ||
                !finiteNumber(shot.duration, "Canonical shot duration") ||
                shot.duration <= 0
            ) {
                throw new Error("Canonical shot timing is invalid at index " + String(index + 1));
            }
            expectedStart += shot.duration;
        }
        if (expectedStart !== 840) {
            throw new Error("Canonical shots must cover exactly 840 seconds");
        }
        return timing;
    }

    function readDeliveryConfig() {
        var value = requireObject(
            JSON.parse(readUtf8(deliveryConfigFile, "animation delivery config")),
            "Animation delivery config"
        );
        var outputRoot;
        var expectedOutputRoot =
            afterEffectsRoot.fsName + OUTPUT_SUFFIX;
        if (ownKeyCount(value) !== 1) {
            throw new Error("Animation delivery config must contain only outputRoot");
        }
        outputRoot = requireString(value.outputRoot, "Animation output root");
        if (
            outputRoot.charAt(0) !== "/" ||
            /\/\.\.(?:\/|$)/.test(outputRoot) ||
            outputRoot !== expectedOutputRoot
        ) {
            throw new Error("Animation output root is outside the approved deliverable location");
        }
        return value;
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

    function contentHashFromMaster(master) {
        var match = /^Video001Export sha256:([0-9a-f]{64})$/.exec(
            String(master.comment || "")
        );
        if (match === null) {
            throw new Error("Source master has no validated exporter content hash");
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

    function copyLinkedAssets(assetFolder, buildState) {
        var copiedBySource = {};
        var copied = [];
        var index;
        var item;
        var sourceFile;
        var destinationName;
        var hashMatch;
        var destination;
        for (index = 1; index <= app.project.numItems; index += 1) {
            item = app.project.item(index);
            if (!(item instanceof FootageItem)) {
                continue;
            }
            try {
                sourceFile = item.mainSource.file;
            } catch (sourceError) {
                sourceFile = null;
            }
            if (sourceFile === null || sourceFile === undefined || !sourceFile.exists) {
                continue;
            }
            if (copiedBySource[sourceFile.fsName] !== undefined) {
                buildState.relinkedAssets[
                    buildState.relinkedAssets.length
                ] = {
                    item: item,
                    originalFile: sourceFile
                };
                item.replace(copiedBySource[sourceFile.fsName]);
                continue;
            }
            hashMatch = /sha256:([0-9a-f]{64})/.exec(String(item.comment || ""));
            destinationName = hashMatch === null
                ? String(index) + "-" + String(sourceFile.name).replace(/[^A-Za-z0-9._-]/g, "_")
                : hashMatch[1] + ".png";
            destination = new File(assetFolder.fsName + "/" + destinationName);
            if (destination.exists || destination.alias === true) {
                throw new Error("Refusing to overwrite collected asset " + destination.name);
            }
            if (!sourceFile.copy(destination.fsName)) {
                throw new Error("Cannot collect linked asset " + sourceFile.name);
            }
            buildState.createdFiles[
                buildState.createdFiles.length
            ] = destination;
            buildState.relinkedAssets[
                buildState.relinkedAssets.length
            ] = {
                item: item,
                originalFile: sourceFile
            };
            item.replace(destination);
            copiedBySource[sourceFile.fsName] = destination;
            copied[copied.length] = destination.name;
        }
        return copied;
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

    function layerArea(layer) {
        var rect;
        try {
            rect = layer.sourceRectAtTime(0, false);
            if (rect.width > 0 && rect.height > 0) {
                return rect.width * rect.height;
            }
        } catch (rectError) {
        }
        if (layer.source !== null && layer.source !== undefined) {
            try {
                return layer.source.width * layer.source.height;
            } catch (sourceSizeError) {
            }
        }
        return 0;
    }

    function collectRevealLayers(comp) {
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
                    index: layer.index,
                    area: layerArea(layer)
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

    function selectHero(revealLayers) {
        var result = null;
        var index;
        for (index = 0; index < revealLayers.length; index += 1) {
            if (isHeroCandidate(revealLayers[index].layer)) {
                return revealLayers[index];
            }
        }
        return result;
    }

    function scaledValue(value, percent) {
        var result = [];
        var index;
        for (index = 0; index < value.length; index += 1) {
            result[result.length] = value[index] * percent / 100;
        }
        return result;
    }

    function easeArrayForProperty(property, influence) {
        var count = 1;
        var result = [];
        var index;
        if (property.propertyValueType === PropertyValueType.TwoD) {
            count = 2;
        } else if (
            property.propertyValueType === PropertyValueType.ThreeD
        ) {
            count = 3;
        }
        for (index = 0; index < count; index += 1) {
            result[result.length] = new KeyframeEase(0, influence);
        }
        return result;
    }

    function applyBezierEase(property) {
        var index;
        var ease;
        for (index = 1; index <= property.numKeys; index += 1) {
            ease = easeArrayForProperty(property, MOTION.easeInfluence);
            property.setTemporalEaseAtKey(index, ease, ease);
            property.setInterpolationTypeAtKey(
                index,
                KeyframeInterpolationType.BEZIER,
                KeyframeInterpolationType.BEZIER
            );
        }
    }

    function requireUnkeyed(property, label) {
        if (property === null || property.numKeys !== 0) {
            throw new Error(label + " must exist and be unkeyed in the duplicated comp");
        }
    }

    function animateOpacity(layer, startTime, endTime) {
        var property = layer
            .property("ADBE Transform Group")
            .property("ADBE Opacity");
        var baseValue;
        requireUnkeyed(property, layer.name + " opacity");
        baseValue = property.value;
        property.setValueAtTime(startTime, 0);
        property.setValueAtTime(endTime, baseValue);
        applyBezierEase(property);
        return baseValue;
    }

    function animatePosition(layer, startTime, endTime) {
        var transform = layer.property("ADBE Transform Group");
        var position = transform.property("ADBE Position");
        var yPosition;
        var baseValue;
        var startValue;
        if (position.dimensionsSeparated) {
            yPosition = transform.property("ADBE Position_1");
            requireUnkeyed(yPosition, layer.name + " separated Y position");
            baseValue = yPosition.value;
            yPosition.setValueAtTime(startTime, baseValue + MOTION.maxTravelPx);
            yPosition.setValueAtTime(endTime, baseValue);
            applyBezierEase(yPosition);
            return {
                separated: true,
                base: baseValue,
                start: baseValue + MOTION.maxTravelPx
            };
        }
        requireUnkeyed(position, layer.name + " position");
        baseValue = propertyValue(position.value);
        startValue = propertyValue(position.value);
        if (!(startValue instanceof Array) || startValue.length < 2) {
            throw new Error(layer.name + " has an unsupported position value");
        }
        startValue[1] += MOTION.maxTravelPx;
        position.setValueAtTime(startTime, startValue);
        position.setValueAtTime(endTime, baseValue);
        applyBezierEase(position);
        return {
            separated: false,
            base: baseValue,
            start: startValue
        };
    }

    function animateScale(layer, startTime, endTime) {
        var property = layer
            .property("ADBE Transform Group")
            .property("ADBE Scale");
        var baseValue;
        var overshootTime =
            startTime + (8 / 30);
        requireUnkeyed(property, layer.name + " scale");
        baseValue = propertyValue(property.value);
        property.setValueAtTime(
            startTime,
            scaledValue(baseValue, MOTION.entryScalePercent)
        );
        property.setValueAtTime(
            overshootTime,
            scaledValue(baseValue, MOTION.appliedOvershootPercent)
        );
        property.setValueAtTime(endTime, baseValue);
        applyBezierEase(property);
        return {
            base: baseValue,
            start: scaledValue(baseValue, MOTION.entryScalePercent),
            overshoot: scaledValue(baseValue, MOTION.appliedOvershootPercent),
            overshootTime: overshootTime
        };
    }

    function animateShot(comp, shot) {
        var revealLayers = collectRevealLayers(comp);
        var hero = selectHero(revealLayers);
        var entries = [];
        var index;
        var record;
        var layer;
        var wasLocked;
        var startTime;
        var endTime;
        var opacityBase;
        var transformRecord;
        for (index = 0; index < revealLayers.length; index += 1) {
            record = revealLayers[index];
            layer = record.layer;
            wasLocked = layer.locked;
            layer.locked = false;
            try {
                startTime = index * MOTION.staggerSeconds;
                endTime = startTime + MOTION.transitionFrames / 30;
                opacityBase = animateOpacity(layer, startTime, endTime);
                if (hero !== null && layer === hero.layer) {
                    transformRecord = animateScale(layer, startTime, endTime);
                    entries[entries.length] = {
                        layerIndex: layer.index,
                        layerName: String(layer.name),
                        mode: "scale",
                        startTime: startTime,
                        endTime: endTime,
                        opacityBase: opacityBase,
                        scale: transformRecord
                    };
                } else {
                    transformRecord = animatePosition(layer, startTime, endTime);
                    entries[entries.length] = {
                        layerIndex: layer.index,
                        layerName: String(layer.name),
                        mode: "position",
                        startTime: startTime,
                        endTime: endTime,
                        opacityBase: opacityBase,
                        position: transformRecord
                    };
                }
            } finally {
                layer.locked = wasLocked;
            }
        }
        comp.comment =
            "Video001 animated shot " + String(shot.index) +
            " | source:" + shot.name + "_v001" +
            " | motion:12f/60ms/24px/96-101.5-100";
        return entries;
    }

    function buildAnimatedMaster(
        animatedComps,
        timing,
        folder,
        contentHash,
        buildState
    ) {
        var master = app.project.items.addComp(
            ANIMATED_MASTER_NAME,
            1920,
            1080,
            1,
            840,
            30
        );
        var index;
        var shot;
        var layer;
        buildState.createdItems[
            buildState.createdItems.length
        ] = master;
        master.parentFolder = folder;
        master.comment =
            "Video001 animated master sha256:" + contentHash +
            " | 48 shots | 840s | 30fps";
        for (index = animatedComps.length - 1; index >= 0; index -= 1) {
            shot = timing.shots[index];
            layer = master.layers.add(animatedComps[index]);
            layer.name = animatedComps[index].name;
            layer.startTime = shot.start;
            layer.inPoint = shot.start;
            layer.outPoint = shot.start + shot.duration;
        }
        master.workAreaStart = 0;
        master.workAreaDuration = 840;
        return master;
    }

    function createRootFolder(name, buildState) {
        var index;
        var item;
        for (index = 1; index <= app.project.numItems; index += 1) {
            item = app.project.item(index);
            if (
                item instanceof FolderItem &&
                item.parentFolder === app.project.rootFolder &&
                item.name === name
            ) {
                throw new Error("Refusing existing animation folder " + name);
            }
        }
        item = app.project.items.addFolder(name);
        buildState.createdItems[
            buildState.createdItems.length
        ] = item;
        return item;
    }

    function restoreRelinkedAssets(buildState) {
        var index;
        var errors = [];
        for (
            index = buildState.relinkedAssets.length - 1;
            index >= 0;
            index -= 1
        ) {
            try {
                buildState.relinkedAssets[index].item.replace(
                    buildState.relinkedAssets[index].originalFile
                );
            } catch (restoreError) {
                errors[errors.length] = restoreError.toString();
            }
        }
        if (errors.length > 0) {
            throw new Error(
                "Cannot restore every linked asset: " +
                errors.join(" | ")
            );
        }
    }

    function removeCreatedItems(buildState) {
        var index;
        var item;
        var errors = [];
        for (
            index = buildState.createdItems.length - 1;
            index >= 0;
            index -= 1
        ) {
            item = buildState.createdItems[index];
            try {
                item.remove();
            } catch (removeError) {
                errors[errors.length] =
                    String(item.name) + ": " + removeError.toString();
            }
        }
        if (errors.length > 0) {
            throw new Error(
                "Cannot remove every partial project item: " +
                errors.join(" | ")
            );
        }
    }

    function removeCreatedOutput(buildState) {
        var index;
        var file;
        var folder;
        var errors = [];
        for (
            index = buildState.createdFiles.length - 1;
            index >= 0;
            index -= 1
        ) {
            file = buildState.createdFiles[index];
            if (
                file.exists &&
                (
                    file.alias === true ||
                    !file.remove()
                )
            ) {
                errors[errors.length] =
                    "file " + file.fsName;
            }
        }
        for (
            index = buildState.createdFolders.length - 1;
            index >= 0;
            index -= 1
        ) {
            folder = buildState.createdFolders[index];
            if (
                folder.exists &&
                (
                    folder.alias === true ||
                    folder.getFiles().length !== 0 ||
                    !folder.remove()
                )
            ) {
                errors[errors.length] =
                    "folder " + folder.fsName;
            }
        }
        if (errors.length > 0) {
            throw new Error(
                "Cannot remove every partial output: " +
                errors.join(" | ")
            );
        }
    }

    function rollbackBuild(buildState) {
        var currentSourceSnapshot;
        var errors = [];
        var projectRestored = true;
        if (transactionOpen) {
            try {
                app.endUndoGroup();
            } catch (undoError) {
                errors[errors.length] = undoError.toString();
                projectRestored = false;
            }
            transactionOpen = false;
        }
        try {
            removeCreatedItems(buildState);
        } catch (itemError) {
            errors[errors.length] = itemError.toString();
            projectRestored = false;
        }
        try {
            restoreRelinkedAssets(buildState);
        } catch (relinkError) {
            errors[errors.length] = relinkError.toString();
            projectRestored = false;
        }
        if (projectRestored) {
            try {
                currentSourceSnapshot = sourceSnapshot(
                    buildState.sourceMaster,
                    buildState.sourceComps
                );
                if (
                    canonicalJson(currentSourceSnapshot) !==
                    canonicalJson(buildState.sourceSnapshot)
                ) {
                    throw new Error(
                        "Rollback could not restore the source comp snapshot"
                    );
                }
            } catch (snapshotError) {
                errors[errors.length] = snapshotError.toString();
                projectRestored = false;
            }
        }
        if (projectRestored) {
            try {
                app.project.save(new File(EXPECTED_INPUT_PROJECT));
                if (
                    app.project.file === null ||
                    app.project.file.fsName !== EXPECTED_INPUT_PROJECT
                ) {
                    throw new Error(
                        "Rollback could not restore the input project"
                    );
                }
            } catch (saveError) {
                errors[errors.length] = saveError.toString();
                projectRestored = false;
            }
        }
        if (projectRestored) {
            try {
                removeCreatedOutput(buildState);
            } catch (outputError) {
                errors[errors.length] = outputError.toString();
            }
        } else {
            errors[errors.length] =
                "Partial outputs were retained for recovery";
        }
        if (errors.length > 0) {
            throw new Error(
                "Animation rollback was incomplete: " +
                errors.join(" | ")
            );
        }
    }

    function main() {
        var timing;
        var deliveryConfig;
        var expectedOutputRoot;
        var outputRoot;
        var assetFolder;
        var renderFolder;
        var evidenceFolder;
        var sourceAep;
        var animatedAep;
        var sourceMaster;
        var sourceComps = [];
        var sourceProvenances = [];
        var sourceVisualSnapshots = [];
        var sourceVisualHashes = [];
        var sourceBefore;
        var sourceAfter;
        var contentHash;
        var trustedEvidence;
        var trustedPackage;
        var visualProvenance;
        var collectedAssets;
        var animationFolder;
        var animatedComps = [];
        var shotReports = [];
        var animatedMaster;
        var reportFile;
        var index;
        var shot;
        var sourceComp;
        var animatedComp;

        if (
            app.project === null ||
            app.project.file === null ||
            app.project.file.fsName !== EXPECTED_INPUT_PROJECT
        ) {
            throw new Error(
                "Refusing animation outside " + EXPECTED_INPUT_PROJECT
            );
        }
        timing = readTiming();
        deliveryConfig = readDeliveryConfig();
        outputRoot = new Folder(deliveryConfig.outputRoot);
        expectedOutputRoot =
            afterEffectsRoot.fsName + OUTPUT_SUFFIX;
        assertSafeOutputAncestors(outputRoot, expectedOutputRoot);

        sourceMaster = findUniqueComp(SOURCE_MASTER_NAME);
        if (
            sourceMaster.width !== 1920 ||
            sourceMaster.height !== 1080 ||
            sourceMaster.frameRate !== 30 ||
            !approximately(sourceMaster.duration, 840) ||
            sourceMaster.numLayers !== 48
        ) {
            throw new Error("Source master geometry or timing is not canonical");
        }
        contentHash = contentHashFromMaster(sourceMaster);
        if (contentHash !== TRUSTED_CONTENT_HASH) {
            throw new Error(
                "Source master content hash does not match the trusted lesson"
            );
        }
        trustedEvidence = loadTrustedSourceEvidence();
        trustedPackage = loadTrustedPackage();
        visualProvenance = loadProvenanceLibrary();
        assertNoItemNamed(ANIMATED_MASTER_NAME);
        for (index = 0; index < timing.shots.length; index += 1) {
            shot = timing.shots[index];
            assertNoItemNamed(shot.name + ANIMATED_SUFFIX);
            sourceComp = findUniqueComp(shot.name + "_v001");
            if (
                sourceComp.width !== 1920 ||
                sourceComp.height !== 1080 ||
                sourceComp.frameRate !== 30 ||
                !approximately(sourceComp.duration, shot.duration)
            ) {
                throw new Error("Source shot geometry or timing is invalid: " + sourceComp.name);
            }
            sourceComps[sourceComps.length] = sourceComp;
            sourceProvenances[sourceProvenances.length] =
                assertSourceCompMatchesTrusted(
                    sourceComp,
                    shot,
                    trustedEvidence.shots[index],
                    contentHash
                );
            sourceVisualSnapshots[sourceVisualSnapshots.length] =
                visualProvenance.assertCompMatchesFrame(
                    sourceComp,
                    trustedPackage.frames[index],
                    trustedPackage,
                    null,
                    null
                );
            sourceVisualHashes[sourceVisualHashes.length] =
                visualProvenance.sha256Utf8(
                    visualProvenance.canonicalJson(
                        sourceVisualSnapshots[index]
                    )
                );
        }
        sourceBefore = sourceSnapshot(sourceMaster, sourceComps);
        activeBuild = {
            createdFiles: [],
            createdFolders: [],
            createdItems: [],
            relinkedAssets: [],
            sourceMaster: sourceMaster,
            sourceComps: sourceComps,
            sourceSnapshot: sourceBefore
        };

        ensureFolder(outputRoot, activeBuild.createdFolders);
        assetFolder = new Folder(outputRoot.fsName + "/assets");
        renderFolder = new Folder(outputRoot.fsName + "/renders");
        evidenceFolder = new Folder(outputRoot.fsName + "/evidence");
        ensureFolder(assetFolder, activeBuild.createdFolders);
        ensureFolder(renderFolder, activeBuild.createdFolders);
        ensureFolder(evidenceFolder, activeBuild.createdFolders);

        collectedAssets = copyLinkedAssets(assetFolder, activeBuild);
        sourceAep = new File(outputRoot.fsName + "/" + SOURCE_AEP_NAME);
        animatedAep = new File(outputRoot.fsName + "/" + ANIMATED_AEP_NAME);
        if (sourceAep.exists || animatedAep.exists) {
            throw new Error("Refusing to overwrite an existing AEP deliverable");
        }
        activeBuild.createdFiles[
            activeBuild.createdFiles.length
        ] = sourceAep;
        app.project.save(sourceAep);
        if (
            app.project.file === null ||
            app.project.file.fsName !== sourceAep.fsName ||
            !sourceAep.exists ||
            sourceAep.length <= 0
        ) {
            throw new Error("Source-import AEP was not saved completely");
        }
        app.beginUndoGroup("Build Video 001 animated lesson");
        transactionOpen = true;
        animationFolder = createRootFolder(
            "02_Animated_Lesson",
            activeBuild
        );
        for (index = 0; index < timing.shots.length; index += 1) {
            shot = timing.shots[index];
            sourceComp = sourceComps[index];
            animatedComp = sourceComp.duplicate();
            activeBuild.createdItems[
                activeBuild.createdItems.length
            ] = animatedComp;
            animatedComp.name = shot.name + ANIMATED_SUFFIX;
            animatedComp.parentFolder = animationFolder;
            animatedComps[animatedComps.length] = animatedComp;
            shotReports[shotReports.length] = {
                index: shot.index,
                sourceComp: sourceComp.name,
                sourceContentHash: contentHash,
                sourceProvenance: sourceProvenances[index],
                sourceVisualSha256: sourceVisualHashes[index],
                animatedComp: animatedComp.name,
                start: shot.start,
                duration: shot.duration,
                animatedLayers: animateShot(animatedComp, shot)
            };
            if (
                visualProvenance.canonicalJson(
                    visualProvenance.assertCompMatchesFrame(
                        animatedComp,
                        trustedPackage.frames[index],
                        trustedPackage,
                        shotReports[index],
                        sourceComp
                    )
                ) !==
                visualProvenance.canonicalJson(
                    sourceVisualSnapshots[index]
                )
            ) {
                throw new Error(
                    "Animated shot static visual content changed: " +
                    animatedComp.name
                );
            }
        }
        animatedMaster = buildAnimatedMaster(
            animatedComps,
            timing,
            animationFolder,
            contentHash,
            activeBuild
        );
        sourceAfter = sourceSnapshot(sourceMaster, sourceComps);
        if (canonicalJson(sourceBefore) !== canonicalJson(sourceAfter)) {
            throw new Error("Source master or source shot comps changed during animation");
        }

        app.endUndoGroup();
        transactionOpen = false;
        activeBuild.createdFiles[
            activeBuild.createdFiles.length
        ] = animatedAep;
        app.project.save(animatedAep);
        if (
            app.project.file === null ||
            app.project.file.fsName !== animatedAep.fsName ||
            !animatedAep.exists ||
            animatedAep.length <= 0
        ) {
            throw new Error("Animated AEP was not saved completely");
        }
        reportFile = new File(
            evidenceFolder.fsName + "/animation-build-report.json"
        );
        writeJsonAtomically(reportFile, {
            reportSchemaVersion: 1,
            status: "PASS",
            generator: "After Effects " + String(app.version),
            contentHash: contentHash,
            trustedEvidenceSha256: TRUSTED_EVIDENCE_SHA256,
            trustedPackageSha256: TRUSTED_PACKAGE_SHA256,
            inputProject: EXPECTED_INPUT_PROJECT,
            sourceAep: SOURCE_AEP_NAME,
            animatedAep: ANIMATED_AEP_NAME,
            collectedAssets: collectedAssets,
            sourceMasterUnchanged: true,
            sourceSnapshot: sourceBefore,
            motion: MOTION,
            animatedMaster: {
                name: animatedMaster.name,
                width: animatedMaster.width,
                height: animatedMaster.height,
                frameRate: animatedMaster.frameRate,
                durationSeconds: animatedMaster.duration,
                durationFrames: Math.round(
                    animatedMaster.duration * animatedMaster.frameRate
                ),
                layerCount: animatedMaster.numLayers
            },
            shots: shotReports
        }, "animation build report", activeBuild.createdFiles);
        activeBuild = null;
        alert(
            "Video 001 animated lesson built successfully.\n" +
            "48 editable shot comps + one 14-minute animated master."
        );
    }

    try {
        main();
    } catch (error) {
        if (activeBuild !== null) {
            try {
                rollbackBuild(activeBuild);
            } catch (rollbackError) {
                error = new Error(
                    error.toString() +
                    "\nRollback failed: " +
                    rollbackError.toString()
                );
            }
            activeBuild = null;
        } else if (transactionOpen) {
            app.endUndoGroup();
            transactionOpen = false;
        }
        alert("Video 001 animation build failed:\n" + error.toString());
        throw error;
    }
}());
