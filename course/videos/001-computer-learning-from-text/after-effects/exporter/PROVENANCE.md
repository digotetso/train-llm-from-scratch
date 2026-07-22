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

The development manifest and controller share the documented `http://localhost:3456` origin. The bridge server remains bound to the numeric IPv4 loopback address `127.0.0.1`; changing the client URL does not broaden the server bind interface.
