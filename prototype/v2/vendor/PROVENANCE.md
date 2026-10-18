# Three.js provenance

Vendored from the official mrdoob/three.js repository, tag r170 (Three.js 0.170.0), 18 October 2026:
https://raw.githubusercontent.com/mrdoob/three.js/r170/build/three.module.js

The source is intentionally unminified despite the contract filename `three.module.min.js`: this preserves the stable in-module class bindings used by the appended renderer. It is a complete single-file ES module with no imports. The build inlines this file followed by train-scene.js into one module script, so file:// requires no network access.

SHA-256: ce1fa418de16a19495a9f72495580e3015d7745c296d3ce0485897f902ddedfb

MIT license is reproduced in LICENSE, from the same tag:
https://raw.githubusercontent.com/mrdoob/three.js/r170/LICENSE
