const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
})[char]);
const number = (value) => Number.isFinite(value)
  ? value.toLocaleString("en-GB", { maximumFractionDigits: 1 }) : "Unknown";
const bands = [
  { level: "Low", radius: 165, key: "low" },
  { level: "Medium", radius: 132, key: "medium" },
  { level: "High", radius: 99, key: "high" },
  { level: "Critical", radius: 66, key: "critical" },
];

export function riskLevel(row) {
  return Number.isFinite(row?.Total_Risk_Index) && bands.some((band) => band.level === row.Total_Risk_Index_Level)
    ? row.Total_Risk_Index_Level : "Unknown";
}

// Sample across the score distribution within every band. Positions are stable,
// not a ranking or a measure of similarity between neighbouring suppliers.
function representatives(rows) {
  const sorted = [...rows].sort((a, b) =>
    a.Total_Risk_Index - b.Total_Risk_Index || a.supplierID.localeCompare(b.supplierID));
  const count = Math.min(7, sorted.length);
  return Array.from({ length: count }, (_, index) =>
    sorted[count === 1 ? 0 : Math.round(index * (sorted.length - 1) / (count - 1))])
    .sort((a, b) => a.supplierID.localeCompare(b.supplierID));
}

export function renderSupplierRing({ rows = [], regionLabel = "All systems", partLabel = "", favorites = new Set() }) {
  const groups = bands.map((band) => ({ ...band, rows: rows.filter((row) => riskLevel(row) === band.level) }));
  const scored = groups.reduce((sum, band) => sum + band.rows.length, 0);
  const unknown = rows.length - scored;
  const maxVolume = rows.reduce((max, row) => Math.max(max,
    Number.isFinite(row["Purchase Order Volume (EUR)"]) ? row["Purchase Order Volume (EUR)"] : 0), 0);
  let sampled = 0;
  const dots = groups.map((band) => {
    const sample = representatives(band.rows);
    sampled += sample.length;
    return sample.map((row, index) => {
      const angle = (sample.length === 1 ? 90 : 42 + index * 276 / (sample.length - 1)) * Math.PI / 180;
      const left = (200 + Math.sin(angle) * band.radius) / 4;
      const top = (200 - Math.cos(angle) * band.radius) / 4;
      const volume = row["Purchase Order Volume (EUR)"];
      const hasVolume = Number.isFinite(volume) && volume >= 0;
      const size = hasVolume && maxVolume > 0 ? 8 + 13 * Math.sqrt(volume / maxVolume) : 8;
      const favorite = favorites.has ? favorites.has(row.supplierID) : favorites.includes(row.supplierID);
      const description = `${row["Supplier Name"] || row.supplierID} · ${row.supplierID}. ${band.level} risk; Total Risk Index ${number(row.Total_Risk_Index)}/100. PO volume ${hasVolume ? `EUR ${number(volume)}` : "unknown"}.${favorite ? " Favorite." : ""} Inspect supplier.`;
      return `<button type="button" class="supplier-ring-dot sr-${band.key}${favorite ? " is-favorite" : ""}${hasVolume ? "" : " volume-unknown"}" style="left:${left.toFixed(3)}%;top:${top.toFixed(3)}%;--dot-size:${size.toFixed(2)}px" data-ring-supplier="${escapeHTML(row.supplierID)}" aria-label="${escapeHTML(description)}" title="${escapeHTML(description)}"><span aria-hidden="true"></span></button>`;
    }).join("");
  }).join("");
  return `<section class="card supplier-ring" aria-label="Supplier risk distribution">
    <div class="supplier-ring-header"><div><span class="eyebrow">Supplier landscape</span><h2>Risk at a glance</h2></div><span class="supplier-ring-total">${number(rows.length)} suppliers</span></div>
    <div class="supplier-ring-stage">
      <svg viewBox="0 0 400 400" aria-hidden="true">${groups.map((band) => `<circle class="supplier-ring-band sr-${band.key}" cx="200" cy="200" r="${band.radius}" fill="none" stroke-width="32"/><text class="supplier-ring-band-label sr-${band.key}" x="200" y="${204 - band.radius}" text-anchor="middle">${band.level.toUpperCase()} · ${number(band.rows.length)}</text>`).join("")}</svg>
      <div class="supplier-ring-centre"><strong>${escapeHTML(partLabel || regionLabel)}</strong><span>${number(rows.length)} suppliers</span></div>
      ${dots}
    </div>
    <div class="supplier-ring-filters" aria-label="Discover suppliers by risk">${groups.map((band) => `<button type="button" data-ring-risk="${band.level}" class="sr-${band.key}" ${band.rows.length ? "" : "disabled"} aria-label="Discover ${number(band.rows.length)} ${band.level.toLowerCase()} risk suppliers"><i aria-hidden="true"></i>${band.level}<strong>${number(band.rows.length)}</strong></button>`).join("")}${unknown ? `<button type="button" data-ring-risk="Unknown" class="sr-unknown" aria-label="Discover ${number(unknown)} unscored suppliers"><i aria-hidden="true"></i>Unscored<strong>${number(unknown)}</strong></button>` : ""}</div>
    <div class="supplier-ring-key"><span><i class="supplier-ring-size" aria-hidden="true"></i>Size tracks PO volume</span><span><i class="supplier-ring-favorite" aria-hidden="true"></i>Favorite</span></div>
    <p class="supplier-ring-caption">${scored ? `${sampled} of ${number(scored)} scored shown · up to 7 per band.` : "No scored suppliers."} Full counts above. Dots inspect; risk labels filter.</p>
    <p class="supplier-ring-provenance">Critical inside · low outside. Synthetic part assignments; illustrative positions.</p>
  </section>`;
}
