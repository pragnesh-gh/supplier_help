import { api } from "./api.js";
import { icon } from "./icons.js";
import { renderAnswer, renderSources, renderCharts } from "./chat-results.js";
// The assistant's display name lives here only. Gretel follows the trail of
// breadcrumbs, a fit for tracing supply chains.
export const ASSISTANT_NAME = "Gretel";
export function createChat({
  esc,
  selected,
  onSave,
  onReport,
  onAdded,
  onCell,
  getMessages,
}) {
  const state = {
    messages: getMessages(),
    open: false,
    busy: false,
    mode: "auto",
    run: null,
    clarify: false,
    config: null,
    expanded: false,
    activeRunId: null,
    details: new Map(),
  };
  const drawer = document.querySelector("#chat-drawer"),
    launch = document.querySelector("#chat-launch");
  launch.innerHTML = `${icon("chat")}<span>Ask ${ASSISTANT_NAME}</span>`;
  launch.setAttribute("aria-label", `Open ${ASSISTANT_NAME}, the sourcing assistant`);
  drawer.setAttribute("aria-label", `${ASSISTANT_NAME} · sourcing assistant`);
  let pollTimer,
    generation = 0,
    forceScroll = false;
  function progress(r) {
    if (!r) return "";
    const events = r.events || [];
    const completed = r.status === "completed";
    const terminal = completed || r.status === "failed";
    const covered = new Set((r.findings || []).map((f) => f.category)).size;
    const sourceIds = new Set((r.sources || []).map(source => source.id));
    const findingBrief = (r.findings || []).slice(0, 2).map(finding => {
      const refs = (finding.source_ids || []).filter(id => sourceIds.has(id));
      const text = [finding.detail || finding.title || "", refs.map(id => `[${id}]`).join(" ")].filter(Boolean).join(" ");
      return `<li>${renderAnswer(text, r.sources || [])}</li>`;
    }).join("");
    const completion = completed
      ? `<div class="research-completion"><div class="eyebrow">Research brief</div><h3>What we found</h3><p>${esc(r.summary || "Research dossier ready for review.")}</p>${findingBrief ? `<ul class="research-finding-brief">${findingBrief}</ul>` : ""}<p class="small muted">${(r.sources || []).length} sources &middot; ${(r.findings || []).length} observations &middot; ${covered}/${(r.plan || []).length || 6} categories with observations</p><div class="actions"><button data-chat-prompt="Show evidence coverage chart">Show evidence chart</button><button data-chat-report="${esc(r.id)}">${icon("description", "sm")}Read report</button><button data-chat-add="${esc(r.id)}">Add as unscored supplier</button></div><p class="small muted">Coverage remains partial; completion is not supplier approval.</p></div>`
      : "";
    return `<section class="research-progress"><div class="row spread"><strong>${esc(r.company)} · ${esc(r.status)}</strong><span>${r.mode === "deep" ? "Deep" : "Basic"}</span></div><p>${r.demo ? "Saved historical example · no live retrieval" : "Live public research · server events"}</p>${completion}<details class="research-plan" data-detail-key="plan-${esc(r.id)}"><summary>Research plan &middot; ${(r.plan || []).length} workstreams</summary><ul>${(
      r.plan || []
    )
      .map((p) => {
        const searched = events.some(
          (e) => e.stage === "search" && e.message.startsWith(p.category + ":"),
        );
        const failed = events.some(
          (e) =>
            e.stage === "search_error" &&
            e.message.startsWith(p.category + ":"),
        );
        const savedEvidence =
          r.demo && (r.findings || []).some((f) => f.category === p.category);
        const label = failed
          ? "Search failed"
          : searched
            ? "Retrieved - review remains partial"
            : savedEvidence
              ? "Saved observations"
              : r.status === "completed"
                ? "No live category retrieval"
                : "Pending retrieval";
        return `<li>${failed ? "!" : searched || savedEvidence ? "&#10003;" : "&#9675;"} <strong>${esc(p.category.replaceAll("_", " "))}</strong><span class="small muted"> - ${label}</span><details data-detail-key="questions-${esc(r.id)}-${esc(p.category)}"><summary>Research questions</summary>${(p.questions || []).map((q) => `<p>${esc(q)}</p>`).join("")}</details></li>`;
      })
      .join(
        "",
      )}</ul></details><details data-detail-key="activity-${esc(r.id)}" ${completed ? "" : "open"}><summary><span class="activity-dot ${terminal ? "done" : ""}"></span>${r.status === "failed" ? "Research stopped" : completed ? "Research activity" : "Working - " + esc(events.at(-1)?.stage?.replaceAll("_", " ") || "queued")} <span class="activity-count">${events.length} events</span></summary><div class="research-events">${events.map((e) => `<p><small>${esc(e.at)}</small><br><strong>${esc(e.stage.replaceAll("_", " "))}</strong> · ${esc(e.message)}</p>`).join("") || "<p>Queued on server. Waiting for first event.</p>"}</div></details>${r.status === "failed" ? `<p role="alert">${esc(r.error || "Research failed. No fallback evidence generated.")}</p>` : ""}</section>`;
  }
  function render() {
    if (!state.open) return;
    drawer.querySelectorAll("details[data-detail-key]").forEach(el => state.details.set(el.dataset.detailKey, el.open));
    const identityForm = drawer.querySelector("#identity-form"),
      identityValues = identityForm
        ? Object.fromEntries(new FormData(identityForm))
        : {},
      identityOpen = drawer.querySelector(".identity-form")?.open;
    const activeField = document.activeElement;
    const activeName = identityForm?.contains(activeField) ? activeField.name : null;
    const activePosition = activeName ? activeField.selectionStart : null;
    const oldList = drawer.querySelector(".chat-messages"),
      oldScroll = oldList?.scrollTop || 0,
      stick =
        !oldList ||
        oldList.scrollHeight - oldList.clientHeight - oldScroll < 65;
    const input = drawer.querySelector("textarea"),
      value = input?.value || "",
      focused = document.activeElement === input,
      pos = input?.selectionStart;
    drawer.hidden = false;
    drawer.classList.toggle("chat-expanded", state.expanded);
    launch.setAttribute("aria-expanded", "true");
    launch.hidden = true;
    drawer.innerHTML = `<div class="chat-head"><div><h2>${icon("chat")}${ASSISTANT_NAME}</h2><small>Your sourcing workspace</small></div><div class="chat-head-actions"><button id="chat-expand" class="quiet" aria-label="${state.expanded ? 'Reduce' : 'Expand'} conversation" aria-pressed="${state.expanded}">${state.expanded ? 'Compact' : 'Expand'}</button><button id="chat-close" class="icon-button quiet" aria-label="Close ${ASSISTANT_NAME}">${icon("close")}</button></div></div><div class="chat-messages" aria-live="polite" aria-relevant="additions text">${state.messages.length ? state.messages.map((m, mi) => `<article class="chat-message ${m.role === "user" ? "user" : "assistant"}"><span class="message-label">${m.role === "user" ? "YOU" : ASSISTANT_NAME.toUpperCase()}</span>${m.role === "user" ? `<div class="message-copy">${esc(m.answer || m.content || "")}</div>` : `<div class="message-copy">${renderAnswer(m.answer || m.content || "", m.citations)}</div>${renderCharts(m, "chart-" + mi)}${renderSources(m.citations, "sources-" + mi)}`}${m.run_id && state.run?.id === m.run_id ? progress(state.run) : m.run_id ? `<button data-resume-run="${esc(m.run_id)}">${icon("history", "sm")}Open research activity</button>` : ""}</article>`).join("") : `<div class="chat-empty">${icon("chat", "lg")}<div class="eyebrow" style="margin-top:8px">Grounded in your sourcing context</div><h2 style="margin-top:10px">What would you like to understand?</h2><p style="margin-top:10px">Compare supplied values, inspect risk profiles, or investigate an identified company with public sources.</p><div class="chat-suggestions"><button data-chat-prompt="Compare financial scores for SUPP_00012, SUPP_00450 and SUPP_00731">Compare three suppliers</button><button data-chat-prompt="Why is SUPP_00012 high risk?">Explain a risk profile</button></div></div>`}${state.busy ? '<p role="status" class="chat-thinking"><span class="activity-dot"></span>Working on your question...</p>' : ""}</div><div class="chat-composer"><details ${state.clarify || identityOpen ? "open" : ""} class="identity-form"><summary>${icon("expand_more", "sm")}Company identity & research scope</summary><p class="small muted">For public research, identify a real company. Catalog context remains separate.</p><form id="identity-form"><div class="identity-fields"><input name="company" aria-label="Company legal name" placeholder="Company legal name" required maxlength="200"><input name="country" aria-label="Country hint" placeholder="Country (optional)" maxlength="200"><input name="website" aria-label="Official website hint" placeholder="Official website (optional)" type="url"><input name="scope" aria-label="Procurement scope" placeholder="Component / procurement scope" maxlength="1000"><button class="primary" ${state.busy ? "disabled" : ""}>${icon("search", "sm")}Research this company</button></div></form><button id="saved-example" type="button" class="small">Open saved Siemens example - no live search</button></details><div class="chat-mode" role="group" aria-label="Research depth"><button type="button" data-chat-mode="auto" aria-pressed="${state.mode === "auto"}">Auto</button><button type="button" data-chat-mode="deep" aria-pressed="${state.mode === "deep"}">${icon("search", "sm")}Deep research</button><span>${state.mode === "deep" ? "Data + public sources" : "Routes your question"}</span></div><form id="assistant-form"><textarea id="assistant-input" aria-label="Message ${ASSISTANT_NAME}" placeholder="Ask about suppliers or research a company…" maxlength="4000" required>${esc(value)}</textarea><button class="primary" ${state.busy ? "disabled" : ""} aria-label="Send message" title="Send (Enter)">${icon("arrow_forward")}</button></form><div class="chat-context">${state.config?.live_available === false ? "Live research is unavailable. Configure the server key or open the saved historical example. " : ""}${selected().length ? `${selected().length} selected catalog records included as context.` : "Ask by supplier ID, or identify a real company for research."} Scores describe supplied data. Public evidence does not grant approval.</div></div>`;
    drawer.querySelectorAll("details[data-detail-key]").forEach(el => { if (state.details.has(el.dataset.detailKey)) el.open = state.details.get(el.dataset.detailKey); });
    for (const [name, value] of Object.entries(identityValues)) {
      const field = drawer.querySelector(`[name="${name}"]`);
      if (field) field.value = value;
    }
    if (focused) {
      drawer.querySelector("textarea").focus();
      drawer.querySelector("textarea").setSelectionRange(pos, pos);
    }
    if (activeName) {
      const field = [...drawer.querySelectorAll("#identity-form [name]")].find(el => el.name === activeName);
      field?.focus();
      if (field && activePosition !== null && ["text", "search", "url", "tel", "password"].includes(field.type)) field.setSelectionRange(activePosition, activePosition);
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
    state.open = false;
    drawer.hidden = true;
    launch.hidden = false;
    launch.setAttribute("aria-expanded", "false");
    launch.focus();
  }
  async function poll(id, token = generation) {
    if (token !== generation) return;
    state.activeRunId = id;
    clearTimeout(pollTimer);
    try {
      const run = await api("/api/research/" + encodeURIComponent(id));
      if (token !== generation || state.activeRunId !== id) return;
      state.run = run;
      onReport(run);
      render();
      if (["queued", "researching"].includes(run.status))
        pollTimer = setTimeout(() => poll(id, token), 1800);
      else onSave();
    } catch (error) {
      if (token !== generation || state.activeRunId !== id) return;
      state.messages.push({
        role: "assistant",
        answer: "Research activity unavailable: " + error.message,
      });
      state.busy = false;
      render();
      onSave();
    }
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
    try {
      const response = await api("/api/assistant", {
        message,
        mode: state.mode,
        selected_ids:
          state.run?.status === "completed" &&
          !identity.company &&
          !/SUPP_\d{5}|supplied|csv|dataset|compare/i.test(message)
            ? []
            : selected().filter((id) => id.startsWith("SUPP_")),
        ...identity,
        ...(!identity.company && state.run?.status === "completed"
          ? { run_id: state.run.id }
          : {}),
      });
      if (token !== generation) return;
      state.clarify = response.kind === "clarify";
      state.messages.push({
        role: "assistant",
        answer: response.answer || response.question || "Research started.",
        citations: response.citations || [],
        chart: response.chart,
        charts: response.charts,
        run_id: response.run_id,
      });
      forceScroll = true;
      if (response.run_id) poll(response.run_id);
    } catch (error) {
      if (token !== generation) return;
      state.messages.push({ role: "assistant", answer: error.message });
    } finally {
      if (token !== generation) return;
      state.busy = false;
      render();
      onSave();
    }
  }
  launch.addEventListener("click", open);
  drawer.addEventListener("submit", (e) => {
    if (e.target.id === "identity-form") {
      e.preventDefault();
      const identity = Object.fromEntries(new FormData(e.target));
      send("Research " + identity.company, identity);
    } else if (e.target.id === "assistant-form") {
      e.preventDefault();
      send(drawer.querySelector("textarea").value);
    }
  });
  drawer.addEventListener("change", (e) => {
    if (e.target.id === "chat-mode") state.mode = e.target.value;
  });
  drawer.addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.id === "chat-close") close();
    if (b.id === "chat-expand") { state.expanded = !state.expanded; render(); drawer.querySelector("#chat-expand").focus(); }
    if (b.dataset.chatMode) { state.mode = b.dataset.chatMode; render(); drawer.querySelector(`[data-chat-mode="${state.mode}"]`).focus(); }
    if (b.id === "saved-example") {
      forceScroll = true;
      const token = generation;
      state.messages.push({
        role: "user",
        answer: "Open the explicit saved historical Siemens AG example.",
      });
      try {
        const r = await api("/api/research", {
          company: "Siemens AG",
          demo: true,
          example: true,
          mode: "deep",
        });
        if (token !== generation) return;
        state.messages.push({
          role: "assistant",
          answer: "Saved historical example. No live search performed.",
          run_id: r.run_id || r.id,
        });
        forceScroll = true;
        poll(r.run_id || r.id);
        onSave();
        render();
      } catch (error) {
        if (token !== generation) return;
        state.messages.push({ role: "assistant", answer: error.message });
        render();
      }
    }
    if (b.dataset.chatPrompt) send(b.dataset.chatPrompt);
    if (b.dataset.dossier) {
      const token = generation;
      try {
        const run = state.run?.id === b.dataset.dossier ? state.run : await api("/api/research/" + encodeURIComponent(b.dataset.dossier));
        if (token === generation) onReport(run, true);
      } catch (error) { if (token === generation) { state.messages.push({role:"assistant", answer:error.message}); render(); } }
    }
    if (b.dataset.citation) onCell(b.dataset.citation, b.dataset.column);
    if (b.dataset.chartLabel) {
      const id = b.dataset.chartLabel.match(/SUPP_\d+/)?.[0];
      if (id) onCell(id);
    }
    if (b.dataset.resumeRun) poll(b.dataset.resumeRun);
    if (b.dataset.chatReport) onReport(state.run, true);
    if (b.dataset.chatAdd) {
      const token = generation;
      try {
        const record = await api("/api/suppliers", {
          run_id: b.dataset.chatAdd,
        });
        if (token !== generation) return;
        onAdded(record.supplier || record);
      } catch (error) {
        if (token !== generation) return;
        state.messages.push({ role: "assistant", answer: error.message });
        render();
      }
    }
  });
  document.addEventListener("keydown", (e) => {
    if (!state.open) return;
    if (e.key === "Escape" && !document.querySelector("dialog[open]")) {
      e.preventDefault();
      close();
    }
    if (e.key === "Tab") {
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
    clearTimeout(pollTimer);
    state.run = null;
    state.activeRunId = null;
    state.messages = [];
    state.busy = false;
    state.clarify = false;
    state.details.clear();
    render();
    onSave();
  }
  return { state, open, close, send, render, poll, reset };
}
