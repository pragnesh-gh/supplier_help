// The research TL;DR card shown in the chat: live progress while running, then a structured
// summary, top to bottom: company intro, risk profile (total on the level band, coverage),
// full-width 6-area radar, 3-5 cited points, one row of actions.
import { icon } from "./icons.js";
import { citeChip, findCitation } from "./citations.js";

export const AREAS = [
  ["financial", "Financial", "Fin.", "Financial"],
  ["legal", "Legal & Governance", "Legal", "Legal"],
  ["country", "Country & Location", "Country", "Country"],
  ["people", "People & Safety", "People", "People"],
  ["operations", "Operations & Delivery", "Ops", "Operations"],
  ["reputation", "Reputation & Outside View", "Rep.", "Reputation"],
];
const CHECKING = {
  financial: "Checking finances",
  legal: "Checking legal and governance",
  country: "Checking country data",
  people: "Checking people and safety",
  operations: "Checking operations and delivery",
  reputation: "Checking reputation",
};
const KIND = { red: "Red flag", amber: "Watch", green: "Strength", neutral: "Context" };
const GLYPH = { red: "◆", amber: "▲", green: "●", neutral: "○" };

function fmtDate(value) {
  if (!value) return "";
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? String(value).slice(0, 10)
    : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

// Small radar: one series, 0-100 per area, higher = more risk. Not assessed = hollow marker
// at the rim, never plotted as 0. Each marker has a hover title; a hidden table repeats the values.
// ``wide``: the full-width card radar, with longer axis names and more room for them.
export function radarSVG(scores, esc, size = 200, { wide = false } = {}) {
  const areas = AREAS.map(([id, label, short, medium]) => {
    const a = (scores?.areas || []).find((x) => x.area === id) || {};
    const value = a.coverage === "not_assessed" || typeof a.score !== "number" ? null : a.score;
    return { id, label, short: wide ? medium : short, value, level: a.level };
  });
  const c = size / 2,
    r = size / 2 - (wide ? 58 : 38);
  const pt = (i, v) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / 6;
    return [c + Math.cos(angle) * r * (v / 100), c + Math.sin(angle) * r * (v / 100)];
  };
  const rings = [25, 50, 75, 100]
    .map((v) => `<polygon points="${areas.map((_, i) => pt(i, v).join(",")).join(" ")}" class="rr-ring${v === 100 ? " outer" : ""}"/>`)
    .join("");
  const spokes = areas.map((_, i) => `<line x1="${c}" y1="${c}" x2="${pt(i, 100)[0]}" y2="${pt(i, 100)[1]}" class="rr-spoke"/>`).join("");
  const scored = areas.map((a, i) => (a.value === null ? null : pt(i, Math.max(a.value, 2))));
  const shape = scored.filter(Boolean).length >= 3
    ? `<polygon class="rr-shape" points="${scored.filter(Boolean).map((p) => p.join(",")).join(" ")}"/>`
    : "";
  const marks = areas
    .map((a, i) => {
      const title = `${a.label}: ${a.value === null ? "Not assessed" : a.value + "/100 · " + (a.level || "")}`;
      if (a.value === null) {
        const [x, y] = pt(i, 100);
        return `<g class="rr-hit"><title>${esc(title)}</title><circle cx="${x}" cy="${y}" r="10" class="rr-target"/><circle cx="${x}" cy="${y}" r="4.5" class="rr-hollow"/></g>`;
      }
      const [x, y] = scored[i];
      return `<g class="rr-hit"><title>${esc(title)}</title><circle cx="${x}" cy="${y}" r="10" class="rr-target"/><circle cx="${x}" cy="${y}" r="4" class="rr-dot"/></g>`;
    })
    .join("");
  const labels = areas
    .map((a, i) => {
      const [x, y] = pt(i, 128);
      const anchor = Math.abs(x - c) < 4 ? "middle" : x > c ? "start" : "end";
      return `<text x="${x}" y="${y}" text-anchor="${anchor}" dominant-baseline="middle" class="rr-label"><tspan>${esc(a.short)}</tspan><tspan x="${x}" dy="12" class="rr-value">${a.value === null ? "n/a" : a.value}</tspan></text>`;
    })
    .join("");
  const summary = areas.map((a) => `${a.label} ${a.value === null ? "not assessed" : a.value}`).join(", ");
  const none = areas.every((a) => a.value === null);
  const dims = wide ? "" : ` width="${size}" height="${size}"`;
  return `<svg viewBox="0 0 ${size} ${size}"${dims} role="img" aria-label="Risk by area, 0 to 100, higher is more risk: ${esc(summary)}" class="rr${wide ? " wide" : ""}">${rings}${spokes}${shape}${marks}${labels}${none ? `<text x="${c}" y="${c}" text-anchor="middle" class="rr-label">Not scored yet</text>` : ""}</svg><div class="sr-only"><table><caption>Risk by area (0 = no risk, 100 = maximum risk)</caption>${areas.map((a) => `<tr><th>${esc(a.label)}</th><td>${a.value === null ? "Not assessed" : esc(a.value + " · " + (a.level || ""))}</td></tr>`).join("")}</table></div>`;
}

