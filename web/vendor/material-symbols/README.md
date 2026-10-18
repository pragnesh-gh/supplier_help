# Material Symbols subset

Thirty-four unmodified, 24px Material Symbols Outlined SVGs from Google's
[material-design-icons repository](https://github.com/google/material-design-icons),
pinned to commit `49d4db35df873165d6bd6ba09b063c7dafbac2f4`.

The original files are at
`symbols/web/<name>/materialsymbolsoutlined/<name>_24px.svg`.
`manifest.json` records each exact source URL, byte length, and SHA-256 digest.
The upstream Apache 2.0 license is included in `LICENSE`.

Available names: `train`, `search`, `compare_arrows`, `description`, `fact_check`,
`history`, `star`, `chat`, `close`, `filter_list`, `download`, `arrow_forward`,
`restart_alt`, `check`, `info`, `expand_more`, `star_filled`, `bookmark`,
`bookmark_filled`, `dashboard`, `explore`, `bookmarks`, `summarize`, `approval`,
`tour`, `shopping_cart`, `add_shopping_cart`, `remove_shopping_cart`, `delete`,
`open_in_full`, `playlist_add`, `playlist_add_check`, `playlist_remove` and
`checklist`. The filled variants are the upstream
`symbols/web/<name>/materialsymbolsoutlined/<name>_fill1_24px.svg` files
(`star`, `bookmark`), renamed locally to distinguish their selected state.
Favourites use `bookmark` / `bookmark_filled`; the star files are kept but unused.

Serve these files locally; no Google Fonts request, remote runtime asset, or
package dependency is needed. Use a CSS mask with `background: currentColor`
for theme-aware color, or an image with an empty `alt` when its adjacent label
already describes the action. An icon-only button still needs an accessible
name on the button. Icons supplement existing text rather than replacing it.
