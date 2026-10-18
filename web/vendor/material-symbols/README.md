# Material Symbols subset

Seventeen unmodified, 24px Material Symbols Outlined SVGs from Google's
[material-design-icons repository](https://github.com/google/material-design-icons),
pinned to commit `49d4db35df873165d6bd6ba09b063c7dafbac2f4`.

The original files are at
`symbols/web/<name>/materialsymbolsoutlined/<name>_24px.svg`.
`manifest.json` records each exact source URL, byte length, and SHA-256 digest.
The upstream Apache 2.0 license is included in `LICENSE`.

Available names: `train`, `search`, `compare_arrows`, `description`, `fact_check`,
`history`, `star`, `chat`, `close`, `filter_list`, `download`, `arrow_forward`,
`restart_alt`, `check`, `info`, `expand_more`, and `star_filled`. The filled star is the upstream
`symbols/web/star/materialsymbolsoutlined/star_fill1_24px.svg` variant,
renamed locally to distinguish its selected state.

Serve these files locally; no Google Fonts request, remote runtime asset, or
package dependency is needed. Use a CSS mask with `background: currentColor`
for theme-aware color, or an image with an empty `alt` when its adjacent label
already describes the action. An icon-only button still needs an accessible
name on the button. Icons supplement existing text rather than replacing it.
