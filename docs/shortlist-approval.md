# Supplier shortlist and approval to negotiate

The buyer explores a system or part, compares candidates, and prepares a shortlist of three to five suppliers. The request asks a named reviewer for permission to negotiate with that shortlist. It does not select a winner or authorize a purchase.

## Selection policy

The suggestion ranks the buyer's comparison set by the supplied Total Risk Index, lowest first. It starts with three scored suppliers and can include the fourth and fifth if their scores are within five points of the third supplier. This is a visible demo heuristic, not a Siemens procurement policy or a claim about technical suitability. Buyers can change the selection; submitting requires three to five distinct suppliers. Unscored researched companies remain unknown and require manual judgement.

Each candidate needs buyer-written trade-offs and negotiation questions. Useful questions include delivery commitments, capacity, price breaks, quality evidence, and how an identified risk will be mitigated. These are preparation notes, not invented supplier quotations or negotiated terms.

## Request record

The request contains project, requester, intended reviewer, scope, shortlist rationale, candidate notes, and source snapshots. The server saves an immutable request with an ID, creation time and `awaiting_approval` status. Subsequent changes to comparison or favorites do not change it. The app can display and print the same saved record.

This localhost version ends at a saved request. Requester and reviewer are named fields, not authenticated roles. It does not send email or claim that an approver has approved it. Actual approval decisions, identity controls and negotiation tracking can be added later.

## Supplier ring

Historical design, superseded by [the radar and motion update](overview-motion-update.md). The active landing page now uses the radar; shortlist approval behavior above remains current.

The landing page groups the selected system/part's suppliers by the dataset's supplied risk level, with critical near the center and low risk outside. Counts cover the full selected scope; a clearly labelled deterministic sample of clickable dots keeps the view readable. Position within a band does not add another risk ranking. Purchase-order volume controls dot size where available, and favorites are outlined. Unscored companies are counted separately.

System and part assignments remain synthetic demo metadata. The ring does not invent history or telemetry. Supplier risk profiles remain available in detail and comparison views.