// Total score on the Low / Medium / High / Critical band bar (0-24, 25-49, 50-74, 75-100).
export function bandBar(total, esc) {
  const bands = [["Low", 0, 25], ["Medium", 25, 50], ["High", 50, 75], ["Critical", 75, 101]];
  const has = typeof total === "number";
  const marker = has ? `<span class="band-marker" style="left:${Math.min(100, Math.max(0, total))}%" aria-hidden="true"></span>` : "";
  return `<div class="band-bar" role="img" aria-label="${has ? `Total ${esc(total)} of 100 on the level scale: Low 0 to 24, Medium 25 to 49, High 50 to 74, Critical 75 to 100` : "No total score"}"><div class="band-track">${bands.map(([l, a, b]) => `<span class="band ${l}" style="flex:${Math.min(b, 100) - a}"></span>`).join("")}${marker}</div><div class="band-labels" aria-hidden="true">${bands.map(([l, a, b]) => `<span style="flex:${Math.min(b, 100) - a}">${l}</span>`).join("")}</div></div>`;
}

function progressSteps(r, esc) {
  const p = r.progress || {};
  const order = ["identity", "search", "read", "verify", "followup", "report", "done"];
  const at = Math.max(0, order.indexOf(p.step || "identity"));
  const state = (step) => (r.status === "failed" ? "pending" : at > order.indexOf(step) ? "done" : at === order.indexOf(step) ? "active" : "pending");
  const mark = (s) => (s === "done" ? icon("check", "sm") : s === "active" ? '<span class="rp-spin" aria-hidden="true"></span>' : '<span class="rp-dot" aria-hidden="true"></span>');
  const areas = AREAS.map(([id]) => {
    const a = p.areas?.[id] || {};
    const s = a.failed && !a.searched ? "failed" : a.searched && at > 1 ? "done" : a.searched ? "active" : at > 1 ? "done" : "pending";
    const detail = a.searched ? `${a.searched} search${a.searched === 1 ? "" : "es"}` : id === "country" && at > 1 ? "index data" : "";
    return `<li class="rp-area ${s}">${s === "failed" ? "!" : mark(s)}<span>${esc(CHECKING[id])}${s === "active" ? "…" : ""}</span><span class="small muted">${esc(detail)}${a.failed ? " · 1 search failed" : ""}</span></li>`;
  }).join("");
  const step = (key, label, detail = "") => {
    const s = state(key);
    return `<li class="${s}">${mark(s)}<span>${esc(label)}${s === "active" ? "…" : ""}</span><span class="small muted">${esc(detail)}</span></li>`;
  };
  return `<ol class="rp-steps">${step("identity", "Confirming the company")}<li class="rp-group ${state("search")}">${mark(state("search"))}<span>Searching public sources</span><ol>${areas}</ol></li>${step("read", "Reading pages", p.pages_read ? `${p.pages_read} pages` : "")}${step("verify", "Checking every fact against its quote", p.facts_verified ? `${p.facts_verified} facts kept` : "")}${r.mode === "basic" ? "" : step("followup", "Following up red flags")}${step("report", "Writing the report")}</ol>`;
}

