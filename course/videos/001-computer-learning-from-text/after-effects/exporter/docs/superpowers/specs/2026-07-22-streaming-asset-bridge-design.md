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

## Re-review remediation

### Measured bottleneck and chunk contract

The first implementation awaits `peek()` and `read()` for every encoded asset byte. On the review machine, the existing 49,157-byte boundary test spends about 256 ms in parse/fingerprint work, and code inspection shows two promise continuations per base64 byte. That control-flow cost scales beyond the 120-second request deadline at production sizes.

The asset-string path instead requests the reader's current contiguous buffer, finds the closing quote synchronously, validates/copies bytes into a 64 KiB quartet-aligned decoder buffer, and awaits only for reader refill, bounded file write, and cancellation checkpoint. Base64 quartet carry, padding position, pad-bit validation, raw manifest accounting, partial-write loops, and 1–3 byte reader-boundary behavior remain exact. A promise-creation budget guards the control-flow shape, while a serialized four-MiB encoded-input benchmark enforces at least 30 MiB/s without cross-file scheduler contention. The final verification recorded 8,624 promises for the 49,157-byte decoded fixture (down from 400,690 before the change) and 65.3 MiB/s with 132 bounded parse checkpoints for the four-MiB fixture.

### Cancellation and commit boundary

A shared `BridgeWorkContext` carries the request deadline signal, shutdown signal, an optional asynchronous checkpoint observer, and an idempotent cancellation callback. Parsing checks it on bounded reader/decoder chunks, fingerprinting on each decoded-file chunk, and verified queue adoption/copy on each source or existing-asset chunk and immediately before publication. Shutdown takes precedence if both signals are aborted. Deadline cancellation maps to `408 REQUEST_TIMEOUT`; shutdown destroys the request without a response.

After body spooling finishes, the server observes deadline and shutdown signals for the complete processing-and-cleanup lifetime and releases the single-flight slot as soon as either aborts. Identity-checked cleanup then continues outside that slot, so cleanup cannot prevent the bounded waiter from advancing. Owner-stamped files remain recoverable if cleanup itself encounters an operational failure. Once the queue manifest has been durably published, the operation is committed and returns `202`; a deadline observed during post-commit source cleanup releases the slot but does not misreport an accepted package as timed out.

### Object-key and nesting parity

Parsed JSON objects use null prototypes, so keys such as `__proto__` and `constructor` remain enumerable own data properties and reach the existing exact-key validator. Top-level, nested-node, and asset regressions compare streaming rejection with `JSON.parse` plus `validatePackage`.

`LIMITS.maxJsonContainerDepth` is the single abuse-prevention limit for both paths. The root object is container depth 1; only arrays and objects increment depth, while scalar values do not. In-memory validation performs an iterative ancestor-aware preflight that rejects cycles but permits repeated non-cyclic references. The streaming parser applies the same count when entering each object or array. Valid nested groups just below the limit and the next group above it prove parity.

### Alternatives considered

- A worker thread would isolate CPU but retain promise-per-byte work and complicate owner/file cancellation; it does not address the root cause.
- A third-party SAX parser could improve tokenization but violates the dependency-free constraint and would still require custom asset-string and canonical-base64 handling.
- Removing the streaming-only depth check would restore parity but discard a useful abuse bound. A shared explicit limit is smaller, testable, and applies equally to resident and streamed packages.
