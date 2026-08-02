/*
 * Direct, plugin-free Video 001 full-lesson import.
 *
 * Safety contract:
 * - run only from a new, unsaved, empty After Effects project;
 * - never open or modify the production AEP;
 * - retain any previous disposable validation AEP as a timestamped backup;
 * - import only the committed, fingerprint-verified 48-shot package.
 */

#include "../exporter/src/ae/import-core.jsxinc"
#include "../exporter/src/ae/importer.jsxinc"

(function () {
    var EXPECTED_TARGET =
        "/private/tmp/Video001-Exporter-Full-Lesson.aep";
    var EXPECTED_CONTENT_HASH =
        "da8c7f9d1100e3a415034f8c486a128e6f99bbd66c86caecb65101d63130e831";
    var EXPECTED_PACKAGE_SHA256 =
        "e00533e4bb05140b2c4b6a8de4635f726722e84c2e33c4a6466b0364a88cb97f";
    var scriptFile = new File($.fileName);
    var afterEffectsRoot = scriptFile.parent.parent;
    var exporterRoot = new Folder(
        afterEffectsRoot.fsName + "/exporter"
    );
    var packageFile = new File(
        exporterRoot.fsName +
        "/evidence/full-lesson/raw/" +
        "full-lesson-package.video001-ae.json"
    );
    var timingFile = new File(
        exporterRoot.fsName +
        "/config/video001-figma-scenes.json"
    );
    var queueRoot = new Folder(
        Folder.userData.fsName + "/Video001FigmaAEExporter"
    );
    var incomingRoot = new Folder(queueRoot.fsName + "/incoming");
    var assetRoot = new Folder(queueRoot.fsName + "/assets");
    var queuePackage = new File(
        incomingRoot.fsName + "/" +
        EXPECTED_CONTENT_HASH +
        ".video001-ae.json"
    );
    var target = new File(EXPECTED_TARGET);
    var backup = null;
    var importResult = null;
    var createdQueuePackage = false;

    File.encoding = "UTF-8";

    function timestamp() {
        var date = new Date();
        function pad(value, width) {
            var result = String(value);
            while (result.length < width) {
                result = "0" + result;
            }
            return result;
        }
        return (
            pad(date.getUTCFullYear(), 4) +
            pad(date.getUTCMonth() + 1, 2) +
            pad(date.getUTCDate(), 2) + "T" +
            pad(date.getUTCHours(), 2) +
            pad(date.getUTCMinutes(), 2) +
            pad(date.getUTCSeconds(), 2) + "Z"
        );
    }

    function assertFreshProject() {
        if (
            app.project.file !== null ||
            app.project.numItems !== 0
        ) {
            throw new Error(
                "Open File > New > New Project first. " +
                "The direct importer refuses every saved or non-empty project."
            );
        }
    }

    function quoteShellArgument(value) {
        return "'" + String(value).replace(/'/g, "'\\''") + "'";
    }

    function sha256File(file) {
        var output;
        var match;
        if (!file.exists || file.alias === true) {
            throw new Error(
                "Cannot hash a missing or aliased package file"
            );
        }
        output = system.callSystem(
            "/usr/bin/shasum -a 256 " +
            quoteShellArgument(file.fsName)
        );
        match = /^([0-9a-f]{64})\b/.exec(String(output));
        if (match === null) {
            throw new Error("Cannot verify package-file SHA-256");
        }
        return match[1];
    }

    function assertInputFiles() {
        if (
            scriptFile.alias === true ||
            !exporterRoot.exists ||
            exporterRoot.alias === true ||
            !packageFile.exists ||
            packageFile.alias === true ||
            !timingFile.exists ||
            timingFile.alias === true
        ) {
            throw new Error(
                "The committed exporter package or timing file is missing or aliased"
            );
        }
    }

    function preparePinnedQueuePackage() {
        if (sha256File(packageFile) !== EXPECTED_PACKAGE_SHA256) {
            throw new Error(
                "Committed package bytes do not match the pinned SHA-256"
            );
        }
        if (
            queuePackage.parent.fsName !== incomingRoot.fsName ||
            queuePackage.name !==
                EXPECTED_CONTENT_HASH + ".video001-ae.json" ||
            queuePackage.alias === true
        ) {
            throw new Error(
                "Pinned queue package is outside the trusted incoming path"
            );
        }
        if (queuePackage.exists) {
            if (sha256File(queuePackage) !== EXPECTED_PACKAGE_SHA256) {
                throw new Error(
                    "Existing queue package does not match the pinned SHA-256"
                );
            }
            return;
        }
        if (!packageFile.copy(queuePackage.fsName)) {
            throw new Error(
                "Cannot stage the pinned package in the trusted queue"
            );
        }
        createdQueuePackage = true;
        system.callSystem(
            "/bin/chmod 600 " +
            quoteShellArgument(queuePackage.fsName)
        );
        if (
            queuePackage.alias === true ||
            sha256File(queuePackage) !== EXPECTED_PACKAGE_SHA256
        ) {
            throw new Error(
                "Staged queue package does not match the pinned SHA-256"
            );
        }
    }

    function cleanupOwnedQueuePackage() {
        if (!createdQueuePackage || !queuePackage.exists) {
            return;
        }
        if (
            queuePackage.alias === true ||
            queuePackage.parent.fsName !== incomingRoot.fsName ||
            queuePackage.name !==
                EXPECTED_CONTENT_HASH + ".video001-ae.json" ||
            sha256File(queuePackage) !== EXPECTED_PACKAGE_SHA256 ||
            !queuePackage.remove()
        ) {
            throw new Error(
                "Cannot clean the owned pinned queue package safely"
            );
        }
    }

    function ensureWorkingFolder(folder, expectedParent) {
        if (
            folder.alias === true ||
            folder.parent.fsName !== expectedParent.fsName
        ) {
            throw new Error(
                "Validation working directory is outside its fixed parent"
            );
        }
        if (!folder.exists && !folder.create()) {
            throw new Error(
                "Cannot create validation working directory " +
                folder.fsName
            );
        }
        if (folder.alias === true) {
            throw new Error(
                "Validation working directory became an alias"
            );
        }
    }

    function backupExistingTarget() {
        var backupName;
        var existingTarget = new File(EXPECTED_TARGET);
        if (
            existingTarget.fsName !== EXPECTED_TARGET ||
            existingTarget.name !== "Video001-Exporter-Full-Lesson.aep" ||
            existingTarget.alias === true
        ) {
            throw new Error(
                "Validation target is outside the fixed temporary path"
            );
        }
        if (!existingTarget.exists) {
            return null;
        }
        backupName =
            "Video001-Exporter-Full-Lesson.pre-refresh-" +
            timestamp() + ".aep";
        backup = new File(existingTarget.parent.fsName + "/" + backupName);
        if (backup.exists || backup.alias === true) {
            throw new Error(
                "Cannot reserve a unique validation-project backup"
            );
        }
        if (!existingTarget.rename(backupName)) {
            throw new Error(
                "Cannot retain the previous validation AEP as a backup"
            );
        }
        return backup;
    }

    function moveFailedTargetAside() {
        var failedName;
        var failed;
        var failedTarget = new File(EXPECTED_TARGET);
        if (!failedTarget.exists || failedTarget.alias === true) {
            return;
        }
        failedName =
            "Video001-Exporter-Full-Lesson.failed-" +
            timestamp() + ".aep";
        failed = new File(failedTarget.parent.fsName + "/" + failedName);
        if (failed.exists || !failedTarget.rename(failedName)) {
            throw new Error(
                "Failed validation AEP could not be retained safely"
            );
        }
    }

    function restoreBackup() {
        if (backup === null || !backup.exists) {
            return;
        }
        if (target.exists || !backup.rename(target.name)) {
            throw new Error(
                "Previous validation AEP could not be restored"
            );
        }
    }

    function assertImportedResult(result) {
        if (
            result === null ||
            result.status !== "IMPORTED" ||
            result.report === null ||
            result.report.contentHash !== EXPECTED_CONTENT_HASH ||
            result.report.createdCompNames.length !== 48 ||
            result.report.createdMasterCompName !==
                "VIDEO001_MASTER_v001"
        ) {
            throw new Error(
                "Direct import did not create the exact trusted 48-shot master"
            );
        }
    }

    assertFreshProject();
    assertInputFiles();
    ensureWorkingFolder(queueRoot, Folder.userData);
    ensureWorkingFolder(incomingRoot, queueRoot);
    ensureWorkingFolder(assetRoot, queueRoot);
    backupExistingTarget();

    try {
        preparePinnedQueuePackage();
        importResult = Video001ExporterImporter.importPackageFile(
            queuePackage,
            {
                allowDuplicate: false,
                removeAfterReport: true,
                queueRoot: queueRoot,
                assetRoot: assetRoot,
                reportFolder: queueRoot,
                timingFile: timingFile
            }
        );
        assertImportedResult(importResult);
        if (queuePackage.exists) {
            throw new Error(
                "Accepted queue package was not consumed after import"
            );
        }
        app.project.save(target);
        if (
            app.project.file === null ||
            app.project.file.fsName !== target.fsName ||
            !target.exists ||
            app.project.dirty === true
        ) {
            throw new Error(
                "Fresh validation project did not save cleanly"
            );
        }
    } catch (importError) {
        cleanupOwnedQueuePackage();
        moveFailedTargetAside();
        restoreBackup();
        throw importError;
    }

    alert(
        "Imported 48 Figma shots into VIDEO001_MASTER_v001.\n" +
        "Saved disposable validation project:\n" +
        target.fsName +
        (
            backup === null
                ? ""
                : "\n\nPrevious validation AEP retained as:\n" +
                    backup.fsName
        )
    );
}());
