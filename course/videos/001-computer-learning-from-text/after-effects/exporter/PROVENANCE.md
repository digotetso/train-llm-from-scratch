# Upstream provenance

This exporter is based on Apache-2.0-compatible concepts from [AEUX](https://github.com/google/AEUX), pinned to upstream commit `573d07d63b13059c6ebeb02561c89b39bb829180`.

The following upstream files were consulted:

- `Figma/AEUX/src/code.ts`
- `Figma/AEUX/src/aeux.js`
- `Ae/AEUX/src/host/AEFT/host.ts`

No DISKO Beam source code is copied or adapted in this project. Every file copied or adapted from AEUX must carry a prominent notice identifying that it was modified, in addition to retaining the upstream Apache 2.0 license and attribution notices.

## Figma Plugin API documentation

The Task 5 controller, UI boundary, manifest, and build pipeline were implemented against the following official Figma documentation, accessed 2026-07-22:

- https://developers.figma.com/docs/plugins/manifest/
- https://developers.figma.com/docs/plugins/making-network-requests/
- https://developers.figma.com/docs/plugins/migrating-to-dynamic-loading/
- https://developers.figma.com/docs/plugins/api/properties/TextNode-getstyledtextsegments/
- https://developers.figma.com/docs/plugins/api/figma/
- https://developers.figma.com/docs/plugins/api/properties/figma-ui-postmessage/
- https://developers.figma.com/docs/plugins/creating-ui/
- https://developers.figma.com/docs/plugins/plugin-quickstart-guide/

The installed official `@figma/plugin-typings` package is pinned to `1.131.0`. The adapter uses `absoluteTransform`, requests `fontName`, `fontSize`, and `fills` from `TextNode.getStyledTextSegments`, sends structured-clone-safe messages through `figma.ui.postMessage`, stores bridge credentials only through `figma.clientStorage`, and requests raster fallback bytes with PNG `SCALE` 1 export settings. The iframe receives controller messages through the documented own `event.data.pluginMessage` property without assuming a specific forwarding `event.source` or a closed schema for Figma routing metadata. Routing metadata is ignored, while every `ControllerToUi` payload remains exact-key and nested-schema validated.

The full-lesson host adapter uses the official [`figma.getNodeByIdAsync`](https://developers.figma.com/docs/plugins/api/figma/) API, accessed 2026-07-23. The official API returns a promise resolving to the document node or `null`; Figma's [dynamic-page loading migration guidance](https://developers.figma.com/docs/plugins/migrating-to-dynamic-loading/), also accessed 2026-07-23, uses the asynchronous lookup in place of `figma.getNodeById`.

That platform boundary is intentionally narrow: the production runtime exposes only `ControllerHost.getNodeByIdAsync(nodeId)` to the full-lesson controller. The controller resolves the 48 embedded canonical IDs sequentially, rechecks cancellation after every awaited host call, and then applies the existing file-key, page, section-ancestry, node-name, dimension, order, serialization, hashing, and bridge validations. Tests replace only this adapter method; they do not emulate or widen the Figma Plugin API. The wire schema remains `2.0.0`, while exporter release metadata is `0.2.0`.

Figma desktop runs the plugin UI in a null-origin iframe where Web Crypto is not guaranteed. Package fingerprints therefore use the shared pure `sha256Hex` implementation; neither generated Figma bundle depends on `crypto.subtle`, and the UI bundle is checked for that dependency at build time.

The development manifest and controller share the documented `http://localhost:3456` origin. The bridge server remains bound to the numeric IPv4 loopback address `127.0.0.1`; changing the client URL does not broaden the server bind interface.

This private, project-local exporter sets the manifest's `enablePrivatePluginApi` to `true` so the documented `figma.fileKey` property is available during local development. The controller continues to fail closed unless both the exact configured file key and page ID match; the private-API flag does not weaken source validation.

Official Figma `get_metadata` evidence for page `90:2`, accessed 2026-07-22, established the prepared-shot SECTION ancestry embedded by the build:

- Shots 1-4: `90:5`, `02 Shots 01-04 — Hook`
- Shots 5-9: `90:6`, `03 Shots 05-09 — Direct Explanation`
- Shots 10-17: `90:7`, `04 Shots 10-17 — Technical Meaning`
- Shots 18-25: `90:8`, `05 Shots 18-25 — Tiny Example`
- Shots 26-32: `90:9`, `06 Shots 26-32 — Repository Walkthrough`
- Shots 33-39: `90:10`, `07 Shots 33-39 — Live Mini-Lab`
- Shots 40-43: `90:11`, `08 Shots 40-43 — Common Mistake`
- Shots 44-48: `90:12`, `09 Shots 44-48 — Recap & Exercise`

The build validates the timing source's corresponding eight section names and shot ranges before attaching the exact Figma section ID and display name to every embedded shot. Runtime selection accepts only a direct child of that exact SECTION whose direct parent is the configured PAGE by ID; it does not rely on Figma proxy object identity.
