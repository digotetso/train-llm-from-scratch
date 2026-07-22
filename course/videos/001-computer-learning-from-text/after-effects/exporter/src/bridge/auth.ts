import { createHash, randomBytes, timingSafeEqual } from "node:crypto";
import {
  chmodSync,
  closeSync,
  constants,
  existsSync,
  fsyncSync,
  fstatSync,
  lstatSync,
  mkdirSync,
  openSync,
  readFileSync,
  renameSync,
  unlinkSync,
  writeFileSync
} from "node:fs";
import { basename, dirname, join } from "node:path";
import { LIMITS } from "../shared/limits.ts";
import { serializeBridgeOwner, type BridgeOwner } from "./ownership.ts";

type Clock = () => number;
type RandomSource = (size: number) => Uint8Array;
export type DirectorySync = (path: string) => void;

interface PairingRecord {
  codeDigest: string;
  createdAt: number;
  used: boolean;
}

interface TokenRecord {
  tokenDigest: string;
  lastUsedAt: number;
}

interface AuthState {
  version: 1;
  pairing: PairingRecord | null;
  tokens: TokenRecord[];
}

const DIGEST_PATTERN = /^[0-9a-f]{64}$/;
const PAIRING_CODE_PATTERN = /^\d{6}$/;
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{43}$/;
const MAX_UNBIASED_PAIRING_VALUE = Math.floor(0x1_0000_0000 / 1_000_000) * 1_000_000;
let temporaryFileSequence = 0;

function digest(value: Uint8Array | string): string {
  return createHash("sha256").update(value).digest("hex");
}

function exactKeys(value: Record<string, unknown>, expected: readonly string[], path: string): void {
  const keys = Object.keys(value);
  if (keys.length !== expected.length || keys.some((key) => !expected.includes(key))) {
    throw new TypeError(`Invalid authentication state at ${path}: unexpected fields`);
  }
}

function record(value: unknown, path: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError(`Invalid authentication state at ${path}: expected an object`);
  }
  return value as Record<string, unknown>;
}

function timestamp(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    throw new TypeError(`Invalid authentication state at ${path}: expected a non-negative timestamp`);
  }
  return value;
}

function digestString(value: unknown, path: string): string {
  if (typeof value !== "string" || !DIGEST_PATTERN.test(value)) {
    throw new TypeError(`Invalid authentication state at ${path}: expected a SHA-256 digest`);
  }
  return value;
}

function parseState(value: unknown): AuthState {
  const state = record(value, "$");
  exactKeys(state, ["version", "pairing", "tokens"], "$");
  if (state.version !== 1) throw new TypeError("Invalid authentication state at $.version");

  let pairing: PairingRecord | null = null;
  if (state.pairing !== null) {
    const persistedPairing = record(state.pairing, "$.pairing");
    exactKeys(persistedPairing, ["codeDigest", "createdAt", "used"], "$.pairing");
    if (typeof persistedPairing.used !== "boolean") {
      throw new TypeError("Invalid authentication state at $.pairing.used");
    }
    pairing = {
      codeDigest: digestString(persistedPairing.codeDigest, "$.pairing.codeDigest"),
      createdAt: timestamp(persistedPairing.createdAt, "$.pairing.createdAt"),
      used: persistedPairing.used
    };
  }

  if (!Array.isArray(state.tokens)) {
    throw new TypeError("Invalid authentication state at $.tokens: expected an array");
  }
  const tokens = state.tokens.map((value, index): TokenRecord => {
    const token = record(value, `$.tokens[${index}]`);
    exactKeys(token, ["tokenDigest", "lastUsedAt"], `$.tokens[${index}]`);
    return {
      tokenDigest: digestString(token.tokenDigest, `$.tokens[${index}].tokenDigest`),
      lastUsedAt: timestamp(token.lastUsedAt, `$.tokens[${index}].lastUsedAt`)
    };
  });

  return { version: 1, pairing, tokens };
}

