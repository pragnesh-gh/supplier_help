// Pure helpers for research citations and the TL;DR card (no browser needed).
import assert from "node:assert/strict";
import { findCitation, quoteParts, fragmentLink, trustLabel, citeChip } from "../web/citations.js";
import { radarSVG, bandBar, researchCard } from "../web/research-card.js";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const c = { n: 1, url: "https://www.example.org/a", link: "https://www.example.org/a#:~:text=fined", quote: "was fined",
  excerpt: "The firm was fined today.", quote_start: 9, quote_end: 18, trust: "trusted", publisher: "Regulator" };

assert.deepEqual(quoteParts(c), { before: "The firm ", quote: "was fined", after: " today." });
assert.deepEqual(quoteParts({ ...c, quote_start: 50 }), { before: "", quote: "was fined", after: "" });
assert.equal(fragmentLink(c), c.link);
assert.equal(fragmentLink({ ...c, link: "https://evil.example/#:~:text=x" }), c.url);
assert.equal(fragmentLink({ ...c, url: "javascript:alert(1)" }), "");
assert.equal(trustLabel({ trust: "unverified" }).startsWith("🟨"), true);
assert.equal(findCitation({ citations: [c] }, "1"), c);
assert.equal(findCitation({ citations: [c] }, 2), null);
assert.match(citeChip({ ...c, trust: "unverified" }, esc, "r1"), /class="cite-chip unverified"/);
assert.doesNotMatch(citeChip({ ...c, publisher: "<b>x</b>" }, esc), /<b>x/);

// Radar: Not assessed is hollow at the rim, never a 0 value.
const scores = { areas: [
  { area: "financial", score: 26, level: "Medium", coverage: "assessed" },
  { area: "legal", score: 50, level: "High", coverage: "assessed" },
  { area: "country", score: 31, level: "Medium", coverage: "assessed" },
  { area: "people", score: 20, level: "Low", coverage: "assessed" },
  { area: "operations", score: 17, level: "Low", coverage: "assessed" },
  { area: "reputation", score: null, level: null, coverage: "not_assessed" },
] };
const svg = radarSVG(scores, esc);
assert.equal((svg.match(/class="rr-hollow"/g) || []).length, 1);
assert.equal((svg.match(/class="rr-dot"/g) || []).length, 5);
assert.match(svg, /Reputation &amp; Outside View: Not assessed/);
assert.doesNotMatch(svg, /Reputation[^<]*: 0/);
assert.match(svg, /Legal &amp; Governance: 50\/100/);
assert.match(radarSVG({ areas: [] }, esc), /Not scored yet/);
assert.match(bandBar(24, esc), /left:24%/);
assert.match(bandBar(null, esc), /No total score/);
const clar = researchCard({ id: "a", company: "Acme", status: "needs_clarification", clarification: { question: "Which Acme?", candidates: [{ legal_name: "Acme AG", country_code: "DE" }, { legal_name: "Acme Ltd", country_code: "GB" }] } }, { esc });
assert.equal((clar.match(/data-clarify-index/g) || []).length, 2);
assert.match(clar, /None of these/);
const running = researchCard({ id: "b", company: "Acme", status: "researching", progress: { step: "search", areas: { financial: { searched: 2 } } } }, { esc });
assert.match(running, /Checking finances/);
assert.match(running, /2 searches/);
console.log("citations ok");
