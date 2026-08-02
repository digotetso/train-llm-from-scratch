/* Assign exact installed fonts to every generated live-text layer in the current Video 001 AEP. */
(function fixVideo001Fonts() {
    var aeDir = new File($.fileName).parent;
    var reportFile = new File(aeDir.fsName + "/font-fix-report.json");
    var projectFile = new File(aeDir.fsName + "/video-001-what-ai-models-actually-do.aep");

    function writeReport(report) {
        try {
            reportFile.encoding = "UTF-8";
            if (reportFile.open("w")) {
                reportFile.write(JSON.stringify(report, null, 2));
                reportFile.close();
            }
        } catch (ignoreWriteError) {}
    }

    function requestedFont(tag) {
        var map = {
            "Sora:Bold": "Sora-Bold",
            "Sora:SemiBold": "Sora-SemiBold",
            "Sora:Medium": "Sora-Medium",
            "Sora:Regular": "Sora-Regular",
            "Inter:Medium": "Inter-Medium",
            "Inter:Regular": "Inter-Regular",
            "JetBrains_Mono:Medium": "JetBrainsMono-Medium",
            "JetBrains Mono:Medium": "JetBrainsMono-Medium"
        };
        return map[tag] || tag.replace(":", "-").replace("JetBrains_Mono", "JetBrainsMono");
    }

    function findFont(postScriptName) {
        var found = app.fonts.getFontsByPostScriptName(postScriptName);
        if (found && found.length > 0) { return found[0]; }
        return null;
    }

    app.beginUndoGroup("Fix Video 001 Fonts");
    var report = {status: "running", changedLayers: 0, skippedLayers: 0, assignments: {}, missing: {}};
    try {
        if (!app.project || app.project.numItems === 0) {
            throw new Error("Open the generated Video 001 AEP before running the font fix.");
        }
        var itemIndex;
        for (itemIndex = 1; itemIndex <= app.project.numItems; itemIndex += 1) {
            var item = app.project.item(itemIndex);
            if (!(item instanceof CompItem)) { continue; }
            var layerIndex;
            for (layerIndex = 1; layerIndex <= item.numLayers; layerIndex += 1) {
                var layer = item.layer(layerIndex);
                if (!(layer instanceof TextLayer) || String(layer.comment).indexOf("Figma live text · ") !== 0) {
                    continue;
                }
                var tag = String(layer.comment).substring("Figma live text · ".length);
                var source = layer.property("ADBE Text Properties").property("ADBE Text Document");
                var documentValue = source.value;
                var wanted = requestedFont(tag);
                if (String(documentValue.text).indexOf("→") >= 0 && tag.indexOf("Sora:") === 0) {
                    wanted = "Inter-Medium";
                }
                var font = findFont(wanted);
                if (!font) {
                    report.missing[wanted] = (report.missing[wanted] || 0) + 1;
                    report.skippedLayers += 1;
                    continue;
                }
                documentValue.fontObject = font;
                source.setValue(documentValue);
                report.assignments[wanted] = font.postScriptName;
                report.changedLayers += 1;
            }
        }
        app.project.save(projectFile);
        report.status = "complete";
        report.project = projectFile.fsName;
        report.fontServerRevision = app.fonts.fontServerRevision;
        writeReport(report);
    } catch (error) {
        report.status = "failed";
        report.error = error.toString();
        writeReport(report);
        alert("Video 001 font fix failed:\n\n" + error.toString());
    } finally {
        app.endUndoGroup();
    }
}());
