# Overview and Discovery refinement

The supplier ring is removed from the active landing page. Restore the six-axis radar and default it to the scored supplier with the lowest supplied Total Risk Index in the selected system/part. Break ties by supplier ID. Unknown scores cannot win. The label must name the ranking metric: this is a data ranking, not supplier qualification or an award recommendation.

Keep recently inspected records distinct from suppliers with demonstration purchase history. Use clear collection labels and preserve their underlying behavior. Shortlist approval remains unchanged.

On entering Discovery, briefly show the assembly together, give it a restrained introductory turn, and separate its component groups into the existing exploded arrangement. This is a finite entrance animation, not a loading spinner. It must not replay on part/filter changes that preserve the scene. Pointer interaction should finish the entrance immediately; reduced-motion preference should show the settled exploded state without animation. Dispose scheduled animation work when leaving the page or losing WebGL.

Correct the dark cab glazing at the train's tapered nose so it follows the shell surface instead of projecting out as rotated boxes. Preserve the white/red appearance and existing selectable systems.

Validation covers radar scope/default/unknown handling, collection labels, animation lifecycle, reduced motion, part filtering, train interaction, syntax and regression tests. Baseline: `25943e4`.

## Verification outcome

- Independent Standards review and Opus Spec review found no blockers. Follow-up polish aligns the prior-use badge wording, opens supplier details from overview cards, and makes the profile chat prompt refer to the radar's supplier.
- 33 Python tests and 2 existing JavaScript regression tests pass; syntax checks pass for all three changed modules.
- All nine assemblies were exercised with a controlled animation clock. Reduced motion, interruption, completion and cleanup were checked; no callbacks remained after destruction.
- Browser checks confirmed the bogie-wide radar selects SUPP_04741 (total 9), while the wheel scope selects SUPP_01420 (total 14). Part selection preserves the canvas and does not replay the entrance.
- Overview fits 1440×790 without scrolling or horizontal overflow; narrow-screen radar and tabs also have no horizontal overflow. Discovery retains ordinary table scrolling.
- Normal and rotated train screenshots confirm the cab glazing lies flush. Entrance screenshots show assembled and separated poses. These are illustrative component models, not engineering CAD.

Historical collection options were Guided suppliers, Lowest total risk, Favorites and Previously used. Active tabs now read Recently viewed and Used before, with distinct browsing and demo sourcing-history captions.
