import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { AuthStore } from "../src/bridge/auth.ts";
import { LIMITS } from "../src/shared/limits.ts";

function randomSequence(...values: number[]): () => Buffer {
  let index = 0;
  return () => {
    const value = values[index];
    if (value === undefined) throw new Error("test random sequence exhausted");
    index += 1;
    return Buffer.alloc(32, value);
  };
}

test("pairing codes are six digits, one-time, and expire after five minutes", () => {
  let now = 1_000;
  const auth = new AuthStore(() => now, randomSequence(7, 8, 9));
  const code = auth.createPairingCode();

  assert.match(code, /^\d{6}$/);
  assert.throws(() => auth.exchangePairingCode("00000"), /invalid/i);
  const token = auth.exchangePairingCode(code);
  assert.equal(Buffer.from(token, "base64url").byteLength, 32);
  assert.throws(() => auth.exchangePairingCode(code), /used|invalid/i);

  const expired = auth.createPairingCode();
  now += LIMITS.pairingTtlMs;
  assert.throws(() => auth.exchangePairingCode(expired), /expired/i);
});

test("bearer tokens use exact syntax, expire after thirty idle days, and can be revoked", () => {
  let now = 1_000;
  const auth = new AuthStore(() => now, randomSequence(1, 2, 3, 4));
  const token = auth.exchangePairingCode(auth.createPairingCode());

  for (const malformed of [
    token,
    `bearer ${token}`,
    `Bearer  ${token}`,
    `Bearer ${token} `,
    `Bearer ${token}, Bearer ${token}`,
    `Basic ${token}`,
    "Bearer abc",
    ""
  ]) {
    assert.equal(auth.authenticateBearer(malformed), false, malformed);
  }

  assert.equal(auth.authenticateBearer(`Bearer ${token}`), true);
  now += LIMITS.tokenIdleTtlMs;
  assert.equal(auth.authenticateBearer(`Bearer ${token}`), false);

  const fresh = auth.exchangePairingCode(auth.createPairingCode());
  auth.revokeAll();
  assert.equal(auth.authenticateBearer(`Bearer ${fresh}`), false);
});

test("only successful authentication refreshes the idle expiry", () => {
  let now = 1_000;
  const auth = new AuthStore(() => now, randomSequence(11, 12));
  const token = auth.exchangePairingCode(auth.createPairingCode());

  now += LIMITS.tokenIdleTtlMs - 1;
  assert.equal(auth.authenticateBearer(`Bearer ${token.slice(0, -1)}x`), false);
  now += 2;
  assert.equal(auth.authenticateBearer(`Bearer ${token}`), false);
});

test("successful authentication extends the idle lifetime", () => {
  let now = 1_000;
  const auth = new AuthStore(() => now, randomSequence(13, 14));
  const token = auth.exchangePairingCode(auth.createPairingCode());

  now += LIMITS.tokenIdleTtlMs - 1;
  assert.equal(auth.authenticateBearer(`Bearer ${token}`), true);
  now += LIMITS.tokenIdleTtlMs - 1;
  assert.equal(auth.authenticateBearer(`Bearer ${token}`), true);
});

test("only secret digests persist atomically with owner-only permissions", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-auth-"));
  const statePath = join(root, "private", "auth.json");
  let now = 20_000;
  const auth = await AuthStore.open(statePath, () => now, randomSequence(21, 22));
  const code = auth.createPairingCode();
  const token = auth.exchangePairingCode(code);
  const persisted = await readFile(statePath, "utf8");
  const state = JSON.parse(persisted) as {
    pairing: { codeDigest: string; createdAt: number; used: boolean };
    tokens: Array<{ tokenDigest: string; lastUsedAt: number }>;
  };

  assert.equal(persisted.includes(token), false);
  assert.equal(persisted.includes(`\"${code}\"`), false);
  assert.match(state.pairing.codeDigest, /^[0-9a-f]{64}$/);
  assert.match(state.tokens[0]?.tokenDigest ?? "", /^[0-9a-f]{64}$/);
  assert.equal((await stat(join(root, "private"))).mode & 0o777, 0o700);
  assert.equal((await stat(statePath)).mode & 0o777, 0o600);
  assert.deepEqual(await readdir(join(root, "private")), ["auth.json"]);

  now += 1;
  assert.equal(auth.authenticateBearer(`Bearer ${token}`), true);
  const refreshed = JSON.parse(await readFile(statePath, "utf8")) as {
    tokens: Array<{ lastUsedAt: number }>;
  };
  assert.equal(refreshed.tokens[0]?.lastUsedAt, now);
});

test("persisted bearer digests survive bridge restarts", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-auth-restart-"));
  const statePath = join(root, "auth.json");
  let now = 30_000;
  const first = await AuthStore.open(statePath, () => now, randomSequence(31, 32));
  const token = first.exchangePairingCode(first.createPairingCode());

  now += 1;
  const reopened = await AuthStore.open(statePath, () => now, randomSequence(33));
  assert.equal(reopened.authenticateBearer(`Bearer ${token}`), true);
});

test("a token-generation failure durably consumes the pairing code", async () => {
  const root = await mkdtemp(join(tmpdir(), "video001-auth-failure-"));
  const statePath = join(root, "auth.json");
  let calls = 0;
  const failingRandom = (): Buffer => {
    calls += 1;
    if (calls === 1) return Buffer.alloc(32, 41);
    throw new Error("random source unavailable");
  };
  const first = await AuthStore.open(statePath, () => 40_000, failingRandom);
  const code = first.createPairingCode();
  assert.throws(() => first.exchangePairingCode(code), /random source unavailable/);

  const reopened = await AuthStore.open(statePath, () => 40_001, randomSequence(42));
  assert.throws(() => reopened.exchangePairingCode(code), /used|invalid/i);
});
