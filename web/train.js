export function mountTrain(root, { regions, counts, selected, onSelect }) {
  const colors = ["#4d8b92", "#79a4a6", "#91b4b2"];
  root.innerHTML = `<div class="train-caption"><span>YOUR SOURCING LANDSCAPE</span><strong>Select a system to explore its suppliers</strong></div><svg viewBox="0 0 1000 245" role="img" aria-label="Illustrative passenger train with selectable systems"><defs><linearGradient id="body" x2="0" y2="1"><stop stop-color="#fcffff"/><stop offset="1" stop-color="#dce8e8"/></linearGradient></defs><ellipse cx="500" cy="215" rx="450" ry="12" fill="#d9e4e4"/><path d="M40 175V93q0-20 26-20h800q34 0 52 25l51 65q8 16-16 16H50q-10 0-10-4Z" fill="url(#body)" stroke="#58757c" stroke-width="2"/><path d="M42 142h910l17 25H42Z" fill="#176b72"/><path d="M871 87h10q14 0 24 15l28 37h-62Z" fill="#264a57"/>${[0, 1, 2].map((i) => `<rect x="${84 + i * 248}" y="93" width="177" height="35" rx="7" fill="#274c59"/>`).join("")}${[111, 198, 410, 497, 710, 797].map((x) => `<circle cx="${x}" cy="188" r="20" fill="#2a4149"/><circle cx="${x}" cy="188" r="10" fill="#99b3b9"/>`).join("")}<path d="M42 179h914" stroke="#6f8e92" stroke-width="7"/>${regions
    .map((r, i) => {
      const x = 50 + i * 100;
      return `<g class="train-hotspot ${selected === r.id ? "active" : ""}" data-system="${r.id}" tabindex="0" role="button" aria-label="${r.label}: ${counts[r.id].total} records" aria-pressed="${selected === r.id}"><rect x="${x}" y="${i % 2 ? 138 : 67}" width="87" height="${i % 2 ? 39 : 68}" rx="6" fill="${colors[i % 3]}"/><text x="${x + 43}" y="${i % 2 ? 162 : 87}" text-anchor="middle">${r.shortLabel || r.label}</text><title>${r.label} · ${counts[r.id].total} records · synthetic association</title></g>`;
    })
    .join(
      "",
    )}</svg><p class="small muted">Illustrative assembly · system assignments are synthetic, not verified capabilities</p>`;
  const activate = (e) => {
    const node = e.target.closest("[data-system]");
    if (node) onSelect(node.dataset.system);
  };
  root.addEventListener("click", activate);
  root.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      activate(e);
    }
  });
  return {
    destroy() {},
    resetView() {},
    highlight(id) {
      root
        .querySelectorAll("[data-system]")
        .forEach((n) =>
          n.classList.toggle("highlight", n.dataset.system === id),
        );
    },
  };
}
