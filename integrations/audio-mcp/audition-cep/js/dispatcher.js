(function () {
  "use strict";

  var handlers = {};

  function hasOwn(value, name) {
    return Object.prototype.hasOwnProperty.call(value, name);
  }

  function exactArguments(args, names) {
    var keys;
    var index;
    if (!args || Object.prototype.toString.call(args) !== "[object Object]") {
      throw new Error("Arguments must be an object.");
    }
    keys = Object.keys(args);
    if (keys.length !== names.length) {
      throw new Error("Arguments do not match the fixed operation schema.");
    }
    for (index = 0; index < names.length; index += 1) {
      if (!hasOwn(args, names[index])) {
        throw new Error("A required argument is missing.");
      }
    }
  }

  function finiteNumber(value) {
    if (typeof value !== "number" || !isFinite(value) || value < 0) {
      throw new Error("Expected a non-negative finite number.");
    }
    return value;
  }

  function trackIndex(value) {
    if (
      typeof value !== "number" ||
      !isFinite(value) ||
      Math.floor(value) !== value ||
      value < 0 ||
      value > 127
    ) {
      throw new Error("Expected a track index from 0 to 127.");
    }
    return value;
  }

  function boundedString(value, maximumLength) {
    if (
      typeof value !== "string" ||
      value.length === 0 ||
      value.length > maximumLength
    ) {
      throw new Error("Expected a bounded non-empty string.");
    }
    return value;
  }

  function quoted(value) {
    return JSON.stringify(value)
      .replace(/\u2028/g, "\\u2028")
      .replace(/\u2029/g, "\\u2029");
  }

  function noArguments(args) {
    exactArguments(args, []);
  }

  handlers.get_status = function (args) {
    noArguments(args);
    return "AudioMcpHost.getStatus()";
  };
  handlers.get_document = function (args) {
    noArguments(args);
    return "AudioMcpHost.getDocument()";
  };
  handlers.get_selection = function (args) {
    noArguments(args);
    return "AudioMcpHost.getSelection()";
  };
  handlers.set_playhead = function (args) {
    exactArguments(args, ["seconds"]);
    return "AudioMcpHost.setPlayhead(" + finiteNumber(args.seconds) + ")";
  };
  handlers.set_selection = function (args) {
    var start;
    var end;
    exactArguments(args, ["start_seconds", "end_seconds"]);
    start = finiteNumber(args.start_seconds);
    end = finiteNumber(args.end_seconds);
    if (end <= start) {
      throw new Error("Selection end must be greater than start.");
    }
    return "AudioMcpHost.setSelection(" + start + "," + end + ")";
  };
  handlers.play = function (args) {
    noArguments(args);
    return "AudioMcpHost.play()";
  };
  handlers.pause = function (args) {
    noArguments(args);
    return "AudioMcpHost.pause()";
  };
  handlers.stop = function (args) {
    noArguments(args);
    return "AudioMcpHost.stop()";
  };
  handlers.record = function (args) {
    noArguments(args);
    return "AudioMcpHost.record()";
  };
  handlers.open = function (args) {
    exactArguments(args, ["path"]);
    return (
      "AudioMcpHost.openDocument(" +
      quoted(boundedString(args.path, 4096)) +
      ")"
    );
  };
  handlers.import_media = function (args) {
    exactArguments(args, ["path", "track_index"]);
    return (
      "AudioMcpHost.importMedia(" +
      quoted(boundedString(args.path, 4096)) +
      "," +
      trackIndex(args.track_index) +
      ")"
    );
  };
  handlers.save = function (args) {
    noArguments(args);
    return "AudioMcpHost.save()";
  };
  handlers.export = function (args) {
    exactArguments(args, ["path"]);
    return (
      "AudioMcpHost.exportDocument(" +
      quoted(boundedString(args.path, 4096)) +
      ")"
    );
  };
  handlers.apply_favorite = function (args) {
    exactArguments(args, ["favorite"]);
    return (
      "AudioMcpHost.applyFavorite(" +
      quoted(boundedString(args.favorite, 256)) +
      ")"
    );
  };

  function publicError(code, message, retryable) {
    return {
      code: code,
      message: message,
      retryable: retryable
    };
  }

  function parseHostResult(raw) {
    var parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (ignored) {
      return {
        error: publicError(
          "PROTOCOL_ERROR",
          "Audition host returned an invalid response.",
          false
        )
      };
    }
    if (
      parsed &&
      parsed.ok === true &&
      parsed.result &&
      Object.prototype.toString.call(parsed.result) === "[object Object]"
    ) {
      return {result: parsed.result};
    }
    if (
      parsed &&
      parsed.ok === false &&
      parsed.error &&
      typeof parsed.error.code === "string" &&
      typeof parsed.error.message === "string" &&
      typeof parsed.error.retryable === "boolean"
    ) {
      return {error: parsed.error};
    }
    return {
      error: publicError(
        "PROTOCOL_ERROR",
        "Audition host response shape is invalid.",
        false
      )
    };
  }

  function runFixedHostCall(hostCall, callback) {
    try {
      window.__adobe_cep__.evalScript(hostCall, function (raw) {
        var parsed = parseHostResult(raw);
        if (parsed.error) {
          callback(parsed.error, null);
        } else {
          callback(null, parsed.result);
        }
      });
    } catch (ignored) {
      callback(
        publicError(
          "APPLICATION_ERROR",
          "Audition rejected the fixed host call.",
          false
        ),
        null
      );
    }
  }

  function handlerFor(operation) {
    switch (operation) {
    case "get_status":
      return handlers.get_status;
    case "get_document":
      return handlers.get_document;
    case "get_selection":
      return handlers.get_selection;
    case "set_playhead":
      return handlers.set_playhead;
    case "set_selection":
      return handlers.set_selection;
    case "play":
      return handlers.play;
    case "pause":
      return handlers.pause;
    case "stop":
      return handlers.stop;
    case "record":
      return handlers.record;
    case "open":
      return handlers.open;
    case "import_media":
      return handlers.import_media;
    case "save":
      return handlers.save;
    case "export":
      return handlers.export;
    case "apply_favorite":
      return handlers.apply_favorite;
    default:
      return null;
    }
  }

  window.AudioMcpDispatcher = {
    isAllowed: function (operation) {
      return typeof operation === "string" && handlerFor(operation) !== null;
    },
    dispatch: function (operation, args, callback) {
      var hostCall;
      var handler = handlerFor(operation);
      if (handler === null) {
        callback(
          publicError(
            "OPERATION_NOT_ALLOWED",
            "Operation is not in the CEP allowlist.",
            false
          ),
          null
        );
        return;
      }
      try {
        hostCall = handler(args);
      } catch (ignored) {
        callback(
          publicError(
            "INVALID_ARGUMENT",
            "Operation arguments failed CEP validation.",
            false
          ),
          null
        );
        return;
      }
      runFixedHostCall(hostCall, callback);
    }
  };
}());