function digestMatches(candidateDigest: string, persistedDigest: string): boolean {
  return timingSafeEqual(Buffer.from(candidateDigest, "hex"), Buffer.from(persistedDigest, "hex"));
}

function syncDirectory(path: string): void {
  const descriptor = openSync(path, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    fsyncSync(descriptor);
  } finally {
    closeSync(descriptor);
  }
}

function readState(statePath: string): AuthState | null {
  let descriptor: number;
  try {
    descriptor = openSync(statePath, constants.O_RDONLY | constants.O_NOFOLLOW);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }
  try {
    return parseState(JSON.parse(readFileSync(descriptor, "utf8")) as unknown);
  } finally {
    closeSync(descriptor);
  }
}

function acquireStateLock(lockPath: string, owner: BridgeOwner | undefined): number {
  let descriptor: number | undefined;
  try {
    descriptor = openSync(
      lockPath,
      constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
      0o600
    );
    if (owner !== undefined) {
      writeFileSync(descriptor, serializeBridgeOwner(owner), "utf8");
      fsyncSync(descriptor);
    }
    return descriptor;
  } catch (error) {
    if (descriptor !== undefined) {
      const acquired = fstatSync(descriptor);
      closeSync(descriptor);
      try {
        const current = lstatSync(lockPath);
        if (current.isFile() && current.dev === acquired.dev && current.ino === acquired.ino) {
          unlinkSync(lockPath);
        }
      } catch {
        // Preserve the owner-record failure and never remove a changed lock.
      }
    }
    if ((error as NodeJS.ErrnoException).code === "EEXIST") {
      throw new Error("Authentication state is locked");
    }
    throw error;
  }
}

export class AuthStore {
  private state: AuthState;
  private statePath: string | undefined;
  private readonly now: Clock;
  private readonly randomSource: RandomSource;
  private readonly directorySync: DirectorySync;
  private readonly lockOwner: BridgeOwner | undefined;
  private stateLockHeld = false;

  constructor(
    now: Clock = Date.now,
    randomSource: RandomSource = randomBytes,
    directorySync: DirectorySync = syncDirectory,
    lockOwner?: BridgeOwner
  ) {
    this.state = { version: 1, pairing: null, tokens: [] };
    this.statePath = undefined;
    this.now = now;
    this.randomSource = randomSource;
    this.directorySync = directorySync;
    this.lockOwner = lockOwner;
  }

  private static fromState(
    statePath: string,
    state: AuthState,
    now: Clock,
    randomSource: RandomSource,
    directorySync: DirectorySync,
    lockOwner?: BridgeOwner
  ): AuthStore {
    const store = new AuthStore(now, randomSource, directorySync, lockOwner);
    store.state = state;
    store.statePath = statePath;
    return store;
  }

  static async open(
    statePath: string,
    now: Clock = Date.now,
    randomSource: RandomSource = randomBytes,
    directorySync: DirectorySync = syncDirectory,
    lockOwner?: BridgeOwner
  ): Promise<AuthStore> {
    if (!statePath || basename(statePath) !== "auth.json") {
      throw new TypeError("Authentication state path must end in auth.json");
    }
    const parent = dirname(statePath);
    mkdirSync(parent, { recursive: true, mode: 0o700 });
    chmodSync(parent, 0o700);
    const store = AuthStore.fromState(
      statePath,
      { version: 1, pairing: null, tokens: [] },
      now,
      randomSource,
      directorySync,
      lockOwner
    );
    store.withStateLock(() => store.persistUnlocked(), true);
    return store;
  }

  createPairingCode(): string {
    return this.withStateLock(() => {
      let randomValue: number;
      do {
        const bytes = this.randomBytes();
        randomValue = bytes.readUInt32BE(0);
      } while (randomValue >= MAX_UNBIASED_PAIRING_VALUE);

      const code = String(randomValue % 1_000_000).padStart(6, "0");
      this.state.pairing = {
        codeDigest: digest(code),
        createdAt: this.now(),
        used: false
      };
      this.persistUnlocked();
      return code;
    });
  }

