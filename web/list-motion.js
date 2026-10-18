// Gentle row transitions for the Discovery results table.
// When the visible supplier set changes (part, filter, sort or page), rows that
// were already visible stay put and newly visible rows fade and slide in with a
// short stagger. Re-renders that keep the same rows (ticking compare, favorites)
// do not animate. Reduced-motion users get the instant swap.
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
let previous = null;
// Rows still mid-entrance, by supplier ID, so a quick second render continues them.
const entering = new Map();
const DURATION = 220;

function visibleRows() {
  return [...document.querySelectorAll(".results tbody tr")]
    .map((row) => ({ row, id: row.querySelector("[data-compare]")?.dataset.compare }))
    .filter((entry) => entry.id);
}

function update() {
  const rows = visibleRows();
  if (!rows.length) {
    // Leaving Discovery or an empty result: the next list is a fresh arrival.
    previous = null;
    return;
  }
  const ids = rows.map((entry) => entry.id);
  const before = previous;
  previous = new Set(ids);
  if (!before || reduced.matches) return;
  const now = performance.now();
  for (const [id, start] of entering) if (now - start > DURATION) entering.delete(id);
  const same = ids.length === before.size && ids.every((id) => before.has(id));
  let order = 0;
  for (const { row, id } of rows) {
    let start = entering.get(id);
    if (start === undefined) {
      if (same || before.has(id)) continue;
      start = now + Math.min(order++, 11) * 18;
      entering.set(id, start);
    }
    row.animate(
      [
        { opacity: 0, transform: "translateY(6px)" },
        { opacity: 1, transform: "none" },
      ],
      { duration: DURATION, delay: start - now, easing: "cubic-bezier(.2,.7,.2,1)", fill: "backwards" },
    );
  }
}

const app = document.getElementById("app");
if (app && "animate" in Element.prototype) {
  new MutationObserver(update).observe(app, { childList: true, subtree: true });
}
