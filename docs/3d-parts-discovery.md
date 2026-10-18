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
