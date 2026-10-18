# Gretel chat: LangChain visual research

Researched 2026-10-18. Scope: first-party visual patterns, not a framework migration.

## Visual evidence

[Open the self-contained contact sheet](assets/gretel-chat/contact-sheet.html) or [view the image](assets/gretel-chat/contact-sheet.jpg). Four panels use two actual first-party screenshots and two explicitly labelled detail crops. They are not invented mockups.

| Local asset | Original | Rights / purpose |
| --- | --- | --- |
| open-canvas-document.png | https://raw.githubusercontent.com/langchain-ai/open-canvas/main/static/screenshot.png | Open Canvas MIT; reference screenshot |
| open-canvas-workspace.png | https://raw.githubusercontent.com/langchain-ai/open-canvas/main/apps/web/public/screenshot.png | Open Canvas MIT; reference screenshot |
| conversation-composer-detail.png | crop of open-canvas-document.png | Same source and license |
| evidence-cards-detail.png | crop of open-canvas-document.png | Same source and license |

License copied verbatim to `assets/gretel-chat/open-canvas-LICENSE.txt`. Images are documentation references only, not shipped application UI or endorsement.

## Verified patterns

- Agent Chat UI renders artifacts separately from the conversation, in a panel to its right. Its artifact source separates title, content and mounted state. This supports a reusable chart/report card rather than encoding every answer as prose. [README](https://github.com/langchain-ai/agent-chat-ui#rendering-artifacts), [artifact source](https://github.com/langchain-ai/agent-chat-ui/blob/main/src/components/thread/artifact.tsx).
- Open Canvas supports quick actions and versioned artifacts. Its supplied screenshots show assistant prose without large enclosing bubbles, quiet user prompts, a persistent bottom composer, and a separate evidence column with source titles and metadata. [Official repository](https://github.com/langchain-ai/open-canvas), screenshots above.
- Deep Agents UI describes planning, files visible during runs, and opening files for inspection. This is useful inspiration for progressive activity plus final output. The repository is archived, as is Open Canvas; these are design references, not dependency recommendations. [Deep Agents UI](https://github.com/langchain-ai/deep-agents-ui), [Open Canvas](https://github.com/langchain-ai/open-canvas).

## Apply to Gretel

These are our design recommendations, not claims about LangChain functionality:

1. Keep the current teal, slate, off-white and restrained risk colors. Use the existing rounded panel and icon language; no LangChain branding.
2. Give Gretel a calm header, a short context line, and a compact mode switch. The transcript should be the largest area. User prompts can have a pale teal background; assistant answers read as editorial text.
3. Put the composer in one bordered surface with textarea, mode, and send/stop action. Do not stack multiple card borders around it.
4. Show one compact run card: current phase, elapsed/progress information only when actually known, and an expandable checklist/activity log. Real events determine the phase; never invent planning progress.
5. Answers can contain ordered blocks: concise summary with small numbered inline citations, a chart card, then source details and report actions. Keep citation numbers local to each answer and resolve only valid source IDs.
6. Chart cards need a title, metric/unit, provenance caption, accessible values/table, and room to expand. Support radar and comparison bars through a small typed renderer. This is inspired by artifact separation; it does not require a new framework.
7. A research radar must only plot available numeric scores with a named scoring method. Unknown research values remain missing, never zero. Qualitative source findings cannot be silently converted to six-axis quantitative scores. A sourced dataset radar can accompany a research answer when entity/context matching is explicit.
8. Do not copy developer-oriented tool argument tables into the buyer UI. Human phase labels and optional details are enough.

## Limits / verification

Both original screenshots were opened and visually inspected. The contact sheet is a static composition of those assets, not a live capture of the current product. Agent Chat live-site screenshots were attempted in the T3 preview; both snapshot attempts returned `Preview automation snapshot timed out after 15000ms.` The contact sheet therefore relies on the official repository screenshots and labels that provenance clearly. No login, API key, or paid research run was used. No application code was changed.
