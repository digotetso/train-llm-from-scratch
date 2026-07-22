export const LIMITS = Object.freeze({
  maxFrames: 48,
  maxAssets: 2_048,
  maxManifestBytes: 32 * 1024 * 1024,
  maxAssetBytes: 32 * 1024 * 1024,
  maxAggregateAssetBytes: 512 * 1024 * 1024,
  maxBodyBytes: 768 * 1024 * 1024,
  requestTimeoutMs: 120_000,
  pairingTtlMs: 5 * 60_000,
  tokenIdleTtlMs: 30 * 24 * 60 * 60_000
});
