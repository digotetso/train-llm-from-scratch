import {
  contentFingerprintInput,
  validatePackage,
  type ExportFrame,
  type ExportNode,
  type ExporterPackage
} from "../shared/contract.ts";
import type { ControllerToUi, FrameSummary, UiToController } from "./controller.ts";

const EXPORT_MEDIA_TYPE = "application/vnd.video001.figma-ae+json";

type UnknownRecord = Record<string, unknown>;

export interface UiViewModel {
  frames: FrameSummary[];
  nativeCount: number;
  rasterCount: number;
  warnings: ExportFrame["warnings"];
  status: string;
  error: string;
  bridgeCode: string;
  packageReady: boolean;
  buildDisabled: boolean;
  sendDisabled: boolean;
  downloadDisabled: boolean;
  busy: boolean;
}

export interface UiDependencies {
  postMessage(message: UiToController): void;
  render(view: UiViewModel): void;
  digest(algorithm: "SHA-256", bytes: ArrayBuffer): Promise<ArrayBuffer>;
  download(value: { bytes: Uint8Array; filename: string; mimeType: string }): void;
}

export interface UiController {
  handleMessage(value: unknown): Promise<void>;
  refresh(): void;
  build(): void;
  pair(code: string): void;
  send(): void;
  download(): void;
  close(): void;
}

function invalidMessage(path: string, message: string): never {
  throw new TypeError(`Invalid plugin message at ${path}: ${message}`);
}

function plainRecord(value: unknown, path: string): UnknownRecord {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    invalidMessage(path, "expected a plain object");
  }
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) {
    invalidMessage(path, "expected a plain object");
  }
  return value as UnknownRecord;
}

function exactKeys(record: UnknownRecord, keys: readonly string[], path: string): void {
  const allowed = new Set(keys);
  for (const key of Object.keys(record)) {
    if (!allowed.has(key)) invalidMessage(`${path}.${key}`, "unknown field");
  }
  for (const key of keys) {
    if (!Object.prototype.hasOwnProperty.call(record, key)) {
      invalidMessage(`${path}.${key}`, "missing required field");
    }
  }
}

function nonEmptyString(value: unknown, path: string): string {
  if (typeof value !== "string" || value.length === 0) invalidMessage(path, "expected a non-empty string");
  return value;
}

function frameSummary(value: unknown, path: string): FrameSummary {
  const record = plainRecord(value, path);
  exactKeys(record, ["nodeId", "name", "duration"], path);
  if (typeof record.duration !== "number" || !Number.isFinite(record.duration) || record.duration <= 0) {
    invalidMessage(`${path}.duration`, "expected a positive duration");
  }
  return {
    nodeId: nonEmptyString(record.nodeId, `${path}.nodeId`),
    name: nonEmptyString(record.name, `${path}.name`),
    duration: record.duration
  };
}

function validateUnhashedPackage(value: unknown): ExporterPackage {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    invalidMessage("$.value", "expected an exporter package");
  }
  const clone = structuredClone(value) as ExporterPackage;
  contentFingerprintInput(clone);
  if (clone.contentHash !== "") invalidMessage("$.value.contentHash", "expected an empty content hash");
  return clone;
}

