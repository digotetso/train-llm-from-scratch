# Streaming Asset Bridge Design

## Goal

Preserve the exact `application/vnd.video001.figma-ae+json` wire contract while accepting packages up to the existing 768 MiB raw-body limit without materializing encoded asset strings in JavaScript memory.

## Invariants

- Authentication completes before export body work.
- Only one export performs body/file/parse/queue work; one request may wait; later requests receive `503 EXPORT_BUSY`.
- Pair/reset bodies remain capped at 1 KiB.
- Raw HTTP input is capped at 768 MiB, non-asset manifest bytes at 32 MiB, each decoded asset at 32 MiB, and aggregate decoded assets at 512 MiB.
- Manifest accounting is the raw package byte count minus bytes between the quotes of top-level `assets[*].dataBase64` values. Keys, quotes, commas, and whitespace count.
- `dataBase64` accepts only unescaped canonical base64. The reader decodes, hashes, and writes it incrementally.
- Existing `validatePackage` and `contentFingerprintInput` behavior remains unchanged.
- The fingerprint remains SHA-256 over the exact existing canonical JSON with blank `exportedAt` and `contentHash`.
- Body and decoded-asset temporaries are exclusive `0600` files in the verified queue `tmp` directory, include the exact lifecycle PID and instance UUID in their names, and are removed with identity checks plus directory fsync.
- Startup removes such files only after validating an exact prior lifecycle owner and proving its PID dead. Live, ambiguous, malformed, symlinked, or owner-mismatched evidence is preserved and startup fails closed.

## Components and data flow

1. `server.ts` authenticates and streams the raw request, with backpressure, to an owner-stamped spool capped by `maxBodyBytes`.
2. `streaming-package.ts` reopens that inode with `O_NOFOLLOW`, tokenizes arbitrary JSON whitespace/key order in bounded chunks, and builds the normal object graph except that each asset data string becomes a private marker plus a verified decoded temporary file.
3. `contract.ts` shares its existing schema/node/reference validator through `validatePackageWithVerifiedAssets`. The external path checks the same exact keys and declared lengths but consumes parser evidence instead of a resident base64 string.
4. `streaming-package.ts` walks the validated external package in canonical key order. For each marker it streams the verified decoded file through an incremental base64 encoder into the fingerprint hash, producing exactly the same digest as `contentFingerprintInput` for an equivalent in-memory package.
5. `QueueStore.enqueueVerified` locks the package, reopens every source no-follow, rechecks inode/device/size/SHA-256, copies through a private temporary file, publishes content-addressed assets atomically, and writes the same slim queued manifest as `enqueue`.
6. The server cleans all source temporaries in `finally`. Startup recovery recognizes only strict owner-stamped names authorized by a dead lifecycle record.

## Error mapping

- Malformed JSON/tokenization: `400 INVALID_JSON`.
- Raw or manifest byte limit: `413 PAYLOAD_TOO_LARGE`.
- Invalid canonical base64, declared/decoded length mismatch, per-asset/aggregate limit, or schema failure: `422 INVALID_PACKAGE`.
- Declared versus actual asset SHA-256 mismatch: `422 ASSET_HASH_MISMATCH`.
- Fingerprint mismatch: `422 CONTENT_HASH_MISMATCH`.
- Duplicate queue package: `409 QUEUE_DUPLICATE`.
- Filesystem/lock/fsync/parser operational errors: generic redacted `500 INTERNAL_ERROR`.

## Testing

All limit tests inject small byte ceilings. Tests cover manifest accounting, raw/per-asset/aggregate limits, JSON/base64 chunk boundaries, arbitrary key order and whitespace, escaped/noncanonical base64 rejection, fingerprint equality with the existing implementation, verified queue publication and tamper rejection, success/error cleanup, exact dead-owner recovery, and live/ambiguous/malformed/mismatched preservation. Each production slice begins with a focused failing test.

## Scope

The vendor media type, JSON schema, content hash contract, Figma serializer, importer format, and dependency set do not change.
