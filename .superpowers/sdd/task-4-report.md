# Task 4 report — generic package contract schema 3 and isolated Video 001 adapter

## Status

Complete and committed after this report is staged. Schema 3 is generic and profile-bound; schema-2 Video 001 acceptance is available only through `src/shared/legacy-video001.ts`.

## RED / GREEN

Initial RED:

```text
./node_modules/.bin/tsx --test tests/contract.test.ts tests/legacy-video001.test.ts
```

failed as expected because `validatePackageAgainstProfile` and `legacy-video001.ts` did not exist.

Additional REDs verified:

- the adapter-owned legacy profile-reference factory was absent before controller compile compatibility was added;
- profile hashing failed when `TextEncoder` was absent from the controller-only type environment;
- the literal-isolation test found the Video 001 media type still declared in the controller.

GREEN verification:

```text
contract + legacy + profile + serializer focused tests: 81 passed
streaming-package tests: 12 passed
npm run typecheck: pass
npm run typecheck:controller: pass
npm run build: pass
git diff --check: pass
```

## Compatibility decisions

- Generic packages require exact schema `3.0.0`, exact root/project keys, and canonical profile identity in content fingerprints.
- `validatePackageAgainstProfile` validates the installed profile hash before enforcing exact reference, source, target, frame dimensions, declared shot ID/name/duration, strict timeline order, and profile frame/asset ceilings. Chronological selected-shot subsets remain valid.
- Existing 32 MiB per-asset and 512 MiB aggregate ceilings remain unchanged.
- `adaptLegacyVideo001Package` accepts only exact schema-2 root keys, only the canonical bundled Video 001 profile reference, and only source/target assumptions matching that profile. It upgrades via the schema-3 validator; generic validation never accepts schema 2.
- The minimal controller compatibility path imports the adapter-owned schema-3 profile reference and media type. It does not make the controller profile-driven or change UI/runtime flow.
- `project-profile.ts` now uses the shared UTF-8 encoder so the browser/controller compilation boundary does not require `TextEncoder`.

## Files

- Modified: `src/shared/contract.ts`, `src/shared/project-profile.ts`, `src/shared/utf8.ts`, `src/figma/controller.ts`
- Added: `src/shared/legacy-video001.ts`, `tests/legacy-video001.test.ts`
- Updated fixtures/tests: `tests/helpers/package.ts`, `tests/contract.test.ts`, `tests/project-profile.test.ts`, `tests/streaming-package.test.ts`

## Full-suite / release note

`npm test` was run. It exposed intentionally deferred migration gaps: the source-release allowlist does not yet include the new profile/adapter modules (not changed per instruction), and old full-lesson synthetic evidence fixtures still construct schema-2 packages without `project`. Those fixture/runtime migrations belong to the later profile-driven integration work. The focused generic contract, serializer, streaming, typecheck, and normal-build paths are green.

## Self-review and concerns

- Reviewed exact keys, hash/reference comparison, selected-shot chronology, frame/asset profile caps, canonical fingerprint inclusion, legacy root-key isolation, and legacy-literal placement.
- The bundled Video 001 hash is pinned in the adapter. A deliberate profile revision requires updating that adapter pin, preventing accidental legacy conversion under a merely similar profile.
- No release allowlist was modified. No user changes were reverted.
