import {api,message} from './api.js';
import {$,$$,esc,title,header,field,selectField,notice,toast} from './ui.js';
import {evidencePanel,bindEvidence} from './evidence.js';

const utilities=['electricity','water','natural_gas','heating_oil','propane','steam','hot_water','chilled_water'];
const headers=['invoice_number','account_identifier','invoice_date','invoice_total','due_date','service_address','currency','previous_balance','amount_due'];
const services=['meter_identifier','period_start','period_end','consumption_quantity','consumption_unit','current_charge','delivery_quantity','demand_quantity','demand_unit','building','reading_type','previous_reading','current_reading','supply_charge','delivery_charge','demand_charge','taxes','fees','credits'];
const roles=[...headers,...services.map(k=>'services.*.'+k)];
const roleLabel=key=>title(key.replace(/^services\.(\d+)\./,(_,i)=>`Service ${Number(i)+1} · `).replace('services.*.','Service · ').replace('consumption_quantity','usage quantity').replace('consumption_unit','quantity unit'));
const required=new Set(['invoice_number','account_identifier','invoice_date','invoice_total',...['meter_identifier','period_start','period_end','consumption_quantity','consumption_unit','current_charge','delivery_quantity','demand_quantity','demand_unit'].map(k=>'services.*.'+k)]);
const units=['kWh','gal','m3','CCF','Mcf','therm','MMBtu','kW','kVA','lb','ton_h'];
const actions=(id)=>`<button class="secondary compact" data-layout="${esc(id)}">Inspect layout</button>`;

function validationTable(validation){
  if(!validation)return notice('No local validation yet. Compare this version with at least two distinct, approved PDF sources.');
  const s=validation.summary;
  return notice(`${s.documents_tested} selected approved bills · ${s.required_failures} required-field failures · ${s.layout_drift} layout conflicts. ${s.eligible?'Eligible for explicit activation.':'Needs further validation or a new draft version.'}`,s.eligible?'success':'warning')+
    `<p class="caption">Last validation: ${esc(validation.created_at)}. Counts apply only to this provider, version and selected set. Manual entry counts refer to missing values in the original import.</p><div class="table-scroll"><table><thead><tr><th>Field</th><th>Exact / tested</th><th>Missing</th><th>Corrected</th><th>Unit conflicts</th><th>Manual entry</th></tr></thead><tbody>${Object.entries(s.fields).map(([key,c])=>`<tr><td>${esc(roleLabel(key))}</td><td>${c.exact} / ${c.tested}</td><td>${c.missing}</td><td>${c.corrected}</td><td>${c.unit_conflicts}</td><td>${c.manual_entry}</td></tr>`).join('')}</tbody></table></div>`;
}

export async function showProviders(container,ctx){
  const data=await api('/providers');
  container.innerHTML=header('Provider Management','Private layouts and local validation stay in this workspace.',`<button class="primary" id="provider-start">Set up a provider</button>`)+
    notice('First review at least two source bills locally. Build a draft layout, compare its extraction with those approved values, then explicitly activate it for future imports. Every candidate still needs ordinary invoice approval.')+
    (data.damaged?notice('Local template integrity needs school IT attention. Candidate templates are quarantined; manual bill review remains available. Preserve the workspace and use an intact private backup.','danger'):'')+
    data.providers.map(provider=>`<section class="panel"><h2>${esc(provider.label)}</h2><p class="caption">${esc(title(provider.commodity))} · Local provider · Private configuration</p><div class="table-scroll"><table><thead><tr><th>Version</th><th>State</th><th>Selected validation</th><th>Approved future sources</th><th>Corrections / provider drift</th><th></th></tr></thead><tbody>${data.layouts.filter(l=>l.provider_id===provider.id).map(l=>`<tr><td>v${l.version}</td><td><span class="status ${l.state==='active'?'approved':'pending'}">${esc(title(l.state))}</span></td><td>${l.validation?`${l.validation.summary.documents_tested} bills · ${l.validation.summary.eligible?'passed selected set':'needs work'}<small>${esc(l.validation.created_at)}</small>`:'Not tested'}</td><td>${l.quality.reviewed_documents}</td><td>${l.quality.correction_count} / ${l.quality.provider_drift_documents}${l.quality.investigate?'<small>Investigate · propose a new version</small>':''}</td><td>${actions(l.id)}</td></tr>`).join('')||'<tr><td colspan="6">No saved layouts yet.</td></tr>'}</tbody></table></div><button class="text-button" data-setup-provider="${provider.id}">Create a draft layout</button></section>`).join('')+
    `<details class="panel"><summary>Built-in fictional development templates</summary><p>Five fictional provider families are shipped with the source release. Their code templates remain separate from this private registry. Neither group changes retained extraction history.</p></details>`;
  $('#provider-start').onclick=()=>ctx.openProviderSetup();
  $$('[data-layout]').forEach(b=>b.onclick=()=>showLayout(container,ctx,b.dataset.layout));
  $$('[data-setup-provider]').forEach(b=>b.onclick=()=>ctx.openProviderSetup(null,{provider_id:b.dataset.setupProvider}));
}

