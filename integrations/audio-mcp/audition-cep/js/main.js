(function () {
  "use strict";

  var PROTOCOL = "audio-mcp-audition/1";
  var MAX_MESSAGE_BYTES = 65536;
  var RECONNECT_DELAYS = [1000, 2000, 5000, 10000];
  var config = null;
  var socket = null;
  var authenticated = false;
  var reconnectIndex = 0;
  var reconnectTimer = null;

  function setStatus(id, value) {
    var element = document.getElementById(id);
    if (element) {
      element.textContent = value;
    }
  }

  function userDataPath() {
    var value = window.AudioMcpCep.userDataPath();
    value = String(value).replace(/^file:\/\//, "");
    try {
      value = decodeURI(value);
    } catch (ignored) {
      return "";
    }
    return value.replace(/\/+$/, "");
  }

  function loadConfiguration() {
    var base = userDataPath();
    var result;
    var parsed;
    if (!base) {
      return null;
    }
    result = window.AudioMcpCep.readFile(
      base + "/audio-mcp/audition.json"
    );
    if (!result || result.err !== 0 || typeof result.data !== "string") {
      return null;
    }
    try {
      parsed = JSON.parse(result.data);
    } catch (ignored) {
      return null;
    }
    if (
      !parsed ||
      parsed.host !== "127.0.0.1" ||
      typeof parsed.port !== "number" ||
      Math.floor(parsed.port) !== parsed.port ||
      parsed.port < 1024 ||
      parsed.port > 65535 ||
      typeof parsed.secret !== "string" ||
      !/^[0-9a-f]{64}$/.test(parsed.secret)
    ) {
      return null;
    }
    return {
      host: "127.0.0.1",
      port: parsed.port,
      secret: parsed.secret
    };
  }

  function byteLength(value) {
    try {
      return unescape(encodeURIComponent(value)).length;
    } catch (ignored) {
      return MAX_MESSAGE_BYTES + 1;
    }
  }

  function exactEnvelope(value) {
    var keys;
    if (!value || Object.prototype.toString.call(value) !== "[object Object]") {
      return false;
    }
    keys = Object.keys(value).sort();
    return (
      keys.join(",") ===
      "arguments,deadline_ms,operation,protocol,request_id"
    );
  }

  function sendResponse(requestId, ok, value) {
    var response = {
      protocol: PROTOCOL,
      request_id: requestId,
      ok: ok
    };
    if (ok) {
      response.result = value;
    } else {
      response.error = value;
    }
    if (socket && socket.readyState === 1 && authenticated) {
      socket.send(JSON.stringify(response));
    }
  }

  function safeError(error) {
    if (
      !error ||
      !isSafeErrorCode(error.code) ||
      typeof error.message !== "string" ||
      error.message.length === 0 ||
      error.message.length > 2048 ||
      typeof error.retryable !== "boolean"
    ) {
      return {
        code: "PROTOCOL_ERROR",
        message: "CEP received an invalid host error.",
        retryable: false
      };
    }
    return {
      code: error.code,
      message: error.message,
      retryable: error.retryable
    };
  }

  function isSafeErrorCode(code) {
    switch (code) {
    case "INVALID_ARGUMENT":
    case "APPLICATION_UNAVAILABLE":
    case "DOCUMENT_NOT_OPEN":
    case "OPERATION_NOT_ALLOWED":
    case "UNSUPPORTED_OPERATION":
    case "APPLICATION_ERROR":
    case "PROTOCOL_ERROR":
      return true;
    default:
      return false;
    }
  }

  function processRequest(raw) {
    var request;
    var completed = false;
    var timer;
    if (
      typeof raw !== "string" ||
      byteLength(raw) > MAX_MESSAGE_BYTES
    ) {
      socket.close(1009, "Message too large");
      return;
    }
    try {
      request = JSON.parse(raw);
    } catch (ignored) {
      socket.close(1002, "Invalid protocol message");
      return;
    }
    if (
      !exactEnvelope(request) ||
      request.protocol !== PROTOCOL ||
      typeof request.request_id !== "string" ||
      request.request_id.length === 0 ||
      typeof request.operation !== "string" ||
      !request.arguments ||
      Object.prototype.toString.call(request.arguments) !== "[object Object]" ||
      typeof request.deadline_ms !== "number" ||
      Math.floor(request.deadline_ms) !== request.deadline_ms ||
      request.deadline_ms < 1 ||
      request.deadline_ms > 60000
    ) {
      socket.close(1002, "Invalid protocol envelope");
      return;
    }

    if (window.AudioMcpDispatcher.isAllowed(request.operation)) {
      setStatus("last-operation", request.operation);
    }
    timer = setTimeout(function () {
      if (!completed) {
        completed = true;
        sendResponse(
          request.request_id,
          false,
          {
            code: "BRIDGE_TIMEOUT",
            message: "Audition host call exceeded the request deadline.",
            retryable: false
          }
        );
      }
    }, request.deadline_ms);

    window.AudioMcpDispatcher.dispatch(
      request.operation,
      request.arguments,
      function (error, result) {
        if (completed) {
          return;
        }
        completed = true;
        clearTimeout(timer);
        if (error) {
          sendResponse(request.request_id, false, safeError(error));
        } else {
          sendResponse(request.request_id, true, result);
        }
      }
    );
  }

  function scheduleReconnect() {
    var delay;
    if (!config || reconnectTimer !== null) {
      return;
    }
    delay = RECONNECT_DELAYS[
      Math.min(reconnectIndex, RECONNECT_DELAYS.length - 1)
    ];
    reconnectIndex = Math.min(
      reconnectIndex + 1,
      RECONNECT_DELAYS.length - 1
    );
    reconnectTimer = setTimeout(function () {
      reconnectTimer = null;
      connect();
    }, delay);
  }

  function connect() {
    authenticated = false;
    setStatus("bridge-status", "connecting");
    try {
      socket = new WebSocket(
        "ws://127.0.0.1:" + config.port
      );
    } catch (ignored) {
      setStatus("bridge-status", "disconnected");
      scheduleReconnect();
      return;
    }
    socket.onopen = function () {
      socket.send(
        JSON.stringify({
          type: "authenticate",
          secret: config.secret
        })
      );
    };
    socket.onmessage = function (event) {
      var message;
      if (!authenticated) {
        try {
          message = JSON.parse(event.data);
        } catch (ignored) {
          socket.close(1008, "Authentication failed");
          return;
        }
        if (
          message &&
          message.type === "authenticated" &&
          Object.keys(message).length === 1
        ) {
          authenticated = true;
          reconnectIndex = 0;
          setStatus("bridge-status", "authenticated");
        } else {
          socket.close(1008, "Authentication failed");
        }
        return;
      }
      processRequest(event.data);
    };
    socket.onerror = function () {
      if (socket) {
        socket.close();
      }
    };
    socket.onclose = function () {
      authenticated = false;
      setStatus("bridge-status", "disconnected");
      scheduleReconnect();
    };
  }

  function start() {
    config = loadConfiguration();
    if (!config) {
      setStatus("configuration-status", "error");
      setStatus("bridge-status", "disconnected");
      return;
    }
    setStatus("configuration-status", "loaded");
    connect();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
}());