export function validateControllerToUi(value: unknown): ControllerToUi {
  const record = plainRecord(value, "$");
  if (typeof record.type !== "string") invalidMessage("$.type", "expected a message type");
  switch (record.type) {
    case "selection": {
      exactKeys(record, ["type", "frames"], "$");
      if (!Array.isArray(record.frames)) invalidMessage("$.frames", "expected an array");
      return { type: "selection", frames: record.frames.map((frame, index) => frameSummary(frame, `$.frames[${index}]`)) };
    }
    case "package-unhashed":
      exactKeys(record, ["type", "value"], "$");
      return { type: "package-unhashed", value: validateUnhashedPackage(record.value) };
    case "bridge-result":
      exactKeys(record, ["type", "status", "code", "message"], "$");
      if (typeof record.status !== "number" || !Number.isSafeInteger(record.status) || record.status < 0 || record.status > 599) {
        invalidMessage("$.status", "expected an HTTP status from 0 to 599");
      }
      return {
        type: "bridge-result",
        status: record.status,
        code: nonEmptyString(record.code, "$.code"),
        message: nonEmptyString(record.message, "$.message")
      };
    case "failure":
      exactKeys(record, ["type", "code", "message"], "$");
      return {
        type: "failure",
        code: nonEmptyString(record.code, "$.code"),
        message: nonEmptyString(record.message, "$.message")
      };
    default:
      invalidMessage("$.type", `unsupported message type ${JSON.stringify(record.type)}`);
  }
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function countNodes(nodes: readonly ExportNode[]): { native: number; raster: number } {
  let native = 0;
  let raster = 0;
  const pending = [...nodes];
  while (pending.length > 0) {
    const node = pending.shift();
    if (node === undefined) continue;
    if (node.kind === "raster") raster += 1;
    else {
      native += 1;
      if (node.kind === "group") pending.unshift(...node.children);
    }
  }
  return { native, raster };
}

export function packageFilename(value: ExporterPackage): string {
  const validated = validatePackage(value);
  const frameName = validated.frames[0]!.name;
  return `${frameName}-${validated.contentHash.slice(0, 12)}.video001-ae.json`;
}

export function downloadPackage(
  value: ExporterPackage,
  save: (blob: Blob, filename: string) => void
): void {
  const validated = validatePackage(value);
  const encoded = new TextEncoder().encode(JSON.stringify(validated));
  const blob = new Blob([
    encoded.buffer.slice(encoded.byteOffset, encoded.byteOffset + encoded.byteLength) as ArrayBuffer
  ], { type: EXPORT_MEDIA_TYPE });
  save(blob, packageFilename(validated));
}

export function createUiController(dependencies: UiDependencies): UiController {
  let retainedPackage: ExporterPackage | undefined;
  let state: UiViewModel = {
    frames: [],
    nativeCount: 0,
    rasterCount: 0,
    warnings: [],
    status: "Select a prepared Video 001 frame.",
    error: "",
    bridgeCode: "",
    packageReady: false,
    buildDisabled: true,
    sendDisabled: true,
    downloadDisabled: true,
    busy: false
  };

  const update = (changes: Partial<UiViewModel>): void => {
    state = { ...state, ...changes };
    dependencies.render(state);
  };

  const handleMessage = async (value: unknown): Promise<void> => {
    let message: ControllerToUi;
    try {
      message = validateControllerToUi(value);
    } catch (error) {
      update({
        busy: false,
        error: error instanceof Error ? error.message : "The plugin sent an invalid message.",
        status: "Plugin message rejected."
      });
      return;
    }

    switch (message.type) {
      case "selection":
        retainedPackage = undefined;
        update({
          frames: message.frames,
          nativeCount: 0,
          rasterCount: 0,
          warnings: [],
          status: `${message.frames.length} frame${message.frames.length === 1 ? "" : "s"} selected.`,
          error: "",
          packageReady: false,
          buildDisabled: message.frames.length === 0,
          sendDisabled: true,
          downloadDisabled: true,
          busy: false
        });
        break;
      case "package-unhashed": {
        update({ busy: true, error: "", status: "Hashing package…" });
        try {
          const input = new TextEncoder().encode(contentFingerprintInput(message.value));
          const digest = await dependencies.digest(
            "SHA-256",
            input.buffer.slice(input.byteOffset, input.byteOffset + input.byteLength) as ArrayBuffer
          );
          const finalValue = validatePackage({
            ...message.value,
            contentHash: bytesToHex(new Uint8Array(digest))
          });
          retainedPackage = finalValue;
          const counts = finalValue.frames.reduce(
            (total, frame) => {
              const count = countNodes(frame.children);
              return { native: total.native + count.native, raster: total.raster + count.raster };
            },
            { native: 0, raster: 0 }
          );
          update({
            nativeCount: counts.native,
            rasterCount: counts.raster,
            warnings: finalValue.frames.flatMap((frame) => frame.warnings),
            status: "Package ready for live send or download.",
            packageReady: true,
            buildDisabled: false,
            sendDisabled: false,
            downloadDisabled: false,
            busy: false
          });
          dependencies.postMessage({ type: "package-ready", value: finalValue });
        } catch (error) {
          retainedPackage = undefined;
          update({
            error: error instanceof Error ? error.message : "Package hashing failed.",
            status: "Package creation failed.",
            packageReady: false,
            sendDisabled: true,
            downloadDisabled: true,
            busy: false
          });
        }
        break;
      }
      case "bridge-result":
        update({
          bridgeCode: message.code,
          status: message.message,
          error: message.status >= 400 || message.status === 0 ? message.message : "",
          busy: false,
          downloadDisabled: retainedPackage === undefined
        });
        break;
      case "failure":
        update({
          status: "The operation could not be completed.",
          error: `${message.code}: ${message.message}`,
          busy: false,
          downloadDisabled: retainedPackage === undefined,
          sendDisabled: retainedPackage === undefined
        });
        break;
    }
  };

  const download = (): void => {
    if (retainedPackage === undefined) {
      update({ error: "Build a package before downloading.", status: "No package is ready." });
      return;
    }
    const bytes = new TextEncoder().encode(JSON.stringify(retainedPackage));
    dependencies.download({
      bytes,
      filename: packageFilename(retainedPackage),
      mimeType: EXPORT_MEDIA_TYPE
    });
    update({ status: "Package downloaded.", error: "" });
  };

  dependencies.render(state);
  return {
    handleMessage,
    refresh: () => dependencies.postMessage({ type: "refresh-selection" }),
    build: () => {
      update({ busy: true, status: "Building package…", error: "" });
      dependencies.postMessage({ type: "build-package" });
    },
    pair: (code) => dependencies.postMessage({ type: "pair", code }),
    send: () => dependencies.postMessage({ type: "send-live" }),
    download,
    close: () => dependencies.postMessage({ type: "close" })
  };
}

function requiredElement<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (element === null) throw new Error(`Missing UI element ${id}`);
  return element as T;
}

