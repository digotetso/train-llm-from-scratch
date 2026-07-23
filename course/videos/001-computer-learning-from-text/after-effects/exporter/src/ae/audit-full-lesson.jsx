/*
 * Video 001 Figma to After Effects Exporter full-lesson read-only audit.
 *
 * This file uses concepts from AEUX and has been modified for this exporter.
 * Copyright 2017 Google Inc.
 * Licensed under the Apache License, Version 2.0.
 */

(function auditVideo001FullLesson() {
    var scriptFile = new File($.fileName);
    var scriptDirectory = scriptFile.parent;
    var timingFile = new File(scriptDirectory.fsName + "/figma-scenes.json");
    var auditFile = new File(scriptDirectory.fsName + "/full-lesson-audit.json");
    var project;
    var master;
    var itemCountBefore;
    var itemCountAfter;
    var projectStateBefore;
    var projectStateAfter;
    var timing;
    var contentHash;
    var importReport;
    var expectedRasterByNodeId = {};
    var observedRasterByNodeId = {};
    var report;
    var index;
    var fallback;
    var nativeTotal;
    var rasterTotal;

    File.encoding = "UTF-8";

    function readUtf8(file) {
        var value;
        file.encoding = "UTF-8";
        if (!file.open("r")) {
            throw new Error("Cannot open UTF-8 file: " + file.fsName);
        }
        try {
            value = file.read();
        } finally {
            file.close();
        }
        return value;
    }

    function writeUtf8(file, value) {
        file.encoding = "UTF-8";
        if (!file.open("w")) {
            throw new Error("Cannot open UTF-8 output file: " + file.fsName);
        }
        try {
            if (!file.write(value)) {
                throw new Error("Cannot complete UTF-8 write: " + file.fsName);
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

    function requireNumber(value, label) {
        if (typeof value !== "number" || !isFinite(value)) {
            throw new Error(label + " must be a finite number");
        }
        return value;
    }

    function requireString(value, label) {
        if (typeof value !== "string" || value.length === 0) {
            throw new Error(label + " must be a non-empty string");
        }
        return value;
    }

    function parseContentHash(comment, label) {
        var match = /^Video001Export sha256:([0-9a-f]{64})$/.exec(String(comment || ""));
        if (match === null) {
            throw new Error(label + " has no exact exporter content hash");
        }
        return match[1];
    }

    function parseNodeComment(comment, label) {
        var value = String(comment || "");
        var match = /^Figma native text ([^ ]+)$/.exec(value);
        if (match !== null) {
            return { type: "native-text", nodeId: match[1] };
        }
        match = /^Figma native vector ([^ ]+) (rect|ellipse)$/.exec(value);
        if (match !== null) {
            return { type: "native-vector", nodeId: match[1], kind: match[2] };
        }
        match = /^Figma group precomp ([^ ]+)$/.exec(value);
        if (match !== null) {
            return { type: "group-precomp", nodeId: match[1] };
        }
        match = /^Figma raster fallback ([^ ]+) sha256:([0-9a-f]{64})$/.exec(value);
        if (match !== null) {
            return { type: "raster-fallback", nodeId: match[1], assetHash: match[2] };
        }
        throw new Error("Layer " + String(label || "") + " has no exact exporter node comment");
    }

    function containsIdentity(values, candidate) {
        var valueIndex;
        for (valueIndex = 0; valueIndex < values.length; valueIndex += 1) {
            if (values[valueIndex] === candidate) {
                return true;
            }
        }
        return false;
    }

    function copyArray(values) {
        var copied = [];
        var valueIndex;
        for (valueIndex = 0; valueIndex < values.length; valueIndex += 1) {
            copied[copied.length] = values[valueIndex];
        }
        return copied;
    }

    function snapshotProjectState(projectValue) {
        var snapshot = [];
        var item;
        var itemSnapshot;
        var itemIndex;
        var layer;
        var layerIndex;
        for (itemIndex = 1; itemIndex <= projectValue.numItems; itemIndex += 1) {
            item = projectValue.item(itemIndex);
            itemSnapshot = {
                index: itemIndex,
                name: String(item.name || ""),
                comment: String(item.comment || ""),
                parentFolder: item.parentFolder && item.parentFolder.name
                    ? String(item.parentFolder.name)
                    : null,
                comp: item instanceof CompItem,
                layers: []
            };
            if (item instanceof CompItem) {
                itemSnapshot.width = item.width;
                itemSnapshot.height = item.height;
                itemSnapshot.fps = item.frameRate;
                itemSnapshot.durationSeconds = item.duration;
                for (layerIndex = 1; layerIndex <= item.numLayers; layerIndex += 1) {
                    layer = item.layer(layerIndex);
                    itemSnapshot.layers[itemSnapshot.layers.length] = {
                        index: layerIndex,
                        name: String(layer.name || ""),
                        comment: String(layer.comment || ""),
                        enabled: layer.enabled === undefined ? null : layer.enabled,
                        startTime: layer.startTime === undefined ? null : layer.startTime,
                        inPoint: layer.inPoint === undefined ? null : layer.inPoint,
                        outPoint: layer.outPoint === undefined ? null : layer.outPoint,
                        source: layer.source && layer.source.name ? String(layer.source.name) : null
                    };
                }
            }
            snapshot[snapshot.length] = itemSnapshot;
        }
        return JSON.stringify(snapshot);
    }

    function loadTiming(file) {
        var value;
        var canvas;
        var shots;
        var shot;
        var result = { shots: [] };
        var expectedStart = 0;
        var shotIndex;
        try {
            value = requireObject(JSON.parse(readUtf8(file)), "Video 001 timing");
        } catch (timingError) {
            throw new Error("Cannot load canonical Video 001 timing: " + timingError.message);
        }
        canvas = requireObject(value.canvas, "Video 001 timing canvas");
        if (
            requireNumber(canvas.width, "Timing width") !== 1920 ||
            requireNumber(canvas.height, "Timing height") !== 1080 ||
            requireNumber(canvas.fps, "Timing fps") !== 30 ||
            canvas.timeUnit !== "seconds" ||
            requireNumber(canvas.duration, "Timing duration") !== 840
        ) {
            throw new Error("Full-lesson timing must be 1920x1080, 30 fps, seconds, and 840 seconds");
        }
        shots = requireArray(value.shots, "Video 001 timing shots");
        if (shots.length !== 48) {
            throw new Error("Full-lesson timing must contain exactly 48 shots");
        }
        for (shotIndex = 0; shotIndex < shots.length; shotIndex += 1) {
            shot = requireObject(shots[shotIndex], "Video 001 timing shot");
            if (shot.index !== shotIndex + 1) {
                throw new Error("Full-lesson timing shot indexes must be canonical");
            }
            if (requireNumber(shot.start, "Shot start") !== expectedStart) {
                throw new Error("Full-lesson timing contains a gap or overlap");
            }
            result.shots[result.shots.length] = {
                index: shotIndex + 1,
                nodeId: requireString(shot.figmaNodeId, "Shot node ID"),
                name: requireString(shot.name, "Shot name"),
                start: shot.start,
                duration: requireNumber(shot.duration, "Shot duration")
            };
            expectedStart += shot.duration;
        }
        if (expectedStart !== 840) {
            throw new Error("Full-lesson timing must cover exactly 840 seconds");
        }
        result.width = 1920;
        result.height = 1080;
        result.fps = 30;
        result.duration = 840;
        return result;
    }

    function loadImportReport(hash) {
        var root = new Folder(Folder.userData.fsName + "/Video001FigmaAEExporter");
        var file = new File(root.fsName + "/import-report-" + hash + ".json");
        var value;
        if (!file.exists) {
            throw new Error("Full-lesson import report is unavailable for content hash " + hash);
        }
        try {
            value = requireObject(JSON.parse(readUtf8(file)), "Full-lesson import report");
        } catch (reportError) {
            throw new Error("Cannot load the full-lesson import report: " + reportError.message);
        }
        if (value.contentHash !== hash) {
            throw new Error("Full-lesson import report content hash does not match the master");
        }
        requireArray(value.createdCompNames, "Import report created comp names");
        requireArray(value.missingFonts, "Import report missing fonts");
        requireArray(value.fallbacks, "Import report fallbacks");
        requireArray(value.warnings, "Import report warnings");
        return value;
    }

    function compIdentityMatches(compName, configuredName) {
        var prefix = configuredName + "_v";
        var suffix;
        if (compName.indexOf(prefix) !== 0) {
            return false;
        }
        suffix = compName.substring(prefix.length);
        return /^[0-9]{3}$/.test(suffix) && suffix !== "000";
    }

    function assertCompGeometry(comp, expectedDuration, label) {
        if (
            comp.width !== timing.width ||
            comp.height !== timing.height ||
            comp.frameRate !== timing.fps
        ) {
            throw new Error(label + " geometry does not match the canonical target");
        }
        if (
            comp.duration !== expectedDuration ||
            Math.round(comp.duration * comp.frameRate) !== Math.round(expectedDuration * timing.fps)
        ) {
            throw new Error(label + " duration does not match the canonical shot duration");
        }
    }

    function appendNativeNode(stats, nodeId) {
        var nodeIndex;
        for (nodeIndex = 0; nodeIndex < stats.nativeNodeIds.length; nodeIndex += 1) {
            if (stats.nativeNodeIds[nodeIndex] === nodeId) {
                throw new Error("Duplicate native node " + nodeId);
            }
        }
        stats.nativeNodeIds[stats.nativeNodeIds.length] = nodeId;
        stats.nativeCount += 1;
    }

    function auditHierarchy(ownerComp, expectedDuration, stack, stats, root) {
        var hierarchy;
        var layer;
        var parsed;
        var childStack;
        var childComment;
        var childMatch;
        var layerIndex;
        assertCompGeometry(
            ownerComp,
            expectedDuration,
            root ? "Shot root" : "Recursive precomp"
        );
        hierarchy = {
            name: ownerComp.name,
            durationSeconds: ownerComp.duration,
            durationFrames: Math.round(ownerComp.duration * ownerComp.frameRate),
            children: []
        };
        stack[stack.length] = ownerComp;
        for (layerIndex = 1; layerIndex <= ownerComp.numLayers; layerIndex += 1) {
            layer = ownerComp.layer(layerIndex);
            parsed = parseNodeComment(layer.comment, layer.name);
            if (
                typeof layer.property === "function" &&
                layer.property("ADBE Transform Group") === null
            ) {
                throw new Error("Exporter layer " + layer.name + " has no ADBE Transform Group");
            }
            if (parsed.type === "group-precomp") {
                if (!(layer instanceof AVLayer) || !(layer.source instanceof CompItem)) {
                    throw new Error("Figma group precomp " + parsed.nodeId + " has the wrong source comp");
                }
                appendNativeNode(stats, parsed.nodeId);
                childComment = String(layer.source.comment || "");
                childMatch = /^Figma recursive precomp ([^ ]+)$/.exec(childComment);
                if (childMatch === null || childMatch[1] !== parsed.nodeId) {
                    throw new Error("Recursive precomp comment does not match group node " + parsed.nodeId);
                }
                if (containsIdentity(stack, layer.source)) {
                    hierarchy.children[hierarchy.children.length] = {
                        name: layer.source.name,
                        nodeId: parsed.nodeId,
                        warning: "cyclic precomp reference"
                    };
                } else {
                    childStack = copyArray(stack);
                    childComment = parsed.nodeId;
                    parsed = auditHierarchy(layer.source, expectedDuration, childStack, stats, false);
                    parsed.nodeId = childComment;
                    hierarchy.children[hierarchy.children.length] = parsed;
                }
            } else if (parsed.type === "raster-fallback") {
                if (!(layer instanceof AVLayer) || layer.source instanceof CompItem) {
                    throw new Error("Raster fallback " + parsed.nodeId + " does not source footage");
                }
                if (expectedRasterByNodeId[parsed.nodeId] !== true) {
                    throw new Error("Unexpected raster fallback " + parsed.nodeId);
                }
                if (observedRasterByNodeId[parsed.nodeId] === true) {
                    throw new Error("Duplicate raster fallback " + parsed.nodeId);
                }
                observedRasterByNodeId[parsed.nodeId] = true;
                stats.rasterCount += 1;
                stats.rasterFallbacks[stats.rasterFallbacks.length] = {
                    nodeId: parsed.nodeId,
                    assetHash: parsed.assetHash
                };
            } else {
                appendNativeNode(stats, parsed.nodeId);
            }
        }
        return hierarchy;
    }

    function auditShot(comp, shot) {
        var shotHash = parseContentHash(comp.comment, "Shot source comp " + comp.name);
        var stats = {
            nativeCount: 0,
            nativeNodeIds: [],
            rasterCount: 0,
            rasterFallbacks: []
        };
        var hierarchy;
        if (shotHash !== contentHash) {
            throw new Error("Shot source comp content hash does not match the master content hash");
        }
        hierarchy = auditHierarchy(comp, shot.duration, [], stats, true);
        return {
            index: shot.index,
            nodeId: shot.nodeId,
            configuredName: shot.name,
            name: comp.name,
            contentHash: shotHash,
            width: comp.width,
            height: comp.height,
            fps: comp.frameRate,
            durationSeconds: comp.duration,
            durationFrames: Math.round(comp.duration * comp.frameRate),
            nativeCount: stats.nativeCount,
            nativeNodeIds: stats.nativeNodeIds,
            rasterCount: stats.rasterCount,
            rasterFallbacks: stats.rasterFallbacks,
            hierarchy: hierarchy
        };
    }

    function auditMasterLayers(masterComp) {
        var values = [];
        var layer;
        var source;
        var shot;
        var layerIndex;
        if (masterComp.numLayers !== timing.shots.length) {
            throw new Error("Full-lesson master must contain exactly 48 layers");
        }
        for (layerIndex = 1; layerIndex <= masterComp.numLayers; layerIndex += 1) {
            layer = masterComp.layer(layerIndex);
            shot = timing.shots[layerIndex - 1];
            if (!(layer instanceof AVLayer) || !(layer.source instanceof CompItem)) {
                throw new Error("Master layer " + layerIndex + " has the wrong source comp type");
            }
            source = layer.source;
            if (!compIdentityMatches(source.name, shot.name)) {
                throw new Error("Master layer " + layerIndex + " has the wrong source comp");
            }
            if (layer.name !== source.name) {
                throw new Error("Master layer " + layerIndex + " name does not match its source comp");
            }
            if (importReport.createdCompNames[layerIndex - 1] !== source.name) {
                throw new Error("Master layer " + layerIndex + " source comp does not match the import report");
            }
            if (layer.startTime !== shot.start || layer.inPoint !== shot.start) {
                if (layer.startTime > shot.start || layer.inPoint > shot.start) {
                    throw new Error("Master layer " + layerIndex + " introduces a timing gap");
                }
                throw new Error("Master layer " + layerIndex + " introduces a timing overlap");
            }
            if (layer.outPoint !== shot.start + shot.duration) {
                throw new Error("Master layer " + layerIndex + " has the wrong out point");
            }
            values[values.length] = {
                index: shot.index,
                nodeId: shot.nodeId,
                name: layer.name,
                sourceComp: source.name,
                startTime: layer.startTime,
                inPoint: layer.inPoint,
                outPoint: layer.outPoint
            };
            report.shots[report.shots.length] = auditShot(source, shot);
        }
        return values;
    }

    if (!app.project || !(app.project.activeItem instanceof CompItem)) {
        throw new Error("Select one VIDEO001_MASTER_vNNN composition before running the full-lesson audit");
    }
    project = app.project;
    master = project.activeItem;
    if (!/^VIDEO001_MASTER_v[0-9]{3}$/.test(master.name) || /_v000$/.test(master.name)) {
        throw new Error("Active composition must be named VIDEO001_MASTER_vNNN");
    }

    itemCountBefore = project.numItems;
    projectStateBefore = snapshotProjectState(project);
    timing = loadTiming(timingFile);
    contentHash = parseContentHash(master.comment, "Full-lesson master");
    importReport = loadImportReport(contentHash);
    if (importReport.createdMasterCompName !== master.name) {
        throw new Error("Import report master name does not match the active full-lesson master");
    }
    for (index = 0; index < importReport.fallbacks.length; index += 1) {
        fallback = importReport.fallbacks[index];
        if (fallback && fallback.type === "raster-fallback") {
            if (typeof fallback.nodeId !== "string" || expectedRasterByNodeId[fallback.nodeId] === true) {
                throw new Error("Import report contains an invalid or duplicate raster fallback");
            }
            expectedRasterByNodeId[fallback.nodeId] = true;
        }
    }
    report = {
        auditSchemaVersion: 1,
        contentHash: contentHash,
        itemCountBefore: itemCountBefore,
        itemCountAfter: 0,
        projectStateUnchanged: false,
        master: null,
        shots: [],
        missingFonts: copyArray(importReport.missingFonts),
        fallbacks: copyArray(importReport.fallbacks),
        warnings: copyArray(importReport.warnings)
    };
    assertCompGeometry(master, 840, "Full-lesson master");
    report.master = {
        name: master.name,
        width: master.width,
        height: master.height,
        fps: master.frameRate,
        durationSeconds: master.duration,
        durationFrames: Math.round(master.duration * master.frameRate),
        layers: auditMasterLayers(master)
    };
    for (fallback in expectedRasterByNodeId) {
        if (
            Object.prototype.hasOwnProperty.call(expectedRasterByNodeId, fallback) &&
            observedRasterByNodeId[fallback] !== true
        ) {
            throw new Error("Expected raster fallback " + fallback + " is missing from the audited shots");
        }
    }
    nativeTotal = 0;
    rasterTotal = 0;
    for (index = 0; index < report.shots.length; index += 1) {
        nativeTotal += report.shots[index].nativeCount;
        rasterTotal += report.shots[index].rasterCount;
    }
    if (importReport.nativeCount !== nativeTotal || importReport.rasterCount !== rasterTotal) {
        throw new Error("Audit native/raster counts do not match the import report");
    }
    itemCountAfter = project.numItems;
    projectStateAfter = snapshotProjectState(project);
    report.itemCountAfter = itemCountAfter;
    report.projectStateUnchanged = (
        itemCountAfter === itemCountBefore &&
        projectStateAfter === projectStateBefore
    );
    if (!report.projectStateUnchanged) {
        throw new Error("Read-only audit detected an unexpected project state or item-count change");
    }
    writeUtf8(auditFile, JSON.stringify(report, null, 2));
}());
