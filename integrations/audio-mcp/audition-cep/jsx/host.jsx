var AudioMcpHost = AudioMcpHost || {};

(function (host) {
  "use strict";

  function quote(value) {
    var text = String(value);
    var result = '"';
    var character;
    var code;
    var index;
    var hex;
    for (index = 0; index < text.length; index += 1) {
      character = text.charAt(index);
      code = text.charCodeAt(index);
      if (character === '"') {
        result += '\\"';
      } else if (character === "\\") {
        result += "\\\\";
      } else if (code === 8) {
        result += "\\b";
      } else if (code === 9) {
        result += "\\t";
      } else if (code === 10) {
        result += "\\n";
      } else if (code === 12) {
        result += "\\f";
      } else if (code === 13) {
        result += "\\r";
      } else if (code < 32) {
        hex = code.toString(16);
        result += "\\u" + ("0000" + hex).slice(-4);
      } else {
        result += character;
      }
    }
    return result + '"';
  }

  function encode(value) {
    var type = typeof value;
    var parts;
    var key;
    var index;
    if (value === null) {
      return "null";
    }
    if (type === "boolean") {
      return value ? "true" : "false";
    }
    if (type === "number") {
      if (!isFinite(value)) {
        throw new Error("Non-finite numbers are unsupported.");
      }
      return String(value);
    }
    if (type === "string") {
      return quote(value);
    }
    if (value instanceof Array) {
      parts = [];
      for (index = 0; index < value.length; index += 1) {
        parts.push(encode(value[index]));
      }
      return "[" + parts.join(",") + "]";
    }
    if (type === "object") {
      parts = [];
      for (key in value) {
        if (Object.prototype.hasOwnProperty.call(value, key)) {
          parts.push(quote(key) + ":" + encode(value[key]));
        }
      }
      return "{" + parts.join(",") + "}";
    }
    throw new Error("Unsupported response value.");
  }

  function success(result) {
    return encode({ok: true, result: result});
  }

  function failure(code, message, retryable) {
    return encode({
      ok: false,
      error: {
        code: code,
        message: message,
        retryable: retryable
      }
    });
  }

  function run(action) {
    try {
      return success(action());
    } catch (ignored) {
      return failure(
        "APPLICATION_ERROR",
        "Adobe Audition could not complete the fixed operation.",
        false
      );
    }
  }

  function unsupported(message) {
    return failure("UNSUPPORTED_OPERATION", message, false);
  }

  function activeDocument() {
    if (!app.activeDocument) {
      return null;
    }
    return app.activeDocument;
  }

  function typeName(value) {
    if (
      value &&
      value.reflect &&
      typeof value.reflect.name === "string"
    ) {
      return value.reflect.name;
    }
    return "";
  }

  function hasMember(value, name) {
    var reflection;
    var groups;
    var groupIndex;
    var memberIndex;
    if (!value || !value.reflect) {
      return false;
    }
    reflection = value.reflect;
    groups = [reflection.properties, reflection.methods];
    for (groupIndex = 0; groupIndex < groups.length; groupIndex += 1) {
      if (!groups[groupIndex]) {
        continue;
      }
      for (
        memberIndex = 0;
        memberIndex < groups[groupIndex].length;
        memberIndex += 1
      ) {
        if (groups[groupIndex][memberIndex].name === name) {
          return true;
        }
      }
    }
    return false;
  }

  function documentResult(document) {
    return {
      display_name: document.displayName ? String(document.displayName) : "",
      id: document.id === undefined ? null : String(document.id),
      path: document.path ? String(document.path) : null,
      type: typeName(document),
      sample_rate: Number(document.sampleRate),
      duration_samples: Number(document.duration),
      playhead_samples: Number(document.playheadPosition)
    };
  }

  function requireDocument() {
    var document = activeDocument();
    if (!document) {
      return null;
    }
    return document;
  }

  host.getStatus = function () {
    return run(function () {
      var document = activeDocument();
      return {
        application: {
          name: "Adobe Audition",
          version: String(app.version),
          build_number: String(app.buildNumber)
        },
        document_open: document !== null,
        document_type: document ? typeName(document) : null,
        transport_available: app.transport !== null
      };
    });
  };

  host.getDocument = function () {
    var document = requireDocument();
    if (!document) {
      return failure(
        "DOCUMENT_NOT_OPEN",
        "No active Adobe Audition document is open.",
        false
      );
    }
    return run(function () {
      return documentResult(document);
    });
  };

  host.getSelection = function () {
    var document = requireDocument();
    var selection;
    if (!document) {
      return failure(
        "DOCUMENT_NOT_OPEN",
        "No active Adobe Audition document is open.",
        false
      );
    }
    if (!hasMember(document, "timeSelection")) {
      return unsupported(
        "This Audition version does not expose a safe timeSelection property."
      );
    }
    try {
      selection = document.timeSelection;
    } catch (ignored) {
      return unsupported(
        "This Audition version cannot read the fixed timeSelection property."
      );
    }
    if (
      !selection ||
      !hasMember(selection, "start") ||
      !hasMember(selection, "end")
    ) {
      return unsupported(
        "This Audition version exposes an unrecognized timeSelection shape."
      );
    }
    return run(function () {
      return {
        playhead_samples: Number(document.playheadPosition),
        start_samples: Number(selection.start),
        end_samples: Number(selection.end)
      };
    });
  };

  host.setPlayhead = function (seconds) {
    var document = requireDocument();
    if (!document) {
      return failure(
        "DOCUMENT_NOT_OPEN",
        "No active Adobe Audition document is open.",
        false
      );
    }
    if (
      typeof seconds !== "number" ||
      !isFinite(seconds) ||
      seconds < 0
    ) {
      return failure("INVALID_ARGUMENT", "Invalid playhead time.", false);
    }
    return run(function () {
      document.playheadPosition = Math.round(seconds * document.sampleRate);
      return {playhead_samples: Number(document.playheadPosition)};
    });
  };

  host.setSelection = function (startSeconds, endSeconds) {
    var document = requireDocument();
    var inCommand;
    var outCommand;
    if (!document) {
      return failure(
        "DOCUMENT_NOT_OPEN",
        "No active Adobe Audition document is open.",
        false
      );
    }
    if (
      typeof startSeconds !== "number" ||
      typeof endSeconds !== "number" ||
      !isFinite(startSeconds) ||
      !isFinite(endSeconds) ||
      startSeconds < 0 ||
      endSeconds <= startSeconds
    ) {
      return failure("INVALID_ARGUMENT", "Invalid selection range.", false);
    }
    if (
      typeof Application.COMMAND_EDIT_SETINPOINTTOCTI === "undefined" ||
      typeof Application.COMMAND_EDIT_SETOUTPOINTTOCTI === "undefined"
    ) {
      return unsupported(
        "This Audition version lacks fixed selection command constants."
      );
    }
    inCommand = Application.COMMAND_EDIT_SETINPOINTTOCTI;
    outCommand = Application.COMMAND_EDIT_SETOUTPOINTTOCTI;
    if (!app.isCommandEnabled(inCommand) || !app.isCommandEnabled(outCommand)) {
      return unsupported("Selection commands are not enabled in this context.");
    }
    return run(function () {
      document.playheadPosition = Math.round(
        startSeconds * document.sampleRate
      );
      app.invokeCommand(inCommand);
      document.playheadPosition = Math.round(
        endSeconds * document.sampleRate
      );
      app.invokeCommand(outCommand);
      return {
        start_seconds: startSeconds,
        end_seconds: endSeconds
      };
    });
  };

  host.play = function () {
    return run(function () {
      app.transport.play();
      return {playing: true};
    });
  };

  host.pause = function () {
    return run(function () {
      app.transport.pause();
      return {paused: true};
    });
  };

  host.stop = function () {
    return run(function () {
      app.transport.stop();
      return {stopped: true};
    });
  };

  host.record = function () {
    return run(function () {
      app.transport.record();
      return {recording_started: true};
    });
  };

  host.openDocument = function (path) {
    if (typeof path !== "string" || path.length === 0) {
      return failure("INVALID_ARGUMENT", "Invalid document path.", false);
    }
    return run(function () {
      var parameter = new DocumentOpenParameter(path);
      var document = app.openDocument(parameter);
      return {
        opened: document !== null,
        document_type: document ? typeName(document) : null
      };
    });
  };

  host.importMedia = function (path, trackIndex) {
    var target = requireDocument();
    var track;
    if (!target) {
      return failure(
        "DOCUMENT_NOT_OPEN",
        "No active Adobe Audition document is open.",
        false
      );
    }
    if (
      typeName(target) !== "MultitrackDocument" ||
      !hasMember(target, "audioTracks") ||
      !hasMember(target, "activate")
    ) {
      return unsupported(
        "The active document does not expose safe multitrack import APIs."
      );
    }
    if (
      typeof path !== "string" ||
      path.length === 0 ||
      typeof trackIndex !== "number" ||
      !isFinite(trackIndex) ||
      Math.floor(trackIndex) !== trackIndex ||
      trackIndex < 0 ||
      trackIndex >= target.audioTracks.length
    ) {
      return failure("INVALID_ARGUMENT", "Invalid import target.", false);
    }
    track = target.audioTracks[trackIndex];
    if (
      !track ||
      !hasMember(track, "audioClips") ||
      !hasMember(track.audioClips, "add")
    ) {
      return unsupported(
        "The target track does not expose a safe audioClips.add method."
      );
    }
    return run(function () {
      var parameter = new DocumentOpenParameter(path);
      var source = app.openDocument(parameter);
      if (!source || typeName(source) !== "WaveDocument") {
        throw new Error("Source is not a wave document.");
      }
      target.activate();
      track.audioClips.add(source, Number(target.playheadPosition));
      return {imported: true, track_index: trackIndex};
    });
  };

  host.save = function () {
    var saveCommand;
    if (!requireDocument()) {
      return failure(
        "DOCUMENT_NOT_OPEN",
        "No active Adobe Audition document is open.",
        false
      );
    }
    if (typeof Application.COMMAND_FILE_SAVE === "undefined") {
      return unsupported("This Audition version lacks the fixed save command.");
    }
    saveCommand = Application.COMMAND_FILE_SAVE;
    if (!app.isCommandEnabled(saveCommand)) {
      return unsupported("Save is not enabled for the active document.");
    }
    return run(function () {
      app.invokeCommand(saveCommand);
      return {saved: true};
    });
  };

  host.exportDocument = function (path) {
    var document = requireDocument();
    if (!document) {
      return failure(
        "DOCUMENT_NOT_OPEN",
        "No active Adobe Audition document is open.",
        false
      );
    }
    if (typeName(document) !== "WaveDocument") {
      return unsupported(
        "Safe export is available only for an active WaveDocument."
      );
    }
    if (typeof path !== "string" || path.length === 0) {
      return failure("INVALID_ARGUMENT", "Invalid export path.", false);
    }
    if (new File(path).exists) {
      return failure(
        "DESTINATION_EXISTS",
        "Export destination already exists.",
        false
      );
    }
    return run(function () {
      document.saveAs(path, true);
      return {exported: true};
    });
  };

  host.applyFavorite = function (name) {
    var document = requireDocument();
    if (!document) {
      return failure(
        "DOCUMENT_NOT_OPEN",
        "No active Adobe Audition document is open.",
        false
      );
    }
    if (typeName(document) !== "WaveDocument") {
      return unsupported(
        "Favorites can be safely applied only to a WaveDocument."
      );
    }
    if (typeof name !== "string" || name.length === 0) {
      return failure("INVALID_ARGUMENT", "Invalid favorite name.", false);
    }
    return run(function () {
      document.applyFavorite(name);
      return {applied: true};
    });
  };
}(AudioMcpHost));