function head(r, esc, extra = "") {
  const sources = (r.sources || []).length;
  const meta = [r.entity?.country_name || r.country, fmtDate(r.completed_at || r.created_at), sources ? `${sources} sources` : ""].filter(Boolean);
  return `<header class="rcard-head"><div><div class="eyebrow">Public research</div><h3>${esc(r.company)}</h3><p class="small muted">${esc(meta.join(" · "))}</p></div>${r.demo ? '<span class="tag demo">Offline example</span>' : ""}${extra}</header>`;
}

export function researchCard(r, { esc, isFavorite = () => false, inCompare = () => false, inShortlist = () => false, pinned = false, pending = null, note = null } = {}) {
  if (!r) return "";
  if (["queued", "researching"].includes(r.status)) {
    return `<section class="rcard running" aria-busy="true">${head(r, esc)}${progressSteps(r, esc)}<p class="small muted">${r.demo ? "Running the offline example on invented data." : "Takes about 1.5 to 2 minutes. You can keep working; the result stays in Reports."}</p></section>`;
  }
  if (r.status === "failed") {
    return `<section class="rcard failed">${head(r, esc)}<p role="alert">${esc(r.error || "Research could not complete.")}</p><div class="rcard-actions"><button data-research-retry="${esc(r.id)}">${icon("restart_alt", "sm")}Try again</button></div></section>`;
  }
  if (r.status === "needs_clarification") {
    const cands = r.clarification?.candidates || [];
    return `<section class="rcard clarify">${head(r, esc)}<p><strong>${esc(r.clarification?.question || "Which company do you mean?")}</strong></p><div class="rcard-options">${cands.map((c, i) => `<button data-clarify-run="${esc(r.id)}" data-clarify-index="${i}"><strong>${esc(c.legal_name)}</strong><span class="small muted">${esc([c.country_name || c.country_code, c.website].filter(Boolean).join(" · "))}</span>${c.description ? `<span class="small">${esc(c.description)}</span>` : ""}</button>`).join("")}</div><button class="link small" data-clarify-none>None of these: enter the details myself</button></section>`;
  }
  const s = r.scores || {};
  const t = r.tldr || {};
  const points = (t.points || []).slice(0, 5);
  const chips = (nums) => nums.map((n) => citeChip(findCitation(r, n), esc, r.id)).join("");
  const level = s.level ? `<span class="risk ${esc(s.level)}">${esc(s.level)}</span>` : '<span class="risk">Not scored</span>';
  const total = typeof s.total === "number" ? `<strong class="rcard-total">${s.total}</strong><span class="muted">/100</span>` : '<strong class="rcard-total na">–</strong>';
  const assessed = `${s.assessed ?? 0} of 6 areas assessed${typeof s.coverage_pct === "number" ? ` · coverage ${s.coverage_pct}%` : ""}`;
  const id = esc(r.id);
  const st = { favorite: isFavorite(r.id), shortlist: inShortlist(r.id), compare: inCompare(r.id) };
  const busy = (kind) => (pending === kind ? ' aria-busy="true" disabled' : "");
  const ICONS = {
    favorite: ["star", "Add to favorites", "In favorites: remove"],
    shortlist: ["fact_check", "Add to the shortlist", "In the shortlist: open it"],
    compare: ["compare_arrows", "Add to comparison", "In comparison: open it"],
  };
  const iconBtn = (kind) => {
    const [name, off, on] = ICONS[kind];
    const label = st[kind] ? on : off;
    return `<button type="button" class="icon-button rcard-icon${kind === "favorite" ? " fav-toggle" : ""}" data-research-${kind}="${id}" aria-pressed="${st[kind]}" aria-label="${label}" title="${label}"${busy(kind)}>${icon(name, "sm")}</button>`;
  };
  const places = [
    st.favorite ? `<a href="#/portfolio">${icon("star", "sm")}Favorited</a>` : "",
    st.shortlist ? `<a href="#/approvals">${icon("check", "sm")}In shortlist</a>` : "",
    st.compare ? `<a href="#/compare">${icon("check", "sm")}In compare</a>` : "",
  ].filter(Boolean);
  const intro = (t.intro || []).filter((p) => p && p.text);
  const lead = intro.find((p) => p.key === "description" || p.key === "products");
  const facts = intro.filter((p) => p !== lead);
  // The last word and its chips never split across lines, so a chip never sits alone on a line.
  const part = (p) => {
    const cites = (p.citations || []).length ? chips(p.citations) : "";
    if (!cites) return esc(p.text);
    const at = p.text.lastIndexOf(" ");
    return `${esc(p.text.slice(0, at + 1))}<span class="nowrap">${esc(p.text.slice(at + 1))} ${cites}</span>`;
  };
  const introHTML = intro.length
    ? `<p class="rcard-intro">${lead ? `<span>${part(lead)}</span>` : ""}${facts.length ? `<span class="rcard-facts">${facts.map(part).join('<span class="sep" aria-hidden="true"> · </span>')}</span>` : ""}</p>`
    : "";
  const pointsHTML = points.map((p) => `<li class="pt ${esc(p.colour)}"><span class="pt-glyph" aria-hidden="true">${GLYPH[p.colour] || "○"}</span><div><span class="pt-kind">${esc(KIND[p.colour] || "Finding")} · ${esc(p.area_label || "")}${p.alleged ? " · alleged" : ""}</span><span class="pt-text">${esc(p.text)}${p.date ? ` <span class="muted">(${esc(p.date)})</span>` : ""}</span><span class="pt-cites">${chips(p.citations || [])}</span></div></li>`).join("")
    || '<li class="pt neutral"><span class="pt-glyph" aria-hidden="true">○</span><div>No red flags, watch items or strengths were found in the sources checked.</div></li>';
  return `<section class="rcard done" data-run="${id}">${head(r, esc)}
    ${introHTML}
    <h4 class="rcard-section">Risk profile</h4>
    <div class="rcard-score">${level}${total}<span class="small muted">${esc(assessed)}</span></div>
    ${bandBar(s.total, esc)}
    <figure class="rcard-radar">${radarSVG(s, esc, 300, { wide: true })}<figcaption class="small muted"><span class="rr-key-hollow" aria-hidden="true"></span>Not assessed · 0 = no risk, 100 = maximum risk</figcaption></figure>
    <ul class="rcard-points">${pointsHTML}</ul>
    <p class="small muted rcard-note">Public research score, not comparable to catalogue scores.${(t.not_assessed || []).length ? " Not assessed: " + esc(t.not_assessed.join(", ")) + "." : ""}</p>
    <div class="rcard-actions"><button type="button" class="primary rcard-open" data-research-report="${id}">${icon("description", "sm")}Open report</button><details class="dl-menu"><summary class="icon-button rcard-icon" aria-label="Download report" title="Download report">${icon("download", "sm")}</summary><div class="dl-options"><button type="button" data-research-pdf="${id}">PDF (print or save)</button><a class="button" href="/api/research/${encodeURIComponent(r.id)}/export?format=html" download>HTML file</a><a class="button" href="/api/research/${encodeURIComponent(r.id)}/export?format=markdown" download>Markdown</a></div></details>${iconBtn("favorite")}${iconBtn("shortlist")}${iconBtn("compare")}</div>
    ${note ? `<p class="rcard-feedback${note.error ? " error" : ""}" role="${note.error ? "alert" : "status"}">${esc(note.text)}${note.href ? ` <a href="${esc(note.href)}">${esc(note.link || "Open")}</a>` : ""}</p>` : ""}
    ${places.length ? `<p class="rcard-places small">${places.join("")}</p>` : ""}
    <div class="rcard-foot"><button type="button" class="link" data-research-ask="${id}" aria-pressed="${pinned}">${icon("chat", "sm")}${pinned ? "Asking about this report" : "Ask about this report"}</button><button type="button" class="link" data-research-save="${id}">Save to my suppliers</button></div></section>`;
}

export function offerCard(m, esc, index = 0) {
  const o = m.offer || {};
  if (m.offer_state === "started") return `<div class="offer-card done small muted">${icon("check", "sm")}Research started.</div>`;
  if (m.offer_state === "dismissed") return "";
  return `<div class="offer-card"><strong>${esc(o.label || "Research this company?")}</strong>${o.note ? `<p class="small muted">${esc(o.note)}</p>` : ""}<div class="rcard-actions"><button class="primary" data-offer-index="${index}" data-offer-start="${esc(m.company || "")}">${icon("search", "sm")}Research</button><button data-offer-dismiss="${index}">Not now</button></div></div>`;
}
