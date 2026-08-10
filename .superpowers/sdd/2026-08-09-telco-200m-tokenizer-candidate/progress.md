# SDD ledger — plan: docs/superpowers/plans/2026-08-09-telco-200m-tokenizer-candidate.md

Baseline: `uv run --extra test pytest -q` passed on commit `e05d7cd` (7 skipped groups shown, no failures).

Task 1: fix round 1/5 (1 addressed, 0 open — enforced pilot stage, seed 42, and exact role quotas; commits a0406a6..5be0d34)
Task 1: complete (commits e05d7cd..5be0d34, review clean)
Task 2: review conflict awaiting operator decision — plan retains canonical patterns and `(index, pattern)` automaton values; reviewer recommends a constant sentinel and no retained tuple to reduce memory.
Task 2: operator decision — follow reviewer; remove redundant retained pattern/value state while preserving boolean equivalence.
Task 2: fix round 1/5 (1 addressed, 0 open — reduced compiled matcher state; commits 642b7f0..97f16e6)
Task 2: complete (commits 5be0d34..97f16e6, review clean)
Task 3: minor (deferred): `units()` materializes all units, hashes, and artifacts; final review should assess whether a paged or lightweight summary API is required before the 12B builder.
Task 3: minor (deferred): caller-provided artifact order remains in `artifacts_json`; final review should assess canonical sorting after path normalization.
Task 3: minor resolved during fix round 1: artifact manifests are now sorted by normalized relative path.
Task 3: fix round 1/5 (2 addressed, 0 open — missing-identity fail-closed check and normalized artifact keys; commits 70d628c..54ea965)
Task 3: complete (commits 97f16e6..54ea965, review clean)
Task 4: review conflict awaiting operator decision — plan/test exposes complete fit/holdout hash arrays, while reviewer requires streamed/on-disk identity state so resume memory is independent of accepted-document count. Reviewer also requires one-at-a-time chunk flushing.
Task 4: operator decision — follow reviewer; use streamed counts/digests and SQLite-backed disjointness, and flush one chunk at a time.
Task 3: minor resolved during Task 4 fix round 1: production resume uses lazy `iter_units()` and bounded per-unit state.
Task 4: fix round 1/5 (2 addressed, 0 open — bounded streamed resume identity and one-at-a-time chunk flushing; commits ff56677..c23d5b3)
Task 4: complete (commits 54ea965..c23d5b3, review clean)
Task 5: minor (deferred): evaluation fingerprints are computed in separate passes from consumption; final review should assess hashing consumed bytes or post-pass checksum verification.
Task 5: fix round 1/5 (5 addressed, 0 open — fingerprint and tokenizer identity gates, manifest v2, exclusive selection, distinct labels; commits cda8f61..a02379e)
Task 5: complete (commits c23d5b3..a02379e, review clean)
Task 6: minor (deferred): notebook prints result paths rather than rendering clickable `FileLink` objects.
Task 6: minor (deferred): notebook disk evidence probes `Path.home()` rather than the editable local-work filesystem and its default path differs from the preserved recipe path in the runbook.
Task 6: fix round 1/5 (2 addressed, 1 open — canonical config/artifact binding and atomic candidate claim landed; contamination manifests were still optional; commits d6a7c6e..e6129b5)
Task 6: fix round 2/5 (1 addressed, 0 open — both Lite/Full contamination manifests are mandatory and fully verified; commits e6129b5..3a3aea5)
Task 6: complete (commits a02379e..3a3aea5, review clean)
Final review: fix wave (9 addressed, 0 open — complete provenance binding, managed-path hardening, bounded dedup, exact-consumption audits, canonical pilot/comparison/selection evidence, side-specific validity gates, storage advisory, and final full-suite evidence; commits 3a3aea5..4fd6bbf)
Final review: complete (commits e05d7cd..4fd6bbf, scoped re-review clean; 487 passed, 14 skipped)
Final review: non-blocking residual — syscall-granularity directory replacement requires a future dirfd/openat redesign; documented and outside this bounded plan.
Whole-plan closure: deferred notebook portability items are resolved — storage evidence probes the configured local-work filesystem, results use guarded clickable `FileLink` rendering, and full-corpus progress resolves the exact currently selected tokenizer namespace. Portable shard metadata also omits new machine-local input/tokenizer paths while legacy reads remain supported. No open Critical/Important findings; 719 passed, 14 skipped in the exact cache-disabled repository suite.
