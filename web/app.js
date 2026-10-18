import { api, safeURL } from "./api.js";
import { mountTrain } from "./train.js";
import { mountParts } from "./parts-scene.js";
import { createChat } from "./chat.js";
("use strict");
document.addEventListener("DOMContentLoaded", async () => {
  try {
    const payload = await api("/api/catalog"),
      manifest = payload.manifest,
      regions = manifest.regions,
      axes = manifest.axes,
      $ = (s) => document.querySelector(s),
      esc = (s) =>
        String(s ?? "").replace(
          /[&<>"']/g,
          (c) =>
            ({
              "&": "&amp;",
              "<": "&lt;",
              ">": "&gt;",
              '"': "&quot;",
              "'": "&#39;",
            })[c],
        ),
      fmt = (x) =>
        typeof x === "number"
          ? x.toLocaleString("en-GB", { maximumFractionDigits: 1 })
          : "Unknown";
    const originals = payload.rows.map((r) =>
        Object.freeze(
          Object.fromEntries(payload.columns.map((c, j) => [c, r[j]])),
        ),
      ),
      sourceById = new Map(originals.map((r) => [r.supplierID, r]));
    let train = null,
      partsScene = null,
      partsRegion = null,
      timer = null,
      toastTimer = null,
      runSequence = 0;
    const initial = () => ({
      route: "overview",
      region: "doors",
      focus: "SUPP_00012",
      tab: "recents",
      recents: [],
      favorites: new Set(
        originals.filter((r) => r.is_favorite_demo).map((r) => r.supplierID),
      ),
      compare: [],
      filters: {
        q: "",
        region: "doors",
        part: "",
        risk: "",
        delivery: "",
        favorite: false,
        used: false,
        sort: "total",
      },
      page: 1,
      portfolio: { group: "favorite", q: "", view: "cards", page: 1 },
      answer:
        "Ask about supplied data. Answers name the metric and exact source cells.",
      query: "",
      added: [],
      reports: {},
      memo: null,
      tour: -1,
      tableRadar: false,
      compareError: "",
    });
    let state = initial();
    let appGeneration = 0;
    const catalog = () => originals.concat(state.added),
      get = (id) =>
        sourceById.get(id) || state.added.find((r) => r.supplierID === id),
      regionOf = (r) => r.train_region_id,
      isUsed = (r) => !!r.previously_used_demo,
      regionLabel = (id) => regions.find((r) => r.id === id)?.label || id,
      nameOf = (r) => r["Supplier Name"];
    const counts = () =>
      Object.fromEntries(
        regions.map((g) => {
          let a = catalog().filter((r) => regionOf(r) === g.id);
          return [
            g.id,
            {
              total: a.length,
              scored: a.filter((r) => !r._research).length,
              researchOnly: a.filter((r) => r._research).length,
            },
          ];
        }),
      );
    const weightText = (w) => (Math.abs(w - 1 / 3) < 1e-8 ? "1/3" : String(w));
    const axisVal = (r, a) =>
        r && typeof r[a.field] === "number" ? r[a.field] : null,
      labelAxis = (a) =>
        a.id === "financial" ? "Financial (derived)" : a.label;
    const statCache = new Map();
    function stats(region) {
      if (statCache.has(region)) return statCache.get(region);
      let rs = originals.filter((r) => regionOf(r) === region),
        s = axes.map((a) => {
          let v = rs
              .map((r) => axisVal(r, a))
              .filter((v) => v !== null)
              .sort((a, b) => a - b),
            q = (p) => (v.length ? v[Math.floor((v.length - 1) * p)] : null);
          return {
            q1: q(0.25),
            median: q(0.5),
            q3: q(0.75),
            mean: v.length ? v.reduce((a, b) => a + b, 0) / v.length : null,
            n: v.length,
          };
        });
      statCache.set(region, s);
      return s;
    }
    function radar(r, region, table = false) {
      let s = stats(region);
      if (table)
        return `<div class="scroll"><table class="axis-table"><thead><tr><th>Derived axis · 0–100</th><th>Focus</th><th>P25 / median / P75</th><th>Mean · n</th><th>Source weights</th></tr></thead><tbody>${axes.map((a, i) => `<tr><td>${esc(labelAxis(a))}</td><td>${fmt(axisVal(r, a))}</td><td>${fmt(s[i].q1)} / ${fmt(s[i].median)} / ${fmt(s[i].q3)}</td><td>${fmt(s[i].mean)} · ${s[i].n}</td><td>${a.components.map((c) => `${esc(c.field)} × ${weightText(c.weight)}`).join("<br>")}</td></tr>`).join("")}</tbody></table></div>`;
      if (!r || r._research)
        return '<div class="empty">No supplied scores, so the radar is not drawn.<br>Unknown values are excluded from statistics.</div>';
      let cx = 220,
        cy = 132,
        R = 91,
        pt = (i, v) => [
          cx + (Math.sin((i * Math.PI) / 3) * R * v) / 100,
          cy - (Math.cos((i * Math.PI) / 3) * R * v) / 100,
        ],
        points = (v) => v.map((x, i) => pt(i, x).join(",")).join(" "),
        ring = s
          .map((x, i) => pt(i, x.q3))
          .concat(s.map((x, i) => pt(i, x.q1)).reverse())
          .map((p) => p.join(","))
          .join(" ");
      return `<svg viewBox="0 0 440 266" role="img" aria-label="Six derived axes for ${esc(r.supplierID)} against ${esc(regionLabel(region))} distribution. Higher means more risk.">${[25, 50, 75, 100].map((n) => `<polygon points="${points(axes.map(() => n))}" fill="none" stroke="#dce2e6"/>`).join("")}${axes.map((a, i) => `<line x1="${cx}" y1="${cy}" x2="${pt(i, 100)[0]}" y2="${pt(i, 100)[1]}" stroke="#dce2e6"/>`).join("")}<polygon points="${ring}" fill="#c8dfe0" fill-rule="evenodd" opacity=".7"/><polygon points="${points(s.map((x) => x.median))}" fill="none" stroke="#7b999c" stroke-dasharray="4 3"/><polygon points="${points(axes.map((a) => axisVal(r, a)))}" fill="#0f6e7425" stroke="#0f6e74" stroke-width="2"/>${axes
        .map((a, i) => {
          let p = pt(i, 128);
          return `<text x="${p[0]}" y="${p[1]}" text-anchor="${i === 1 || i === 2 ? "start" : i === 4 || i === 5 ? "end" : "middle"}" dominant-baseline="middle" fill="#56656f" font-size="13">${esc(a.id === "legal" ? "Legal" : a.id === "country" ? "Country" : labelAxis(a))} ${fmt(axisVal(r, a))}<title>${esc(a.components.map((c) => c.field + " × " + c.weight).join(" + "))}; value ${fmt(axisVal(r, a))}; mean ${fmt(s[i].mean)}; n ${s[i].n}</title></text>`;
        })
        .join(
          "",
        )}<text x="225" y="39" font-size="10" fill="#87949c">100</text></svg>`;
    }
    function tags(r) {
      return `${state.favorites.has(r.supplierID) ? '<span class="tag">Favorite</span>' : ""}${isUsed(r) ? '<span class="tag">Previously used · demo</span>' : ""}${r._research ? '<span class="tag demo">Research-only · unscored</span>' : ""}`;
    }
    function supplierCard(r) {
      return `<article class="supplier ${state.focus === r.supplierID ? "focused" : ""}" data-focus="${esc(r.supplierID)}" tabindex="0"><div class="row spread"><strong class="small">${esc(r.supplierID)}</strong><button class="quiet" data-action="favorite" data-id="${esc(r.supplierID)}" aria-label="Toggle favorite ${esc(r.supplierID)}">${state.favorites.has(r.supplierID) ? "★" : "☆"}</button></div><div class="name">${esc(nameOf(r))}</div><div class="meta"><span>Total ${fmt(r.Total_Risk_Index)}</span><span class="risk ${esc(r.Total_Risk_Index_Level)}">${esc(r.Total_Risk_Index_Level || "Unknown")}</span></div><div class="row" style="margin-top:7px"><button data-action="detail" data-id="${r.supplierID}">Inspect</button><button data-action="recommend" data-id="${r.supplierID}">Request review</button></div>${isUsed(r) ? '<div class="small muted">Previously used · demo history</div>' : ""}</article>`;
    }
    function overview() {
      let c = counts()[state.region],
        all = catalog().filter((r) => regionOf(r) === state.region),
        rs = (
          state.tab === "used"
            ? all
                .filter(isUsed)
                .sort((a, b) => a.supplierID.localeCompare(b.supplierID))
            : state.recents
                .map(get)
                .filter((r) => r && regionOf(r) === state.region)
        ).slice(0, 3);
      let focus = get(state.focus);
      if (!focus || regionOf(focus) !== state.region) {
        focus = rs[0] || all[0];
        state.focus = focus?.supplierID;
      }
      return `<div class="overview"><div class="left"><section class="card train-card"><div class="card-head"><div class="row"><h2>Explore the train</h2><span class="tag demo">Illustrative assembly</span></div><button class="quiet small" data-action="reset-view">↺ Reset view</button></div><div id="train-scene" class="train-scene"></div><div class="regions">${regions.map((r) => `<button title="${esc(r.label)} · ${counts()[r.id].total} assigned records" data-action="region" data-region="${r.id}" aria-pressed="${state.region === r.id}" class="${state.region === r.id ? "selected" : ""}"><strong>${esc(r.shortLabel || r.label)}</strong><span class="count">${fmt(counts()[r.id].total)}</span></button>`).join("")}</div></section><section class="card supplier-strip"><div class="card-head"><div class="supplier-tabs" role="group" aria-label="Supplier collection"><button data-action="supplier-tab" data-tab="recents" aria-pressed="${state.tab === "recents"}">Recents</button><button data-action="supplier-tab" data-tab="used" aria-pressed="${state.tab === "used"}">Previously used</button></div><span class="small muted">${state.tab === "recents" ? "Recently viewed in this system" : "Illustrative previous-use relationships"}</span></div><div class="suppliers">${rs.length ? rs.map(supplierCard).join("") : `<div class="empty recent-empty">${state.tab === "recents" ? "Inspect a supplier in Discovery to see it here." : "No previously used demonstration suppliers in this system."} <button data-action="discover-region" class="link">Explore Discovery</button></div>`}</div></section></div><div class="right"><section class="card summary"><div><div class="eyebrow">Selected system · demo assignment</div><h1>${esc(regionLabel(state.region))}</h1><div><strong class="stat">${fmt(c.total)}</strong><span class="muted small"> records · ${fmt(c.scored)} scored · ${c.researchOnly} research-only</span></div><p class="small muted">${all.filter((r) => r.Total_Risk_Index_Level === "Critical").length} Critical · supplied total-risk level</p></div><button class="primary" data-action="discover-region">Discover →</button></section><section class="card radar-card"><div class="card-head"><div><h2>Risk profile</h2><span class="small muted">Focus ${esc(state.focus || "none")} · higher = more risk</span></div><button class="quiet small" data-action="radar-table">${state.tableRadar ? "Chart" : "View as table"}</button></div><div class="radar-body">${radar(focus, state.region, state.tableRadar)}</div><div class="radar-note"><div class="legend"><span><i></i>Focused supplier</span><span><i class="band"></i>System P25–P75</span><span>− − Median</span></div>Assignments are synthetic and independent of risk; system distributions are similar. <button class="link small" data-action="mapping">Weights & mapping</button></div></section></div></div>`;
    }
    function filtered() {
      let f = state.filters;
      return catalog()
        .filter(
          (r) =>
            (!f.region || regionOf(r) === f.region) &&
            (!f.part || r.train_part_id === f.part) &&
            (!f.q ||
              (r.supplierID + " " + nameOf(r))
                .toLowerCase()
                .includes(f.q.toLowerCase())) &&
            (!f.risk || r.Total_Risk_Index_Level === f.risk) &&
            (!f.delivery ||
              (typeof r["Supplier Delivery Rating"] === "number" &&
                r["Supplier Delivery Rating"] >= Number(f.delivery))) &&
            (!f.favorite || state.favorites.has(r.supplierID)) &&
            (!f.used || isUsed(r)),
        )
        .sort((a, b) =>
          f.sort === "id"
            ? a.supplierID.localeCompare(b.supplierID)
            : f.sort === "delivery"
              ? (b["Supplier Delivery Rating"] ?? -Infinity) -
                  (a["Supplier Delivery Rating"] ?? -Infinity) ||
                a.supplierID.localeCompare(b.supplierID)
              : (a.Total_Risk_Index ?? Infinity) -
                  (b.Total_Risk_Index ?? Infinity) ||
                a.supplierID.localeCompare(b.supplierID),
        );
    }
    const partLabel = (id) =>
      regions
        .flatMap((region) => region.parts || [])
        .find((part) => part.id === id)?.label || "Unassigned part";
    function partCounts(region) {
      return Object.fromEntries(
        (region?.parts || []).map((part) => [
          part.id,
          catalog().filter(
            (r) => regionOf(r) === region.id && r.train_part_id === part.id,
          ).length,
        ]),
      );
    }
    function assemblySelector() {
      const region = regions.find((r) => r.id === state.filters.region);
      if (!region)
        return `<section class="card assembly-selector assembly-empty"><div><div class="eyebrow">Explore a system assembly</div><h2>Choose a train system</h2><p class="muted">Select a system in the filters to inspect its parts and narrow the catalog.</p></div></section>`;
      const counts = partCounts(region),
        total = catalog().filter((r) => regionOf(r) === region.id).length;
      const unassigned =
        total - Object.values(counts).reduce((sum, value) => sum + value, 0);
      return `<section class="card assembly-selector"><div class="card-head"><div><h2>${esc(region.label)} assembly</h2><p class="small muted">Select a part to filter suppliers &middot; illustrative geometry and assignments</p></div><button data-action="reset-parts" class="quiet small">Reset view</button></div><div id="parts-scene" class="parts-scene"></div><div class="part-chips" aria-label="Assembly part filters"><button data-action="part" data-part="" aria-pressed="${!state.filters.part}">All parts <span>${fmt(total)}</span></button>${(region.parts || []).map((part) => `<button data-action="part" data-part="${esc(part.id)}" aria-pressed="${state.filters.part === part.id}">${esc(part.label)} <span>${fmt(counts[part.id])}</span></button>`).join("")}</div>${unassigned ? `<p class="part-unassigned">${fmt(unassigned)} ${unassigned === 1 ? "record has" : "records have"} no part assignment; included in All parts.</p>` : ""}</section>`;
    }
    function selectPart(id) {
      const region = regions.find((r) => r.id === state.filters.region);
      const restoreFocus = !!document.activeElement?.closest(
        ".part-chips,#parts-scene",
      );
      state.filters.part = region?.parts.some((part) => part.id === id)
        ? id
        : "";
      state.page = 1;
      render();
      if (restoreFocus)
        document
          .querySelector(`.part-chips [data-part="${state.filters.part}"]`)
          ?.focus();
    }
    function touchSupplier(id) {
      if (!get(id)) return;
      state.recents = [
        id,
        ...state.recents.filter((value) => value !== id),
      ].slice(0, 50);
    }
    function discovery() {
      let result = filtered(),
        pages = Math.max(1, Math.ceil(result.length / 12));
      state.page = Math.min(state.page, pages);
      let visible = result.slice((state.page - 1) * 12, state.page * 12),
        hidden = state.compare.filter(
          (id) => !result.some((r) => r.supplierID === id),
        ).length,
        f = state.filters;
      return `<div class="discovery-intro"><div class="screen-title"><div><div class="eyebrow">Supplier catalog</div><h1>Discovery</h1><p class="muted small">${fmt(result.length)} matching · ${fmt(catalog().length)} total · relationship tags are demo metadata</p></div><button data-action="provenance">Inspect provenance</button></div>${assemblySelector()}</div><div class="discovery"><aside class="card filters stack"><label>Search ID or name<input data-filter="q" value="${esc(f.q)}" placeholder="e.g. SUPP_00731"></label><label>Train system<select data-filter="region"><option value="">All systems</option>${regions.map((r) => `<option value="${r.id}" ${f.region === r.id ? "selected" : ""}>${esc(r.label)}</option>`).join("")}</select></label><label>Supplied total-risk level<select data-filter="risk"><option value="">All levels</option>${["Low", "Medium", "High", "Critical"].map((x) => `<option ${f.risk === x ? "selected" : ""}>${x}</option>`).join("")}</select></label><label>Minimum delivery rating (%)<input data-filter="delivery" type="number" min="0" max="100" value="${esc(f.delivery)}" placeholder="No minimum"></label><label class="check"><input type="checkbox" data-filter="favorite" ${f.favorite ? "checked" : ""}> Favorites only</label><label class="check"><input type="checkbox" data-filter="used" ${f.used ? "checked" : ""}> Previously used · demo only</label><button data-action="clear-filters">Clear filters</button><p class="small muted">Filters combine with AND. Country filtering is unavailable: a country-risk score does not identify country.</p><div class="notice">Previous use does not mean qualified. All candidates use the same approval request.</div></aside><section class="card results"><div class="card-head"><h2>Supplier records</h2><label class="row">Rank by<select data-filter="sort">${[
        ["total", "Supplied total risk ↑"],
        ["delivery", "Delivery rating ↓"],
        ["id", "Supplier ID ↑"],
      ]
        .map(
          ([v, l]) =>
            `<option value="${v}" ${f.sort === v ? "selected" : ""}>${l}</option>`,
        )
        .join(
          "",
        )}</select></label></div><div class="scroll"><table><thead><tr><th>Select</th><th>Supplier</th><th>System</th><th>Total risk</th><th>Delivery</th><th>Relationship · demo</th><th>Actions</th></tr></thead><tbody>${visible.map((r) => `<tr><td><input type="checkbox" aria-label="Compare ${r.supplierID}" data-compare="${r.supplierID}" ${state.compare.includes(r.supplierID) ? "checked" : ""}></td><td><button class="link" data-action="detail" data-id="${r.supplierID}">${esc(nameOf(r))}</button><div class="small muted">${r.supplierID}</div></td><td class="small">${esc(regionLabel(regionOf(r)))}<div class="part-name">${esc(partLabel(r.train_part_id))}</div></td><td><strong>${fmt(r.Total_Risk_Index)}</strong> <span class="risk ${esc(r.Total_Risk_Index_Level)}">${esc(r.Total_Risk_Index_Level || "Unknown")}</span></td><td>${fmt(r["Supplier Delivery Rating"])}${r._research ? "" : "%"}</td><td>${tags(r) || '<span class="muted small">No demo relationship</span>'}</td><td><button data-action="favorite" data-id="${r.supplierID}" aria-label="Toggle favorite ${r.supplierID}">${state.favorites.has(r.supplierID) ? "★" : "☆"}</button> <button data-action="recommend" data-id="${r.supplierID}">Request review</button></td></tr>`).join("")}</tbody></table>${!visible.length ? '<div class="empty">No results. Adjust filters; comparison selections are preserved.</div>' : ""}</div><div class="pagination"><span class="small muted">Page ${state.page} of ${pages} · 12 per page · unknown scores last</span><div class="row"><button data-action="prev-page" ${state.page === 1 ? "disabled" : ""}>← Previous</button><button data-action="next-page" ${state.page === pages ? "disabled" : ""}>Next →</button></div></div><div class="tray"><div><strong>${state.compare.length} / 20 selected</strong><span class="small muted"> · ${hidden} outside current filters</span>${state.compareError ? `<div class="error">${esc(state.compareError)}</div>` : ""}</div><div class="row"><button data-action="manage-compare">Manage selection</button><button class="primary" data-action="compare" ${!state.compare.length ? "disabled" : ""}>Compare →</button></div></div></section></div>`;
    }
    function compare() {
      let rs = state.compare.map(get).filter(Boolean),
        focus = rs.find((r) => r.supplierID === state.focus) || rs[0];
      if (focus) state.focus = focus.supplierID;
      if (!rs.length)
        return '<div class="empty">No suppliers selected. <a href="#/discover">Open Discovery</a>.</div>';
      let fields = [
        ...axes.map((a) => [labelAxis(a), (r) => fmt(axisVal(r, a))]),
        ["Supplied Total_Risk_Index", (r) => fmt(r.Total_Risk_Index)],
        [
          "Supplied total-risk level",
          (r) => esc(r.Total_Risk_Index_Level || "Unknown"),
        ],
        ["Delivery rating (%)", (r) => fmt(r["Supplier Delivery Rating"])],
        ["Confirmation rate (%)", (r) => fmt(r["Order Confirmation Rate"])],
        [
          "Financial_Health_Score (supplied)",
          (r) => fmt(r.Financial_Health_Score),
        ],
        ["Relationship · demo", (r) => tags(r) || "None"],
        ["Illustrative delivery history · 12 weeks", (r) => sparkline(r)],
      ];
      return `<div class="screen-title"><div><div class="eyebrow">Comparison · ${rs.length} of 20</div><h1>Evidence side by side</h1><p class="muted small">Focus one supplier's six-axis profile. Unknown is never treated as low risk.</p></div><a class="button" href="#/discover">← Discovery</a></div><div class="compare-layout"><section class="card matrix"><table><thead><tr><th>Metric · higher scores = more risk</th>${rs.map((r) => `<th><button class="link" data-action="compare-focus" data-id="${r.supplierID}">${r.supplierID}</button><div class="small muted">${esc(nameOf(r))}</div><button data-action="remove-compare" data-id="${r.supplierID}">Remove</button></th>`).join("")}</tr></thead><tbody>${fields.map(([label, fn]) => `<tr><td>${esc(label)}</td>${rs.map((r) => `<td class="${r._research ? "unknown" : ""}">${fn(r)}</td>`).join("")}</tr>`).join("")}<tr><td>Next action</td>${rs.map((r) => `<td><button data-action="source-cells" data-id="${r.supplierID}">Source cells</button><button data-action="recommend" data-id="${r.supplierID}">Approval request</button></td>`).join("")}</tr></tbody></table></section><aside class="stack"><section class="card radar-card" style="min-height:340px"><div class="card-head"><h2>${esc(focus.supplierID)}</h2></div><div class="radar-body">${radar(focus, regionOf(focus))}</div><p class="radar-note">One focused supplier against its system P25–P75 band. Equal weights disclosed in each axis.</p></section><section class="card padded"><h2>Sourcing Copilot</h2><p class="small muted" style="margin:8px 0">Scope: selected IDs, independent of Discovery filters.</p><button class="primary" data-action="financial">Compare financial source score</button><div class="answer" style="margin-top:10px">${state.answer}</div></section></aside></div>`;
    }
    function missingMemo(m) {
      return [
        ["Project / decision context", m.project],
        ["Component need", m.component],
        ["Buyer rationale", m.rationale],
        ["Preparer", m.preparer],
        ["Reviewer", m.reviewer],
        ["Next action", m.action],
        ["Mitigation owner", m.owner],
        ["Due date", m.due],
        ["Alternatives / reason none", m.alternatives],
      ]
        .filter((x) => !x[1]?.trim())
        .map((x) => x[0]);
    }
    async function newMemo(id) {
      const token = appGeneration;
      let r = get(id);
      if (r?._research) {
        try {
          r._report = await api(
            "/api/research/" +
              encodeURIComponent(r._record?.run_id || r._report?.id),
          );
        } catch (error) {
          if (token !== appGeneration) return;
          toast(error.message);
          return;
        }
      }
      if (token !== appGeneration) return;
      state.memo = {
        id: "MEMO-" + id.replace(/[^a-z0-9]/gi, "") + "-01",
        candidate: id,
        rev: 1,
        date: new Date().toLocaleDateString("en-GB"),
        project: "",
        component: "",
        rationale: "",
        preparer: "",
        reviewer: "",
        disposition: "Further assessment",
        alternatives: "",
        action: "",
        owner: "",
        due: "",
        comments: "",
        selection: state.compare.slice(),
        filters: JSON.parse(JSON.stringify(state.filters)),
        relationship: tags(r).replace(/<[^>]*>/g, " ") || "Neither",
        stale: false,
        preview: null,
      };
      navigate("memo");
    }
    function memo() {
      let m = state.memo;
      if (!m)
        return '<div class="empty">Choose a supplier to draft an approval request. <a href="#/discover">Open Discovery</a>.</div>';
      let fields = [
        ["project", "Project / decision context"],
        ["component", "Component need"],
        ["preparer", "Prepared by"],
        ["reviewer", "Intended reviewer"],
        ["rationale", "Rationale · trade-offs · buyer judgment"],
        ["alternatives", "Alternatives / reason none"],
        ["action", "Next action · evidence needed"],
        ["owner", "Action owner"],
        ["due", "Due date"],
        ["comments", "Reviewer comments (pending)"],
      ];
      m.preview = memoDocument(m);
      return `<div class="screen-title"><div><div class="eyebrow">Shared approval workflow · new and previously used</div><h1>Prepare a review request</h1><p class="small muted">${esc(m.id)} · rev ${m.rev} · Draft / not approved</p></div><button class="primary" data-action="print-memo">Print / Save as PDF</button></div><div class="memo-layout"><section class="card padded memo-form"><h2>${esc(nameOf(get(m.candidate)))}</h2><p class="small muted">${esc(m.candidate)}</p><div class="notice" style="margin-top:12px">${missingMemo(m).length ? "Incomplete draft · " + esc(missingMemo(m).join(", ")) : m.stale ? "Stale · update selection basis" : "Ready for review · no approval granted."}</div><label>Proposed disposition<select data-memo="disposition">${["Further assessment", "Conditional shortlist", "Do not proceed"].map((x) => `<option ${m.disposition === x ? "selected" : ""}>${x}</option>`).join("")}</select></label>${fields.map(([key, label]) => `<label>${label}${["rationale", "alternatives", "action", "comments"].includes(key) ? `<textarea data-memo="${key}">${esc(m[key])}</textarea>` : `<input data-memo="${key}" value="${esc(m[key])}" ${key === "due" ? 'type="date"' : ""}>`}</label>`).join("")}<button data-action="update-selection">Update selection basis from current exploration</button><p class="small muted" style="margin-top:10px">Missing owner, reviewer or date prevents ready status. Preview and print share this revision. Print cancellation changes no status.</p></section><section class="preview" id="memo-preview">${m.preview}</section></div>`;
    }
    function detail(id) {
      let r = get(id);
      if (!r) return '<div class="empty">Record unavailable.</div>';
      return `<div class="screen-title"><div><div class="eyebrow">Catalog record · ${esc(id)}</div><h1>${esc(nameOf(r))}</h1><p class="small muted">${esc(regionLabel(regionOf(r)))} · ${r._research ? "Buyer-selected research association" : "Synthetic assignment"} · ${tags(r)}</p></div><div class="row"><a class="button" href="#/discover">Discovery</a><button class="primary" data-action="recommend" data-id="${esc(id)}">Approval request</button></div></div><div class="two"><section class="card padded"><h2>Risk profile · ${esc(id)}</h2><div style="height:290px">${radar(r, regionOf(r))}</div><p class="small muted">Scores and relationship history do not establish qualification.</p></section><section class="card padded"><h2>Identity & relationship</h2><p style="margin:12px 0">${r._research ? "Public research company record. Exact contracting entity, component fit and current qualification require buyer verification." : "Supplier name is anonymized. No real-company identity or country established."}</p><p class="small muted">Favorites are personal session preferences. Previous use is demo history, not qualification. ${isUsed(r) ? "Demo history: prior-program sourcing; date, outcome, applicability and freshness Unknown." : ""}</p><div class="actions" style="margin-top:12px"><button data-action="favorite" data-id="${esc(id)}">${state.favorites.has(id) ? "Remove favorite" : "Add favorite"}</button><button data-action="toggle-compare" data-id="${esc(id)}">${state.compare.includes(id) ? "Remove from" : "Add to"} comparison</button>${r._research ? `<button data-action="saved-report" data-run="${r._report.id}">Linked risk report</button>` : ""}</div>${r._research ? '<div class="notice" style="margin-top:14px">Separate research-only record. All source scores Unknown and excluded from numeric aggregates.</div>' : ""}</section><section class="card padded" style="grid-column:1/-1"><div class="row spread"><h2>Supplied cells & derived mapping</h2><button data-action="source-cells" data-id="${esc(id)}">Inspect all cells</button></div>${radar(r, regionOf(r), true)}<p class="screen-note">Source Total_Risk_Index weights unavailable; derived axes do not reproduce its weighting.</p></section></div>`;
    }

    function deliveryHistory(r) {
      if (!r || r._research || !isUsed(r)) return null;
      let n = Number(r.supplierID.replace(/\D/g, "")),
        base = Number(r["Supplier Delivery Rating"]);
      return Array.from(
        { length: 12 },
        (_, i) =>
          Math.round(
            Math.min(
              100,
              Math.max(
                0,
                base +
                  Math.sin((n + i) * 1.7) * 2 +
                  (11 - i) * ((n % 7) - 3) * 0.28,
              ),
            ) * 100,
          ) / 100,
      );
    }
    function sparkline(r) {
      let v = deliveryHistory(r);
      if (!v) return '<span class="small muted">History unavailable</span>';
      let points = v
        .map((x, i) => `${8 + i * 16.7},${43 - x * 0.36}`)
        .join(" ");
      return `<button class="spark-button" data-action="trend" data-id="${esc(r.supplierID)}" aria-label="View illustrative delivery history for ${esc(r.supplierID)}"><span>Illustrative delivery history</span><svg viewBox="0 0 200 48" aria-hidden="true"><line x1="8" y1="43" x2="192" y2="43" stroke="#ccd7da"/><polyline points="${points}" fill="none" stroke="#0f6e74" stroke-width="2"/></svg><span>12 example weeks · 0–100%</span></button>`;
    }
    function showTrend(id) {
      let r = get(id),
        v = deliveryHistory(r);
      if (!v) return;
      dialog(
        "Illustrative delivery history · " + id,
        `<p class="notice">Synthetic example only. These weekly values are not in the supplied CSV and are not used for ranking, risk scores or approval evidence. Previously-used status is also demo metadata.</p><h2 style="margin-top:16px">${esc(nameOf(r))}</h2><p>Supplied snapshot delivery rating: ${fmt(r["Supplier Delivery Rating"])}%. Example weeks are relative, not actual observation dates.</p><svg class="trend-large" viewBox="0 0 600 200" role="img" aria-label="Illustrative delivery percentages on a zero to one hundred scale">${[0, 50, 100].map((v) => `<text x="0" y="${180 - v * 1.5}" font-size="12">${v}%</text><line x1="40" x2="585" y1="${180 - v * 1.5}" y2="${180 - v * 1.5}" stroke="#dce5e7"/>`).join("")}<polyline points="${v.map((x, i) => `${45 + i * 48},${180 - x * 1.5}`).join(" ")}" fill="none" stroke="#0f6e74" stroke-width="2"/>${v.map((x, i) => `<circle tabindex="0" cx="${45 + i * 48}" cy="${180 - x * 1.5}" r="5" fill="#0f6e74"><title>Example week ${i + 1}: ${x}%</title></circle>`).join("")}</svg><table><thead><tr><th>Example week</th><th>Illustrative delivery %</th></tr></thead><tbody>${v.map((x, i) => `<tr><td>${i + 1}</td><td>${x}</td></tr>`).join("")}</tbody></table>`,
      );
    }
    function portfolio() {
      let p = state.portfolio,
        rs = catalog().filter(
          (r) =>
            (p.group === "favorite"
              ? state.favorites.has(r.supplierID)
              : p.group === "used"
                ? isUsed(r)
                : state.favorites.has(r.supplierID) || isUsed(r)) &&
            (!p.q ||
              (r.supplierID + " " + nameOf(r))
                .toLowerCase()
                .includes(p.q.toLowerCase())),
        ),
        pages = Math.max(1, Math.ceil(rs.length / 9));
      p.page = Math.min(p.page, pages);
      let rows = rs.slice((p.page - 1) * 9, p.page * 9),
        actions = (r) =>
          `<div class="row"><button data-action="detail" data-id="${r.supplierID}">Inspect</button><button data-action="toggle-compare" data-id="${r.supplierID}">${state.compare.includes(r.supplierID) ? "Remove from compare" : "Compare"}</button><button data-action="favorite" data-id="${r.supplierID}" aria-label="Toggle favorite ${r.supplierID}">${state.favorites.has(r.supplierID) ? "★" : "☆"}</button></div>`;
      return `<div class="screen-title"><div><div class="eyebrow">Your supplier collections</div><h1>My suppliers</h1><p class="muted">A quick view of favorites and demo supplier relationships.</p></div><button data-action="compare">Compare selected (${state.compare.length}/20)</button></div><div class="portfolio-tools">${[
        ["favorite", "Favorites"],
        ["used", "Previously used"],
        ["all", "Both collections"],
      ]
        .map(
          ([v, l]) =>
            `<button data-collection="${v}" aria-pressed="${p.group === v}">${l}</button>`,
        )
        .join(
          "",
        )}<input id="portfolio-search" aria-label="Search my suppliers" placeholder="Find a name or supplier ID" value="${esc(p.q)}">${["cards", "rows"].map((v) => `<button data-portfolio-view="${v}" aria-pressed="${p.view === v}">${v === "cards" ? "Cards" : "Trend rows"}</button>`).join("")}</div><p class="notice">${rs.length.toLocaleString()} matching records. Trend lines are illustrative examples for previously-used suppliers only; the CSV contains no historical series. Favorites without demo history show History unavailable.</p>${state.compareError ? `<p role="alert">${esc(state.compareError)}</p>` : ""}<div style="margin-top:16px" class="${p.view === "cards" ? "portfolio-grid" : "card portfolio-table"}">${p.view === "cards" ? rows.map((r) => `<article class="card portfolio-widget"><div><div class="small muted">${r.supplierID} · ${esc(regionLabel(regionOf(r)))}</div><h2>${esc(nameOf(r))}</h2></div><div>${tags(r)}</div><div class="widget-metrics"><div><div class="small muted">Supplied total risk</div><strong>${fmt(r.Total_Risk_Index)} / 100</strong></div><div><div class="small muted">Delivery snapshot</div><strong>${fmt(r["Supplier Delivery Rating"])}%</strong></div></div>${sparkline(r)}${actions(r)}</article>`).join("") : `<table><thead><tr><th>Supplier / relationship</th><th>Total risk / 100</th><th>Delivery snapshot</th><th>Illustrative history</th><th>Actions</th></tr></thead><tbody>${rows.map((r) => `<tr><td><strong>${esc(nameOf(r))}</strong><div class="small">${r.supplierID}</div>${tags(r)}</td><td>${fmt(r.Total_Risk_Index)}</td><td>${fmt(r["Supplier Delivery Rating"])}%</td><td>${sparkline(r)}</td><td>${actions(r)}</td></tr>`).join("")}</tbody></table>`}</div>${!rows.length ? '<p class="empty">No suppliers match this collection and search.</p>' : ""}<div class="portfolio-tools"><button data-portfolio-page="-1" ${p.page === 1 ? "disabled" : ""}>Previous</button><span>Page ${p.page} of ${pages}</span><button data-portfolio-page="1" ${p.page === pages ? "disabled" : ""}>Next</button></div>`;
    }
    document.addEventListener("click", (e) => {
      let b = e.target.closest("button");
      if (!b) return;
      if (b.dataset.collection) {
        state.portfolio.group = b.dataset.collection;
        state.portfolio.page = 1;
        render();
      } else if (b.dataset.portfolioView) {
        state.portfolio.view = b.dataset.portfolioView;
        render();
      } else if (b.dataset.portfolioPage) {
        state.portfolio.page += Number(b.dataset.portfolioPage);
        render();
      } else if (b.dataset.action === "trend") showTrend(b.dataset.id);
    });
    document.addEventListener("input", (e) => {
      if (e.target.id !== "portfolio-search") return;
      let pos = e.target.selectionStart;
      state.portfolio.q = e.target.value;
      state.portfolio.page = 1;
      render();
      let input = $("#portfolio-search");
      input.focus();
      input.setSelectionRange(pos, pos);
    });

    function render() {
      const route = location.hash.replace(/^#\//, "") || "overview";
      const preservedParts =
        route === "discover" &&
        partsScene &&
        partsRegion === state.filters.region
          ? $("#parts-scene")
          : null;
      train?.destroy();
      train = null;
      if (!preservedParts) {
        partsScene?.destroy();
        partsScene = null;
        partsRegion = null;
      }
      if (route.startsWith("supplier/") && route !== state.route)
        touchSupplier(decodeURIComponent(route.slice(9)));
      state.route = route;
      $("#app").innerHTML =
        route === "overview"
          ? overview()
          : route === "discover"
            ? discovery()
            : route === "portfolio"
              ? portfolio()
              : route === "compare"
                ? compare()
                : route === "research"
                  ? research()
                  : route === "reports"
                    ? reports()
                    : route === "memo"
                      ? memo()
                      : route.startsWith("supplier/")
                        ? detail(decodeURIComponent(route.slice(9)))
                        : overview();
      $("#header-count").textContent =
        fmt(catalog().length) + " records · demo assignments";
      document
        .querySelectorAll("#nav a")
        .forEach((a) =>
          a.classList.toggle(
            "active",
            a.hash ===
              "#/" +
                (route.startsWith("supplier/") || route === "compare"
                  ? "discover"
                  : route === "memo"
                    ? "reports"
                    : route),
          ),
        );
      if (route === "overview")
        train = mountTrain($("#train-scene"), {
          regions,
          counts: counts(),
          selected: state.region,
          onSelect: selectRegion,
        });
      if (route === "discover" && $("#parts-scene")) {
        if (preservedParts) {
          $("#parts-scene").replaceWith(preservedParts);
          partsScene.highlight(state.filters.part);
        } else {
          const region = regions.find((r) => r.id === state.filters.region);
          partsScene = mountParts($("#parts-scene"), {
            region,
            counts: partCounts(region),
            selected: state.filters.part,
            onSelect: selectPart,
          });
          partsRegion = region.id;
        }
      }
      renderTour();
      persistWorkspace();
    }
    function navigate(route) {
      if (location.hash === "#/" + route) render();
      else location.hash = "/" + route;
    }
    function selectRegion(id) {
      state.region = id;
      state.filters.region = id;
      state.filters.part = "";
      state.page = 1;
      state.focus = null;
      render();
    }
    function toast(msg) {
      clearTimeout(toastTimer);
      $("#toast-root").innerHTML = `<div class="toast">${esc(msg)}</div>`;
      toastTimer = setTimeout(() => ($("#toast-root").innerHTML = ""), 4500);
    }
    function dialog(title, html) {
      $("#dialog-title").textContent = title;
      $("#dialog-body").innerHTML = html;
      $("#dialog").showModal();
    }
    function cells(id, column) {
      touchSupplier(id);
      persistWorkspace();
      let r = get(id);
      if (!r) return;
      dialog(
        "Source cells · " + id,
        `<p class="small muted">${r._research ? "Research-only: no supplied CSV row." : "Exact immutable source record · physical CSV row " + (originals.indexOf(r) + 2) + " (header is row 1). First 46 columns are original supplied cells; remaining columns are separate illustrative augmentation. Derived axes never substitute a source value."}</p><p class="small" style="overflow-wrap:anywhere">Source SHA-256: ${esc(payload.sha256)}</p><table><thead><tr><th>Exact column</th><th>Value</th></tr></thead><tbody>${payload.columns.map((c) => `<tr ${c === column ? 'class="selected"' : ""}><td>${esc(c)}</td><td>${r._research ? "Unknown" : esc(r[c])}</td></tr>`).join("")}</tbody></table>`,
      );
      if (column)
        $("#dialog-body .selected")?.scrollIntoView({ block: "center" });
    }
    function toggleCompare(id) {
      if (state.compare.includes(id)) {
        state.compare = state.compare.filter((x) => x !== id);
        state.compareError = "";
      } else if (state.compare.length >= 20) {
        state.compareError =
          "Limit reached: 20 selected. Remove a supplier in Manage selection to make room.";
        toast(state.compareError);
      } else {
        state.compare.push(id);
        state.compareError = "";
      }
      if (state.memo) state.memo.stale = true;
      render();
    }
    const tourSteps = [
      [
        "Choose a train system",
        "Select Doors on the train or its labelled button. Counts describe synthetic catalog assignments, never capacity or qualification.",
        "Explore Doors",
        () => {
          state.region = "doors";
          state.filters.part = "";
          navigate("overview");
        },
      ],
      [
        "Discover with a visible scope",
        "Open Discovery with Doors selected. Try search, supplied risk level, minimum delivery, favorites or demo previous-use filters; all combine with AND.",
        "Open Doors Discovery",
        () => {
          state.filters.region = "doors";
          state.filters.part = "";
          state.page = 1;
          navigate("discover");
        },
      ],
      [
        "Build a comparison set",
        "Select actual supplier rows in Discovery. Part and system filters narrow candidates while comparison selections persist across filters, up to 20 suppliers.",
        "Choose comparison candidates",
        () => navigate("discover"),
      ],
      [
        "Name the financial metric",
        "Ask which supplier has the lowest supplied Financial_Health_Score. Inspect its exact cells. The derived Financial axis also includes credit rating and may produce a different ordering.",
        "Ask financial source question",
        () => {
          navigate("compare");
          financial();
        },
      ],
      [
        "Research in one conversation",
        "Open the sourcing assistant. Supply a company identity to investigate public sources. Actual server activity and evidence stay in the drawer.",
        "Open sourcing assistant",
        () => openChat(),
      ],
      [
        "Read the report and add carefully",
        "Open a completed dossier from the conversation. Review its identity, gaps and source evidence. Added research suppliers stay separate from anonymized CSV records and retain Unknown scores.",
        "Open research conversation",
        () => openChat(),
      ],
      [
        "Review new and previously used candidates",
        "Every candidate uses the same approval template. Open a previously used demo supplier now; prior history does not waive fresh checks. A new candidate can be chosen from Discovery too.",
        "Draft for previously used candidate",
        () => {
          let r =
            originals.find((r) => regionOf(r) === "doors" && isUsed(r)) ||
            get("SUPP_00012");
          newMemo(r.supplierID);
        },
      ],
      [
        "Preview the request and print",
        "Fill context, rationale, alternatives, preparer, reviewer, next action, owner and due date. The preview remains Draft / not approved. Use Print / Save as PDF to invoke your browser; cancellation changes no status.",
        "Open memo preview",
        () => {
          if (state.memo) navigate("memo");
          else {
            navigate("discover");
            toast(
              "Choose a candidate and Request review to create the shared memo.",
            );
          }
        },
      ],
    ];
    function renderTour() {
      let t = state.tour;
      $("#tour-root").innerHTML =
        t < 0
          ? ""
          : `<aside class="tour"><div class="row spread"><span class="eyebrow">Guided journey · ${t + 1} / ${tourSteps.length}</span><button class="quiet small" data-action="end-tour">Close</button></div><h2>${tourSteps[t][0]}</h2><p>${tourSteps[t][1]}</p><div class="row spread"><button data-action="tour-do">${tourSteps[t][2]}</button><button class="primary" data-action="tour-next">${t === tourSteps.length - 1 ? "Finish" : "Next →"}</button></div></aside>`;
    }
    document.addEventListener("click", (e) => {
      let b = e.target.closest("[data-action]");
      if (!b) return;
      let a = b.dataset.action,
        id = b.dataset.id;
      if (id && ["detail", "compare-focus"].includes(a)) touchSupplier(id);
      switch (a) {
        case "supplier-tab":
          state.tab = b.dataset.tab;
          render();
          break;
        case "part":
          selectPart(b.dataset.part);
          break;
        case "reset-parts":
          partsScene?.resetView();
          break;
        case "region":
          selectRegion(b.dataset.region);
          break;
        case "reset-view":
          train?.resetView();
          break;
        case "discover-region":
          state.filters.region = state.region;
          state.filters.part = "";
          state.page = 1;
          navigate("discover");
          break;
        case "favorite":
          state.favorites.has(id)
            ? state.favorites.delete(id)
            : state.favorites.add(id);
          if (state.memo?.candidate === id) {
            state.memo.relationship =
              tags(get(id)).replace(/<[^>]*>/g, " ") || "Neither";
            state.memo.rev++;
            state.memo.stale = true;
          }
          render();
          break;
        case "detail":
          navigate("supplier/" + encodeURIComponent(id));
          break;
        case "recommend":
          newMemo(id);
          break;
        case "radar-table":
          state.tableRadar = !state.tableRadar;
          render();
          break;
        case "mapping":
          dialog(
            "Six derived axes · equal weights",
            radar(get(state.focus) || get("SUPP_00012"), state.region, true) +
              '<p class="screen-note">0 = no risk, 100 = maximum risk. Financial (derived) is distinct from supplied Financial_Health_Score. Source total unchanged.</p>',
          );
          break;
        case "financial":
          financial();
          break;
        case "why-high":
          whyHigh();
          break;
        case "research-mode":
          openChat();
          break;
        case "clear-filters":
          state.filters = {
            q: "",
            region: "",
            part: "",
            risk: "",
            delivery: "",
            favorite: false,
            used: false,
            sort: "total",
          };
          state.page = 1;
          render();
          break;
        case "prev-page":
          state.page--;
          render();
          break;
        case "next-page":
          state.page++;
          render();
          break;
        case "compare":
          state.focus = state.compare[0];
          navigate("compare");
          break;
        case "compare-focus":
          state.focus = id;
          render();
          break;
        case "toggle-compare":
        case "remove-compare":
          toggleCompare(id);
          break;
        case "manage-compare":
          dialog(
            "Comparison selection · " + state.compare.length + " / 20",
            `<p>Selections stay across pages and filters. Remove a record to free a slot.</p><div class="selection-tags">${state.compare.map((x) => `<button data-action="remove-dialog-compare" data-id="${esc(x)}">${esc(x)} ×</button>`).join("") || "<p>No selections.</p>"}</div>`,
          );
          break;
        case "remove-dialog-compare":
          toggleCompare(id);
          b.remove();
          $("#dialog-title").textContent =
            "Comparison selection · " + state.compare.length + " / 20";
          break;
        case "close-dialog":
        case "close-link":
          $("#dialog").close();
          break;
        case "source-cells":
          cells(id);
          break;
        case "provenance":
          provenance();
          break;
        case "saved-report":
          showRisk(state.reports[b.dataset.run] || state.added[0]?._report);
          break;
        case "print-memo":
          state.memo.preview = memoDocument(state.memo);
          printDoc(state.memo.preview);
          break;
        case "update-selection":
          state.memo.selection = state.compare.slice();
          state.memo.filters = JSON.parse(JSON.stringify(state.filters));
          state.memo.rev++;
          state.memo.stale = false;
          render();
          break;
        case "tour":
          state.tour = 0;
          renderTour();
          break;
        case "end-tour":
          state.tour = -1;
          renderTour();
          break;
        case "tour-next":
          state.tour =
            state.tour === tourSteps.length - 1 ? -1 : state.tour + 1;
          renderTour();
          break;
        case "tour-do":
          tourSteps[state.tour][3]();
          break;
        case "reset":
          if (
            (state.memo || state.added.length) &&
            !confirm(
              "Reset this session? Drafts, local research associations, notes and selections will be reset. Research dossiers remain saved on the server.",
            )
          )
            return;
          clearRun();
          appGeneration++;
          if (chat) chat.reset();
          state = initial();
          statCache.clear();
          $("#dialog").close();
          $("#print-root").innerHTML = "";
          navigate("overview");
          toast("Reset complete · original 10,000 records restored.");
          break;
      }
    });
    document.addEventListener("click", (e) => {
      if (e.target.closest("button,a,input,select")) return;
      let c = e.target.closest("[data-focus]");
      if (c && state.focus !== c.dataset.focus) {
        state.focus = c.dataset.focus;
        touchSupplier(c.dataset.focus);
        render();
      }
    });
    document.addEventListener("keydown", (e) => {
      let c = e.target.closest("[data-focus]");
      if (c && e.key === "Enter") {
        state.focus = c.dataset.focus;
        touchSupplier(c.dataset.focus);
        render();
      }
    });
    document.addEventListener("focusin", (e) => {
      let b = e.target.closest('[data-action="region"]');
      if (b) train?.highlight(b.dataset.region);
    });
    document.addEventListener("focusout", (e) => {
      if (e.target.closest('[data-action="region"]')) train?.highlight(null);
    });
    document.addEventListener("change", (e) => {
      let el = e.target;
      if (el.dataset.filter) {
        if (["q", "delivery"].includes(el.dataset.filter)) return;
        if (el.dataset.filter === "region") {
          state.filters.part = "";
          if (el.value) state.region = el.value;
        }
        state.filters[el.dataset.filter] =
          el.type === "checkbox" ? el.checked : el.value;
        state.page = 1;
        render();
      } else if (el.dataset.compare) toggleCompare(el.dataset.compare);
      else if (el.id === "supplier-tab") {
        state.tab = el.value;
        state.focus = null;
        render();
      } else if (el.dataset.memo) {
        return;
      }
    });
    document.addEventListener("input", (e) => {
      let el = e.target;
      if (["q", "delivery"].includes(el.dataset.filter)) {
        let key = el.dataset.filter,
          pos = el.selectionStart;
        state.filters[key] = el.value;
        state.page = 1;
        render();
        let input = document.querySelector('[data-filter="' + key + '"]');
        input.focus();
        if (input.type === "text" && pos !== null)
          input.setSelectionRange(pos, pos);
        return;
      }
      if (el.dataset.memo) {
        state.memo[el.dataset.memo] = el.value;
        state.memo.rev++;
        state.memo.preview = memoDocument(state.memo);
        $("#memo-preview").innerHTML = state.memo.preview;
        let status = $(".memo-form .notice");
        if (status)
          status.textContent = missingMemo(state.memo).length
            ? "Incomplete draft · " + missingMemo(state.memo).join(", ")
            : state.memo.stale
              ? "Stale · update selection basis"
              : "Ready for review · no approval granted.";
      }
    });

    let chat;
    const recoveryKey = "supplier-workspace-pending-v1";
    let pendingWorkspace = null,
      saveTask = null;
    function savingStatus(message) {
      let node = document.querySelector("#workspace-status");
      if (!node) {
        node = document.createElement("small");
        node.id = "workspace-status";
        node.className = "muted";
        node.setAttribute("role", "status");
        document.querySelector("header").append(node);
      }
      node.textContent = message;
    }
    function boundedChat() {
      let messages = chat.state.messages
        .map((m) => ({
          ...m,
          answer: String(m.answer || m.content || "").slice(0, 20000),
          citations: (m.citations || []).slice(0, 24),
          ...(m.chart
            ? {
                chart: {
                  ...m.chart,
                  points: (m.chart.points || []).slice(0, 20),
                },
              }
            : {}),
        }))
        .slice(-199);
      let removed = false;
      const bytes = (v) => new TextEncoder().encode(JSON.stringify(v)).length;
      while (messages.length && bytes(messages) > 95000) {
        messages.shift();
        removed = true;
      }
      if (removed)
        messages.unshift({
          role: "assistant",
          answer:
            "Earlier conversation turns were omitted from saved history to keep workspace storage bounded.",
        });
      chat.state.messages = messages;
      return messages;
    }
    function workspaceSnapshot() {
      const drafts = [];
      if (state.memo)
        drafts.push({ kind: "approval", memo: { ...state.memo, preview: "" } });
      state.added.forEach((record) =>
        drafts.push({
          kind: "research-record",
          record: {
            ...record,
            _record: record._record
              ? { id: record._record.id, run_id: record._record.run_id }
              : null,
            _report: record._report ? { id: record._report.id } : null,
          },
        }),
      );
      return {
        favorites: [...state.favorites],
        recents: state.recents,
        compare: state.compare,
        drafts,
        chat: boundedChat(),
        region: state.region,
      };
    }
    function persistWorkspace() {
      if (!chat) return Promise.resolve();
      pendingWorkspace = workspaceSnapshot();
      try {
        localStorage.setItem(recoveryKey, JSON.stringify(pendingWorkspace));
      } catch {}
      savingStatus("Saving...");
      return flushWorkspace();
    }
    function flushWorkspace(exiting = false) {
      if (saveTask) return saveTask;
      saveTask = (async () => {
        while (pendingWorkspace) {
          const snapshot = pendingWorkspace;
          pendingWorkspace = null;
          try {
            const body = JSON.stringify(snapshot);
            const response = await fetch("/api/workspace", {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body,
              keepalive:
                exiting && new TextEncoder().encode(body).length < 60000,
            });
            if (!response.ok) {
              const error = await response.json();
              throw Error(error.error || "Server rejected workspace");
            }
            // Consume the successful response before starting the next serialized write.
            await response.text();
            if (!pendingWorkspace) {
              try {
                localStorage.removeItem(recoveryKey);
              } catch {}
              savingStatus("Saved locally");
            }
          } catch (error) {
            if (!pendingWorkspace) pendingWorkspace = snapshot;
            savingStatus("Save failed - recovery stored in this browser");
            toast("Workspace could not be saved: " + error.message);
            throw error;
          }
        }
      })().finally(() => {
        saveTask = null;
      });
      saveTask.catch(() => {});
      return saveTask;
    }
    window.addEventListener("pagehide", () => {
      if (chat && (saveTask || pendingWorkspace)) {
        pendingWorkspace = workspaceSnapshot();
        try {
          localStorage.setItem(recoveryKey, JSON.stringify(pendingWorkspace));
        } catch {}
        if (!saveTask) flushWorkspace(true).catch(() => {});
      }
    });
    async function restoreWorkspace() {
      let w = await api("/api/workspace");
      try {
        const recovered = JSON.parse(
          localStorage.getItem(recoveryKey) || "null",
        );
        if (
          recovered &&
          Array.isArray(recovered.drafts) &&
          Array.isArray(recovered.chat)
        ) {
          w = recovered;
          savingStatus("Restored unsaved browser changes");
        }
      } catch {}
      if (Array.isArray(w.favorites)) state.favorites = new Set(w.favorites);
      state.compare = (w.compare || [])
        .filter((id) => sourceById.has(id))
        .slice(0, 20);
      if (regions.some((r) => r.id === w.region)) {
        state.region = w.region;
        state.filters.region = w.region;
      }
      for (const draft of w.drafts || []) {
        if (draft.kind === "approval" && draft.memo) state.memo = draft.memo;
        if (draft.kind === "research-record" && draft.record)
          state.added.push(draft.record);
      }
      state.compare = (w.compare || []).filter((id) => get(id)).slice(0, 20);
      state.recents = (w.recents || []).filter((id) => get(id)).slice(0, 50);
      chat = createChat({
        esc,
        selected: () => state.compare,
        getMessages: () => w.chat || [],
        onSave: persistWorkspace,
        onCell: (id, column) => {
          if (get(id)) cells(id, column);
        },
        onReport: (run, show) => {
          state.reports[run.id] = run;
          if (show) showRisk(run);
        },
        onAdded: (record) => {
          const row = {
            supplierID: "research:" + record.id,
            "Supplier Name": record.company,
            train_region_id: state.region,
            _research: true,
            _report: state.reports[record.run_id],
            _record: record,
          };
          if (!get(row.supplierID)) state.added.push(row);
          persistWorkspace();
          render();
          toast("Research supplier added · scores remain Unknown");
        },
      });
      try {
        const data = await api("/api/research");
        for (const run of data.runs || []) state.reports[run.id] = run;
      } catch {}
      if (state.memo) {
        const candidate = get(state.memo.candidate);
        if (candidate?._research) {
          try {
            candidate._report = await api(
              "/api/research/" +
                encodeURIComponent(
                  candidate._record?.run_id || candidate._report?.id,
                ),
            );
          } catch {}
        }
      }
      const active = [...chat.state.messages].reverse().find((m) => m.run_id);
      if (active) chat.poll(active.run_id);
    }
    function openChat() {
      chat?.open();
    }
    function clearRun() {
      clearTimeout(timer);
    }
    function startRun(entity) {
      chat.send("Research " + entity);
    }
    function research() {
      queueMicrotask(openChat);
      return `<section class="card padded"><h1>Research stays in your conversation</h1><p>Use the sourcing assistant to investigate an identified company, follow actual research activity and inspect its evidence.</p><button id="open-assistant-page">Open sourcing assistant</button></section>`;
    }
    function financial() {
      chat.send(
        state.compare.length
          ? "Compare Financial_Health_Score for " + state.compare.join(", ")
          : "Help me select suppliers to compare their supplied Financial_Health_Score",
      );
    }
    function whyHigh() {
      chat.send(
        state.focus
          ? "Explain the supplied risk profile of " + state.focus
          : "Help me inspect a supplied risk profile",
      );
    }
    function reports() {
      return `<div class="screen-title"><div><div class="eyebrow">Evidence & decisions</div><h1>Reports and approval requests</h1><p class="small muted">Saved on this local server. Browser printing creates a review copy.</p></div><button id="open-assistant-page" class="primary">Research a company</button></div><div class="two"><section class="card padded"><h2>Research dossiers</h2>${
        Object.values(state.reports)
          .map(
            (r) =>
              `<div class="source"><strong>${esc(r.company)}</strong><p>${esc(r.status)} · ${r.demo ? "saved historical example" : "public research"} · ${esc(r.mode)}</p><p class="small muted">${esc(r.summary || "Research is in progress.")}</p><button data-live-report="${esc(r.id)}">Open dossier</button></div>`,
          )
          .join("") ||
        '<p style="margin-top:12px">No research runs yet. Start in the sourcing assistant.</p>'
      }</section><section class="card padded"><h2>Approval request</h2>${state.memo ? `<p style="margin:12px 0">${esc(state.memo.id)} · ${esc(state.memo.candidate)} · rev ${state.memo.rev}<br>Draft / not approved</p><a class="button" href="#/memo">Continue draft →</a>` : '<p style="margin:12px 0">Choose a candidate in Discovery to prepare an approval request.</p>'}<p class="small muted">Previously used suppliers follow the same review workflow.</p></section></div>`;
    }
    function riskDocument(r) {
      return `<article class="document"><div class="doc-header">SUPPLIER RESEARCH · ${esc(r.id)}</div><h1>${esc(r.company)}</h1><div class="doc-status">${esc(r.status)} · ${r.demo ? "SAVED HISTORICAL EXAMPLE" : "PUBLIC RESEARCH"} · NO APPROVAL GRANTED</div><h2>Identity & scope</h2><p>Country hint: ${esc(r.country || "Unknown")} · website hint: ${esc(r.website || "Unknown")}</p><p>${esc(r.scope || "Procurement scope unspecified")}</p><p>Entity verification: ${esc(r.entity?.verification || "Unverified")}</p>${r.dataset_context ? `<h3>Separate supplied-data context</h3><pre>${esc(JSON.stringify(r.dataset_context, null, 2))}</pre><p>Supplied records do not establish the real company’s identity or numerical risk.</p>` : ""}<h2>Summary</h2><p>${esc(r.summary || r.error || "Not completed")}</p><h2>Research plan</h2>${(r.plan || []).map((p) => `<details><summary>${esc(p.category)}</summary>${p.questions.map((q) => `<p>${esc(q)}</p>`).join("")}</details>`).join("")}<h2>${r.demo ? "Saved historical observations" : "Source-bound observations"}</h2><div class="research-findings">${(r.findings || []).map((f) => `<article><h3>${esc(f.id)} · ${esc(f.title)}</h3><p>${esc(f.category)} · ${esc(f.severity)} · confidence ${esc(f.confidence)}</p><p>${esc(f.detail)}</p>${(f.evidence || []).map((e) => `${r.demo ? "<div><p><strong>Saved historical paraphrase (not a verified source quotation)</strong></p><p>" : "<blockquote>"}${esc(e.quote)}<p class="small">${esc(e.source_id)} · ${esc(e.locator || "")}</p>${r.demo ? "</p></div>" : "</blockquote>"}`).join("")}</article>`).join("") || "<p>No retained source-bound observations.</p>"}</div><h2>Gaps and limits</h2>${[...(r.gaps || []), ...(r.limitations || [])].map((v) => `<p>• ${esc(v)}</p>`).join("")}<h2>Buyer actions</h2>${(r.actions || []).map((a) => `<p>☐ ${esc(a.action)} · ${esc(a.owner || "Unassigned")} · ${esc(a.status)}</p>`).join("")}<h2>Source register</h2>${(r.sources || []).map((s, i) => `<section class="source"><a class="citation-chip" href="${esc(safeURL(s.url))}" target="_blank" rel="noopener noreferrer"><b>${i + 1}</b>${esc(s.title || s.id)}</a><p class="small">${esc(s.id)} · ${esc(s.url)}</p><details><summary>Retrieved excerpt</summary><p>${esc(s.excerpt || "No excerpt available")}</p></details></section>`).join("")}<h2>Actual activity</h2>${(r.events || []).map((e) => `<p class="small">${esc(e.at)} · ${esc(e.stage)} · ${esc(e.message)}</p>`).join("")}</article>`;
    }
    async function showRisk(run) {
      const token = appGeneration;
      if (!run?.id) return;
      try {
        const r = await api("/api/research/" + encodeURIComponent(run.id));
        if (token !== appGeneration) return;
        state.reports[r.id] = r;
        dialog(
          "Research dossier · " + r.company,
          `<div class="actions"><button id="print-live-risk" class="primary">Print / Save as PDF</button><a class="button" href="/api/research/${encodeURIComponent(r.id)}/export?format=markdown" target="_blank" rel="noopener">Export Markdown</a>${r.status === "completed" ? `<button data-add-live="${esc(r.id)}">Add as unscored supplier</button>` : ""}</div>${riskDocument(r)}`,
        );
        $("#print-live-risk").onclick = () => printDoc(riskDocument(r));
      } catch (error) {
        if (token !== appGeneration) return;
        toast(error.message);
      }
    }
    async function printDoc(html) {
      const token = appGeneration;
      $("#print-root").innerHTML =
        '<div class="running-print-header">DRAFT / NOT APPROVED - SUPPLIER REVIEW COPY</div>' +
        html;
      try {
        await persistWorkspace();
        if (token === appGeneration) window.print();
      } catch {
        toast(
          "Save failed. Your browser recovery copy is retained; retry saving before printing.",
        );
      }
    }
    function sourceAppendix(r) {
      const table = (columns) =>
        `<table><thead><tr><th>Exact column</th><th>Value</th></tr></thead><tbody>${columns.map((c) => `<tr><td>${esc(c)}</td><td>${esc(r[c])}</td></tr>`).join("")}</tbody></table>`;
      return `<h3>Original supplied CSV cells</h3><p>Source: ${esc(payload.source)}<br>SHA-256: ${esc(payload.sha256)}<br>Physical CSV row: ${originals.indexOf(r) + 2}</p>${table(payload.columns.slice(0, 46))}<h3>Augmented demonstration fields</h3><p>Separate augmentation source: docs/supplier_risk_dataset_augmented.csv<br>Augmentation SHA-256: ${esc(manifest.augmentation?.sha256 || "See manifest")}<br>Derived axes and train/relationship associations are illustrative enrichment, not original source cells.</p>${table(payload.columns.slice(46))}`;
    }
    function memoDocument(m) {
      const r = get(m.candidate);
      if (!r) return "<p>Candidate unavailable. Choose another supplier.</p>";
      return `<article class="document"><div class="doc-header">APPROVAL REQUEST · ${esc(m.id)} · REV ${m.rev}</div><h1>${esc(nameOf(r))}</h1><div class="doc-status">DRAFT · ${esc(m.disposition)} · NO APPROVAL GRANTED</div><p>Candidate ${esc(r.supplierID)} · ${r._research ? "Public research record · no supplied scores" : "Anonymized supplied-data record"}</p>${[
        ["project", "Project / decision context"],
        ["component", "Component need"],
        ["preparer", "Prepared by"],
        ["reviewer", "Intended reviewer"],
        ["rationale", "Rationale / trade-offs"],
        ["alternatives", "Alternatives"],
        ["action", "Next evidence / action"],
        ["owner", "Action owner"],
        ["due", "Due date"],
        ["comments", "Reviewer comments"],
      ]
        .map(
          ([k, label]) =>
            `<h2>${label}</h2><p>${esc(m[k] || "Not supplied")}</p>`,
        )
        .join(
          "",
        )}<h2>Selection basis</h2><p>Comparison: ${esc((m.selection || []).join(", ") || "No alternatives selected")} · ${m.stale ? "STALE — refresh selection basis" : "Saved selection snapshot"}</p><p>Required fields: ${esc(missingMemo(m).join(", ") || "Complete for review; no approval granted")}</p><h2>Evidence appendix</h2>${r._research ? `<p>Separate research dossier: ${esc(r._record?.run_id || r._report?.id)}. Source scores Unknown. Public evidence is not qualification.</p>${r._report?.findings ? riskDocument(r._report) : "<p>Dossier evidence not loaded. Open its linked report before preparing the review copy.</p>"}` : sourceAppendix(r)}<h2>Scope statement</h2><p>System associations and previous-use tags are illustrative. Trend examples are not historical observations. Supplied total risk weights are unknown. This request grants no qualification, award or approval; reviewer decision remains pending.</p></article>`;
    }
    function provenance() {
      dialog(
        "Data, scope & assumptions",
        `<div class="notice">Immutable supplied dataset · local persisted workspace · public research remains separate from anonymized supplier identities.</div><h3 style="margin-top:16px">Illustrative enrichment</h3><p>System assignments, initial favorites and previous-use metadata are synthetic. Trend lines are illustrative and are never evidence. Country-risk scores do not identify country.</p><h3 style="margin-top:16px">Risk mapping</h3><p>Six derived axes are equal-weight means of disclosed source scores, higher = more risk. Original total-risk weights are unavailable. Unknowns are excluded from statistics.</p><p style="overflow-wrap:anywhere">${esc(payload.source)}<br>SHA-256 ${esc(payload.sha256)}</p><details><summary>Full reproducibility manifest</summary><pre>${esc(JSON.stringify(manifest, null, 2))}</pre></details>`,
      );
    }
    document.addEventListener("click", async (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      if (b.id === "open-assistant-page") openChat();
      if (b.dataset.liveReport) showRisk({ id: b.dataset.liveReport });
      if (b.dataset.addLive) {
        const token = appGeneration;
        try {
          const result = await api("/api/suppliers", {
            run_id: b.dataset.addLive,
          });
          if (token !== appGeneration) return;
          const record = result.supplier || result;
          const id = "research:" + record.id;
          if (!get(id))
            state.added.push({
              supplierID: id,
              "Supplier Name": record.company,
              train_region_id: state.region,
              _research: true,
              _report: state.reports[record.run_id],
              _record: record,
            });
          persistWorkspace();
          toast("Added separate research supplier · scores Unknown");
        } catch (error) {
          if (token !== appGeneration) return;
          toast(error.message);
        }
      }
    });
    document.addEventListener("input", (e) => {
      if (e.target.dataset.memo) persistWorkspace();
    });

    await restoreWorkspace();
    window.addEventListener("hashchange", render);
    window.__supplierApp = {
      get state() {
        return state;
      },
      get catalog() {
        return catalog();
      },
      get counts() {
        return counts();
      },
      get manifest() {
        return manifest;
      },
      get sourceRows() {
        return originals;
      },
      stats,
      axisVal,
      render,
    };
    render();
  } catch (error) {
    document.querySelector("#app").textContent =
      "Unable to load supplier workspace: " + error.message;
  }
});