  exchangePairingCode(code: string): string {
    return this.withStateLock(() => {
      const pairing = this.state.pairing;
      if (!PAIRING_CODE_PATTERN.test(code) || pairing === null) {
        throw new Error("Invalid pairing code");
      }
      if (!digestMatches(digest(code), pairing.codeDigest)) {
        throw new Error("Invalid pairing code");
      }
      if (pairing.used) throw new Error("Pairing code already used");
      if (this.now() - pairing.createdAt >= LIMITS.pairingTtlMs) {
        throw new Error("Pairing code expired");
      }

      pairing.used = true;
      this.persistUnlocked();
      const token = this.randomBytes().toString("base64url");
      this.state.tokens.push({ tokenDigest: digest(token), lastUsedAt: this.now() });
      this.persistUnlocked();
      return token;
    });
  }

  authenticateBearer(header: string | readonly string[] | undefined): boolean {
    if (typeof header !== "string") return false;
    const match = /^Bearer ([A-Za-z0-9_-]{43})$/.exec(header);
    const token = match?.[1];
    if (token === undefined || !TOKEN_PATTERN.test(token)) return false;

    const decoded = Buffer.from(token, "base64url");
    if (decoded.byteLength !== 32 || decoded.toString("base64url") !== token) return false;
    return this.withStateLock(() => {
      const candidateDigest = digest(token);
      const now = this.now();

      for (const persisted of this.state.tokens) {
        if (!digestMatches(candidateDigest, persisted.tokenDigest)) continue;
        if (now - persisted.lastUsedAt >= LIMITS.tokenIdleTtlMs) return false;
        persisted.lastUsedAt = now;
        this.persistUnlocked();
        return true;
      }
      return false;
    });
  }

  revokeAll(): void {
    this.withStateLock(() => {
      this.state.pairing = null;
      this.state.tokens = [];
      this.persistUnlocked();
    });
  }

  private randomBytes(): Buffer {
    const bytes = Buffer.from(this.randomSource(32));
    if (bytes.byteLength !== 32) throw new Error("Random source must return exactly 32 bytes");
    return bytes;
  }

  private withStateLock<T>(operation: () => T, allowMissingState = false): T {
    if (this.statePath === undefined) return operation();
    const lockPath = `${this.statePath}.lock`;
    const lockDescriptor = acquireStateLock(lockPath, this.lockOwner);
    const lockIdentity = fstatSync(lockDescriptor);
    this.stateLockHeld = true;
    try {
      const persisted = readState(this.statePath);
      if (persisted === null) {
        if (!allowMissingState) throw new Error("Authentication state is missing while locked");
        this.state = { version: 1, pairing: null, tokens: [] };
      } else {
        this.state = persisted;
      }
      return operation();
    } finally {
      this.stateLockHeld = false;
      closeSync(lockDescriptor);
      const current = lstatSync(lockPath);
      if (current.dev !== lockIdentity.dev || current.ino !== lockIdentity.ino || !current.isFile()) {
        throw new Error("Authentication lock changed ownership before release");
      }
      unlinkSync(lockPath);
    }
  }

  private persistUnlocked(): void {
    if (this.statePath === undefined) return;
    if (!this.stateLockHeld) throw new Error("Authentication state must be locked before persistence");
    const parent = dirname(this.statePath);
    temporaryFileSequence += 1;
    const temporaryPath = join(
      parent,
      `.${basename(this.statePath)}.${process.pid}.${temporaryFileSequence}.tmp`
    );
    let descriptor: number | undefined;
    try {
      descriptor = openSync(
        temporaryPath,
        constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
        0o600
      );
      writeFileSync(descriptor, JSON.stringify(this.state), "utf8");
      fsyncSync(descriptor);
      closeSync(descriptor);
      descriptor = undefined;
      renameSync(temporaryPath, this.statePath);
      this.directorySync(parent);
    } catch (error) {
      if (descriptor !== undefined) closeSync(descriptor);
      if (existsSync(temporaryPath)) unlinkSync(temporaryPath);
      throw error;
    }
  }
}
