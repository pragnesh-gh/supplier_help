# Unified app verification

Baseline: aaf5b7a on main. Status: implementation and verification in progress.

## Acceptance record

| Area | Required verification |
| --- | --- |
| Source data | Original CSV hash preserved;10000 rows; augmented metadata distinguished |
| Data assistant | Challenge financial answer53/54/65, exact citations/chart, high-total explanation without invented weights; unknown question clarifies |
| Research | Explicit saved example vs live, correct company identity, selected CSV context isolated, actual events and errors, clean source links |
| Workspace | Favorites, compare selection, chat and approval draft restored after reload; safe bounded persistence |
| UI | Compact2D train selection, no permanent landing chat panel, bubble keyboard/Escape, same conversation across routes, mobile |
| Discovery | Filter/sort/page, compare max20, retain selection across views |
| Reports | Source-linked research report; add unscored company; approval draft/print uses actual saved data |
| HTTP | Loopback host/origin checks, bounded bodies, no secret/static path escape |
| Delivery | One command/local URL, README/code map, final tests, code review and main commit |

## Review rounds

Opus preflight: docs/research/unified-app-preflight.md. This is architecture feedback, not final acceptance. Five key integration findings cover example request naming, workspace body size, separate storage roots, anonymous-vs-real identities, and isolated dataset context. Final implementation review will use the fixed baseline above.

## Scope

User selected localhost instead of public hosting for this pass. Real telemetry remains absent; example trends retain clear labels. Public research uses provider excerpts/source links, not exhaustive crawling or independently audited source text. No live research claims are inferred from automated fake-provider tests.
