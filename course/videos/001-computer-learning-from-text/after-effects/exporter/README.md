# Video 001 Figma → After Effects Exporter

## Prerequisites

- macOS with Figma desktop and After Effects 25+ installed.
- Node.js 20+ and npm. Node is used only to build this source and run the local bridge.
- The prepared Video 001 Figma file and its page `02 Video 001 - AE Assets`.
- Permission in Figma desktop to create and import a development plugin.
- After Effects permission to run scripts.

No Adobe Creative Cloud desktop app, Adobe Media Encoder, cloud bridge, or hosted service is required by this exporter. Figma talks only to the bridge on `localhost`; the bridge binds only to `127.0.0.1`.

## Build and operate

Run these steps in order. Recovery for each boundary is beside the step where it is useful.

1. Install the pinned build dependencies:

   ```bash
   npm ci
   ```

   If installation reports a lockfile mismatch, do not use `npm install` to rewrite it. Restore the committed `package-lock.json` and run `npm ci` again.

2. Create a local Figma development-plugin ID. In Figma desktop, use **Plugins → Development → New plugin**, record the numeric ID Figma assigns, then save only that ID locally:

   ```bash
   printf '%s\n' 'YOUR_FIGMA_PLUGIN_ID' > .figma-plugin-id
   ```

   `.figma-plugin-id` is deliberately ignored and is never included in a source release. If the build says the ID is missing or invalid, replace the placeholder with the 10–30 digit ID assigned by Figma; do not copy an access token or API key.

3. Build the Figma plugin, local bridge, and After Effects scripts:

   ```bash
   npm run build
   ```

   The build owns only `dist/figma` and emits:

   - `dist/figma/manifest.json`
   - `dist/bridge/video001-bridge.mjs`
   - `dist/ae/Video001-Figma-AE-Exporter.jsx`

   If a build reports a timing, manifest, or ownership error, stop and fix that error. Do not edit generated `dist` files; rebuild them from the source.

4. In Figma desktop, choose **Plugins → Development → Import plugin from manifest** and select `dist/figma/manifest.json`. Open the exact prepared Video 001 file and page before running the plugin.

   If Figma rejects the manifest, recreate `.figma-plugin-id`, run `npm run build`, and import the newly generated manifest. A release recipient must always rebuild with their own local development-plugin ID.

5. In After Effects, choose **File → Scripts → Run Script File…** and run `dist/ae/Video001-Figma-AE-Exporter.jsx`. Keep the exporter palette open, then select **Start bridge**. The palette shows a six-digit pairing code and expiry.

   If the bridge does not start, confirm `node --version` is 20 or newer and that port 3456 is free. Use **Stop bridge**, then **Start bridge** to retry. If stale or expired pairing state persists, use **Reset pairing** and start the bridge again. Closing the palette stops only this exporter bridge.

6. Run the development plugin in Figma. Enter the six-digit code from After Effects and select **Pair**.

   If pairing is rejected or expires, use **Reset pairing** in After Effects, start the bridge, and enter the new code. Never paste the code into logs, issues, or release artifacts.

7. In Figma, select **Build full lesson (48 shots)**. This resolves the canonical 48 prepared frames and builds the exact 840-second package; a manual selection is not required. Wait until the package is ready and review its warning count.

   A missing node, wrong page, wrong section ancestry, renamed frame, or non-1920×1080 frame fails closed. Repair the prepared Figma document or canonical config and rebuild; do not patch the exported JSON.

8. Select **Send to After Effects**. In After Effects, wait until the queue count increases, then select **Import next**.

   A successful full-lesson import creates 48 immutable shot compositions plus one `VIDEO001_MASTER_v###` composition at 1920×1080, 30 fps, and 840 seconds. If import fails, the transaction removes only items created by that attempt. Correct the reported problem and resend or re-import; existing project items remain untouched.

This is the start → pair → build → send → import path. The bridge and package stay local to the Mac.

## Duplicate and version behavior

The first import uses `_v001`; later successful imports use the next available three-digit version without modifying earlier comps. Sending unchanged content and choosing **Import next** reports `DUPLICATE_CONTENT` and creates no composition.

Use **Import duplicate** only when another immutable copy of identical content is intentional. For that path, use **Download package** in Figma, then choose the downloaded `.video001-ae.json` file from **Import duplicate**. Versioning stops at `_v999`.

## Font and raster warnings

The redacted After Effects report lists every missing font, raster fallback, warning, created comp, and content hash. Treat a missing font as a visual review gate: install the intended font or accept and document the substitution before rendering.

A raster fallback means an unsupported Figma property—such as a gradient—was deliberately imported as a content-addressed PNG. The surrounding composition remains editable, but that fallback layer is not vector-editable. Compare the result with Figma and resolve unexpected fallback warnings before continuing.

## Troubleshooting and recovery

| Symptom | Check | Recovery |
| --- | --- | --- |
| Figma cannot reach the bridge | After Effects palette says the bridge is running on `127.0.0.1:3456` | Stop/start the bridge, pair again, and retry. Do not broaden the bind address or manifest allowlist. |
| Pairing returns unauthorized | Code expired, was mistyped, or old local auth state remains | **Reset pairing**, **Start bridge**, then pair with the new code. |
| **Send to After Effects** is disabled | A package has not finished building or pairing is incomplete | Finish pairing, run **Build full lesson (48 shots)** again, and wait for package-ready status. |
| **Import next** says the queue is empty | Send was not accepted or a previous duplicate was consumed | Check the Figma status, send again, and wait for the AE queue count to increase. |
| Import reports a fingerprint, asset, timing, or source mismatch | Package or canonical config is invalid or stale | Rebuild from Figma and resend. Never hand-edit a package, checksum, asset, or `dist` file. |
| Import stops partway through | The transactional importer rolled back the new items | Resolve the first redacted error and retry. Do not delete pre-existing comps as “cleanup.” |
| Missing-font or raster-fallback warning remains | The import completed with a declared fidelity exception | Review the affected layers against Figma; install fonts or accept the declared raster result explicitly. |

The bridge stores queue and pairing state in the current macOS user's application-data area. Use the palette controls for stop/reset/recovery; do not copy that mutable state into the repository or a release.

## Source release and verification

After `npm ci`, creating `.figma-plugin-id`, and running a fresh `npm run build`, create and independently verify the reproducible 0.2.0 release:

```bash
npm run release:build
npm run release:verify
```

The commands produce and verify:

- `release/video001-figma-ae-exporter-0.2.0.tar.gz`
- `release/video001-figma-ae-exporter-0.2.0.sha256`

The builder uses an explicit file allowlist, fixed POSIX ustar metadata, and zero-time gzip output. The verifier independently checks the lowercase SHA-256 line, gzip header, archive headers, member allowlist, paths, ownership, modes, timestamps, padding, and version agreement. The release excludes `.figma-plugin-id`, live evidence, AEP files, credentials, and mutable user paths. Run `npm run build` after extracting so the Figma manifest uses the recipient's local plugin ID.

This source and release are licensed under Apache License 2.0; see `LICENSE`, `NOTICE`, and `PROVENANCE.md`. The provenance record identifies the pinned AEUX upstream and the official Figma Plugin API documentation used by the adapter.
