/*
 * Live-only evidence capture for the Video 001 unchanged full-lesson resend.
 *
 * This file uses concepts from AEUX and has been modified for this exporter.
 * Copyright 2017 Google Inc.
 * Licensed under the Apache License, Version 2.0.
 *
 * Run this script only after the duplicate package is queued and the initial
 * 48-shot import has completed in the disposable validation project.
 */

#include "import-core.jsxinc"
#include "importer.jsxinc"

(function () {
    var EXPECTED_PROJECT_PATH = "/private/tmp/Video001-Exporter-Full-Lesson.aep";
    var WITNESS_PATH = "/private/tmp/video001-full-lesson-duplicate-witness.json";
    var PACKAGE_SUFFIX = ".video001-ae.json";
    var scriptFile = new File($.fileName);
    var exporterRoot = scriptFile.parent.parent.parent;
    var rawDirectory = new Folder(exporterRoot.fsName + "/evidence/full-lesson/raw");
    var duplicateEvidenceFile = new File(
        rawDirectory.fsName + "/full-lesson-duplicate-result.json"
    );
    var postResendAuditFile = new File(
        rawDirectory.fsName + "/full-lesson-post-resend-audit.json"
    );
    var queueRoot = new Folder(Folder.userData.fsName + "/Video001FigmaAEExporter");
    var incomingFolder = new Folder(queueRoot.fsName + "/incoming");
    var assetFolder = new Folder(queueRoot.fsName + "/assets");
    var timingFile = new File(exporterRoot.fsName + "/config/video001-figma-scenes.json");
    var witnessFile = new File(WITNESS_PATH);
    var witness;
    var queuePackage;
    var before;
    var result;
    var after;

    File.encoding = "UTF-8";

    function requireObject(value, label) {
        if (value === null || typeof value !== "object" || value instanceof Array) {
            throw new Error(label + " must be an object");
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

    function readJson(file, label) {
        if (!file.exists) {
            throw new Error(label + " is missing");
        }
        return requireObject(
            JSON.parse(Video001ExporterImporter.readUtf8(file)),
            label
        );
    }

    function assertSafeRawDirectory() {
        var expectedPath = exporterRoot.fsName + "/evidence/full-lesson/raw";
        var expectedNames = [
            "raw",
            "full-lesson",
            "evidence",
            exporterRoot.name
        ];
        var cursor = rawDirectory;
        var index;
        if (
            scriptFile.alias === true ||
            rawDirectory.fsName !== expectedPath
        ) {
            throw new Error("Raw evidence directory is missing, aliased, or outside the exporter root");
        }
        for (index = 0; index < expectedNames.length; index += 1) {
            if (
                cursor === null ||
                !cursor.exists ||
                cursor.alias === true ||
                cursor.name !== expectedNames[index]
            ) {
                throw new Error("Raw evidence ancestor chain is missing, aliased, or redirected");
            }
            if (
                index === expectedNames.length - 1 &&
                cursor.fsName !== exporterRoot.fsName
            ) {
                throw new Error("Raw evidence ancestor chain does not terminate at the exporter root");
            }
            cursor = cursor.parent;
        }
    }

    function assertSafeNewEvidenceTarget(file, label) {
        assertSafeRawDirectory();
        if (
            file.parent.fsName !== rawDirectory.fsName ||
            file.alias === true ||
            file.exists
        ) {
            throw new Error(label + " must be a new non-alias file inside the raw evidence directory");
        }
    }

    function temporaryEvidenceFile(target) {
        var suffix = String(new Date().getTime()) + "-" +
            String(Math.floor(Math.random() * 1000000000));
        var temporary = new File(
            rawDirectory.fsName + "/." + target.name + "." + suffix + ".tmp"
        );
        if (temporary.alias === true || temporary.exists) {
            throw new Error("Cannot reserve a safe temporary evidence sibling");
        }
        return temporary;
    }

    function removeOwnedTemporary(file) {
        assertSafeRawDirectory();
        if (
            file !== null &&
            file.parent.fsName === rawDirectory.fsName &&
            file.alias !== true &&
            file.exists &&
            !file.remove()
        ) {
            throw new Error("Cannot remove an owned temporary evidence file");
        }
    }

    function writeEvidencePair(duplicateValue, postResendValue) {
        var duplicateTemporary = null;
        var postResendTemporary = null;
        var duplicatePublished = false;
        var postResendPublished = false;
        assertSafeNewEvidenceTarget(
            duplicateEvidenceFile,
            "Duplicate-result evidence"
        );
        assertSafeNewEvidenceTarget(
            postResendAuditFile,
            "Post-resend audit evidence"
        );
        try {
            duplicateTemporary = temporaryEvidenceFile(duplicateEvidenceFile);
            postResendTemporary = temporaryEvidenceFile(postResendAuditFile);
            Video001ExporterImporter.writeUtf8(
                duplicateTemporary,
                JSON.stringify(duplicateValue, null, 2) + "\n"
            );
            Video001ExporterImporter.writeUtf8(
                postResendTemporary,
                JSON.stringify(postResendValue, null, 2) + "\n"
            );
            assertSafeNewEvidenceTarget(
                duplicateEvidenceFile,
                "Duplicate-result evidence"
            );
            assertSafeNewEvidenceTarget(
                postResendAuditFile,
                "Post-resend audit evidence"
            );
            if (!duplicateTemporary.rename(duplicateEvidenceFile.name)) {
                throw new Error("Cannot publish duplicate-result evidence");
            }
            duplicatePublished = true;
            if (!postResendTemporary.rename(postResendAuditFile.name)) {
                throw new Error("Cannot publish post-resend audit evidence");
            }
            postResendPublished = true;
        } catch (writeError) {
            if (duplicatePublished) {
                removeOwnedTemporary(new File(duplicateEvidenceFile.fsName));
            }
            if (postResendPublished) {
                removeOwnedTemporary(new File(postResendAuditFile.fsName));
            }
            throw writeError;
        } finally {
            if (!duplicatePublished) {
                removeOwnedTemporary(duplicateTemporary);
            }
            if (!postResendPublished) {
                removeOwnedTemporary(postResendTemporary);
            }
        }
    }

    function isoTimestamp() {
        var date = new Date();
        function pad(value, width) {
            var result = String(value);
            while (result.length < width) {
                result = "0" + result;
            }
            return result;
        }
        return (
            pad(date.getUTCFullYear(), 4) + "-" +
            pad(date.getUTCMonth() + 1, 2) + "-" +
            pad(date.getUTCDate(), 2) + "T" +
            pad(date.getUTCHours(), 2) + ":" +
            pad(date.getUTCMinutes(), 2) + ":" +
            pad(date.getUTCSeconds(), 2) + "." +
            pad(date.getUTCMilliseconds(), 3) + "Z"
        );
    }

    function queuedPackageCount() {
        var files;
        var count = 0;
        var index;
        var file;
        if (!incomingFolder.exists) {
            return 0;
        }
        files = incomingFolder.getFiles();
        for (index = 0; index < files.length; index += 1) {
            file = files[index];
            if (
                file instanceof File &&
                /^[0-9a-f]{64}\.video001-ae\.json$/.test(file.name)
            ) {
                count += 1;
            }
        }
        return count;
    }

    function itemKind(item) {
        if (item instanceof CompItem) {
            return "comp";
        }
        if (item instanceof FootageItem) {
            return "footage";
        }
        if (item instanceof FolderItem) {
            return "folder";
        }
        return "other";
    }

    function itemRecord(item, index) {
        var kind = itemKind(item);
        var record = {
            index: index,
            name: String(item.name),
            kind: kind,
            parentName: item.parentFolder === null ||
                item.parentFolder === undefined ||
                item.parentFolder === app.project.rootFolder
                ? ""
                : String(item.parentFolder.name),
            width: null,
            height: null,
            duration: null,
            frameRate: null,
            layerCount: null
        };
        if (kind === "comp") {
            record.width = item.width;
            record.height = item.height;
            record.duration = item.duration;
            record.frameRate = item.frameRate;
            record.layerCount = item.numLayers;
        } else if (kind === "footage") {
            record.width = item.width;
            record.height = item.height;
            record.duration = item.duration;
            record.frameRate = item.frameRate;
        }
        return record;
    }

    function projectSnapshot() {
        var items = [];
        var index;
        var name;
        var v002Count = 0;
        var masterV001Count = 0;
        var shotV001Count = 0;
        for (index = 1; index <= app.project.numItems; index += 1) {
            items[items.length] = itemRecord(app.project.item(index), index);
            name = String(app.project.item(index).name);
            if (/_v002$/.test(name)) {
                v002Count += 1;
            }
            if (name === "VIDEO001_MASTER_v001") {
                masterV001Count += 1;
            }
            if (/^S001_SH[0-9]{2}_.+_v001$/.test(name)) {
                shotV001Count += 1;
            }
        }
        return {
            itemCount: app.project.numItems,
            queueCount: queuedPackageCount(),
            v002Count: v002Count,
            masterV001Count: masterV001Count,
            shotV001Count: shotV001Count,
            items: items
        };
    }

    function sameJson(left, right) {
        return JSON.stringify(left) === JSON.stringify(right);
    }

    if (
        app.project === null ||
        app.project.file === null ||
        app.project.file.fsName !== EXPECTED_PROJECT_PATH
    ) {
        throw new Error(
            "Refusing duplicate evidence capture outside " + EXPECTED_PROJECT_PATH
        );
    }
    if (!rawDirectory.exists || !timingFile.exists) {
        throw new Error("Committed evidence or canonical timing directory is unavailable");
    }
    assertSafeNewEvidenceTarget(
        duplicateEvidenceFile,
        "Duplicate-result evidence"
    );
    assertSafeNewEvidenceTarget(
        postResendAuditFile,
        "Post-resend audit evidence"
    );

    witness = readJson(witnessFile, "Duplicate resend witness");
    if (
        ownKeyCount(witness) !== 3 ||
        requireString(witness.sessionId, "Witness session ID").length === 0 ||
        !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
            requireString(witness.requestId, "Witness request ID")
        ) ||
        !/^[0-9a-f]{64}$/.test(
            requireString(witness.contentHash, "Witness content hash")
        )
    ) {
        throw new Error("Duplicate resend witness identity is invalid");
    }

    queuePackage = new File(
        incomingFolder.fsName + "/" + witness.contentHash + PACKAGE_SUFFIX
    );
    if (!queuePackage.exists) {
        throw new Error("The witnessed duplicate package is not queued");
    }

    before = projectSnapshot();
    if (
        before.queueCount !== 1 ||
        before.v002Count !== 0 ||
        before.masterV001Count !== 1 ||
        before.shotV001Count !== 48
    ) {
        throw new Error("The pre-resend project or queue snapshot is not canonical");
    }

    result = Video001ExporterImporter.importPackageFile(queuePackage, {
        allowDuplicate: false,
        removeAfterReport: true,
        queueRoot: queueRoot,
        assetRoot: assetFolder,
        reportFolder: queueRoot,
        timingFile: timingFile
    });
    after = projectSnapshot();

    if (
        result.status !== "DUPLICATE_CONTENT" ||
        result.report !== null ||
        before.itemCount !== after.itemCount ||
        !sameJson(before.items, after.items) ||
        after.queueCount !== 0 ||
        after.v002Count !== 0 ||
        after.masterV001Count !== 1 ||
        after.shotV001Count !== 48
    ) {
        throw new Error("The unchanged resend was not a verified duplicate no-op");
    }

    writeEvidencePair({
        evidenceSchemaVersion: 1,
        generator: "After Effects " + String(app.version),
        capturedAt: isoTimestamp(),
        sessionId: witness.sessionId,
        requestId: witness.requestId,
        contentHash: witness.contentHash,
        projectPath: EXPECTED_PROJECT_PATH,
        importResult: {
            status: result.status,
            report: result.report
        },
        before: before,
        after: after
    }, {
        evidenceSchemaVersion: 1,
        generator: "After Effects " + String(app.version),
        capturedAt: isoTimestamp(),
        sessionId: witness.sessionId,
        requestId: witness.requestId,
        contentHash: witness.contentHash,
        projectPath: EXPECTED_PROJECT_PATH,
        snapshot: projectSnapshot()
    });

    alert("Duplicate resend evidence captured: DUPLICATE_CONTENT, project unchanged.");
}());
