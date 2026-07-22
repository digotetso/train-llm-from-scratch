export interface BridgeOwner {
  version: 1;
  pid: number;
  instanceId: string;
}

export type OwnedHttpTemporaryKind = "http-asset" | "http-body";

const INSTANCE_ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const OWNED_HTTP_TEMPORARY_PATTERN = /^(\.http-(?:asset|body))\.([1-9]\d*)\.([0-9a-f-]{36})\.([0-9a-f-]{36})\.tmp$/;

export function parseBridgeOwner(value: unknown): BridgeOwner {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError("Bridge owner record must be an object");
  }
  const record = value as Record<string, unknown>;
  const keys = Object.keys(record);
  if (keys.length !== 3 || !keys.includes("version") || !keys.includes("pid") || !keys.includes("instanceId")) {
    throw new TypeError("Bridge owner record has unexpected fields");
  }
  if (record.version !== 1) throw new TypeError("Bridge owner version is unsupported");
  if (!Number.isSafeInteger(record.pid) || (record.pid as number) <= 0) {
    throw new TypeError("Bridge owner PID is invalid");
  }
  if (typeof record.instanceId !== "string" || !INSTANCE_ID_PATTERN.test(record.instanceId)) {
    throw new TypeError("Bridge owner instance ID is invalid");
  }
  return { version: 1, pid: record.pid as number, instanceId: record.instanceId };
}

export function sameBridgeOwner(first: BridgeOwner, second: BridgeOwner): boolean {
  return first.version === second.version && first.pid === second.pid && first.instanceId === second.instanceId;
}

export function serializeBridgeOwner(owner: BridgeOwner): string {
  return JSON.stringify(parseBridgeOwner(owner));
}

export function ownedHttpTemporaryFilename(
  kind: OwnedHttpTemporaryKind,
  ownerValue: BridgeOwner,
  fileId: string
): string {
  const owner = parseBridgeOwner(ownerValue);
  if (!INSTANCE_ID_PATTERN.test(fileId)) throw new TypeError("HTTP temporary file ID is invalid");
  return `.${kind}.${owner.pid}.${owner.instanceId}.${fileId}.tmp`;
}

export function parseOwnedHttpTemporaryFilename(
  filename: string
): { fileId: string; kind: OwnedHttpTemporaryKind; owner: BridgeOwner } {
  const match = OWNED_HTTP_TEMPORARY_PATTERN.exec(filename);
  if (match === null) throw new TypeError("HTTP temporary filename is malformed");
  const kind = match[1] === ".http-asset" ? "http-asset" : "http-body";
  const pid = Number(match[2]);
  const instanceId = match[3] ?? "";
  const fileId = match[4] ?? "";
  if (!INSTANCE_ID_PATTERN.test(fileId)) throw new TypeError("HTTP temporary file ID is invalid");
  return {
    fileId,
    kind,
    owner: parseBridgeOwner({ version: 1, pid, instanceId })
  };
}
