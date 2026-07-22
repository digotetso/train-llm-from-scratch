/*
 * Video 001 Figma to After Effects Exporter ScriptUI panel.
 *
 * This file uses concepts from AEUX and has been modified for this exporter.
 * Copyright 2017 Google Inc.
 * Licensed under the Apache License, Version 2.0.
 */

var Video001ExporterPanel = (function (thisObject, importer) {
    var POLL_INTERVAL_MS = 1000;
    var PACKAGE_SUFFIX = ".video001-ae.json";
    var scriptFile = new File($.fileName);
    var scriptDirectory = scriptFile.parent;
    var bridgeCli = new File(scriptDirectory.parent.fsName + "/bridge/video001-bridge.mjs");
    var queueRoot = new Folder(Folder.userData.fsName + "/Video001FigmaAEExporter");
    var incomingFolder = new Folder(queueRoot.fsName + "/incoming");
    var assetFolder = new Folder(queueRoot.fsName + "/assets");
    var stateFile = new File(queueRoot.fsName + "/state.json");
    var authFile = new File(queueRoot.fsName + "/auth.json");
    var timingDirectory = scriptDirectory;
    var timingFile;
    var palette;
    var statusText;
    var pairingCodeText;
    var expiryText;
    var reportText;
    var pollTaskId = 0;
    var resetPending = false;
    var closing = false;
    var index;

    for (index = 0; index < 3; index += 1) {
        timingDirectory = timingDirectory.parent;
    }
    timingFile = new File(timingDirectory.fsName + "/figma-scenes.json");

    function trim(value) {
        return String(value).replace(/^\s+|\s+$/g, "");
    }

    function quoteShellArgument(value) {
        return "'" + String(value).replace(/'/g, "'\\''") + "'";
    }

    function redact(value) {
        var result = String(value);
        result = result.replace(/("(?:token|pairingCode|authorization)"\s*:\s*")[^"]*(")/gi, "$1[REDACTED]$2");
        result = result.replace(/Bearer\s+[A-Za-z0-9._~-]+/gi, "Bearer [REDACTED]");
        result = result.replace(/\b[0-9]{6}\b/g, "[PAIRING CODE REDACTED]");
        result = result.replace(new RegExp(Folder.userData.fsName.replace(/([\\^$.*+?()[\]{}|])/g, "\\$1"), "g"), "[USER DATA]");
        return result;
    }

    function setStatus(value) {
        if (statusText !== undefined && statusText !== null) {
            statusText.text = value;
        }
    }

    function appendReport(value) {
        var safeValue = redact(value);
        if (reportText.text.length > 0) {
            reportText.text += "\n\n";
        }
        reportText.text += safeValue;
        reportText.active = true;
    }

    function isPositiveInteger(value) {
        return typeof value === "number" && isFinite(value) && value > 0 && Math.floor(value) === value;
    }

    function readBridgeStateSnapshot() {
        var raw;
        var state;
        if (!stateFile.exists) {
            return null;
        }
        raw = importer.readUtf8(stateFile);
        state = JSON.parse(raw);
        if (
            state === null ||
            typeof state !== "object" ||
            !isPositiveInteger(state.pid) ||
            !isPositiveInteger(state.port) ||
            typeof state.pairingCode !== "string" ||
            !/^[0-9]{6}$/.test(state.pairingCode) ||
            typeof state.pairingExpiresAt !== "number" ||
            !isFinite(state.pairingExpiresAt)
        ) {
            throw new Error("Bridge state is invalid");
        }
        return { raw: raw, state: state };
    }

    function findNodeExecutable() {
        var value = trim(system.callSystem("/usr/bin/which node"));
        var file;
        if (value.length === 0 || value.charAt(0) !== "/" || /[\r\n]/.test(value)) {
            throw new Error("Node 20 or newer was not found on PATH");
        }
        file = new File(value);
        if (!file.exists) {
            throw new Error("The resolved Node executable does not exist");
        }
        return file;
    }

    function startBridge() {
        var nodeExecutable;
        var command;
        if (readLiveBridgeState() !== null) {
            setStatus("Bridge is already running");
            return;
        }
        if (!bridgeCli.exists) {
            throw new Error("Bundled exporter bridge is missing: " + bridgeCli.fsName);
        }
        nodeExecutable = findNodeExecutable();
        command = quoteShellArgument(nodeExecutable.fsName) +
            " " + quoteShellArgument(bridgeCli.fsName) +
            " --root " + quoteShellArgument(queueRoot.fsName) +
            " --port 3456 >/dev/null 2>&1 &";
        system.callSystem(command);
        setStatus("Starting exporter bridge...");
    }

    function commandPathContainsBridge(pid) {
        var firstCommand;
        var secondCommand;
        if (!isPositiveInteger(pid)) {
            return false;
        }
        firstCommand = system.callSystem("/bin/ps -p " + String(pid) + " -o command=");
        if (firstCommand.indexOf(bridgeCli.fsName) < 0) {
            return false;
        }
        secondCommand = system.callSystem("/bin/ps -p " + String(pid) + " -o command=");
        return secondCommand.indexOf(bridgeCli.fsName) >= 0;
    }

    function removeStaleBridgeState(snapshot) {
        if (!stateFile.exists) {
            return true;
        }
        if (importer.readUtf8(stateFile) !== snapshot.raw) {
            return false;
        }
        if (commandPathContainsBridge(snapshot.state.pid)) {
            return false;
        }
        if (!stateFile.remove()) {
            throw new Error("Stale exporter bridge state could not be removed");
        }
        return true;
    }

    function readLiveBridgeState() {
        var snapshot;
        var attempt;
        for (attempt = 0; attempt < 2; attempt += 1) {
            snapshot = readBridgeStateSnapshot();
            if (snapshot === null) {
                return null;
            }
            if (commandPathContainsBridge(snapshot.state.pid)) {
                return snapshot.state;
            }
            if (removeStaleBridgeState(snapshot)) {
                return null;
            }
        }
        throw new Error("Exporter bridge state changed while liveness was being verified");
    }

    function stopBridge(silent) {
        var state = readLiveBridgeState();
        if (state === null) {
            if (!silent) {
                setStatus("Bridge is stopped");
            }
            return;
        }
        if (!commandPathContainsBridge(state.pid)) {
            throw new Error("Refusing to stop PID " + state.pid + ": its command is not this exporter bridge");
        }
        system.callSystem("/bin/kill -TERM " + String(state.pid));
        if (!silent) {
            setStatus("Stopping exporter bridge...");
        }
    }

    function completeResetPairing() {
        if (readLiveBridgeState() !== null) {
            return false;
        }
        if (authFile.exists && !authFile.remove()) {
            throw new Error("Pairing state could not be reset");
        }
        resetPending = false;
        pairingCodeText.text = "------";
        expiryText.text = "Not paired";
        setStatus("Pairing reset; start the bridge to create a new code");
        return true;
    }

    function resetPairing() {
        if (readLiveBridgeState() === null) {
            completeResetPairing();
            return;
        }
        resetPending = true;
        stopBridge(false);
        setStatus("Stopping bridge before pairing reset...");
    }

    function queuedFiles() {
        var files;
        var result = [];
        var file;
        var fileIndex;
        if (!incomingFolder.exists) {
            return result;
        }
        files = incomingFolder.getFiles();
        for (fileIndex = 0; fileIndex < files.length; fileIndex += 1) {
            file = files[fileIndex];
            if (
                file instanceof File &&
                file.name.length === 64 + PACKAGE_SUFFIX.length &&
                file.name.substring(64) === PACKAGE_SUFFIX &&
                /^[0-9a-f]{64}$/.test(file.name.substring(0, 64))
            ) {
                result[result.length] = file;
            }
        }
        result.sort(function (first, second) {
            if (first.name < second.name) {
                return -1;
            }
            if (first.name > second.name) {
                return 1;
            }
            return 0;
        });
        return result;
    }

    function importOptions(allowDuplicate, removeAfterReport) {
        if (!timingFile.exists) {
            throw new Error("Approved Video 001 timing file is missing");
        }
        if (!queueRoot.exists && !queueRoot.create()) {
            throw new Error("Exporter queue root cannot be created");
        }
        if (!assetFolder.exists && !assetFolder.create()) {
            throw new Error("Exporter asset directory cannot be created");
        }
        return {
            allowDuplicate: allowDuplicate,
            removeAfterReport: removeAfterReport,
            queueRoot: queueRoot,
            assetRoot: assetFolder,
            reportFolder: queueRoot,
            timingFile: timingFile
        };
    }

    function displayImportResult(result) {
        if (result.status === "DUPLICATE_CONTENT") {
            setStatus("DUPLICATE_CONTENT: no comp was created");
            appendReport("DUPLICATE_CONTENT: use Import duplicate only when another immutable comp is intentional.");
            return;
        }
        setStatus("Imported " + result.report.createdCompNames.length + " versioned comp(s)");
        appendReport(JSON.stringify(result.report, null, 2));
    }

    function importSelectedFile(packageFile, allowDuplicate, removeAfterReport) {
        var result = importer.importPackageFile(
            packageFile,
            importOptions(allowDuplicate, removeAfterReport)
        );
        displayImportResult(result);
    }

    function importNext(allowDuplicate) {
        var files = queuedFiles();
        if (files.length === 0) {
            setStatus("Queue is empty");
            return;
        }
        importSelectedFile(files[0], allowDuplicate, true);
    }

    function choosePackageFile(allowDuplicate) {
        var packageFile = File.openDialog(
            "Choose a Video 001 Figma to AE package",
            function (candidate) {
                return candidate instanceof Folder ||
                    (candidate instanceof File && candidate.name.substring(candidate.name.length - PACKAGE_SUFFIX.length) === PACKAGE_SUFFIX);
            },
            false
        );
        if (packageFile !== null) {
            importSelectedFile(packageFile, allowDuplicate, false);
        }
    }

    function importFile() {
        choosePackageFile(false);
    }

    function importDuplicate() {
        choosePackageFile(true);
    }

    function guarded(action) {
        try {
            action();
        } catch (error) {
            setStatus("Exporter action failed");
            appendReport("ERROR: " + error.toString());
        }
    }

    function poll() {
        var state;
        var files;
        if (closing) {
            return;
        }
        try {
            if (resetPending && completeResetPairing()) {
                return;
            }
            state = readLiveBridgeState();
            files = queuedFiles();
            if (state === null) {
                pairingCodeText.text = "------";
                expiryText.text = "Bridge stopped";
                setStatus(files.length + " package(s) queued; bridge stopped");
            } else {
                pairingCodeText.text = state.pairingCode;
                expiryText.text = new Date(state.pairingExpiresAt).toUTCString();
                setStatus("Bridge running on 127.0.0.1:" + state.port + "; " + files.length + " package(s) queued");
            }
        } catch (pollError) {
            setStatus("Bridge or queue state is invalid");
            appendReport("POLL ERROR: " + pollError.toString());
        }
    }

    function addButton(parent, label, action) {
        var button = parent.add("button", undefined, label);
        button.onClick = function () {
            guarded(action);
        };
        return button;
    }

    function buildPalette() {
        var windowValue = thisObject instanceof Panel
            ? thisObject
            : new Window("palette", "Video 001 Figma to AE Exporter", undefined, { resizeable: true });
        var pairingGroup;
        var bridgeButtons;
        var importButtons;
        var reportLabel;

        windowValue.orientation = "column";
        windowValue.alignChildren = ["fill", "top"];
        windowValue.spacing = 8;
        windowValue.margins = 12;

        statusText = windowValue.add("statictext", undefined, "Status: initializing", { multiline: true });
        statusText.preferredSize.height = 34;

        pairingGroup = windowValue.add("group");
        pairingGroup.orientation = "row";
        pairingGroup.add("statictext", undefined, "Pairing code:");
        pairingCodeText = pairingGroup.add("statictext", undefined, "------");
        pairingCodeText.characters = 10;
        pairingGroup.add("statictext", undefined, "Expires:");
        expiryText = pairingGroup.add("statictext", undefined, "Bridge stopped");
        expiryText.characters = 28;

        bridgeButtons = windowValue.add("group");
        bridgeButtons.orientation = "row";
        addButton(bridgeButtons, "Start bridge", startBridge);
        addButton(bridgeButtons, "Stop bridge", function () { stopBridge(false); });
        addButton(bridgeButtons, "Reset pairing", resetPairing);

        importButtons = windowValue.add("group");
        importButtons.orientation = "row";
        addButton(importButtons, "Import next", function () { importNext(false); });
        addButton(importButtons, "Import file", importFile);
        addButton(importButtons, "Import duplicate", importDuplicate);

        reportLabel = windowValue.add("statictext", undefined, "Redacted report");
        reportLabel.alignment = ["left", "top"];
        reportText = windowValue.add("edittext", undefined, "", {
            multiline: true,
            scrolling: true,
            readonly: true
        });
        reportText.preferredSize = [620, 260];
        reportText.alignment = ["fill", "fill"];

        windowValue.onResizing = windowValue.onResize = function () {
            this.layout.resize();
        };
        windowValue.onClose = function () {
            closing = true;
            if (pollTaskId !== 0) {
                app.cancelTask(pollTaskId);
                pollTaskId = 0;
            }
            try {
                stopBridge(true);
            } catch (closeError) {
                appendReport("CLOSE ERROR: " + closeError.toString());
            }
            return true;
        };
        return windowValue;
    }

    palette = buildPalette();
    palette.layout.layout(true);
    palette.layout.resize();
    poll();
    pollTaskId = app.scheduleTask("Video001ExporterPanel.poll()", POLL_INTERVAL_MS, true);
    if (palette instanceof Window) {
        palette.center();
        palette.show();
    }

    return {
        poll: poll,
        startBridge: startBridge,
        stopBridge: stopBridge,
        resetPairing: resetPairing,
        importNext: importNext
    };
}(this, Video001ExporterImporter));