function startRuntime(): void {
  const selection = requiredElement<HTMLUListElement>("selection-list");
  const nativeCount = requiredElement<HTMLElement>("native-count");
  const rasterCount = requiredElement<HTMLElement>("raster-count");
  const warnings = requiredElement<HTMLUListElement>("warning-list");
  const status = requiredElement<HTMLElement>("status");
  const error = requiredElement<HTMLElement>("error");
  const bridgeCode = requiredElement<HTMLElement>("bridge-code");
  const buildButton = requiredElement<HTMLButtonElement>("build-package");
  const sendButton = requiredElement<HTMLButtonElement>("send-live");
  const downloadButton = requiredElement<HTMLButtonElement>("download-package");
  const pairingInput = requiredElement<HTMLInputElement>("pairing-code");

  const ui = createUiController({
    postMessage: (message) => parent.postMessage({ pluginMessage: message }, "*"),
    digest: (algorithm, bytes) => crypto.subtle.digest(algorithm, bytes),
    download: ({ bytes, filename, mimeType }) => {
      const blob = new Blob([
        bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer
      ], { type: mimeType });
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      anchor.hidden = true;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
    },
    render: (view) => {
      selection.replaceChildren(...view.frames.map((frame) => {
        const item = document.createElement("li");
        item.textContent = `${frame.name} · ${frame.duration} frames`;
        return item;
      }));
      warnings.replaceChildren(...view.warnings.map((warning) => {
        const item = document.createElement("li");
        item.textContent = `${warning.nodeName} (${warning.nodeId}): ${warning.property} → PNG`;
        return item;
      }));
      nativeCount.textContent = String(view.nativeCount);
      rasterCount.textContent = String(view.rasterCount);
      status.textContent = view.status;
      error.textContent = view.error;
      error.hidden = view.error.length === 0;
      bridgeCode.textContent = view.bridgeCode;
      buildButton.disabled = view.buildDisabled || view.busy;
      sendButton.disabled = view.sendDisabled || view.busy;
      downloadButton.disabled = view.downloadDisabled || view.busy;
      document.documentElement.setAttribute("aria-busy", String(view.busy));
    }
  });

  requiredElement<HTMLButtonElement>("refresh-selection").addEventListener("click", () => ui.refresh());
  buildButton.addEventListener("click", () => ui.build());
  requiredElement<HTMLFormElement>("pair-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const code = pairingInput.value.trim();
    if (!/^\d{6}$/.test(code)) {
      pairingInput.setCustomValidity("Enter the six-digit code shown in After Effects.");
      pairingInput.reportValidity();
      return;
    }
    pairingInput.setCustomValidity("");
    ui.pair(code);
  });
  pairingInput.addEventListener("input", () => pairingInput.setCustomValidity(""));
  sendButton.addEventListener("click", () => ui.send());
  downloadButton.addEventListener("click", () => ui.download());
  requiredElement<HTMLButtonElement>("close-plugin").addEventListener("click", () => ui.close());
  window.addEventListener("message", (event: MessageEvent<unknown>) => {
    if (event.source !== parent) return;
    if (event.data === null || typeof event.data !== "object" || Array.isArray(event.data)) return;
    const envelope = event.data as UnknownRecord;
    if (Object.keys(envelope).length !== 1 || !Object.prototype.hasOwnProperty.call(envelope, "pluginMessage")) return;
    void ui.handleMessage(envelope.pluginMessage);
  });
  ui.refresh();
}

if (typeof document !== "undefined" && typeof window !== "undefined") {
  startRuntime();
}
