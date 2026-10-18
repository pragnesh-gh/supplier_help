import { api, safeURL } from "./api.js";
import { icon } from "./icons.js";
import { citeChip, createCitationPanel, findCitation } from "./citations.js";
import { researchCard, offerCard } from "./research-card.js";

export function createChat({
  esc,
  selected,
  onSave,
  onReport,
  onAdded,
  onCell,
  onAction = () => {},
  isFavorite = () => false,
  inCompare = () => false,
  inShortlist = () => false,
  getMessages,
}) {
  const state = {
    messages: getMessages(),
    open: false,
    busy: false,
    run: null, // the most recent run (kept for app callers)
    runs: {}, // run id -> latest run object
    pinned: null, // run id the follow-up questions are about
    clarify: false,
    config: null,
    pending: {}, // run id -> card action in progress ("favorite", "shortlist", "compare")
    notes: {}, // run id -> { text, href, link, error } shown under the card's actions
  };
  const drawer = document.querySelector("#chat-drawer"),
    launch = document.querySelector("#chat-launch");
  const panel = createCitationPanel({ esc });
  const timers = {};
  let generation = 0,
    forceScroll = false;

  function citation(c, index, m) {
    if (c.kind === "web" && c.n !== undefined) return citeChip(c, esc, c.run_id || "");
    const label =
      c.kind === "dataset"
        ? `${c.supplier_id || "CSV"} · ${c.column || c.title || "source cells"}`
        : c.title || "Public source";
    return c.url
      ? `<a class="citation-chip" href="${esc(safeURL(c.url))}" target="_blank" rel="noopener noreferrer" title="${esc(label + " · " + c.url)}"><b>${index + 1}</b><span class="chip-label">${esc(label)}</span></a>`
      : `<button class="citation-chip" data-citation="${esc(c.supplier_id || "")}" data-column="${esc(c.column || "")}" title="${esc(label + " = " + (c.value ?? c.title ?? "source cell"))}">${icon("description")}<b>${index + 1}</b><span class="chip-label">${esc(label)}</span></button>`;
  }
  function chart(c) {
    if (!c?.points?.length) return "";
    const points = c.points.filter((p) => Number.isFinite(p.value));
    const max = Math.max(1, ...points.map((p) => Math.abs(p.value)));
    return `<div class="chat-chart"><strong>${esc(c.label || c.metric)}</strong><p class="small muted">${esc(c.metric || "")} · catalogue snapshot</p>${points.map((p) => `<div class="chart-point"><button data-chart-label="${esc(p.label)}" title="Inspect ${esc(p.label)}">${esc(p.label)}</button><div class="chart-bar"><i style="width:${(Math.max(0, p.value) / max) * 100}%"></i></div><strong>${esc(p.value)}</strong></div>`).join("")}<details><summary>View exact values</summary><table><thead><tr><th>Supplier</th><th>${esc(c.metric || "Value")}</th></tr></thead><tbody>${points.map((p) => `<tr><td>${esc(p.label)}</td><td>${esc(p.value)}</td></tr>`).join("")}</tbody></table></details></div>`;
  }
  // Reports made before the current research pipeline keep their simple summary block.
  function legacyRun(r) {
    const done = r.status === "completed";
    return `<section class="research-progress"><div class="row spread"><strong>${esc(r.company)}</strong><span class="small muted">${esc(r.status)}</span></div>${done ? `<p>${esc(r.summary || "Report ready.")}</p><div class="actions"><button data-research-report="${esc(r.id)}">${icon("description", "sm")}Open report</button><button data-research-save="${esc(r.id)}">Save to my suppliers</button></div>` : ""}${r.status === "failed" ? `<p role="alert">${esc(r.error || "Research could not complete.")}</p>` : ""}</section>`;
  }
  function runBlock(id) {
    const r = state.runs[id];
    if (!r) return `<button data-resume-run="${esc(id)}">${icon("history", "sm")}Show research result</button>`;
    if (r.schema_version !== "research-run-v2") return legacyRun(r);
    return researchCard(r, { esc, isFavorite, inCompare, inShortlist, pinned: state.pinned === id, pending: state.pending[id] || null, note: state.notes[id] || null });
  }
  function messageHTML(m, index) {
    const user = m.role === "user";
    const body = m.run_id && !user && /^Researching /.test(m.answer || "") ? "" : esc(m.answer || m.content || "");
    return `<article class="chat-message ${user ? "user" : "assistant"}${m.run_id ? " has-card" : ""}"><span class="message-label">${user ? "YOU" : "SOURCING ASSISTANT"}</span>${body}${(m.citations || []).length ? `<div class="source-chip-list">${m.citations.map((c, i) => citation(c, i, m)).join("")}</div>` : ""}${chart(m.chart)}${m.kind === "offer" ? offerCard(m, esc, index) : ""}${m.run_id ? runBlock(m.run_id) : ""}</article>`;
  }
  function pinnedBar() {
    const r = state.runs[state.pinned];
    if (!r) return "";
    const date = (r.completed_at || r.created_at || "").slice(0, 10);
    return `<div class="pinned-report">${icon("description", "sm")}<span>Talking about: <strong>${esc(r.company)}</strong> · report of ${esc(date)}</span><button class="icon-button compact quiet" data-unpin aria-label="Stop asking about this report">${icon("close", "sm")}</button></div>`;
  }
  function render() {
    if (!state.open) return;
    const identityForm = drawer.querySelector("#identity-form"),
      identityValues = identityForm ? Object.fromEntries(new FormData(identityForm)) : {},
      identityOpen = drawer.querySelector(".identity-form")?.open;
    const oldList = drawer.querySelector(".chat-messages"),
      oldScroll = oldList?.scrollTop || 0,
      stick = !oldList || oldList.scrollHeight - oldList.clientHeight - oldScroll < 65;
    const input = drawer.querySelector("textarea"),
      value = input?.value || "",
      focused = document.activeElement === input,
      pos = input?.selectionStart;
    drawer.hidden = false;
    launch.setAttribute("aria-expanded", "true");
    launch.hidden = true;
    const offline = state.config?.offline_fixture;
    const unavailable = state.config && !state.config.live_available && !offline;
    drawer.innerHTML = `<div class="chat-head"><div><h2>${icon("chat")}Sourcing assistant</h2><small>Catalogue questions and company research</small></div><button id="chat-close" class="icon-button quiet" aria-label="Close sourcing assistant">${icon("close")}</button></div><div class="chat-messages" aria-live="polite" aria-relevant="additions text">${state.messages.length ? state.messages.map(messageHTML).join("") : `<div class="chat-empty">${icon("chat", "lg")}<div class="eyebrow" style="margin-top:8px">Catalogue data and public research</div><h2 style="margin-top:10px">What would you like to understand?</h2><p style="margin-top:10px">Compare catalogue values, explain a risk profile, or research a real company from public sources.</p><div class="chat-suggestions"><button data-chat-prompt="Compare financial scores for SUPP_00012, SUPP_00450 and SUPP_00731">Compare three suppliers</button><button data-chat-prompt="Why is SUPP_00012 high risk?">Explain a risk profile</button><button data-offline-example>Offline research example</button></div></div>`}${state.busy ? '<p role="status" class="muted">Working on it…</p>' : ""}</div><div class="chat-composer">${pinnedBar()}<details ${state.clarify || identityOpen ? "open" : ""} class="identity-form"><summary>${icon("expand_more", "sm")}Company details for research</summary><form id="identity-form"><div class="identity-fields"><input name="company" aria-label="Company legal name" placeholder="Company legal name" required maxlength="200"><input name="country" aria-label="Country" placeholder="Country (optional)" maxlength="200"><input name="website" aria-label="Official website" placeholder="Official website (optional)"><input name="scope" aria-label="What you are buying" placeholder="What you are buying (optional)" maxlength="1000"><button class="primary" ${state.busy ? "disabled" : ""}>${icon("search", "sm")}Research this company</button></div></form><button type="button" class="small quiet" data-offline-example>Open the offline example (fictional company)</button></details><form id="assistant-form"><textarea id="assistant-input" aria-label="Message sourcing assistant" placeholder="Ask about suppliers, or name a company to research…" maxlength="4000" required>${esc(value)}</textarea><div class="composer-buttons"><button type="button" id="deep-research" ${state.busy ? "disabled" : ""} title="Research the company named in your message">${icon("search", "sm")}Deep research</button><button class="primary" ${state.busy ? "disabled" : ""} aria-label="Send message" title="Send (Enter)">${icon("arrow_forward")}</button></div></form><div class="chat-context">${offline ? "Offline mode: research runs on an invented example company. " : unavailable ? "Live research is not set up on this server; the offline example still works. " : ""}${selected().filter((id) => id.startsWith("SUPP_")).length ? `${selected().filter((id) => id.startsWith("SUPP_")).length} selected catalogue suppliers included as context. ` : ""}Catalogue scores and public research scores are kept apart.</div></div>`;
    for (const [name, v] of Object.entries(identityValues)) {
      const field = drawer.querySelector(`[name="${name}"]`);
      if (field) field.value = v;
    }
    if (focused) {
      drawer.querySelector("textarea").focus();
      drawer.querySelector("textarea").setSelectionRange(pos, pos);
    }
    const list = drawer.querySelector(".chat-messages");
    list.scrollTop = forceScroll || stick ? list.scrollHeight : oldScroll;
    forceScroll = false;
  }
  function open() {
    state.open = true;
    render();
    drawer.querySelector("textarea").focus();
  }
  function close() {
    panel.close();
    state.open = false;
    drawer.hidden = true;
    launch.hidden = false;
    launch.setAttribute("aria-expanded", "false");
    launch.focus();
  }
  async function poll(id, token = generation) {
    if (token !== generation || !id) return;
    clearTimeout(timers[id]);
    try {
      const run = await api("/api/research/" + encodeURIComponent(id));
      if (token !== generation) return;
      delete run.report_html; // fetched again by the report view; keep chat state small
      state.runs[id] = run;
      state.run = run;
      onReport(run);
      render();
      if (["queued", "researching"].includes(run.status)) timers[id] = setTimeout(() => poll(id, token), 1500);
      else onSave();
    } catch (error) {
      if (token !== generation) return;
      state.messages.push({ role: "assistant", answer: "Could not load the research result: " + error.message });
      render();
      onSave();
    }
  }
  function followUpRun() {
    if (state.pinned && state.runs[state.pinned]?.status === "completed") return state.pinned;
    const last = [...state.messages].reverse().find((m) => m.run_id && state.runs[m.run_id]?.status === "completed");
    return last?.run_id || null;
  }
  async function send(message, identity = {}) {
    if (state.busy || !message.trim()) return;
    const token = generation;
    open();
    drawer.querySelector("textarea").value = "";
    forceScroll = true;
    state.messages.push({ role: "user", answer: message });
    state.busy = true;
    render();
    onSave();
    const runId = identity.company ? null : followUpRun();
    try {
      const response = await api("/api/assistant", {
        message,
        mode: identity.mode || "deep",
        selected_ids:
          runId && !/SUPP_\d{5}|catalog|dataset|compare/i.test(message)
            ? []
            : selected().filter((id) => id.startsWith("SUPP_")),
        ...identity,
        ...(runId ? { run_id: runId } : {}),
      });
      if (token !== generation) return;
      state.clarify = response.kind === "clarify";
      state.messages.push({
        role: "assistant",
        kind: response.kind,
        answer: response.answer || response.question || "",
        citations: response.citations || [],
        chart: response.chart,
        run_id: response.run_id,
        ...(response.kind === "offer"
          ? { offer: response.offer, company: response.company, country: response.country, website: response.website }
          : {}),
      });
      forceScroll = true;
      if (response.run_id) {
        state.pinned = null;
        poll(response.run_id);
      }
    } catch (error) {
      if (token !== generation) return;
      state.messages.push({ role: "assistant", answer: error.message });
    } finally {
      if (token === generation) {
        state.busy = false;
        render();
        onSave();
      }
    }
  }
  function lastCompany() {
    for (const m of [...state.messages].reverse()) {
      if (m.run_id && state.runs[m.run_id]) return state.runs[m.run_id].requested_company || state.runs[m.run_id].company;
      if (m.kind === "offer" && m.company) return m.company;
    }
    return "";
  }
  function startFromInput() {
    const form = drawer.querySelector("#identity-form");
    const identity = form ? Object.fromEntries(new FormData(form)) : {};
    const typed = drawer.querySelector("textarea").value.trim();
    const company = identity.company?.trim() || typed || lastCompany();
    if (!company) {
      state.clarify = true;
      render();
      drawer.querySelector('[name="company"]')?.focus();
      return;
    }
    send(typed || "Research " + company, { ...identity, company: identity.company?.trim() || company, trigger: "button", mode: "deep" });
  }
  async function runExample() {
    const token = generation;
    open();
    forceScroll = true;
    state.messages.push({ role: "user", answer: "Open the offline research example." });
    render();
    try {
      const r = await api("/api/research", { demo: true, mode: "deep" });
      if (token !== generation) return;
      state.messages.push({ role: "assistant", answer: "Researching the offline example.", run_id: r.run_id || r.id });
      poll(r.run_id || r.id);
    } catch (error) {
      if (token !== generation) return;
      state.messages.push({ role: "assistant", answer: error.message });
    }
    render();
    onSave();
  }
  // PDF: print the same report file (same citation numbers) from a hidden same-origin frame.
  function printReport(runId) {
    document.querySelector("#report-print-frame")?.remove();
    const frame = document.createElement("iframe");
    frame.id = "report-print-frame";
    frame.title = "Report for printing";
    frame.style.cssText = "position:fixed;width:0;height:0;border:0;right:0;bottom:0";
    frame.src = "/api/research/" + encodeURIComponent(runId) + "/report.html";
    frame.onload = () => {
      try {
        frame.contentWindow.focus();
        frame.contentWindow.print();
      } catch {
        window.open(frame.src, "_blank", "noopener");
      }
    };
    document.body.append(frame);
  }
  launch.addEventListener("click", open);
  drawer.addEventListener("submit", (e) => {
    if (e.target.id === "identity-form") {
      e.preventDefault();
      const identity = Object.fromEntries(new FormData(e.target));
      send("Research " + identity.company, { ...identity, trigger: "form" });
    } else if (e.target.id === "assistant-form") {
      e.preventDefault();
      send(drawer.querySelector("textarea").value);
    }
  });
  function findMessageCitation(button) {
    const runId = button.dataset.citeRun;
    const n = button.dataset.citeN;
    const fromRun = findCitation(state.runs[runId], n);
    if (fromRun) return { ...fromRun, _run: runId };
    for (const m of state.messages)
      for (const c of m.citations || []) if (c.run_id === runId && String(c.n) === String(n)) return { ...c, _run: runId };
    return null;
  }
  // The download menu closes after a choice or a click elsewhere.
  document.addEventListener("click", (e) => {
    for (const menu of drawer.querySelectorAll(".dl-menu[open]"))
      if (!menu.contains(e.target) || e.target.closest(".dl-options a, .dl-options button")) menu.open = false;
  });
  drawer.addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.id === "chat-close") close();
    if (b.id === "deep-research") startFromInput();
    if (b.hasAttribute("data-offline-example")) runExample();
    if (b.dataset.chatPrompt) send(b.dataset.chatPrompt);
    if (b.dataset.citation) onCell(b.dataset.citation, b.dataset.column);
    if (b.dataset.chartLabel) {
      const id = b.dataset.chartLabel.match(/SUPP_\d+/)?.[0];
      if (id) onCell(id);
    }
    if (b.dataset.citeN !== undefined) {
      const c = findMessageCitation(b);
      if (c) panel.open(c, b);
      else if (b.dataset.citeRun) {
        await poll(b.dataset.citeRun);
        const again = findMessageCitation(b);
        if (again) panel.open(again, b);
      }
    }
    if (b.dataset.resumeRun) poll(b.dataset.resumeRun);
    if (b.dataset.offerStart !== undefined) {
      const m = state.messages[Number(b.dataset.offerIndex)];
      if (m) m.offer_state = "started";
      send("Research " + (m?.company || b.dataset.offerStart), {
        company: m?.company || b.dataset.offerStart,
        country: m?.country || "",
        website: m?.website || "",
        trigger: "offer",
        mode: "deep",
      });
    }
    if (b.dataset.offerDismiss !== undefined) {
      const m = state.messages[Number(b.dataset.offerDismiss)];
      if (m) m.offer_state = "dismissed";
      render();
      onSave();
    }
    if (b.dataset.clarifyRun) {
      const r = state.runs[b.dataset.clarifyRun];
      const c = r?.clarification?.candidates?.[Number(b.dataset.clarifyIndex)];
      if (c)
        send("Research " + c.legal_name, {
          company: c.legal_name,
          country: c.country_code || c.country_name || "",
          website: c.website || "",
          scope: r.scope || "",
          parent_run_id: r.id,
          trigger: "form",
          mode: r.mode || "deep",
        });
    }
    if (b.hasAttribute("data-clarify-none")) {
      state.clarify = true;
      render();
      drawer.querySelector('[name="company"]')?.focus();
    }
    if (b.dataset.researchRetry) {
      const r = state.runs[b.dataset.researchRetry];
      if (r) send("Research " + (r.requested_company || r.company), { company: r.requested_company || r.company, country: r.country || "", website: r.website || "", trigger: "form", mode: r.mode || "deep" });
    }
    if (b.dataset.researchPdf) printReport(b.dataset.researchPdf);
    if (b.dataset.unpin !== undefined) {
      state.pinned = null;
      render();
    }
    if (b.dataset.researchAsk) {
      state.pinned = state.pinned === b.dataset.researchAsk ? null : b.dataset.researchAsk;
      render();
      if (state.pinned) drawer.querySelector("textarea").focus();
    }
    const actions = {
      researchReport: "report",
      researchFavorite: "favorite",
      researchShortlist: "shortlist",
      researchCompare: "compare",
      researchSave: "save",
    };
    for (const [key, kind] of Object.entries(actions)) {
      if (!b.dataset[key]) continue;
      const run = state.runs[b.dataset[key]];
      if (kind === "report") {
        onReport(run || { id: b.dataset[key] }, true);
        continue;
      }
      const token = generation;
      const runId = b.dataset[key];
      if (state.pending[runId]) continue; // one card action at a time
      state.pending[runId] = kind;
      delete state.notes[runId];
      render();
      try {
        const saved = await api("/api/suppliers", { run_id: runId });
        if (token !== generation) return;
        const record = saved.supplier || saved;
        onAdded(record, true);
        const note = await onAction(kind, run, record);
        if (token !== generation) return;
        if (note) state.notes[runId] = note;
      } catch (error) {
        if (token !== generation) return;
        state.notes[runId] = { text: "Could not save: " + error.message, error: true };
      } finally {
        if (token === generation) {
          delete state.pending[runId];
          render();
        }
      }
    }
  });
  document.addEventListener("keydown", (e) => {
    if (!state.open) return;
    if (e.key === "Escape" && !document.querySelector("dialog[open]")) {
      e.preventDefault();
      if (!panel.close()) close();
    }
    if (e.key === "Tab" && !panel.element.contains(document.activeElement)) {
      const nodes = [
        ...drawer.querySelectorAll(
          "button:not([disabled]),input:not([disabled]),textarea:not([disabled]),select:not([disabled]),a[href],summary",
        ),
      ].filter((node) => node.getClientRects().length > 0 && !node.hidden);
      const first = nodes[0],
        last = nodes.at(-1);
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    if (e.key === "Enter" && !e.shiftKey && e.target.id === "assistant-input") {
      e.preventDefault();
      send(e.target.value);
    }
  });
  api("/api/config")
    .then((config) => {
      state.config = config;
      render();
    })
    .catch(() => {});
  function reset() {
    generation++;
    Object.values(timers).forEach(clearTimeout);
    panel.close();
    state.run = null;
    state.runs = {};
    state.pinned = null;
    state.pending = {};
    state.notes = {};
    state.messages = [];
    state.busy = false;
    state.clarify = false;
    render();
    onSave();
  }
  return { state, open, close, send, render, poll, reset, runExample, printReport };
}
