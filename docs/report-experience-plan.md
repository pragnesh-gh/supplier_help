# Report experience: chat, report page and what happens after

How a user meets our research agent inside the product. Covers memory, the chat TL;DR, the report page, the charts, and how a report connects to favorites, compare and the shortlist. The backend wiring (adapter, routes, run object) is in [integration-plan.md](integration-plan.md); this file is the user-facing side.

Read from `main` after the merge of 2026-10-18 (`web/chat.js`, `web/app.js`, `supplier_app/core.py`, `docs/shortlist-approval.md`).

---

## 1. What the app does today (facts)

| Thing | Today on main | Problem for us |
| --- | --- | --- |
| Chat memory | **One** conversation, saved on the server in `.local/.../workspace.json` (max 200 messages, 100 KB). Survives reload and restart. "Reset" wipes it. | No list of past chats. Follow-up questions only work on the **last** completed run (`state.run`). |
| Research runs | Saved in `state.json`, survive restart, listed under **Reports**. | Older runs can only be opened, not asked about. |
| Chat TL;DR | Text summary + counts + "Read report" + "Add as unscored supplier". | No scores, no radar, no citations, no favorite/shortlist. |
| Report | Opens as a **modal dialog** (`showRisk` → `riskDocument`). Print / Markdown export. | Not a page you can link to, go back to, or keep open while comparing. |
| Researched company | "Add as unscored supplier" makes a `research:<id>` row: all scores Unknown, no radar. | We now have real scores; this label is wrong. |
| Favorites, compare, shortlist | Work on any row, including `research:` rows. Shortlist suggestion ranks by the dataset `Total_Risk_Index`. | Must keep real-company scores **apart** from the synthetic dataset scores (agreed rule). |

So the app does not "forget" when the session ends. But it does forget **which report you are talking about**, and there is only one conversation.

## 2. Memory: the report is the memory

Main idea: the chat stays light, and every finished research run is a saved report that the user can come back to and ask about.

1. **Every run is saved as a report** (already true). The report has a fixed id, date and version.
2. **"Ask about this report"** button on the report page and on the TL;DR card. It opens the chat with that report pinned at the top ("Talking about: Knorr-Bremse AG · report of 18 Oct"). Follow-ups use that `run_id`, not just the latest run. *Why:* fixes the "only the last run" limit with one small change.
3. **Same company asked again** → the chat answers: "We researched Knorr-Bremse on 18 Oct (Medium, 41). Open it, or run a fresh check?" Uses our `cache.py`. *Why:* saves Tavily credits and time, and the user sees history instead of a duplicate.
4. **Stale reports** older than 30 days show a "Refresh" chip. A refresh is a new version; `diff_runs.py` shows "what changed since last time".
5. **Several conversations** (a history list like ChatGPT) are not needed for the demo. The reports list already acts as the history. Can be added later.

## 3. Chat TL;DR card (the first thing the user sees)

One card, not a wall of text. Top to bottom:

```
┌─────────────────────────────────────────────────────────┐
│ Knorr-Bremse AG · DE                  18 Oct · 42 sources│
│ ● Medium risk  41/100   coverage 5 of 6 areas           │
│                                                         │
│  [ mini radar, 6 areas ]   • 2 open safety recalls  ①③   │
│  hollow dot = not assessed • Fined €3M in 2024 ②         │
│                            • Strong cash position ④      │
│                            • No sanctions hits ⑤         │
│                                                         │
│ [Open report]  [☆ Favorite]  [+ Shortlist]  [Compare]   │
│ Ask about this report ›                                 │
└─────────────────────────────────────────────────────────┘
```

- **Radar**: the 6 umbrellas. An area with no evidence is a hollow dot at the edge, labelled "Not assessed" (never 0). It is the same radar as in the report, only smaller.
- **3 to 5 points**, red flags first, then watch items, then strengths. Each point has numbered citation chips.
- **Citation chip** → a side panel with the exact quote highlighted, source name, date, trust label (trusted or 🟡) and a deep link that jumps to the quote on the source page. Same numbers in chat, report and export.
- **While running**: the card shows live steps ("Checking finances… 12 sources") and fills in when done. No spinner-only wait.
- **Needs clarification** ("Which Knorr-Bremse: AG or Systems for Rail Vehicles GmbH?") shows as clickable options.

## 4. Report page (Reports section)

Move the report from a modal to its own page: `#/reports/<id>`. *Why:* it can be linked, bookmarked, opened next to Compare, and the back button works. The Reports list links to it.

**Recommendation: build the page natively in `web/` from the run JSON**, using the same section order as `report_html.py`. Keep `report_html.py` for print, PDF and HTML export. *Why:* an `<iframe>` of `report_html.py` (the idea in integration-plan.md section 3.6) cannot have clickable citations, hover, or buttons that talk to the app, because it must be script-free. A native page can do all of that and still look identical when printed.

Layout, following our risk report structure:

