# 3D train and system-to-part discovery

Baseline: 7e83789. Implement directly on main. Review server: port 8880.

## Behavior

- Overview uses a compact procedural 3D passenger train with a tapered nose, white body, red stripe and dark windows inspired by the ICE. Region picking, hover counts, bounded drag rotation and labelled system buttons remain available. The model is illustrative, not engineering CAD.
- Selecting a system and choosing Discover opens its exploded assembly. Clicking a component or its labelled chip filters suppliers by part. These filters combine with search, risk level, delivery and relationship filters. Changing system clears the part; Clear filters clears both. Comparison selection survives filter changes.
- With All systems selected, Discovery asks the buyer to choose a system before displaying an assembly.
- Use the existing augmented CSV fields `train_region_id` and `train_part_id`, with labels and membership from the manifest. Preserve both CSV files and their hashes. Research-only records without a part assignment appear under All parts and do not match a specific part.
- The overview has two visible tabs: Recents and Previously used. Recents contains actually inspected suppliers in most-recent-first order, with up to 50 IDs persisted. Previous use remains labelled demo metadata. Favorites and risk ordering stay in Discovery and the portfolio.
- Use pinned local Three.js, render on demand, dispose scenes when leaving a view, and provide keyboard alternatives and a WebGL fallback. No walkthrough update requested.

## Verification

Test recent-ID ordering, persistence and validation, plus every augmented part/system pair. Check browser navigation from system to Discovery to part: bogie frame and suspension each have 334 supplied records; damper, wheel, axle and axle bearing each have 333. Verify combined filters, part reset, comparison preservation, recents after reload, real mesh picking, desktop/mobile layout and fallback behavior. Review, commit and push main.

## Verification outcome

- All 28 backend tests pass, including recent-ID persistence/order/bounds and all 10,000 system/part assignments. Original and augmented CSV files are unchanged.
- Browser: clicking the actual wheel mesh selects `wheel` and returns 333 rows; frame returns 334. The existing 20-supplier comparison survives part changes. All nine systems render their manifest parts.
- Recents starts empty, records inspection, and survives reload. Favorites and rejected comparison additions do not promote records. Previously used shows the existing demo tags.
- Assembly canvas identity is preserved across search and part selection, including after a drag rotation. Changing system destroys the prior canvas. WebGL context loss enables a working labelled fallback.
- Desktop 1440x790 and mobile 390x844 screenshots checked. Scene height and camera distance corrected to prevent cropping. Part controls and notes use at least 12px text.
- Opus review: `docs/research/3d-parts-review.md`. Findings addressed: reuse the scene, preserve rotation, strictly record inspected recents, correct fallback instructions, and release GPU contexts/listeners on destruction and loss. An independent spec audit confirmed filtering and persistence behavior; the in-app tour was adjusted only to remove references to the obsolete fixed shortlist. No new video was produced.
