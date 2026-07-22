import { createHash, randomBytes, timingSafeEqual } from "node:crypto";
import {
  chmodSync,
  closeSync,
  existsSync,
  fsyncSync,
  mkdirSync,
  openSync,
  readFileSync,
  renameSync,
  unlinkSync,
  writeFileSync
} from "node:fs";
import { basename, dirname, join } from "node:path";
import { LIMITS } from "../shared/limits.ts";

type Clock = () => number;
type RandomSource = (size: number) => Uint8Array;

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

export class AuthStore {
  private state: AuthState;
  private statePath: string | undefined;
  private readonly now: Clock;
  private readonly randomSource: RandomSource;

  constructor(now: Clock = Date.now, randomSource: RandomSource = randomBytes) {
    this.state = { version: 1, pairing: null, tokens: [] };
    this.statePath = undefined;
    this.now = now;
    this.randomSource = randomSource;
  }

  private static fromState(
    statePath: string,
    state: AuthState,
    now: Clock,
    randomSource: RandomSource
  ): AuthStore {
    const store = new AuthStore(now, randomSource);
    store.state = state;
    store.statePath = statePath;
    return store;
  }

  static async open(
    statePath: string,
    now: Clock = Date.now,
    randomSource: RandomSource = randomBytes
  ): Promise<AuthStore> {
    if (!statePath || basename(statePath) !== "auth.json") {
      throw new TypeError("Authentication state path must end in auth.json");
    }
    const parent = dirname(statePath);
    mkdirSync(parent, { recursive: true, mode: 0o700 });
    chmodSync(parent, 0o700);
    const state = existsSync(statePath)
      ? parseState(JSON.parse(readFileSync(statePath, "utf8")) as unknown)
      : { version: 1 as const, pairing: null, tokens: [] };
    const store = AuthStore.fromState(statePath, state, now, randomSource);
    store.persist();
    return store;
  }

  createPairingCode(): string {
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
    this.persist();
    return code;
  }

  exchangePairingCode(code: string): string {
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
    this.persist();
    const token = this.randomBytes().toString("base64url");
    this.state.tokens.push({ tokenDigest: digest(token), lastUsedAt: this.now() });
    this.persist();
    return token;
  }

  authenticateBearer(header: string | readonly string[] | undefined): boolean {
    if (typeof header !== "string") return false;
    const match = /^Bearer ([A-Za-z0-9_-]{43})$/.exec(header);
    const token = match?.[1];
    if (token === undefined || !TOKEN_PATTERN.test(token)) return false;

    const decoded = Buffer.from(token, "base64url");
    if (decoded.byteLength !== 32 || decoded.toString("base64url") !== token) return false;
    const candidateDigest = digest(token);
    const now = this.now();

    for (const persisted of this.state.tokens) {
      if (!digestMatches(candidateDigest, persisted.tokenDigest)) continue;
      if (now - persisted.lastUsedAt >= LIMITS.tokenIdleTtlMs) return false;
      persisted.lastUsedAt = now;
      this.persist();
      return true;
    }
    return false;
  }

  revokeAll(): void {
    this.state.pairing = null;
    this.state.tokens = [];
    this.persist();
  }

  private randomBytes(): Buffer {
    const bytes = Buffer.from(this.randomSource(32));
    if (bytes.byteLength !== 32) throw new Error("Random source must return exactly 32 bytes");
    return bytes;
  }

  private persist(): void {
    if (this.statePath === undefined) return;
    const parent = dirname(this.statePath);
    temporaryFileSequence += 1;
    const temporaryPath = join(
      parent,
      `.${basename(this.statePath)}.${process.pid}.${temporaryFileSequence}.tmp`
    );
    let descriptor: number | undefined;
    try {
      descriptor = openSync(temporaryPath, "wx", 0o600);
      writeFileSync(descriptor, JSON.stringify(this.state), "utf8");
      fsyncSync(descriptor);
      closeSync(descriptor);
      descriptor = undefined;
      renameSync(temporaryPath, this.statePath);
    } catch (error) {
      if (descriptor !== undefined) closeSync(descriptor);
      if (existsSync(temporaryPath)) unlinkSync(temporaryPath);
      throw error;
    }
  }
}