async function showLayout(container,ctx,id){
  const current=ctx.beginView();
  const [{provider,layout},documents]=await Promise.all([api(`/provider-layouts/${id}`),api('/providers/documents')]);
  if(!current())return;
  const approved=documents.filter(d=>d.status==='approved');
  container.innerHTML=`<button class="text-button back-button" id="providers-back">Back to Provider Management</button>`+header(`${provider.label} · v${layout.version}`,`${title(layout.state)} · ${title(provider.commodity)} · ${title(layout.provenance)}`)+
    `<section class="panel"><h2>Immutable layout version</h2><p class="source-hash">Template hash: ${esc(layout.hash)}</p><p class="caption">Created ${esc(layout.created_at)}. Previous versions, source bytes and extraction snapshots remain unchanged.</p><div class="action-row"><button class="secondary" id="new-layout-version">Create a new version</button></div>${layout.quality.investigate?notice('Drift or repeated approved corrections need investigation. Review this version and propose a separately validated replacement.','warning'):''}<p>Approved future sources: ${layout.quality.reviewed_documents} · Corrections: ${layout.quality.correction_count} · Provider drift: ${layout.quality.provider_drift_documents}</p>${Object.entries(layout.quality.field_corrections).map(([k,n])=>`<p class="caption">${esc(roleLabel(k))}: ${n} approved correction(s)</p>`).join('')}<details><summary>Private rule definition</summary><pre class="diagnostics">${esc(JSON.stringify(layout.definition,null,2))}</pre></details></section>`+
    `<section class="panel"><h2>Validate selected approved bills</h2><p>Choose one to ten sources reviewed under this provider label. Activation requires at least two distinct sources, exact required fields and a matching service structure. This does not measure general provider accuracy.</p><div class="provider-document-list">${approved.map(d=>`<label class="check-label"><input type="checkbox" data-validation-document="${d.id}"><span>${esc(d.filename)} · source ${d.id}</span></label>`).join('')||'<p>No approved PDFs yet. Complete ordinary bill review first.</p>'}</div><div class="action-row"><button class="secondary" id="run-local-validation">Validate selected bills</button></div><div id="validation-error"></div><div id="local-validation-result">${validationTable(layout.validation)}</div></section>`+
    `<section class="panel"><h2>Test a retained document</h2>${selectField('Source for preview','test-document',documents.map(d=>[String(d.id),`${d.filename} · ${d.status}`]),String(documents[0]?.id||''))}<button class="secondary" id="test-layout">Preview this layout</button><div id="layout-preview"></div></section>`+
    `<section class="panel"><h2>Staff-controlled status</h2><p>Activation proposes candidates on future imports. It never approves a financial record. Retirement is permanent for this version; create a new draft if it needs revision.</p>${layout.state!=='retired'?`<label class="check-label"><input type="checkbox" id="layout-state-ack"><span>I reviewed this version and its local results, and confirm this status change.</span></label><div class="action-row">${layout.state==='draft'?`<button class="primary" id="activate-layout" ${layout.validation?.summary.eligible?'':'disabled'}>Activate validated layout</button>`:''}<button class="secondary" id="retire-layout">Retire this version</button></div>`:notice('Retired version retained for provenance.')}<div id="state-error"></div><details><summary>Validation and status history</summary><ul>${layout.states.map(s=>`<li>${esc(s.created_at)} · ${esc(title(s.state))}</li>`).join('')}${layout.validations.map(v=>`<li>${esc(v.created_at)} · ${v.summary.documents_tested} selected sources · ${v.summary.eligible?'passed selected set':'needs work'}</li>`).join('')}</ul></details></section>`+
    `<section class="panel"><h2>Provider Extraction Support Bundle</h2><p>Preview the exact value-free JSON before downloading. It excludes source documents, OCR text, private labels, invoice values, dates, paths and the rule definition. The anonymous IDs and template hash can link repeat reports from this workspace.</p><button class="secondary" id="preview-provider-support">Preview safe bundle</button><div id="provider-support"></div></section>`;
  $('#providers-back').onclick=()=>ctx.navigate('providers');
  $('#new-layout-version').onclick=()=>ctx.openProviderSetup(null,{provider_id:provider.id,parent:layout});
  $('#run-local-validation').onclick=async e=>{
    const button=e.currentTarget;button.disabled=true;
    $('#validation-error').innerHTML=notice('Comparing selected sources locally. Keep this page open until the comparison finishes.');
    try{await api(`/provider-layouts/${id}/validate`,{method:'POST',body:{document_ids:$$('[data-validation-document]:checked').map(i=>Number(i.dataset.validationDocument))}});if(button.isConnected){await showLayout(container,ctx,id);toast('Local validation saved.');}}
    catch(error){if(button.isConnected){$('#validation-error').innerHTML=notice(message(error.message),'danger');button.disabled=false;}}
  };
  $('#test-layout').onclick=()=>ctx.openProviderSetup(Number($('[name=test-document]').value),{provider_id:provider.id,inspect:layout});
  for(const state of ['activate','retire']){
    const button=$(`#${state}-layout`);if(!button)continue;
    button.onclick=async()=>{button.disabled=true;try{await api(`/provider-layouts/${id}/${state}`,{method:'POST',body:{state_id:layout.state_id,validation_id:layout.validation?.id,acknowledge:$('#layout-state-ack').checked}});if(!button.isConnected)return;await showLayout(container,ctx,id);toast(state==='activate'?'Layout activated for future candidates.':'Layout retired; history retained.');}catch(e){$('#state-error').innerHTML=notice(message(e.message),'danger');button.disabled=false;}};
  }
  $('#preview-provider-support').onclick=async e=>{
    const trigger=e.currentTarget;
    try{const result=await api(`/provider-layouts/${id}/support`),target=$('#provider-support');
      if(!target||!trigger.isConnected)return;
      target.innerHTML=`<pre class="diagnostics" id="support-exact-preview"></pre><p class="source-hash">Preview SHA-256: ${esc(result.sha256)}</p><label class="check-label"><input id="support-preview-ack" type="checkbox"><span>I reviewed the exact preview and choose to download it.</span></label><button class="secondary" id="download-provider-support" disabled>Download previewed safe bundle</button>`;
      $('#support-exact-preview').textContent=result.text;
      $('#support-preview-ack').onchange=e=>$('#download-provider-support').disabled=!e.target.checked;
      $('#download-provider-support').onclick=()=>{const url=URL.createObjectURL(new Blob([result.text],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='utilityos-provider-support.json';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);};
    }catch(e){toast(message(e.message),true);}
  };
}

export async function showProviderSetup(container,ctx,documentId=null,options={}){
  const current=ctx.beginView();
  const [listing,documents]=await Promise.all([api('/providers'),api('/providers/documents')]);
  if(!current())return;
  if(!options.parent&&!options.inspect&&listing.providers.some(p=>p.id===options.provider_id)){const retained=listing.layouts.filter(l=>l.provider_id===options.provider_id);if(retained.length)options={...options,parent:retained.at(-1)};}
  if(!documentId)documentId=documents[0]?.id;
  if(!documentId){container.innerHTML=header('Provider Setup Wizard','Import a PDF before choosing source fields.')+`<button class="primary" id="studio-import">Import a source PDF</button>`;$('#studio-import').onclick=ctx.openImport;return;}
  const document=documents.find(d=>d.id===documentId);
  let observed=await api(`/providers/documents/${documentId}/observations`);
  if(!current())return;
  let providerId=options.provider_id||'',selected=null,rules=structuredClone(options.draft?.rules||options.parent?.definition.rules||options.inspect?.definition.rules||[]);
  const original=options.draft||options.parent?.definition||options.inspect?.definition;
  let providerAnchor=structuredClone(original?.provider_anchor||{literal:'',page:1,region:[0,0,4000,4000]});
  let layoutAnchor=structuredClone(original?.layout_anchor||null),controller;
  const previewOnly=Boolean(options.inspect);
  container.innerHTML=`<button class="text-button back-button" id="studio-back">Back to Provider Management</button>`+header('Provider Setup Wizard',previewOnly?'Preview an immutable version against a selected source.':'Select local source fields and save a new immutable draft layout.')+
    notice('Definitions and source text stay private in this workspace. First approve two representative bills through ordinary review; validation will compare against those final values. Previewing a source never rewrites its original extraction.')+
    `<section class="panel"><h2>1. Provider and source</h2><div class="form-grid two">${selectField('Local provider','studio-provider',[['','Choose or create a provider'],...listing.providers.map(p=>[p.id,p.label])],providerId)}${selectField('Source PDF','studio-document',documents.map(d=>[String(d.id),`${d.filename} · ${d.status}`]),String(documentId))}</div><form id="new-provider-form"><details ${providerId?'':'open'}><summary>Create a private local provider</summary><div class="form-grid two">${field('Local provider label','local-provider-label','','text','maxlength="120" required')}${selectField('Provider commodity','local-provider-commodity',utilities.map(v=>[v,title(v)]),'electricity')}</div><button class="secondary" type="submit">Create local provider</button></details></form><div id="provider-create-error"></div></section>`+
    `<div class="evidence-workspace studio-workspace"><div id="studio-source"></div><div class="evidence-entry"><section class="panel"><h2>2. Select a source candidate</h2><p class="caption">Click a line in the rendered page or choose it below. Selection supplies a proposed locator; review its literal label and constraints before adding the rule.</p>${field('Filter source candidates','candidate-filter')}<div id="source-candidates" class="source-candidates"></div><p id="selected-candidate" class="evidence-raw">No source candidate selected.</p><div class="action-row"><button class="secondary compact" id="set-provider-anchor">Use as provider identifier</button><button class="secondary compact" id="set-layout-anchor">Use as layout marker</button><button class="secondary compact" id="set-section-prefix">Use as service section start</button></div></section>
    <section class="panel"><h2>3. Assign a field and locator</h2><form id="studio-rule-form"><div class="form-grid two">${selectField('Semantic field','rule-field',roles.map(r=>[r,roleLabel(r)]),'invoice_number')}${selectField('Locate value','rule-mode',[['inline','After literal label and colon'],['below','Below a literal label'],['right','Right of a literal label'],['region','Single line in selected region']],'inline')}${field('Literal label','rule-label','','text','maxlength="120"')}${selectField('Date format','rule-date',[['iso','YYYY-MM-DD'],['mdy','MM/DD/YYYY'],['dmy','DD/MM/YYYY']],'iso')}${selectField('Expected unit (unit fields only)','rule-unit',[['','No expectation'],...units.map(v=>[v,v])],'')}${field('Maximum nearby distance, points','rule-distance','60','number','min="1" max="200"')}</div><label class="check-label"><input type="checkbox" id="rule-region"><span>Constrain lookup to the selected page and row region (repeated services usually use their section instead).</span></label><label class="check-label"><input type="checkbox" id="rule-required" checked><span>Required for matching and activation.</span></label><div class="action-row"><button class="secondary" type="submit">Add or replace field rule</button></div></form><div id="rule-error"></div></section></div></div>`+
    `<section class="panel"><h2>4. Layout semantics and mapped rules</h2><div class="form-grid three">${field('Provider identifier text','provider-anchor',providerAnchor.literal,'text','maxlength="120"')}${field('Layout marker text (optional)','layout-anchor',layoutAnchor?.literal||'','text','maxlength="120"')}${selectField('Service layout','service-layout',[['single','One service in the document'],['repeated','Numbered repeated service sections']],original?(original.section_prefix?'repeated':'single'):'single')}${field('Repeated section prefix (followed by 1, 2…)','section-prefix',original?.section_prefix||'Service point ','text','maxlength="100"')}${selectField('Document type','layout-kind',['invoice','credit','corrected_invoice','rebill','supporting_document'].map(v=>[v,title(v)]),original?.document_kind||'invoice')}${selectField('Quantity treatment','layout-treatment',[['consumption','Consumption'],['charges_only','Charges only, zero repeated quantity'],['delivery','Fuel delivered / purchased']],original?.quantity_treatment||'consumption')}</div><label class="check-label"><input id="end-inclusive" type="checkbox" ${original?.end_date_inclusive?'checked':''}><span>The printed period end includes that day; propose the next day as the ledger’s exclusive end.</span></label><p class="caption">Required: invoice reference, account, date and current total; service identifier, start/end, unit and current line charge; usage or delivered volume where applicable. Demand should be required when applicable. Never use previous balance or amount due as current charges.</p><div id="studio-rules"></div><div id="studio-error"></div><div class="action-row"><button class="secondary" id="preview-local-layout">Preview extraction</button>${previewOnly?'':'<button class="primary" id="save-local-layout">Save new draft layout</button>'}${document?'<button class="secondary" id="return-source-review">Return to bill review</button>':''}</div></section><section class="panel" id="studio-preview" hidden></section>`;
  function setCandidate(line){selected=line;$('#selected-candidate').textContent=`Page ${line.page}: ${line.text}`;controller?.showObservation(line,'Selected source candidate');$('[name=rule-label]').value=line.text.includes(':')?line.text.split(':')[0]:line.text;const semantic=$('[name=rule-field]').value;$('#rule-region').checked=!semantic.startsWith('services.');}
  function renderSource(){
    const fields={invoice_total:{value:null,raw:null,page:null,bbox:null,method:'unavailable',state:'missing',parser_version:'local setup observation'}};
    const item={document_id:documentId,intake:{extraction:{fields,pages:observed.pages,pdf_kind:observed.pages.some(p=>p.method==='ocr')?'scanned':'digital_text',layout_state:'unknown_provider'},differences:[]}};
    $('#studio-source').innerHTML=evidencePanel(item);
    controller=bindEvidence(item,{observations:observed.lines,onObservation:setCandidate});
    candidates();
  }
  function candidates(){
    const filter=$('[name=candidate-filter]').value.toLowerCase();
    const found=observed.lines.map((line,i)=>({line,i})).filter(({line})=>line.text.toLowerCase().includes(filter));
    $('#source-candidates').innerHTML=found.slice(0,200).map(({line,i})=>`<button class="candidate-line" data-candidate="${i}"><small>Page ${line.page} · ${esc(line.method)}</small>${esc(line.text)}</button>`).join('')||'<p>No readable candidates. Use manual review; optional local OCR may be needed for scans.</p>';
    if(found.length>200)$('#source-candidates').insertAdjacentHTML('beforeend','<p>Showing 200 matches. Refine the filter to reach other lines.</p>');
    $$('[data-candidate]').forEach(b=>b.onclick=()=>setCandidate(observed.lines[Number(b.dataset.candidate)]));
  }
  function renderRules(){
    $('#studio-rules').innerHTML=`<div class="table-scroll"><table><thead><tr><th>Field</th><th>Literal / locator</th><th>Scope</th><th>Required</th><th></th></tr></thead><tbody>${rules.map((r,i)=>`<tr><td>${esc(roleLabel(r.field))}</td><td>${esc(r.label||'Selected region')}<small>${esc(r.mode)} · ${esc(r.date_format)}${r.expected_unit?' · '+esc(r.expected_unit):''}</small></td><td>${r.region?`Page ${r.page} row region`:r.page?`Page ${r.page}`:'Repeated service section'}</td><td>${r.required?'Yes':'No'}</td><td><button class="text-button" data-remove-rule="${i}">Remove rule</button></td></tr>`).join('')||'<tr><td colspan="5">Select and map the source fields above.</td></tr>'}</tbody></table></div>`;
    $$('[data-remove-rule]').forEach(b=>b.onclick=()=>{rules.splice(Number(b.dataset.removeRule),1);renderRules();});
  }
  function getDefinition(){
    return {format:1,provider_anchor:{...providerAnchor,literal:$('[name=provider-anchor]').value},layout_anchor:$('[name=layout-anchor]').value?{...(layoutAnchor||{page:1,region:[0,0,4000,4000]}),literal:$('[name=layout-anchor]').value}:null,section_prefix:$('[name=service-layout]').value==='single'?null:$('[name=section-prefix]').value,document_kind:$('[name=layout-kind]').value,quantity_treatment:$('[name=layout-treatment]').value,end_date_inclusive:$('#end-inclusive').checked,rules};
  }
  function region(line){const page=observed.pages.find(p=>p.number===line.page);return [Math.max(0,line.bbox[0]-16),Math.max(0,line.bbox[1]-8),page.width,Math.min(page.height,line.bbox[3]+8)];}
  $('#studio-back').onclick=()=>ctx.navigate('providers');
  if(document)$('#return-source-review').onclick=()=>ctx.openStage(document.staged_id);
  $('[name=studio-document]').onchange=e=>ctx.openProviderSetup(Number(e.target.value),{...options,provider_id:providerId,draft:getDefinition()});
  $('[name=studio-provider]').onchange=e=>{providerId=e.target.value;};
  $('#new-provider-form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget;try{const p=await api('/providers',{method:'POST',body:{label:$('[name=local-provider-label]').value,commodity:$('[name=local-provider-commodity]').value}});if(!form.isConnected)return;listing.providers.push(p);providerId=p.id;$('[name=studio-provider]').insertAdjacentHTML('beforeend',`<option value="${esc(p.id)}">${esc(p.label)}</option>`);$('[name=studio-provider]').value=p.id;$('#new-provider-form details').open=false;toast('Private provider created.');}catch(error){$('#provider-create-error').innerHTML=notice(message(error.message),'danger');}};
  $('[name=candidate-filter]').oninput=candidates;
  $('#set-provider-anchor').onclick=()=>{if(!selected)return;providerAnchor={literal:selected.text,page:selected.page,region:region(selected)};$('[name=provider-anchor]').value=selected.text;};
  $('#set-layout-anchor').onclick=()=>{if(!selected)return;layoutAnchor={literal:selected.text,page:selected.page,region:region(selected)};$('[name=layout-anchor]').value=selected.text;};
  $('#set-section-prefix').onclick=()=>{if(selected){$('[name=section-prefix]').value=selected.text.replace(/\d+\s*$/,'');$('[name=service-layout]').value='repeated';}};
  $('[name=rule-field]').onchange=e=>{const key=e.target.value;$('#rule-required').checked=required.has(key);$('#rule-region').checked=!key.startsWith('services.');$('[name=rule-date]').value='iso';$('[name=rule-unit]').value='';};
  $('#studio-rule-form').onsubmit=e=>{
    e.preventDefault();if(!selected){$('#rule-error').innerHTML=notice('Choose a source candidate first.','warning');return;}
    const key=$('[name=rule-field]').value,mode=$('[name=rule-mode]').value,bounded=$('#rule-region').checked||mode==='region';
    const rule={field:key,label:$('[name=rule-label]').value,mode,page:bounded?selected.page:null,region:bounded?region(selected):null,distance:Number($('[name=rule-distance]').value),required:$('#rule-required').checked,date_format:$('[name=rule-date]').value,expected_unit:$('[name=rule-unit]').value||null};
    const index=rules.findIndex(r=>r.field===key);if(index<0)rules.push(rule);else rules[index]=rule;
    $('#rule-error').innerHTML='';renderRules();toast('Field rule added to this unsaved draft.');
  };
  $('#preview-local-layout').onclick=async e=>{
    const button=e.currentTarget;button.disabled=true;$('#studio-error').innerHTML=notice('Extracting a local preview…');
    try{const result=await api(previewOnly?`/provider-layouts/${options.inspect.id}/preview`:'/providers/preview',{method:'POST',body:previewOnly?{document_id:documentId}:{provider_id:providerId,document_id:documentId,definition:getDefinition()}});
      const target=$('#studio-preview');if(!target)return;
      $('#studio-error').innerHTML='';target.hidden=false;
      target.innerHTML=`<h2>Candidate preview · ${esc(title(result.extraction.layout_state))}</h2>${notice(result.extraction.codes.join(' · ')||'Required source fields located. Compare every value; this preview has no approval authority.',result.extraction.layout_state==='known'?'success':'warning')}<div class="table-scroll"><table><thead><tr><th>Field</th><th>Proposed value</th><th>Evidence</th></tr></thead><tbody>${Object.entries(result.extraction.fields).filter(([key,f])=>f.value!==null||f.state==='conflict'||rules.some(r=>r.field===key.replace(/services\.\d+\./,'services.*.'))).map(([key,f],i)=>`<tr><td>${esc(roleLabel(key))}</td><td>${esc(f.value??'Missing')}</td><td><button class="text-button" data-preview-field="${esc(key)}">${esc(title(f.state))}${f.page?' · page '+f.page:''}</button></td></tr>`).join('')}</tbody></table></div><p class="caption">The original extraction and approved history were not changed. Save a draft version, then validate it on approved sources before activation.</p>`;
      $$('[data-preview-field]').forEach(b=>b.onclick=()=>{const f=result.extraction.fields[b.dataset.previewField];controller.showObservation({...f,text:f.raw||'No source value',bbox:f.bbox},roleLabel(b.dataset.previewField));});
      target.scrollIntoView({block:'start',behavior:'instant'});
    }catch(error){if(button.isConnected)$('#studio-error').innerHTML=notice(message(error.message),'danger');}finally{if(button.isConnected)button.disabled=false;}
  };
  if(!previewOnly)$('#save-local-layout').onclick=async e=>{
    const button=e.currentTarget;button.disabled=true;
    try{const latest=Math.max(0,...listing.layouts.filter(l=>l.provider_id===providerId).map(l=>l.version));const saved=await api(`/providers/${providerId}/layouts`,{method:'POST',body:{definition:getDefinition(),parent_layout_id:options.parent?.id||null,expected_version:latest}});if(!button.isConnected)return;await showLayout(container,ctx,saved.id);toast('Immutable draft saved. Validation and activation are separate actions.');}
    catch(error){if(button.isConnected){$('#studio-error').innerHTML=notice(message(error.message),'danger');button.disabled=false;}}
  };
  renderSource();renderRules();
  if(previewOnly){$$('input,select,button',container).filter(node=>!['studio-document','candidate-filter'].includes(node.name)&&!['preview-local-layout','studio-back','return-source-review','toggle-evidence'].includes(node.id)&&!node.dataset.candidate&& !['evidence-page','evidence-zoom'].includes(node.id)).forEach(node=>node.disabled=true);}
}
