import { safeURL } from './api.js';

export const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const list = value => Array.isArray(value) ? value : [];
const valueText = value => Number.isFinite(value) ? String(value) : 'Unknown';
export function renderCitation(c, label, inline = false) {
  const cls = inline ? 'inline-citation' : 'citation-chip';
  const title = [c.title || c.column || 'Source', c.supplier_id, c.value].filter(v => v != null).join(' · ');
  const text = escapeHTML(label);
  if (c.url && safeURL(c.url) !== '#') return `<a class="${cls}" href="${escapeHTML(safeURL(c.url))}" target="_blank" rel="noopener noreferrer" title="${escapeHTML(title)}" aria-label="Source ${text}: ${escapeHTML(title)}">${text}</a>`;
  if (c.kind === 'dataset' && c.supplier_id) return `<button class="${cls}" data-citation="${escapeHTML(c.supplier_id)}" data-column="${escapeHTML(c.column || '')}" title="${escapeHTML(title)}" aria-label="Source ${text}: ${escapeHTML(title)}">${text}</button>`;
  if (c.kind === "dossier" && c.run_id) return `<button class="${cls}" data-dossier="${escapeHTML(c.run_id)}" title="${escapeHTML(title)}" aria-label="Source ${text}: ${escapeHTML(title)}">${text}</button>`;
  return `<span class="${cls}" title="${escapeHTML(title)}">${text}</span>`;
}
export function renderAnswer(answer, citations = []) {
  const sources = new Map(list(citations).filter(c => c && typeof c === 'object').map(c => [String(c.id), c]));
  return String(answer || '').split(/(\[(?:D|S|E)\d+(?:,\s*(?:D|S|E)\d+)*\])/g).map(part => {
    if (!/^\[(?:D|S|E)\d+(?:,\s*(?:D|S|E)\d+)*\]$/.test(part)) return escapeHTML(part);
    const ids = part.slice(1,-1).split(',').map(id => id.trim());
    if (!ids.some(id => sources.has(id))) return escapeHTML(part);
    return ids.map(id => sources.has(id) ? renderCitation(sources.get(id), id, true) : escapeHTML(`[${id}]`)).join('');
  }).join('');
}
export function renderSources(citations, key) {
  const sources = list(citations).filter(c => c && typeof c === 'object');
  return sources.length ? `<details class="chat-sources" data-detail-key="${escapeHTML(key)}"><summary>${sources.length} source${sources.length === 1 ? '' : 's'} · inspect evidence</summary><div class="source-chip-list">${sources.map((c,i) => renderCitation(c, `${c.id || i+1} · ${c.title || c.column || c.supplier_id || 'Public source'}`)).join('')}</div></details>` : '';
}
export function renderChart(chart, key) {
  if (!chart || typeof chart !== 'object' || !['bar','radar',undefined].includes(chart.type)) return '';
  const e = escapeHTML;
  let graphic = '', rows = '', head = '';
  if (chart.type === 'radar') {
    const axes = list(chart.axes).slice(0,6);
    const allSeries = list(chart.series).filter(s => s && Array.isArray(s.values));
    const series = allSeries.slice(0,5);
    if (axes.length !== 6 || !series.length || axes.some(a => !a || typeof a.label !== 'string')) return '';
    const xy = (i,v) => { const a = i*Math.PI/3-Math.PI/2; return [200+Math.cos(a)*v,155+Math.sin(a)*v]; };
    const point = (i,v) => xy(i,v).map(n => n.toFixed(2)).join(',');
    graphic = `<svg class="chat-radar" viewBox="0 0 400 320" role="img" aria-label="${e(chart.label || 'Six-axis risk chart')}"><title>Risk scores from 0 to 100. Unknown values are omitted.</title>${[25,50,75,100].map(v => `<polygon class="radar-grid" points="${axes.map((_,i)=>point(i,v)).join(' ')}"/>`).join('')}${axes.map((a,i)=> {const [x,y]=xy(i,129); return `<line class="radar-grid" x1="200" y1="155" x2="${xy(i,100)[0]}" y2="${xy(i,100)[1]}"/><text x="${x}" y="${y}" text-anchor="middle">${e(a.label)}</text>`;}).join('')}${series.map((s,j)=> {
      const values = axes.map((_,i)=>Number.isFinite(s.values[i]) && s.values[i]>=0 && s.values[i]<=100 ? s.values[i] : null);
      const polygon = values.every(v=>v!==null) ? `<polygon class="radar-shape series-${j}" points="${values.map((v,i)=>point(i,v)).join(' ')}"/>` : '';
      return polygon + values.map((v,i)=> v===null ? '' : `<circle class="radar-dot series-${j}" cx="${xy(i,v)[0]}" cy="${xy(i,v)[1]}" r="4" tabindex="0" role="img" aria-label="${e(s.label)}: ${e(axes[i].label)} ${v}"><title>${e(s.label)} · ${e(axes[i].label)}: ${v}</title></circle><text class="radar-focus-value" x="200" y="310" text-anchor="middle">${e(s.label)}: ${e(axes[i].label)} ${v}</text>`).join('');
    }).join('')}</svg><div class="chart-legend">${series.map((s,j)=>`<span class="series-${j}"><i></i>${e(s.label)}</span>`).join('')}</div><p class="chart-note">0–100 · higher means greater risk. Unknown and out-of-range scores are omitted from the chart; incomplete profiles have no filled shape.</p>`;
    if (allSeries.length > series.length) graphic += `<p class="chart-note">Showing ${series.length} of ${allSeries.length} suppliers in the chart for readability. All ${allSeries.length} are included in the exact values below.</p>`;
    head = `<th>Risk axis</th>${allSeries.map(s=>`<th>${e(s.label)}</th>`).join('')}`;
    rows = axes.map((a,i)=>`<tr><th>${e(a.label)}</th>${allSeries.map(s=>`<td>${e(valueText(s.values[i]))}${Number.isFinite(s.values[i]) && (s.values[i]<0 || s.values[i]>100) ? " (outside 0-100)" : ""}</td>`).join('')}</tr>`).join('');
  } else {
    const points = list(chart.points).filter(p=>p && typeof p.label === 'string').slice(0,20);
    if (!points.length) return '';
    const max = Math.max(1,...points.map(p=>Number.isFinite(p.value) ? Math.abs(p.value) : 0));
    graphic = `<div class="chat-bars">${points.map(p=>`<div class="chat-bar-row" tabindex="0" aria-label="${e(p.label)}: ${e(valueText(p.value))}">${/SUPP_\d{5}/.test(p.label) ? `<button data-chart-label="${e(p.label)}" title="Inspect ${e(p.label)}">${e(p.label)}</button>` : `<span>${e(p.label)}</span>`}<div class="chat-bar-track">${Number.isFinite(p.value) && p.value>=0 ? `<i style="width:${p.value/max*100}%"></i>` : ''}</div><strong>${e(valueText(p.value))}</strong></div>`).join('')}</div>`;
    head = `<th>Record</th><th>${e(chart.metric || 'Value')}</th>`;
    rows = points.map(p=>`<tr><th>${e(p.label)}</th><td>${e(valueText(p.value))}</td></tr>`).join('');
  }
  return `<section class="chat-result-card"><div class="chat-result-title"><span class="eyebrow">${chart.type === 'radar' ? 'Risk profile' : 'Data view'}</span><h3>${e(chart.label || chart.title || chart.metric || 'Results')}</h3></div>${graphic}<p class="chart-note">${e(chart.provenance || 'Supplied snapshot')}</p><details data-detail-key="${e(key)}" class="chat-exact-values"><summary>View exact values</summary><div class="chat-table-scroll"><table><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div></details></section>`;
}
export function renderCharts(message, key) {
  const charts = Array.isArray(message.charts) ? message.charts : message.chart ? [message.chart] : [];
  return charts.slice(0,5).map((c,i)=>renderChart(c, `${key}-${i}`)).join('');
}
