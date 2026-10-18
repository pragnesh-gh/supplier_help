import { api, safeURL } from './api.js';

export function suggestShortlist(rows) {
  const ranked = rows.filter(r => typeof r.Total_Risk_Index === 'number' && Number.isFinite(r.Total_Risk_Index))
    .sort((a,b) => a.Total_Risk_Index - b.Total_Risk_Index || a.supplierID.localeCompare(b.supplierID));
  if (ranked.length < 3) return ranked.map(r => r.supplierID);
  return ranked.slice(0,5).filter((r,i) => i < 3 || r.Total_Risk_Index <= ranked[2].Total_Risk_Index + 5).map(r => r.supplierID);
}

// Shortlist cart: an ordered, de-duplicated list of supplier IDs (max 20).
export const CART_LIMIT = 20;
export function cartAdd(cart, id, limit = CART_LIMIT) {
  if (!id) return {cart, status:'invalid'};
  if (cart.includes(id)) return {cart, status:'duplicate'};
  if (cart.length >= limit) return {cart, status:'full'};
  return {cart:[...cart,id], status:'added'};
}
export function cartRemove(cart, id) { return cart.filter(x => x !== id); }

// One-click request from the cart. The backend still requires requester, reviewer,
// project, rationale and per-candidate notes, so they are filled with explicit defaults.
export const QUICK_DEFAULTS = Object.freeze({
  requester:'Demo buyer', reviewer:'Sourcing lead',
  tradeoffs:'Not captured at shortlist stage. Review the frozen evidence before negotiation.',
  negotiation_questions:'To be prepared once approval to negotiate is granted.',
});
export function quickRequest({ids, scope = '', project = '', note = ''}) {
  const unique = [...new Set(ids || [])];
  if (unique.length !== (ids || []).length) throw Error('Approval candidates must be distinct');
  if (unique.length < 3 || unique.length > 5) throw Error('Pick 3 to 5 candidates to request approval');
  const text = String(note || '').trim().slice(0, 1000);
  return {
    requester:QUICK_DEFAULTS.requester, reviewer:QUICK_DEFAULTS.reviewer,
    project:(String(project || '').trim() || 'Shortlist comparison').slice(0, 300),
    scope:String(scope || '').slice(0, 1000),
    rationale:`Shortlist comparison of ${unique.length} candidates.${text ? ' Note: ' + text : ''}`,
    candidates:unique.map(id => ({supplier_id:id, tradeoffs:QUICK_DEFAULTS.tradeoffs, negotiation_questions:QUICK_DEFAULTS.negotiation_questions})),
  };
}

