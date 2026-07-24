export const LIMITS = Object.freeze({
  maxFrames: 48,
  maxAssets: 2_048,
  maxJsonContainerDepth: 64,
  maxManifestBytes: 32 * 1024 * 1024,
  maxAssetBytes: 32 * 1024 * 1024,
  maxAggregateAssetBytes: 512 * 1024 * 1024,
  maxBodyBytes: 768 * 1024 * 1024,
  requestTimeoutMs: 120_000,
  pairingTtlMs: 5 * 60_000,
  tokenIdleTtlMs: 30 * 24 * 60 * 60_000
});

export const PROFILE_LIMITS = Object.freeze({
  maxProfileBytes: 1 * 1024 * 1024,
  maxInstalledProfiles: 256,
  maxFrames: 256,
  maxAssets: 2_048,
  maxDimension: 16_384,
  maxFps: 120,
  maxDurationSeconds: 6 * 60 * 60,
  maxNameCharacters: 120,
  maxRequiredFonts: 256,
  maxFontFallbacks: 512
});
