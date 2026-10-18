// Research citations: numbered chips, and a side panel with the exact quote highlighted in
// its surrounding text, the source, date, trust label and a deep link to the quote.
// Pure helpers are exported for tests (tests/test_citations.mjs).
import { safeURL } from "./api.js";
import { icon } from "./icons.js";

export const TRUST = {
  trusted: "Trusted source",
  company_stated: "Trusted source · the company's own statement",
  unverified: "🟨 Not in our trusted source list",
};

export function findCitation(run, n) {
  return (run?.citations || []).find((c) => Number(c.n) === Number(n)) || null;
}

// Split the excerpt into before / quote / after using the server's character offsets.
// Falls back to the quote alone when the offsets do not point at the quote.
export function quoteParts(c) {
  const quote = String(c?.quote || "");
  const excerpt = String(c?.excerpt || "");
  const s = Number(c?.quote_start),
    e = Number(c?.quote_end);
  if (quote && excerpt && Number.isInteger(s) && Number.isInteger(e) && s >= 0 && e > s && e <= excerpt.length) {
    // The server matches words; take trailing punctuation that is part of the quote too.
    let end = e;
    while (end < excerpt.length && /[.,;:!?"”’)]/.test(excerpt[end]) && quote.trimEnd().endsWith(excerpt.slice(e, end + 1))) end++;
    return { before: excerpt.slice(0, s), quote: excerpt.slice(s, end), after: excerpt.slice(end) };
  }
  return { before: "", quote, after: "" };
}

// The deep link only if it is an http(s) link to the same page as the source URL.
export function fragmentLink(c) {
  const url = safeURL(c?.url || "");
  if (url === "#") return "";
  const link = String(c?.link || "");
  if (!link || safeURL(link) === "#") return url;
  return link.split("#")[0] === url.split("#")[0] ? link : url;
}

export function trustLabel(c) {
  return TRUST[c?.trust] || TRUST.unverified;
}

export function citeChip(c, esc, runId = "") {
  if (!c) return "";
  const unverified = c.trust === "unverified";
  const label = `Source ${c.n}: ${c.publisher || c.title || "source"}${unverified ? " (not in our trusted source list)" : ""}`;
  return `<button type="button" class="cite-chip${unverified ? " unverified" : ""}" data-cite-n="${esc(c.n)}" data-cite-run="${esc(runId)}" aria-label="${esc(label)}" title="${esc(label)}">${esc(c.n)}</button>`;
}

export function createCitationPanel({ esc }) {
  const panel = document.createElement("aside");
  panel.id = "cite-panel";
  panel.className = "cite-panel";
  panel.hidden = true;
  panel.setAttribute("aria-live", "polite");
  panel.setAttribute("aria-labelledby", "cite-panel-title");
  document.body.append(panel);
  let current = null,
    returnFocus = null;

  function render(c) {
    const parts = quoteParts(c);
    const link = fragmentLink(c);
    const page = safeURL(c.url || "");
    const domain = page !== "#" ? new URL(page).hostname.replace(/^www\./, "") : "";
    const quote = parts.quote
      ? `<blockquote class="cite-quote">${parts.before ? `<span>${esc(parts.before)}</span>` : ""}<mark>${esc(parts.quote)}</mark>${parts.after ? `<span>${esc(parts.after)}</span>` : ""}</blockquote>
         <p class="small muted">${c.context_found ? "Quote checked against the page text we read." : "Quote as recorded when the fact was checked."}</p>`
      : `<p class="cite-quote empty">This source supports the finding as a second, independent source. The quote is shown on the main source.</p>`;
    panel.innerHTML = `<div class="cite-head"><div><div class="eyebrow">Source ${esc(c.n)}${c.area_label ? " · " + esc(c.area_label) : ""}</div><h3 id="cite-panel-title" tabindex="-1">${esc(c.title || c.publisher || "Source")}</h3></div><button type="button" class="icon-button quiet" data-cite-close aria-label="Close source">${icon("close")}</button></div>
      <div class="cite-meta"><span class="trust-badge ${c.trust === "unverified" ? "unverified" : "trusted"}">${esc(trustLabel(c))}</span><span>${esc(c.publisher || domain)}</span><span>${c.published ? "Published " + esc(c.published) : "Publication date not stated"}</span>${c.accessed ? `<span>Read ${esc(c.accessed)}</span>` : ""}</div>
      ${quote}
      <div class="cite-actions">${link ? `<a class="button primary" href="${esc(link)}" target="_blank" rel="noopener noreferrer">${icon("arrow_forward", "sm")}Open at quote</a>` : ""}${page !== "#" ? `<a class="button" href="${esc(page)}" target="_blank" rel="noopener noreferrer">Open source</a>` : ""}${parts.quote ? `<button type="button" data-cite-copy>Copy quote</button>` : ""}</div>
      ${link && link !== page ? '<p class="small muted">“Open at quote” scrolls to the passage in most browsers; PDFs and some pages open at the top.</p>' : ""}
      ${domain ? `<p class="small muted cite-domain">${esc(domain)}</p>` : ""}`;
  }

  function open(c, anchor) {
    if (!c) return;
    if (current && current.n === c.n && current.run === c._run && !panel.hidden) return close();
    current = { n: c.n, run: c._run };
    returnFocus = anchor || null;
    render(c);
    panel.hidden = false;
    document.body.classList.add("cite-open");
    panel.querySelector("#cite-panel-title")?.focus();
  }
  function close() {
    if (panel.hidden) return false;
    panel.hidden = true;
    current = null;
    document.body.classList.remove("cite-open");
    if (returnFocus?.isConnected) returnFocus.focus();
    returnFocus = null;
    return true;
  }
  panel.addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.hasAttribute("data-cite-close")) close();
    if (b.hasAttribute("data-cite-copy")) {
      try {
        await navigator.clipboard.writeText(panel.querySelector("mark")?.textContent || "");
        b.textContent = "Copied";
      } catch {
        b.textContent = "Copy not available";
      }
    }
  });
  return { open, close, isOpen: () => !panel.hidden, element: panel };
}
