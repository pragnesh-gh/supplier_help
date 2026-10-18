import { api, safeURL } from "./api.js";
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
  };
  const drawer = document.querySelector("#chat-drawer"),
    launch = document.querySelector("#chat-launch");
  let pollTimer,
    generation = 0;
  function citation(c, index) {
    const label =
      c.kind === "dataset"
        ? `${c.supplier_id || "CSV"} · ${c.column || c.title || "source cells"}`
        : c.title || "Public source";
    return c.url
      ? `<a class="citation-chip" href="${esc(safeURL(c.url))}" target="_blank" rel="noopener noreferrer"><b>${index + 1}</b>${esc(label)}</a>`
      : `<button class="citation-chip" data-citation="${esc(c.supplier_id || "")}" data-column="${esc(c.column || "")}" title="${esc(c.value ?? c.title ?? "Source cell")}"><b>${index + 1}</b>${esc(label)}</button>`;
  }
  function chart(c) {
    if (!c?.points?.length) return "";
    const points = c.points.filter((p) => Number.isFinite(p.value));
    const max = Math.max(1, ...points.map((p) => Math.abs(p.value)));
    return `<div class="chat-chart"><strong>${esc(c.label || c.metric)}</strong><p class="small muted">${esc(c.metric || "")} · supplied snapshot</p>${points.map((p) => `<div class="chart-point"><button data-chart-label="${esc(p.label)}" title="Inspect ${esc(p.label)}">${esc(p.label)}</button><div class="chart-bar"><i style="width:${(Math.max(0, p.value) / max) * 100}%"></i></div><strong>${esc(p.value)}</strong></div>`).join("")}<details><summary>View exact values</summary><table><thead><tr><th>Supplier</th><th>${esc(c.metric || "Value")}</th></tr></thead><tbody>${points.map((p) => `<tr><td>${esc(p.label)}</td><td>${esc(p.value)}</td></tr>`).join("")}</tbody></table></details></div>`;
  }
  function progress(r) {
    if (!r) return "";
    const events = r.events || [];
    return `<section class="research-progress"><div class="row spread"><strong>${esc(r.company)} · ${esc(r.status)}</strong><span>${r.mode === "deep" ? "Deep" : "Basic"}</span></div><p>${r.demo ? "Saved historical example · no live retrieval" : "Live public research · server events"}</p><ul>${(
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
            ? "Retrieved ? review remains partial"
            : savedEvidence
              ? "Saved observations"
              : r.status === "completed"
                ? "No live category retrieval"
                : "Pending retrieval";
        return `<li>${failed ? "!" : searched || savedEvidence ? "&#10003;" : "&#9675;"} <strong>${esc(p.category.replaceAll("_", " "))}</strong><span class="small muted"> - ${label}</span><details><summary>Research questions</summary>${(p.questions || []).map((q) => `<p>${esc(q)}</p>`).join("")}</details></li>`;
      })
      .join(
        "",
      )}</ul><details open><summary>Actual research activity (${events.length})</summary><div class="research-events">${events.map((e) => `<p><small>${esc(e.at)}</small><br><strong>${esc(e.stage.replaceAll("_", " "))}</strong> · ${esc(e.message)}</p>`).join("") || "<p>Queued on server. Waiting for first event.</p>"}</div></details>${r.status === "failed" ? `<p role="alert">${esc(r.error || "Research failed. No fallback evidence generated.")}</p>` : ""}${r.status === "completed" ? `<p>${esc(r.summary)}</p><div class="actions"><button data-chat-report="${esc(r.id)}">Read report</button><button data-chat-add="${esc(r.id)}">Add as unscored supplier</button></div>` : ""}</section>`;
  }
  function render() {
    if (!state.open) return;
    const identityForm = drawer.querySelector("#identity-form"),
      identityValues = identityForm
        ? Object.fromEntries(new FormData(identityForm))
        : {},
      identityOpen = drawer.querySelector(".identity-form")?.open;
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
    launch.setAttribute("aria-expanded", "true");
    launch.hidden = true;
    drawer.innerHTML = `<div class="chat-head"><div><h2>✦ Sourcing assistant</h2><small>One conversation, from data to diligence</small></div><button id="chat-close" aria-label="Close sourcing assistant">✕</button></div><div class="chat-messages" aria-live="polite" aria-relevant="additions text">${state.messages.length ? state.messages.map((m) => `<article class="chat-message ${m.role === "user" ? "user" : "assistant"}"><span class="message-label">${m.role === "user" ? "YOU" : "SOURCING ASSISTANT"}</span>${esc(m.answer || m.content || "")}<div class="source-chip-list">${(m.citations || []).map(citation).join("")}</div>${chart(m.chart)}${m.run_id && state.run?.id === m.run_id ? progress(state.run) : m.run_id ? `<button data-resume-run="${esc(m.run_id)}">Open research activity</button>` : ""}</article>`).join("") : `<div><div class="eyebrow">Grounded in your sourcing context</div><h2 style="margin-top:10px">What would you like to understand?</h2><p style="margin-top:10px">Compare supplied values, inspect risk profiles, or investigate an identified company with public sources.</p><div class="chat-suggestions"><button data-chat-prompt="Compare financial scores for SUPP_00012, SUPP_00450 and SUPP_00731">Compare three suppliers</button><button data-chat-prompt="Why is SUPP_00012 high risk?">Explain a risk profile</button></div></div>`}${state.busy ? '<p role="status" class="muted">Reviewing your question…</p>' : ""}</div><div class="chat-composer"><details ${state.clarify || identityOpen ? "open" : ""} class="identity-form"><summary>Company identity & research scope</summary><p class="small muted">For public research, identify a real company. Catalog context remains separate.</p><form id="identity-form"><div class="identity-fields"><input name="company" aria-label="Company legal name" placeholder="Company legal name" required maxlength="200"><input name="country" aria-label="Country hint" placeholder="Country (optional)" maxlength="200"><input name="website" aria-label="Official website hint" placeholder="Official website (optional)" type="url"><input name="scope" aria-label="Procurement scope" placeholder="Component / procurement scope" maxlength="1000"><button class="primary" ${state.busy ? "disabled" : ""}>Research this company</button></div></form><button id="saved-example" type="button" class="small">Open saved Siemens example - no live search</button></details><div class="chat-mode"><label for="chat-mode">Research depth</label><select id="chat-mode"><option value="auto" ${state.mode === "auto" ? "selected" : ""}>Auto · data or research</option><option value="deep" ${state.mode === "deep" ? "selected" : ""}>Deep · additional research</option></select></div><form id="assistant-form"><textarea id="assistant-input" aria-label="Message sourcing assistant" placeholder="Ask about suppliers or research a company…" maxlength="4000" required>${esc(value)}</textarea><button class="primary" ${state.busy ? "disabled" : ""} aria-label="Send message">↑</button></form><div class="chat-context">${state.config?.live_available === false ? "Live research is unavailable. Configure the server key or open the saved historical example. " : ""}${selected().length ? `${selected().length} selected catalog records included as context.` : "Ask by supplier ID, or identify a real company for research."} Scores describe supplied data. Public evidence does not grant approval.</div></div>`;
    for (const [name, value] of Object.entries(identityValues)) {
      const field = drawer.querySelector(`[name="${name}"]`);
      if (field) field.value = value;
    }
    if (focused) {
      drawer.querySelector("textarea").focus();
      drawer.querySelector("textarea").setSelectionRange(pos, pos);
    }
    const list = drawer.querySelector(".chat-messages");
    list.scrollTop = stick ? list.scrollHeight : oldScroll;
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
    clearTimeout(pollTimer);
    try {
      const run = await api("/api/research/" + encodeURIComponent(id));
      if (token !== generation) return;
      state.run = run;
      onReport(run);
      render();
      if (["queued", "researching"].includes(run.status))
        pollTimer = setTimeout(() => poll(id, token), 1800);
      else onSave();
    } catch (error) {
      if (token !== generation) return;
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
        run_id: response.run_id,
      });
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
    if (b.id === "saved-example") {
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
    if (b.dataset.citation) onCell(b.dataset.citation, b.dataset.column);
    if (b.dataset.chartLabel) {
      const id = b.dataset.chartLabel.match(/SUPP_\d+/)?.[0];
      if (id) onCell(id);
    }
    if (b.dataset.resumeRun) poll(b.dataset.resumeRun);
    if (b.dataset.chatReport) onReport(state.run, true);
    if (b.dataset.chatAdd) {
      try {
        const record = await api("/api/suppliers", {
          run_id: b.dataset.chatAdd,
        });
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
    state.messages = [];
    state.busy = false;
    state.clarify = false;
    render();
    onSave();
  }
  return { state, open, close, send, render, poll, reset };
}
