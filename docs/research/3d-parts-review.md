# 3D parts discovery review

Scope: `git diff 7e83789...7f893ee`, excluding `web/vendor/three.module.min.js`. I read the code against `docs/3d-parts-discovery.md`. I didn't open a browser; the browser results here come from the implementer.

## Findings

### 1. Medium: every Discovery search keystroke or delivery-slider step rebuilds the WebGL scene
`web/app.js:886-893` calls `render()` on each `input` event. `render()` (`app.js:472-529`) destroys `partsScene` and calls `mountParts` again. That creates a new `WebGLRenderer` and rebuilds all the geometry, including the bogie springs (each a 140-segment `TubeGeometry`). `disposeWebGL` (`web/parts-scene.js:367-382`) calls `renderer.dispose()` but never `renderer.forceContextLoss()`. Contexts stay alive until garbage collection, so dragging the delivery slider can trigger Chrome's "Too many active WebGL contexts" warning and visible jank. The train scene on the overview has the same pattern, but it isn't exposed to text input.
Fix: call `renderer.forceContextLoss()` in `disposeWebGL`. Keep the scene mounted while `filters.region` is unchanged and update it with `partsScene.highlight(part)`, which is already exported but never used.

### 2. Medium: clicking a part resets the user's rotation
`selectPart` (`app.js:228-242`) calls `render()`, which remounts the scene. `yaw`/`pitch` then go back to their defaults (`parts-scene.js:256-257`). A buyer who rotated the assembly to reach a hidden component (for example, a bearing behind a wheel) sees the view jump back after each pick. Click-vs-drag detection itself is correct: 5px threshold, pointer capture released, and `pointercancel` handled.
Fix: same as #1 (call `highlight` instead of remounting), or keep yaw/pitch in `state` and pass them into the scene.

### 3. Low–Medium (spec): Recents records actions that aren't inspections
The spec says Recents holds "actually inspected suppliers". `toggleCompare` (`app.js:567`) adds to Recents for checkbox toggles, including *removing* a supplier from comparison. `app.js:669-673` also adds for `favorite` and `recommend`. Unchecking a row in Discovery therefore moves that supplier to the top of Recents.
Fix: only record detail views, source-cell views (`cells`), `compare-focus`, and overview card focus.

### 4. Low: the WebGL fallback after context loss shows stale copy
After `contextLost` (`parts-scene.js:383-387`), the SVG fallback is prepended but the `.pa-note` from line 12 still says "drag to rotate". Nothing in the fallback rotates. Initial-failure fallback (line 18) has the same issue.
Fix: update the note text in `fallback()`.

### 5. Low: the train context-loss path leaves the renderer live
`train.js:376-379` switches to the SVG fallback but leaves the canvas listeners and renderer in place until `destroy()`. A context restore is never handled, so the 3D view doesn't come back. This is acceptable for a demo; noted for completeness.

## Checked and correct
- **Part filter:** `filtered()` matches on `train_part_id` together with the other filters. Changing the system dropdown (`app.js:869-872`), `selectRegion`, `discover-region`, and the tour steps all clear the part; Clear filters resets both. Comparison selection isn't touched by any filter path.
- **All systems:** shows the "Choose a train system" panel with no scene.
- **Part data:** manifest part IDs match the bogie mesh IDs exactly (six parts), and every other system's parts are rendered from the manifest. Records without a part count toward All parts only, and the unassigned note is correct. The new backend test covers every system/part pair.
- **Recents persistence:** client and server both cap the list at 50. The server rejects unknown IDs and removes duplicates while keeping order, recovery mode applies the 50 limit, and the list is re-filtered on load. Overview tabs are Recents and Previously used only.
- **XSS:** labels go through `esc()` in templates and `textContent`/`setAttribute` in the scenes, so no unescaped data reaches `innerHTML`.
- **Vendor:** local Three.js r170 is a single-file module with no CDN import, and its MIT LICENSE is included.
- **Motion:** no autoplay or inertia, and rotation is clamped in both scenes.