**Top bar (always visible):** company, country, date, status · actions: Favorite, Add to shortlist, Compare, Ask about this report, Refresh, Export (PDF / Markdown / HTML).

**Page 1, at a glance**
1. Verdict banner: one sentence, coloured by level.
2. Total score: big number + level band bar (Low 0–24, Medium 25–49, High 50–74, Critical 75–100) + coverage ("5 of 6 areas assessed").
3. Radar of the 6 umbrella scores (clickable: a click on an axis scrolls to that area).
4. Red flags and watch items, each with chips.
5. Strengths.
6. Recommended next steps (these become the follow-up action list, with owner and status, which already exists on main).

**Page 2, detail (expandable on screen, full in print)**
7. Area table: score · level · coverage · number of sources (trusted / 🟡) per area.
8. Event timeline: dated flags on a time axis (exists in `report_html.py`).
9. "How was this scored?": a drawer with the per-fact breakdown: fact → rule → points → area score → weight → total.
10. Sources: trust label, date, link.
11. Method and limits.

**Charts, and why each one is there**

| Chart | Where | Why |
| --- | --- | --- |
| Radar, 6 areas | Chat card, report, supplier detail | Whole profile at a glance; it is the agreed overview. |
| Level band bar for the total | Report top | Shows where 41 sits (Medium) without reading a legend. |
| Event timeline | Report page 2 | Shows if problems are old or recent. |
| Score breakdown (stacked bar per area) | "How was this scored?" | Shows which facts moved the score. Builds trust. |
| Coverage bars (trusted vs 🟡 sources per area) | Area table | Shows how much evidence sits behind each number. |

No other charts. More charts would make it look like a generic dashboard.

## 5. After the report: connecting to the product

| Action | Where it appears | What happens | Rule |
| --- | --- | --- | --- |
| **Favorite ☆** | TL;DR card, report top bar, supplier detail | Saves the company as a `research:` supplier **and** stars it, in one click. Today this needs two steps. | It shows in My suppliers → Favorites. |
| **Add to shortlist** | Card, report, supplier detail | Adds to the comparison set and opens the shortlist builder (shortlists need 3–5 suppliers). | The automatic suggestion still ranks dataset suppliers only; a researched company is added by the buyer by hand. |
| **Compare** | Card, report | Adds to the comparison. | The research score sits in its **own labelled row** ("Public research score, not comparable to dataset scores"). Never in the same radar or ranking as dataset suppliers. |
| **Submit shortlist for approval** | Approvals | The approval request freezes a copy of the report (scores, TL;DR, sources, report version). | Already done for the old dossier; switch it to our report fields. |
| **Follow-up actions** | Report page 1 | "Next steps" become tasks with owner and status. | Exists on main; we feed it from our next steps. |
| **Refresh** | Report top bar, Reports list | New run, new version, "what changed". | Old versions stay readable. |
| **Export** | Report top bar | PDF (print), Markdown, HTML. | Same citation numbers everywhere. |

New places that show research results:
- **My suppliers** → new tab **"Researched"** next to Favorites and Previously used. Cards show the research score with a "Public research" tag.
- **Supplier detail** for a `research:` row → our radar (not the dataset radar) and "Open report".
- **Reports list** → cards with company, date, total + level, mini radar, flag count, Fresh/Stale.
- **Overview** (train page) → unchanged. Real companies are not part of the train's dataset statistics.

Rename "Add as unscored supplier" → **"Save to my suppliers"**, because we now have scores.

## 6. Making it not look like a normal AI tool

- Structured cards, numbers and levels, not long chat paragraphs. The chat answer for research is the card, nothing else.
- Every claim has a chip. No claim without a source.
- Fixed template: same sections in the same order every time, so users learn where to look.
- Use the app's existing style: Material components, colours and type in `web/styles.css` (see `docs/ui-polish.md`). No new design language.
- Plain labels: "Not assessed", "Public research", "Trusted source" / 🟡 "Not in our trusted list". No "AI-generated insights".
- Live progress shows real steps, not a fake typing effect.

## 7. Build order

1. Backend adapter from integration-plan.md (run object has `scores`, `tldr`, `citations`, `scoring`).
2. TL;DR card in `web/chat.js` with the radar and chips, and the citation side panel (`web/citations.js`).
3. Report page `#/reports/<id>` in `web/app.js`, plus print styles.
4. Action buttons wired to the existing favorite, compare and shortlist code; the "Researched" tab; supplier detail radar.
5. "Ask about this report", same-company reuse, Refresh with diff.
6. Approval snapshot switched to our report fields.

## 8. Open decisions

1. Report page native in `web/` (recommended) or `report_html.py` in an iframe?
2. One conversation plus a reports list as memory (recommended), or a list of past chats as well?
3. Researched companies in Compare: own labelled score row, kept out of the automatic shortlist ranking (recommended, follows the "keep separate" rule). OK?
