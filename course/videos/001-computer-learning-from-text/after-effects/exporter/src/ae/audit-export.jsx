/*
 * Video 001 Figma to After Effects Exporter read-only audit.
 *
 * This file uses concepts from AEUX and has been modified for this exporter.
 * Copyright 2017 Google Inc.
 * Licensed under the Apache License, Version 2.0.
 */

(function auditVideo001Export() {
    var scriptFile = new File($.fileName);
    var auditFile = new File(scriptFile.parent.fsName + "/audit-report.json");
    var itemCountBefore;
    var itemCountAfter;
    var comp;
    var contentHash;
    var importReport;
    var report;
    var fallback;
    var fallbackIndex;

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
            throw new Error("Cannot write UTF-8 file: " + file.fsName);
        }
        try {
            if (!file.write(value)) {
                throw new Error("Cannot complete UTF-8 write: " + file.fsName);
            }
        } finally {
            file.close();
        }
    }

    function layerType(layer) {
        if (layer instanceof TextLayer) {
            return "text";
        }
        if (layer instanceof ShapeLayer) {
            return "shape";
        }
        if (layer instanceof CameraLayer) {
            return "camera";
        }
        if (layer instanceof LightLayer) {
            return "light";
        }
        if (layer instanceof AVLayer && layer.source instanceof CompItem) {
            return "precomp";
        }
        if (layer instanceof AVLayer) {
            return "raster";
        }
        return "layer";
    }

    function collectShapeMatchNames(propertyGroup, values) {
        var property;
        var propertyIndex;
        if (propertyGroup === null || propertyGroup === undefined || propertyGroup.numProperties === undefined) {
            return;
        }
        for (propertyIndex = 1; propertyIndex <= propertyGroup.numProperties; propertyIndex += 1) {
            property = propertyGroup.property(propertyIndex);
            if (property === null) {
                continue;
            }
            if (
                property.matchName === "ADBE Vector Shape - Rect" ||
                property.matchName === "ADBE Vector Shape - Ellipse"
            ) {
                values[values.length] = property.matchName;
            }
            collectShapeMatchNames(property, values);
        }
    }

    function auditText(layer) {
        var source = layer.property("ADBE Text Properties").property("ADBE Text Document");
        var documentValue = source.value;
        var fontName = documentValue.font;
        if (documentValue.fontObject && documentValue.fontObject.postScriptName) {
            fontName = documentValue.fontObject.postScriptName;
        }
        return {
            text: documentValue.text,
            font: fontName,
            fontSize: documentValue.fontSize,
            boxDimensions: documentValue.boxTextSize === undefined ? null : documentValue.boxTextSize
        };
    }

    function auditLayer(layer, ownerComp) {
        var type = layerType(layer);
        var shapeMatchNames = [];
        var result = {
            comp: ownerComp.name,
            name: layer.name,
            type: type,
            comment: layer.comment || "",
            text: null,
            font: null,
            fontSize: null,
            boxDimensions: null,
            shapeMatchNames: shapeMatchNames,
            sourceComp: null
        };
        if (type === "text") {
            var textAudit = auditText(layer);
            result.text = textAudit.text;
            result.font = textAudit.font;
            result.fontSize = textAudit.fontSize;
            result.boxDimensions = textAudit.boxDimensions;
        }
        if (type === "shape") {
            collectShapeMatchNames(layer.property("ADBE Root Vectors Group"), shapeMatchNames);
        }
        if (type === "precomp") {
            result.sourceComp = layer.source.name;
        }
        return result;
    }

    function containsComp(stack, candidate) {
        var stackIndex;
        for (stackIndex = 0; stackIndex < stack.length; stackIndex += 1) {
            if (stack[stackIndex] === candidate) {
                return true;
            }
        }
        return false;
    }

    function auditHierarchy(ownerComp, layers, stack) {
        var hierarchy = {
            name: ownerComp.name,
            width: ownerComp.width,
            height: ownerComp.height,
            fps: ownerComp.frameRate,
            durationSeconds: ownerComp.duration,
            durationFrames: Math.round(ownerComp.duration * ownerComp.frameRate),
            children: []
        };
        var layer;
        var layerIndex;
        var childStack;
        stack[stack.length] = ownerComp;
        for (layerIndex = 1; layerIndex <= ownerComp.numLayers; layerIndex += 1) {
            layer = ownerComp.layer(layerIndex);
            layers[layers.length] = auditLayer(layer, ownerComp);
            if (layer instanceof AVLayer && layer.source instanceof CompItem) {
                if (containsComp(stack, layer.source)) {
                    hierarchy.children[hierarchy.children.length] = {
                        name: layer.source.name,
                        warning: "cyclic precomp reference"
                    };
                } else {
                    childStack = stack.slice(0);
                    hierarchy.children[hierarchy.children.length] = auditHierarchy(layer.source, layers, childStack);
                }
            }
        }
        return hierarchy;
    }

    function hashFromComment(comment) {
        var match = /^Video001Export sha256:([0-9a-f]{64})$/.exec(String(comment || ""));
        return match === null ? "" : match[1];
    }

    function loadImportReport(hash, warnings) {
        var root = new Folder(Folder.userData.fsName + "/Video001FigmaAEExporter");
        var file;
        if (hash === "") {
            warnings[warnings.length] = "Active comp has no exact Video 001 content-hash marker";
            return null;
        }
        file = new File(root.fsName + "/import-report-" + hash + ".json");
        if (!file.exists) {
            warnings[warnings.length] = "Import report is unavailable for the active comp content hash";
            return null;
        }
        try {
            return JSON.parse(readUtf8(file));
        } catch (reportError) {
            warnings[warnings.length] = "Import report could not be read as UTF-8 JSON";
            return null;
        }
    }

    if (!app.project || !(app.project.activeItem instanceof CompItem)) {
        throw new Error("Select one imported Video 001 comp before running the audit");
    }

    itemCountBefore = app.project.numItems;
    comp = app.project.activeItem;
    contentHash = hashFromComment(comp.comment);
    report = {
        projectPath: app.project.file === null ? null : app.project.file.fsName,
        itemCountBefore: itemCountBefore,
        itemCountAfter: 0,
        comp: {
            name: comp.name,
            width: comp.width,
            height: comp.height,
            fps: comp.frameRate,
            durationSeconds: comp.duration,
            durationFrames: Math.round(comp.duration * comp.frameRate)
        },
        layers: [],
        precompHierarchy: null,
        contentHash: contentHash,
        missingFonts: [],
        rasterFallbacks: [],
        warnings: []
    };
    report.precompHierarchy = auditHierarchy(comp, report.layers, []);
    importReport = loadImportReport(contentHash, report.warnings);
    if (importReport !== null) {
        report.missingFonts = importReport.missingFonts || [];
        if (importReport.fallbacks && importReport.fallbacks.length) {
            for (fallbackIndex = 0; fallbackIndex < importReport.fallbacks.length; fallbackIndex += 1) {
                fallback = importReport.fallbacks[fallbackIndex];
                if (fallback && fallback.type === "raster-fallback") {
                    report.rasterFallbacks[report.rasterFallbacks.length] = fallback;
                }
            }
        }
        if (importReport.warnings && importReport.warnings.length) {
            report.warnings = report.warnings.concat(importReport.warnings);
        }
    }
    itemCountAfter = app.project.numItems;
    report.itemCountAfter = itemCountAfter;
    if (itemCountAfter !== itemCountBefore) {
        throw new Error("Read-only audit detected an unexpected project item-count change");
    }
    writeUtf8(auditFile, JSON.stringify(report, null, 2));
}());