export function createApproval({get, esc, fmt, render, navigate, save, print, scope, comparison}) {
  let draft = null, requests = [], active = null, error = '', notice = '', busy = false, generation = 0;
  const empty = () => ({requester:'',reviewer:'',project:'',rationale:'',scope:scope(),candidates:[],pool:[]});
  const note = id => ({supplier_id:id,tradeoffs:'',negotiation_questions:''});
  function start(ids, suggest = false) {
    if (busy) return;
    const existed=!!draft;
    if (!draft) draft = empty();
    draft.pool = [...new Set([...draft.pool,...ids])].filter(id=>get(id)).slice(0,20);
    notice=existed ? 'Existing shortlist draft resumed; written notes and current candidates are preserved.' : '';
    error='';
    if (!(existed && suggest)) {
      const chosen = suggest ? suggestShortlist(ids.map(get).filter(Boolean)) : ids;
      for (const id of chosen) if (get(id) && !draft.candidates.some(c=>c.supplier_id===id)) {
        if(draft.candidates.length>=5) {error='The shortlist already has five candidates. Remove one before adding '+id+'.';continue;}
        draft.candidates.push(note(id));
      }
    }
    active = null; navigate('approvals'); render();
  }
  function replaceCandidates(ids) {
    if(draft.candidates.some(c=>!ids.includes(c.supplier_id)&&(c.tradeoffs.trim()||c.negotiation_questions.trim())) && !confirm('This changes the shortlist and removes notes for excluded candidates. Continue?')) return false;
    draft.candidates=ids.map(id=>draft.candidates.find(c=>c.supplier_id===id)||note(id)); error='';return true;
  }
  async function refresh() {
    const token=generation;
    try {const data=await api('/api/approvals'); if(token!==generation)return; requests=[...(data.requests||[]),...requests.filter(r=>!(data.requests||[]).some(item=>item.id===r.id))]; error='';}
    catch(e){if(token===generation)error=e.message;}
    if(token===generation && location.hash==='#/approvals')render();
  }
  function candidateDocument(c) {
    const snapshot=c.snapshot||{}, row=snapshot.values||{}, research=snapshot.kind==='research';
    const title=research?snapshot.record?.company:row['Supplier Name'];
    const evidence=research ? `<p>${esc(snapshot.dossier?.summary || 'No retained summary.')}</p><h4>Sources</h4>${(snapshot.dossier?.sources||[]).map(source=>`<p><a href="${esc(safeURL(source.url))}" target="_blank" rel="noopener noreferrer">${esc(source.title||source.url)}</a><br><span class="small">${esc(source.url)}</span></p>`).join('')}` : `<dl class="approval-metrics"><div><dt>Total risk</dt><dd>${fmt(row.Total_Risk_Index)} / 100 &middot; ${esc(row.Total_Risk_Index_Level||'Unknown')}</dd></div><div><dt>Delivery rating</dt><dd>${fmt(row['Supplier Delivery Rating'])}%</dd></div><div><dt>System / part &middot; synthetic</dt><dd>${esc(row.train_region_id||'Unknown')} / ${esc(row.train_part_id||'Unknown')}</dd></div></dl>`;
    const provenance=research?`Saved research dossier ${esc(snapshot.dossier?.id||'Unknown')} &middot; ${esc(snapshot.dossier?.status||'Unknown')}`:`Original source: ${esc(snapshot.source)}<br>SHA-256: <span class="approval-hash">${esc(snapshot.sha256)}</span><br>Demo augmentation: ${esc(snapshot.augmentation?.path||'Unknown')}<br>SHA-256: <span class="approval-hash">${esc(snapshot.augmentation?.sha256||'Unknown')}</span>`;
    return `<section class="approval-candidate"><h2>${esc(title||c.supplier_id)}</h2><p class="small muted">${esc(c.supplier_id)} &middot; ${research?'Research-only; numeric scores unknown':'Supplied dataset record'}</p>${evidence}<h3>Trade-offs and unresolved issues</h3><p>${esc(c.tradeoffs)}</p><h3>Negotiation questions</h3><p>${esc(c.negotiation_questions)}</p><p class="small muted">${esc(snapshot.notice||'')}</p><p class="small">${provenance}</p>${research?'':`<details class="approval-evidence"><summary>Frozen source-cell appendix</summary><table><thead><tr><th>Field</th><th>Value</th></tr></thead><tbody>${Object.entries(row).map(([field,value])=>`<tr><td>${esc(field)}</td><td>${esc(value??'Unknown')}</td></tr>`).join('')}</tbody></table></details>`}</section>`;
  }
  function documentHTML(r) {
    return `<article class="document approval-document"><div class="doc-header">SHORTLIST REVIEW &middot; ${esc(r.id)}</div><h1>Request approval to negotiate</h1><div class="doc-status">AWAITING APPROVAL &middot; NO AWARD AUTHORIZED</div><p>Saved ${esc(r.created_at)} &middot; ${r.candidates.length} candidates</p><h2>Request</h2><p><strong>Project:</strong> ${esc(r.project)}<br><strong>Scope:</strong> ${esc(r.scope || 'Not specified')}<br><strong>Requester:</strong> ${esc(r.requester)}<br><strong>Reviewer:</strong> ${esc(r.reviewer)}</p><h2>Shortlist rationale</h2><p>${esc(r.rationale)}</p>${r.candidates.map(candidateDocument).join('')}<h2>Decision boundary</h2><p>This request seeks permission to negotiate with the shortlist. It does not approve qualification, a purchase order or an award. No approval decision or notification has been sent. The named reviewer is a local workflow field, not an authenticated user.</p></article>`;
  }
  function page() {
    const request=requests.find(r=>r.id===active);
    const saved=`<section class="card padded approval-register"><div class="row spread"><h2>Saved requests</h2><button data-approval="refresh">Refresh</button></div>${requests.length?requests.map(r=>`<button class="approval-saved" data-approval="view" data-id="${esc(r.id)}"><strong>${esc(r.project)}</strong><span>${esc(r.id)} · ${r.candidates.length} candidates · Awaiting approval</span></button>`).join(''):'<p>No submitted requests yet.</p>'}</section>`;
    const top=`<div class="screen-title"><div><div class="eyebrow">Compare → Shortlist → Approval to negotiate</div><h1>Shortlist approval</h1><p class="small muted">Save a request for 3–5 candidates. Negotiation and final award remain separate decisions.</p></div><a class="button" href="#/shortlist">Back to shortlist</a></div>${notice?`<p class="notice">${esc(notice)}</p>`:''}${error?`<p class="notice error" role="alert">${esc(error)}</p>`:''}`;
    if(request)return top+`<div class="approval-layout"><section><div class="actions"><button data-approval="draft">Return to draft</button><button class="primary" data-approval="print">Print / Save as PDF</button></div>${documentHTML(request)}</section>${saved}</div>`;
    if(!draft)return top+`<div class="two"><section class="card padded"><h2>Build a shortlist</h2><p>Add suppliers to the shortlist from Discovery, a supplier page or Compare. In the shortlist, pick 3–5 candidates and send one approval request.</p><a class="button primary" href="#/shortlist">Open shortlist →</a></section>${saved}</div>`;
    const selected=new Set(draft.candidates.map(c=>c.supplier_id));
    return top+`<div class="approval-layout"><section class="card padded"><form id="approval-form"><fieldset class="approval-fieldset" ${busy?'disabled':''}><div class="row spread"><h2>${draft.candidates.length} / 5 candidates</h2><button type="button" data-approval="suggest">Suggest from draft pool</button><button type="button" data-approval="replace-comparison">Replace from current comparison</button></div><p class="small muted">Suggestion: lowest supplied Total_Risk_Index first; take three, then up to two more within 5 points of third place. A transparent demo heuristic; verify component fit, qualification and commercial terms. Unknown scores are not ranked.</p><div class="approval-pool">${draft.pool.map(id=>{const r=get(id);return `<label><input type="checkbox" data-approval-candidate="${esc(id)}" ${selected.has(id)?'checked':''} ${!selected.has(id)&&selected.size>=5?'disabled':''}>${esc(id)} <span>Total risk ${fmt(r.Total_Risk_Index)}</span></label>`}).join('')}</div><a class="small" href="#/discover">Find more candidates in Discovery</a><div class="approval-fields">${[['requester','Requester'],['reviewer','Reviewer'],['project','Project / sourcing package'],['scope','System / part scope']].map(([key,label])=>`<label>${label}<input data-approval-field="${key}" value="${esc(draft[key])}" maxlength="${key === 'scope' ? 1000 : key === 'project' ? 300 : 200}" required></label>`).join('')}</div><label>Why these candidates? What alternatives were considered?<textarea data-approval-field="rationale" maxlength="4000" required>${esc(draft.rationale)}</textarea></label>${draft.candidates.map((c,i)=>{const r=get(c.supplier_id);return `<section class="approval-candidate"><div class="row spread"><h3>${i+1}. ${esc(r?.['Supplier Name']||c.supplier_id)}</h3><button type="button" data-approval="remove" data-id="${esc(c.supplier_id)}">Remove</button></div><p class="small muted">${esc(c.supplier_id)} · Total risk ${fmt(r?.Total_Risk_Index)} · Delivery ${fmt(r?.['Supplier Delivery Rating'])}</p><label>Trade-offs / issues to resolve<textarea data-approval-note="tradeoffs" data-id="${esc(c.supplier_id)}" maxlength="2000" required placeholder="Explain fit, key risks and why this candidate remains in the shortlist.">${esc(c.tradeoffs)}</textarea></label><label>Negotiation questions<textarea data-approval-note="negotiation_questions" data-id="${esc(c.supplier_id)}" maxlength="2000" required placeholder="For example: lead-time commitments, capacity evidence, warranty, mitigation owners and pricing conditions.">${esc(c.negotiation_questions)}</textarea></label></section>`}).join('')}<p class="notice">Saved locally on this server. Submission freezes the candidate evidence. It does not notify the reviewer or grant approval. User accounts and negotiation tracking are not enabled.</p><button class="primary" type="submit" ${busy||selected.size<3||selected.size>5?'disabled':''}>${busy?'Saving request…':'Request approval to negotiate'}</button><span class="small muted"> Draft saves automatically.</span></fieldset></form></section>${saved}</div>`;
  }
  document.addEventListener('input',e=>{
    if(!draft)return;
    const el=e.target;
    if(el.dataset.approvalField){draft[el.dataset.approvalField]=el.value;save();}
    if(el.dataset.approvalNote){const c=draft.candidates.find(c=>c.supplier_id===el.dataset.id);if(c)c[el.dataset.approvalNote]=el.value;save();}
  });
  document.addEventListener('change',e=>{
    const id=e.target.dataset.approvalCandidate;if(!id||!draft)return;
    if(e.target.checked&&draft.candidates.length<5)draft.candidates.push(note(id));else replaceCandidates(draft.candidates.map(c=>c.supplier_id).filter(value=>value!==id));
    render();
  });
  document.addEventListener('click',e=>{
    const b=e.target.closest('[data-approval]');if(!b)return;
    const action=b.dataset.approval;
    if(action==='refresh')refresh();
    if(action==='view'){active=b.dataset.id;render();}
    if(action==='draft'){active=null;render();}
    if(action==='print'){const r=requests.find(r=>r.id===active);if(r)print(documentHTML(r));}
    if(action==='remove'){replaceCandidates(draft.candidates.map(c=>c.supplier_id).filter(id=>id!==b.dataset.id));render();}
    if(action==='replace-comparison'){const pool=comparison().filter(id=>get(id));if(replaceCandidates(suggestShortlist(pool.map(get)))){draft.pool=pool;notice='Replaced using the current comparison. Review the suggested candidates.';}render();}
    if(action==='suggest'){
      const ids=suggestShortlist(draft.pool.map(get).filter(Boolean));
      replaceCandidates(ids);render();
    }
  });
  document.addEventListener('submit',async e=>{
    if(e.target.id!=='approval-form')return;e.preventDefault();if(busy||!draft)return;
    const token=generation;
    busy=true;error='';render();
    try{
      const {pool,...body}=structuredClone(draft);
      const request=await api('/api/approvals',body);
      if(token!==generation)return;
      requests=[request,...requests.filter(r=>r.id!==request.id)];active=request.id;draft=null;
    }catch(e){if(token===generation)error=e.message;}
    finally{if(token===generation){busy=false;render();}}
  });
  async function requestQuick(options) {
    if (busy) throw Error('A request is already being saved');
    const body = quickRequest(options), token = generation;
    busy = true; error = '';
    try {
      const request = await api('/api/approvals', body);
      if (token !== generation) return null;
      requests = [request, ...requests.filter(r => r.id !== request.id)]; active = request.id; notice = '';
      return request;
    } finally { if (token === generation) busy = false; }
  }
  return {start,page,refresh,requestQuick,isBusy:()=>busy,snapshot:()=>draft,restore(value){if(value&&Array.isArray(value.candidates)){draft={...empty(),...value};draft.candidates=draft.candidates.filter(c=>get(c.supplier_id)).slice(0,5);draft.pool=[...new Set([...(draft.pool||[]),...draft.candidates.map(c=>c.supplier_id)])].filter(id=>get(id)).slice(0,20);}},reset(){generation++;draft=null;active=null;busy=false;error='';}};
}
