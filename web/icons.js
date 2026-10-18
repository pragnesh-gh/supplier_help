// Decorative Material Symbols (Apache 2.0) served from web/vendor/material-symbols.
// Icons always sit next to a visible label or inside a control with its own accessible name.
const NAMES = new Set([
  "train", "search", "compare_arrows", "description", "fact_check", "history",
  "star", "chat", "close", "filter_list", "download", "arrow_forward",
  "restart_alt", "check", "info", "expand_more", "bookmark", "bookmark_filled",
  "arrow_back", // mirrored arrow_forward (see ui.css)
]);

export function icon(name, className = "") {
  if (!NAMES.has(name)) return "";
  return `<span class="msi msi-${name}${className ? " " + className : ""}" aria-hidden="true"></span>`;
}
