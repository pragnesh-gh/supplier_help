'use strict';

const $ = selector => document.querySelector(selector);
const labels = {financial:'Financial',legal:'Legal',country:'Country',people_safety:'People & safety',operations:'Operations',reputation:'Reputation'};
const state = {config:null,run:null,runs:[],suppliers:[],poll:null,starting:false,chatBusy:false,saveBusy:false,tab:'research',pollFailures:0};
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const list = value => Array.isArray(value) ? value : [];
const asText = value => typeof value === 'string' ? value : value == null ? '' : JSON.stringify(value);
const pretty = value => String(value ?? 'unknown').replace(/_/g,' ').replace(/^./,c=>c.toUpperCase());
const safeURL = value => {try {const u = new URL(value);return ['https:','http:'].includes(u.protocol) ? u.href : null;} catch {return null;}};
const stamp = value => {if (!value) return 'Not provided';const d = new Date(value);return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'});};
const timeStamp = value => {if (!value) return '';const d=new Date(value);return Number.isNaN(d.getTime())?String(value):d.toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit',second:'2-digit'});};
const badge = (value, suffix='') => {const css=String(value || 'unknown').toLowerCase();return `<span class="badge ${['low','moderate','high','critical','unknown','queued','researching','completed','failed','review_required'].includes(css)?css:'neutral'}">${esc(pretty(value))}${esc(suffix)}</span>`;};
const isRunning = run => run && ['queued','researching'].includes(run.status);
function persistRun(id){try {localStorage.setItem('supplier-research-run',id);}catch{}}
function storedRun(){try{return localStorage.getItem('supplier-research-run');}catch{return null;}}

async function api(path,options={}){
  const response=await fetch(path,{...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});
  const raw=await response.text();let data;try{data=raw?JSON.parse(raw):{};}catch{throw new Error(`The server returned an unreadable response (${response.status}).`);}
  if(!response.ok)throw new Error(asText(data.error?.message || data.error || data.detail || `Request failed (${response.status}).`));
  return data;
}
function error(message){$('#global-error').textContent=message;$('#global-error').classList.toggle('hidden',!message);}
function toast(message){$('#toast').textContent=message;$('#toast').classList.remove('hidden');clearTimeout(state.toastTimer);state.toastTimer=setTimeout(()=>$('#toast').classList.add('hidden'),4500);}
function setTab(tab){state.tab=tab;document.querySelectorAll('[data-tab]').forEach(button=>{button.classList.toggle('active',button.dataset.tab===tab);if(button.dataset.tab===tab)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');});document.querySelectorAll('.tab-panel').forEach(panel=>panel.classList.toggle('hidden',panel.id!==`tab-${tab}`));if(tab==='suppliers')refreshSuppliers();}
function refreshControls(){
  const busy=state.starting||isRunning(state.run);
  $('#start-button').disabled=busy||!state.config?.live_available;
  $('#start-button').innerHTML=busy?'Research in progress…':'Start research <span aria-hidden="true">↗</span>';
  $('#demo-button').disabled=busy;
  document.querySelectorAll('#research-form input,#research-form textarea').forEach(el=>el.disabled=busy);
  const chatReady=state.run?.status==='completed'&&!state.chatBusy;
  $('#chat-input').disabled=!chatReady;$('#chat-send').disabled=!chatReady;
  document.querySelectorAll('[data-question]').forEach(b=>b.disabled=!chatReady);
  $('#chat-status').textContent=state.chatBusy?'Checking this investigation’s evidence…':isRunning(state.run)?'Questions become available when research completes.':state.run?.status==='failed'?'Research failed. Review the evidence and retry.':'Grounded in this investigation’s evidence.';
  $('#save-supplier').disabled=state.run?.status!=='completed'||state.saveBusy;
  $('#print-report').disabled=!state.run||isRunning(state.run);
}
async function init(){
  document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>setTab(button.dataset.tab)));
  $('#research-form').addEventListener('submit',event=>{event.preventDefault();startResearch(false);});
  $('#demo-button').addEventListener('click',()=>startResearch(true));
  $('#chat-form').addEventListener('submit',event=>{event.preventDefault();sendChat();});
  $('#chat-input').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendChat();}});
  document.querySelectorAll('[data-question]').forEach(button=>button.addEventListener('click',()=>{$('#chat-input').value=button.dataset.question;sendChat();}));
  $('#save-supplier').addEventListener('click',saveSupplier);$('#print-report').addEventListener('click',()=>window.print());$('#refresh-suppliers').addEventListener('click',refreshSuppliers);
  $('#history').addEventListener('click',event=>{const button=event.target.closest('[data-run]');if(button)loadRun(button.dataset.run,true);});
  $('#suppliers-list').addEventListener('click',event=>{const button=event.target.closest('[data-open-run]');if(button)loadRun(button.dataset.openRun,true);});
  $('#suppliers-list').addEventListener('change',updateAction);
  refreshControls();
  const results=await Promise.allSettled([api('/api/config'),refreshHistory(),refreshSuppliers()]);
  if(results[0].status==='fulfilled'){
    state.config=results[0].value;
    if(state.config.budgets){const b=state.config.budgets;$('#budget-note').textContent=`Basic: ${b.basic_searches ?? 6} category searches. Deep: up to ${b.deep_searches_max ?? 9} searches with adaptive follow-up. ${b.results_per_search ?? 5} results per search. ${state.config.search_engine||'Web search'}.`;}
    $('#connection-status').textContent=state.config.live_available ? `Live research connected${state.config.model?` · ${state.config.model}`:''}. Sources and gaps remain visible.` : 'Live research is not configured. Use the dated Siemens example to explore, or configure the server’s API key.';
  }else{$('#connection-status').textContent='Cannot connect to the research server.';error(results[0].reason.message);}
  refreshControls();const id=storedRun();if(id)await loadRun(id,false);
}
async function refreshHistory(){
  try{const data=await api('/api/research');state.runs=list(data.runs);$('#history').innerHTML=state.runs.length?state.runs.slice(0,6).map(run=>`<button class="history-item" data-run="${esc(run.id)}"><strong>${esc(run.company || run.entity?.name || 'Investigation')}</strong><span>${esc(stamp(run.created_at))} · ${esc(pretty(run.status))}${run.demo?' · historical example':''}</span></button>`).join(''):'<p class="muted small">No investigations yet.</p>';}catch(e){$('#history').innerHTML=`<p class="muted small">History unavailable: ${esc(e.message)}</p>`;}
}
async function startResearch(demo){
  if(state.starting||isRunning(state.run))return;
  if(!demo&&!$('#research-form').reportValidity())return;
  const form=new FormData($('#research-form'));
  const body={company:demo?'Siemens AG':String(form.get('company')||'').trim(),country:demo?'Germany':String(form.get('country')||'').trim(),website:demo?'https://www.siemens.com':String(form.get('website')||'').trim(),scope:String(form.get('scope')||'').trim(),mode:String(form.get('mode')||'basic'),demo};
  if(!demo&&!body.company){$('#company').focus();return;}
  state.starting=true;error('');refreshControls();
  try{const result=await api('/api/research',{method:'POST',body:JSON.stringify(body)});if(!result.id)throw new Error('The server did not return an investigation ID.');
    if(demo){$('#company').value='Siemens AG';$('#country').value='Germany';$('#website').value='https://www.siemens.com';}
    await loadRun(result.id,true);refreshHistory();
  }catch(e){error(e.message);}finally{state.starting=false;refreshControls();}
}
async function loadRun(id,changeTab){
  clearTimeout(state.poll);error('');
  try{const run=await api(`/api/research/${encodeURIComponent(id)}`);const changed=state.run?.id!==run.id;state.run=run;state.pollFailures=0;persistRun(run.id);if(changed)resetChat();renderRun();if(changeTab)setTab('research');schedulePoll();}
  catch(e){error(`Could not open this investigation: ${e.message}`);refreshControls();}
}
function schedulePoll(){clearTimeout(state.poll);if(isRunning(state.run)){const id=state.run.id;state.poll=setTimeout(()=>pollRun(id),1800);}}
async function pollRun(id){
  if(state.run?.id!==id)return;
  try{const run=await api(`/api/research/${encodeURIComponent(id)}`);if(state.run?.id!==id)return;const wasRunning=isRunning(state.run);state.run=run;state.pollFailures=0;error('');renderRun();if(wasRunning&&!isRunning(run)){refreshHistory();toast(run.status==='completed'?'Investigation ready. Explore the findings and report.':'Investigation ended with an error. Available evidence is preserved.');}schedulePoll();}
  catch(e){state.pollFailures++;error(`Status update failed: ${e.message} ${state.pollFailures<5?'Retrying automatically.':'Use a recent investigation to reconnect.'}`);if(state.pollFailures<5)state.poll=setTimeout(()=>pollRun(id),Math.min(15000,state.pollFailures*3000));}
}
function categoriesFor(run){return Object.entries(labels).map(([id,label])=>{const value=list(run.categories).find(c=>c.id===id)||{};return {id,label,assessment:'unknown',confidence:'low',summary:'Evidence has not yet established an assessment.',gaps:[],...value};});}
function categoryHTML(c){return `<div class="category-card"><div class="category-top"><h4>${esc(c.label||labels[c.id]||pretty(c.id))}</h4>${badge(c.assessment)}</div><p>${esc(c.summary)}</p><span class="confidence">${esc(pretty(c.confidence))} confidence${list(c.gaps).length?` · ${list(c.gaps).length} open gap${list(c.gaps).length===1?'':'s'}`:''}</span></div>`;}
function sourceRefs(ids,prefix=''){return list(ids).map(id=>`<a class="source-ref" href="#${prefix}source-${esc(String(id).replace(/[^a-zA-Z0-9_-]/g,'_'))}">${esc(id)}</a>`).join(' ');}
function findingHTML(f,prefix=''){return `<div class="finding"><div class="finding-head"><h4>${esc(f.title)}</h4>${badge(f.severity)}</div><p>${esc(f.detail)}</p><div class="finding-meta"><span class="badge neutral">${esc(labels[f.category]||pretty(f.category))}</span><span class="badge neutral">${esc(pretty(f.status))}</span><span class="badge neutral">${esc(pretty(f.confidence))} confidence</span>${sourceRefs(f.source_ids,prefix)}</div>${list(f.evidence).length?`<details class="finding-evidence"><summary>Inspect supporting evidence</summary>${list(f.evidence).map(e=>`<blockquote>${esc(e.quote)}<footer>${sourceRefs([e.source_id],prefix)} · ${state.run?.demo?'Saved fixture paraphrase':'Retained source excerpt'}</footer></blockquote>`).join('')}</details>`:''}${f.follow_up?`<p class="follow-up"><strong>Follow up:</strong> ${esc(asText(f.follow_up))}</p>`:''}</div>`;}
function sourceHTML(source,print=false){const url=safeURL(source.url),id=String(source.id).replace(/[^a-zA-Z0-9_-]/g,'_'),excerpt=source.excerpt||'No excerpt was retained.';return `<div class="source-card" id="${print?'report-':''}source-${esc(id)}"><div><span class="source-label">${esc(source.id)}</span>${url?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(source.title||source.url)} ↗</a>`:`<strong>${esc(source.title||'Untitled source')}</strong>`}</div><p>${esc(excerpt.length>650?excerpt.slice(0,650)+'…':excerpt)}</p>${excerpt.length>650?`<details class="source-full"><summary>Read full retained excerpt</summary><p>${esc(excerpt)}</p></details>`:''}<div class="source-meta">${esc(source.publisher||'Publisher not provided')} · Published: ${esc(stamp(source.published_at))} · Accessed: ${esc(stamp(source.accessed_at))}<br>${esc(['provider_search_excerpt','retrieved_excerpt'].includes(source.kind)?'Search excerpt only — full document has not been independently verified.':pretty(source.kind||'public source'))}${source.verification?`<br>${esc(source.verification)}`:''}</div></div>`;}
function renderRun(){
  const run=state.run;if(!run)return;
  $('#empty-state').classList.add('hidden');$('#investigation-workspace').classList.remove('hidden');
  $('#workspace-title').textContent=run.company||run.entity?.name||'Supplier investigation';
  $('#workspace-subtitle').textContent=[run.country?`Country hint: ${run.country}`:'',`${pretty(run.mode)} research`,stamp(run.created_at),run.scope].filter(Boolean).join(' · ');
  $('#run-badge').className=`badge ${['queued','researching','completed','failed'].includes(run.status)?run.status:'neutral'}`;const coverage=categoriesFor(run).filter(c=>list(c.finding_ids).length).length;$('#run-badge').textContent=run.status==='completed'?`Research finished: ${coverage}/6 with findings`:pretty(run.status);
  const demo=run.demo||run.research_type==='historical_demo'||run.data_mode==='demo'||run.entity?.historical_demo;
  const historical=demo||list(run.limitations).some(value=>/historical|fixture/i.test(asText(value)));
  $('#run-notice').innerHTML=`${isRunning(run)?'<div class="loading-line" role="progressbar" aria-label="Research in progress"></div>':''}${historical?'<div class="notice warning"><strong>Historical Siemens example.</strong> This is a dated, saved evidence fixture. It does not describe the company’s current risk and does not perform live research.</div>':''}${run.status==='failed'?`<div class="notice error"><strong>Research could not complete.</strong> ${esc(asText(run.error||'Review the available evidence and try again.'))} Partial findings remain visible.</div>`:''}`;
  $('#run-summary').innerHTML=`<div class="summary-card"><h3>${isRunning(run)?'Following the evidence.':historical?'Saved research picture':'The research picture'}</h3><p>${esc(run.summary||'The investigation is collecting and checking public evidence. Coverage will update as findings become available.')}</p><div class="summary-meta"><span>${list(run.sources).length} sources retained</span><span>·</span><span>${list(run.findings).length} findings</span><span>·</span><span>Numerical scores: unknown</span><span>Partial public-source coverage; ${coverage}/6 categories with findings</span></div><p class="entity-status"><strong>Entity verification:</strong> ${esc(run.entity?.verification||'Unverified')}</p></div>`;
  if(list(run.gaps).length){$('#run-summary').insertAdjacentHTML('beforeend',`<details class="panel gaps-panel"><summary>Evidence gaps & incomplete checks: ${list(run.gaps).length}</summary><ul>${list(run.gaps).map(g=>`<li>${esc(asText(g))}</li>`).join('')}</ul></details>`);}
  $('#category-grid').innerHTML=categoriesFor(run).map(categoryHTML).join('');
  $('#finding-count').textContent=`${list(run.findings).length} recorded`;
  $('#findings').innerHTML=list(run.findings).length?run.findings.map(f=>findingHTML(f)).join(''):`<p class="muted small">${isRunning(run)?'Findings will appear as evidence is reviewed.':'No evidence-backed findings were established. This does not establish low risk.'}</p>`;
  $('#source-count').textContent=`${list(run.sources).length} retained`;
  $('#sources').innerHTML=list(run.sources).length?run.sources.map(s=>sourceHTML(s)).join(''):'<p class="muted small">No sources retained yet.</p>';
  $('#research-plan').innerHTML=list(run.plan).map(part=>`<div class="plan-category"><h4>${esc(labels[part.category]||part.category||part.title||'Research questions')}</h4><ul>${list(part.questions).map(q=>`<li>${esc(asText(q))}</li>`).join('')}</ul></div>`).join('')||'<p class="muted small">The research plan is being prepared.</p>';
  $('#timeline').innerHTML=list(run.events).map(event=>`<li><time>${esc(timeStamp(event.at))} · ${esc(pretty(event.stage))}</time><p>${esc(event.message)}</p></li>`).join('');
  const canReport=!isRunning(run)&&(run.status==='completed'||list(run.findings).length>0);
  $('#report-empty').classList.toggle('hidden',canReport);$('#report-ready').classList.toggle('hidden',!canReport);
  if(canReport){renderReport(run,historical);const root=`/api/research/${encodeURIComponent(run.id)}/export`;$('#export-markdown').href=`${root}?format=markdown`;$('#export-json').href=`${root}?format=json`;$('#report-state').textContent=`${run.status==='failed'?'Partial report':'Research report'} · generated ${stamp(run.completed_at||run.created_at)}`;}
  refreshControls();
}
function renderReport(run,historical){
  const gaps=list(run.gaps).map(asText).concat(categoriesFor(run).flatMap(c=>list(c.gaps).map(g=>`${c.label}: ${asText(g)}`)));
  $('#report-document').innerHTML=`<div class="section-eyebrow">SUPPLIER RISK REPORT · ${run.status==='failed'?'PARTIAL':'RESEARCH EVIDENCE'}</div><h1 class="report-title">${esc(run.company||run.entity?.name)}</h1><div class="report-meta">Country hint: ${esc(run.country||'Not provided')} · ${esc(pretty(run.mode))} investigation · ${esc(stamp(run.created_at))}<br>Entity verification: ${esc(run.entity?.verification||'Unverified')}<br>Research ID: ${esc(run.id)}${run.scope?`<br>Sourcing context: ${esc(run.scope)}`:''}</div>${historical?'<div class="notice warning"><strong>Historical example.</strong> Dated fixture evidence, not a current company assessment.</div>':''}<div class="notice">Research-derived record. No numeric risk score is assigned. The original CSV uses synthetic scores with no validated calibration to public research. This report does not establish supplier qualification.</div><section class="report-section"><h3>Executive assessment</h3><p>${esc(run.summary||'No summary available.')}</p></section><section class="report-section"><h3>Six-category risk coverage</h3><div class="category-grid">${categoriesFor(run).map(categoryHTML).join('')}</div></section><section class="report-section"><h3>Findings and evidence</h3>${list(run.findings).map(f=>findingHTML(f,'report-')).join('')||'<p>No supported findings were established.</p>'}</section><section class="report-section"><h3>Unknowns and evidence gaps</h3><ul>${[...new Set(gaps)].map(g=>`<li>${esc(g)}</li>`).join('')||'<li>No explicit gaps recorded. This does not imply that all risks have been assessed.</li>'}</ul></section><section class="report-section"><h3>Follow-up action list</h3>${actionsTable(run.actions)}</section><section class="report-section"><h3>Sources and dates</h3>${list(run.sources).map(s=>sourceHTML(s,true)).join('')||'<p>No sources retained.</p>'}</section><section class="report-section"><h3>Method and limitations</h3><p>Public-source research across financial, legal, country, people and safety, operations, and reputation risk. Assessments describe the retained evidence; confidence reflects its support, not mathematical probability. Allegations and company disclosures require separate verification.</p><ul>${list(run.limitations).map(limit=>`<li>${esc(asText(limit))}</li>`).join('')}</ul><p>Decision status: research only. Qualification, mitigation ownership, review, and final approval remain pending.</p></section>`;
}
function actionsTable(actions){if(!list(actions).length)return '<p>No actions recorded. Determine the qualification checks needed for the specific component and manufacturing site.</p>';return `<table class="report-actions"><thead><tr><th>Action</th><th>Category / priority</th><th>Owner / status</th></tr></thead><tbody>${list(actions).map(a=>`<tr><td>${esc(a.action||a.title)}</td><td>${esc(labels[a.category]||pretty(a.category))}<br>${esc(pretty(a.priority))}</td><td>${esc(a.owner||'Unassigned')}<br>${esc(pretty(a.status||'open'))}</td></tr>`).join('')}</tbody></table>`;}
function resetChat(){
  $('#chat-messages').replaceChildren();appendMessage('assistant','I can help interpret the retained findings, explain evidence gaps, and identify follow-up checks. Ask a question when the investigation is ready.');$('#chat-input').value='';
}
function appendMessage(role,text){const node=document.createElement('div');node.className=`chat-message ${role}`;node.textContent=asText(text);$('#chat-messages').append(node);$('#chat-messages').scrollTop=$('#chat-messages').scrollHeight;return node;}
async function sendChat(){
  const message=$('#chat-input').value.trim();if(!message||state.chatBusy||state.run?.status!=='completed')return;
  const id=state.run.id;state.chatBusy=true;appendMessage('user',message);$('#chat-input').value='';const pending=appendMessage('assistant','Checking the retained evidence…');refreshControls();
  try{const result=await api(`/api/research/${encodeURIComponent(id)}/chat`,{method:'POST',body:JSON.stringify({message})});if(state.run?.id===id){pending.textContent=asText(result.answer||'No answer was returned.');const sources=list(result.source_ids||result.citations);if(sources.length){const refs=document.createElement('div');refs.innerHTML=sourceRefs(sources.map(s=>typeof s==='object'?s.source_id||s.id:s));pending.append(refs);}}}
  catch(e){if(state.run?.id===id){pending.classList.add('error');pending.textContent=`Unable to answer: ${e.message}`;$('#chat-input').value=message;}}
  finally{state.chatBusy=false;refreshControls();if(state.run?.id===id)$('#chat-input').focus();}
}
async function saveSupplier(){
  if(state.run?.status!=='completed'||state.saveBusy)return;state.saveBusy=true;refreshControls();
  try{await api('/api/suppliers',{method:'POST',body:JSON.stringify({run_id:state.run.id})});await refreshSuppliers();toast('Saved with evidence and follow-up actions. Qualification remains pending.');setTab('suppliers');}
  catch(e){error(`Could not save supplier: ${e.message}`);}finally{state.saveBusy=false;refreshControls();}
}
async function refreshSuppliers(){
  try{const data=await api('/api/suppliers');state.suppliers=list(data.suppliers);$('#supplier-count').textContent=state.suppliers.length;renderSuppliers();}
  catch(e){$('#suppliers-list').innerHTML=`<div class="notice error">Could not load saved suppliers: ${esc(e.message)}</div>`;}
}
function renderSuppliers(){
  $('#suppliers-list').innerHTML=state.suppliers.length?state.suppliers.map(s=>{const run=s.research||s.report||s.run||{},actions=list(s.actions||run.actions),company=s.company||s.entity?.name||run.company||'Supplier',runId=s.run_id||s.research_run_id||run.id;return `<article class="supplier-card"><div class="supplier-header"><div><h4>${esc(company)}</h4><p>Country hint: ${esc(s.country||run.country||'Not provided')} · Saved ${esc(stamp(s.saved_at||s.created_at||s.added_at))} · ${s.demo?'Historical example. ':''}Research-derived record</p></div><div>${badge('unknown',' scores')} ${runId?`<button class="button secondary compact" data-open-run="${esc(runId)}">Open investigation →</button>`:''}</div></div><p class="supplier-summary">${esc(s.summary||run.summary||'Evidence and follow-up checks retained from the investigation.')}<br><strong>Qualification pending.</strong> Research findings do not populate or replace the synthetic catalog scores.</p><h4 class="small">Follow-up queue · ${actions.filter(a=>a.status!=='done').length} open</h4>${actions.length?actions.map(a=>`<div class="action-row ${a.status==='done'?'done':''}"><input type="checkbox" id="action-${esc(s.id)}-${esc(a.id)}" data-supplier="${esc(s.id)}" data-action="${esc(a.id)}" data-field="status" ${a.status==='done'?'checked':''} aria-label="Mark action ${esc(a.action||a.title)} complete"><div class="action-content"><label for="action-${esc(s.id)}-${esc(a.id)}">${esc(a.action||a.title)}</label><small>${esc(labels[a.category]||pretty(a.category))} · ${esc(pretty(a.priority))} priority</small></div><label class="sr-only" for="owner-${esc(s.id)}-${esc(a.id)}">Action owner</label><input id="owner-${esc(s.id)}-${esc(a.id)}" class="action-owner" placeholder="Assign owner" maxlength="100" value="${esc(a.owner||'')}" data-supplier="${esc(s.id)}" data-action="${esc(a.id)}" data-field="owner"></div>`).join(''):'<p class="muted small">No follow-up actions were retained.</p>'}</article>`;}).join(''):'<div class="saved-empty"><h4>Build an evidence-backed supplier list.</h4><p>Save a completed risk report to retain the research, keep scores explicitly unknown, and assign its follow-up actions here.</p></div>';
}
async function updateAction(event){
  const input=event.target;if(!input.dataset.action)return;const supplier=state.suppliers.find(s=>String(s.id)===input.dataset.supplier);const action=list(supplier?.actions||supplier?.research?.actions||supplier?.report?.actions||supplier?.run?.actions).find(a=>String(a.id)===input.dataset.action);if(!action)return;
  const status=input.dataset.field==='status'?(input.checked?'done':'open'):(action.status||'open');const owner=input.dataset.field==='owner'?input.value.trim():(action.owner||'');input.disabled=true;
  const change=input.dataset.field==='status'?{status}:{owner};
  try{await api(`/api/suppliers/${encodeURIComponent(input.dataset.supplier)}/actions/${encodeURIComponent(input.dataset.action)}`,{method:'PATCH',body:JSON.stringify(change)});await refreshSuppliers();toast('Follow-up action updated.');}
  catch(e){input.disabled=false;if(input.type==='checkbox')input.checked=action.status==='done';else input.value=action.owner||'';error(`Could not update action: ${e.message}`);}
}
init();
