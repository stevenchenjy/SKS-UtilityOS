import {evidencePanel,detailPanel,bindEvidence,collectDetails} from './evidence.js';
import {lifecyclePanel,bindLifecycle} from './lifecycle.js';
import {api,message} from './api.js';
import {$,$$,esc,exactDollars,title,header,empty,field,selectField,toast,notice,localTime,quantity} from './ui.js';
const commodityUnits={electricity:['kWh'],water:['gal','m3','CCF'],natural_gas:['therm','CCF','Mcf','MMBtu'],heating_oil:['gal'],propane:['gal'],steam:['lb','MMBtu'],hot_water:['MMBtu'],chilled_water:['ton_h','MMBtu']};
const commodities=Object.keys(commodityUnits).map(v=>[v,title(v)]);
function renderFlags(flags) { return flags.length?flags.map(flag=>notice(message(flag.code),flag.blocking?'danger':'warning')).join(''):notice('The entered fields pass the pilot’s checks. Confirm them against the source before approval.','success'); }
function lineFields(line,index,readonly=false) {
  return `<fieldset class="line-editor" data-line="${index}"><legend>Service line ${index+1}</legend>${readonly?'':`<button type="button" class="text-button danger-text" data-remove-line="${index}">Remove service line ${index+1}</button>`}<div class="form-grid four">
    ${field('Meter / fuel point code','meter_code',line.meter_code)}${field('Building (optional)','building',line.building)}
    ${selectField('Utility type','commodity',commodities,line.commodity)}${selectField('Unit','unit',(commodityUnits[line.commodity]||['kWh']).map(v=>[v,v]),line.unit)}
    ${field('Period start','period_start',line.period_start,'date')}${field('Period end (exclusive)','period_end',line.period_end,'date')}
    ${field('Quantity','usage',line.usage,'text','inputmode="decimal"')}${field('Current line charge, USD','current_charge',line.current_charge,'text','inputmode="decimal"')}
    ${selectField('Quantity treatment','usage_role',[['consumption','Consumption'],['charges_only','Charges only (quantity 0)'],['delivery','Fuel delivered / purchased']],line.usage_role)}
    ${selectField('Supplier reading type','read_type',[['actual','Actual'],['estimated','Estimated'],['unknown','Unknown']],line.read_type)}
  </div></fieldset>`;
}
function collectBill() {
  const form=$('#bill-editor');
  const result={};
  for(const name of ['provider','account_alias','invoice_number','bill_date','current_total'])result[name]=form.elements.namedItem(name).value;
  result.lines=$$('[data-line]',form).map(line=>Object.fromEntries($$('input,select',line).map(input=>[input.name,input.value])));
  return result;
}
export async function showReview(container,ctx) {
  const stages=await api('/staged');
  const pending=stages.filter(r=>r.status==='pending').length;
  ctx.updatePending(pending);
  container.innerHTML=header('Review queue','Check source records before they enter the ledger.',`<button class="primary" id="import-review">Import a file</button>`)+
    `<div class="tabs" role="group" aria-label="Review filter"><button class="active" data-filter="pending" aria-pressed="true">Awaiting review <span>${pending}</span></button><button data-filter="all" aria-pressed="false">All imports</button></div><p class="caption">All pending drafts and the latest 500 closed imports. Older invoices remain searchable in Invoice ledger.</p><div id="review-list"></div>`;
  function render(filter){
    const rows=stages.filter(r=>filter==='all'||r.status==='pending');
    $('#review-list').innerHTML=rows.length?`<section class="panel table-panel"><div class="table-scroll"><table><thead><tr><th>Source / reference</th><th>Type</th><th>Status</th><th class="numeric">Current charges</th><th></th></tr></thead><tbody>${rows.map(row=>`<tr><td><strong>${esc(row.label)}</strong><small>${esc(row.provider)} · ${esc(row.filename)}</small></td><td>${row.kind==='bill'?'Utility invoice':'Interval data'}</td><td><span class="status ${row.status}">${esc(title(row.bill_status||row.status))}</span></td><td class="numeric">${row.current_total?exactDollars(Number(row.current_total)*100):row.interval_count?`${row.interval_count} readings`:'Needs entry'}</td><td class="numeric"><button class="secondary compact" data-review="${row.id}" aria-label="${row.status==='pending'?'Review':'View'} ${esc(row.label)}">${row.status==='pending'?'Review':'View'}</button></td></tr>`).join('')}</tbody></table></div></section>`:empty('The review queue is clear','Import a CSV, an electricity XML export, or a PDF source to add the next item.');
    $$('[data-review]').forEach(button=>button.onclick=()=>ctx.openStage(Number(button.dataset.review)));
  }
  render('pending');
  $$('[data-filter]').forEach(button=>button.onclick=()=>{$$('[data-filter]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));});render(button.dataset.filter);});
  $('#import-review').onclick=ctx.openImport;
}
export async function showStage(container,ctx,id) {
  const item=await api(`/staged/${id}`);
  if(item.data_error)return showDamagedStage(container,ctx,item);
  const readonly=item.status!=='pending';
  if(item.kind==='intervals')return showIntervalStage(container,ctx,item);
  const backRoute=ctx.route==='bills'?'bills':'review';
  let payload=item.payload;
  // Rendering a changed service-line list must not discard unsaved bill details.
  const retainDetails=()=>{if(item.intake)Object.assign(item.intake.reviewed_values,collectDetails(item));};
  function render(){
    container.innerHTML=`<button class="text-button back-button" id="back-review">${backRoute==='bills'?'Back to invoice ledger':'Back to review queue'}</button>`+
      header(payload.invoice_number||'Enter the source invoice',`${item.filename} · ${title(item.bill?.status||item.status)}`,`<a class="secondary" href="/api/sources/${item.document_id}">Download original locally</a>`)+
      (item.extension==='.pdf'?notice('Local extraction proposes values for review. Compare every field with the retained original. Missing or conflicting values need staff entry; no draft is approved automatically.'):notice('Compare the imported values with the original. The source file is retained unchanged.'))+
      `<details class="panel"><summary>Source provenance</summary><p class="source-hash">SHA-256: ${esc(item.source_sha256)}</p><p>Importer release: ${esc(item.importer_version)}. Earlier releases did not record their importer version. The retained original and saved review revisions stay separate.</p></details>`+
      `${item.intake?`<div class="evidence-workspace">${evidencePanel(item)}<div class="evidence-entry">`:''}<form id="bill-editor"><fieldset><section class="panel"><h2>Invoice details</h2><div class="form-grid three">
      ${field('Provider','provider',payload.provider)}${field('Local account label','account_alias',payload.account_alias)}${field('Invoice reference','invoice_number',payload.invoice_number)}
      ${field('Invoice date','bill_date',payload.bill_date,'date')}${field('Total current charges, USD','current_total',payload.current_total,'text','inputmode="decimal"')}
      </div><p class="caption">Use current-period charges. A balance due may include earlier invoices, payments, or adjustments. Full portal account numbers are unnecessary.</p></section>
      ${payload.lines.map((line,index)=>lineFields(line,index,readonly)).join('')}
      ${readonly?'':`<button type="button" id="add-line" class="secondary">Add a service line</button>`}</fieldset></form>
      ${detailPanel(item,readonly)}${item.intake?'</div></div>':''}${lifecyclePanel(item)}
      ${readonly?'': `<section class="review-checks"><h2>Review checks</h2><div id="flags" aria-live="polite">${renderFlags(item.flags)}</div><label class="check-label"><input type="checkbox" id="acknowledge"> <span>I checked the source, current charges, units, and meter-to-building mapping.</span></label>${item.correction_of&&ctx.mode==='staff'?field('Confirm local app passphrase','current_passphrase','','password','autocomplete="current-password" maxlength="256"'):''}<div class="action-row"><button class="primary" id="approve" disabled>Approve into ledger</button><button class="secondary" id="validate">Check fields</button><button class="text-button danger-text" id="reject">Reject draft</button></div></section>`}`;
    $('#back-review').onclick=()=>ctx.navigate(backRoute);
    if(item.extension==='.pdf'){const button=document.createElement('button');button.type='button';button.className='secondary';button.id='open-provider-setup';button.textContent='Set up or inspect provider layout';button.onclick=async()=>{try{if(!readonly)await api(`/staged/${item.id}/draft`,{method:'POST',body:{payload:collectBill(),intake_details:collectDetails(item),revision:item.revision,correction_of:item.correction_of,reason:item.correction_reason}});await ctx.openProviderSetup(item.document_id,{provider_id:item.intake?.extraction.provider_key||''});}catch(e){toast(message(e.message),true);}};$('.page-heading').after(button);}
    if(readonly)$$('input,select',$('#bill-editor')).forEach(input=>input.disabled=true);
    bindLifecycle(item,ctx,collectBill,()=>collectDetails(item));
    bindEvidence(item);
    if(readonly)return;
    $('#acknowledge').onchange=e=>$('#approve').disabled=!e.target.checked;
    $('#bill-editor').onsubmit=e=>e.preventDefault();
    const invalidate=()=>{$('#acknowledge').checked=false;$('#approve').disabled=true;};
    $('#bill-editor').oninput=invalidate;
    const details=$('.intake-details');if(details)details.oninput=invalidate;
    $$('[data-remove-line]').forEach(b=>b.onclick=()=>{payload=collectBill();if(payload.lines.length===1){toast('An invoice needs at least one service line.',true);return;}retainDetails();const index=Number(b.dataset.removeLine);payload.lines.splice(index,1);render();$(`[data-line="${Math.min(index,payload.lines.length-1)}"] input`).focus();});
    $$('[data-line]').forEach(line=>{
      $('[name=commodity]',line).onchange=e=>{
        const value=e.target.value;
        $('[name=unit]',line).innerHTML=commodityUnits[value].map(u=>`<option>${esc(u)}</option>`).join('');
        if(['heating_oil','propane'].includes(value))$('[name=usage_role]',line).value='delivery';
      };
    });
    $('#add-line').onclick=()=>{payload=collectBill();retainDetails();payload.lines.push({meter_code:'',building:'',commodity:'electricity',unit:'kWh',period_start:'',period_end:'',usage:'',current_charge:'',usage_role:'charges_only',read_type:'unknown'});render();$(`[data-line="${payload.lines.length-1}"] input`).focus();};
    $('#validate').onclick=async()=>{
      try {const data=await api('/validate-bill',{method:'POST',body:{payload:collectBill(),staged_id:id,intake_details:collectDetails(item)}});$('#flags').innerHTML=renderFlags(data.flags);toast('Field checks completed.');}
      catch(error){$('#flags').innerHTML=notice(message(error.message),'danger');}
    };
    $('#approve').onclick=async()=>{
      $('#approve').disabled=true;
      try {await api(`/staged/${id}/approve`,{method:'POST',body:{payload:collectBill(),intake_details:collectDetails(item),revision:item.revision,acknowledge:$('#acknowledge').checked,current_passphrase:$('[name=current_passphrase]')?.value}});toast('Approved. The ledger totals have updated.');ctx.navigate('review');}
      catch(error){$('#flags').innerHTML=notice(message(error.message),'danger');$('#approve').disabled=false;}
    };
    $('#reject').onclick=async()=>{if(confirm('Reject this draft? The original source will remain in local history.')){await api(`/staged/${id}/reject`,{method:'POST',body:{}});toast('Draft rejected. Source preserved locally.');ctx.navigate('review');}};
  }
  render();
}
async function showIntervalStage(container,ctx,item){
  const inventory=await api('/inventory'),p=item.payload,readonly=item.status!=='pending';
  const meters=inventory.meters.filter(m=>m.commodity==='electricity'&&m.unit==='kWh');
  container.innerHTML=`<button class="text-button back-button" id="back-review">Back to review queue</button>`+header('Review interval readings',`${item.filename} · ${title(item.bill?.status||item.status)}`,`<a class="secondary" href="/api/sources/${item.document_id}">Download original locally</a>`)+
    notice('This importer accepts a limited Green Button XML subset: forward, incremental electricity in Wh, converted to kWh. Each source stream must be mapped to the correct local meter.')+
    `<section class="panel"><h2>Source summary</h2><dl class="details"><dt>Readings</dt><dd>${p.interval_count}</dd><dt>Total imported energy</dt><dd>${quantity(p.total_kwh)} kWh</dd><dt>Coverage starts</dt><dd>${esc(localTime(p.first_utc))}</dd><dt>Coverage ends</dt><dd>${esc(localTime(p.last_utc))}</dd><dt>Storage time basis</dt><dd>UTC epoch seconds, including interval duration</dd><dt>Data cost</dt><dd>No API or processing subscription</dd></dl><p class="caption">Interval records remain separate from billed consumption and charges. Coverage may contain gaps; a continuous stream has not been established.</p></section>`+
    (readonly?notice('This interval import is closed.'): `<section class="panel"><h2>Confirm meter mapping</h2>${selectField('Local electricity meter','meter_code',[['','Select a meter'],...meters.map(m=>[m.code,`${m.code} · ${m.building||'Unassigned / shared'}`])],'')}<p class="caption">Create a meter by approving its first bill. Source URLs inside the XML are never fetched.</p><label class="check-label"><input type="checkbox" id="interval-ack"><span>I verified that the source stream belongs to this meter and reviewed its measurement type.</span></label><div id="interval-error" aria-live="polite"></div><div class="action-row"><button id="approve-interval" class="primary" disabled>Approve interval import</button><button id="reject-interval" class="text-button danger-text">Reject draft</button></div></section>`);
  $('#back-review').onclick=()=>ctx.navigate('review');
  if(readonly)return;
  $('#interval-ack').onchange=e=>$('#approve-interval').disabled=!e.target.checked;
  $('#approve-interval').onclick=async()=>{
    try {const result=await api(`/staged/${item.id}/approve`,{method:'POST',body:{meter_code:$('[name=meter_code]').value,acknowledge:$('#interval-ack').checked}});toast(`${result.inserted} readings approved. ${result.identical_readings_skipped} identical readings skipped.`);ctx.navigate('intervals');}
    catch(error){$('#interval-error').innerHTML=notice(message(error.message),'danger');}
  };
  $('#reject-interval').onclick=async()=>{if(confirm('Reject this interval draft?')){await api(`/staged/${item.id}/reject`,{method:'POST',body:{}});ctx.navigate('review');}};
}

function showDamagedStage(container,ctx,item){
  container.innerHTML=header('Review data needs recovery','This item has not been silently repaired.',`<a class="secondary" href="/api/sources/${item.document_id}">Download original locally</a>`)+notice('The saved review could not be validated. Financial records remain unchanged. Recover the most recent readable saved revision or original draft, then check it against the source before approval. If recovery is unavailable, preserve the workspace and ask authorized local IT to inspect it.','danger')+`<div id="recovery-error" aria-live="polite"></div>`+(item.status==='pending'?`<section class="panel">${item.kind==='bill'?'<label class="check-label"><input type="checkbox" id="recover-ack"><span>I will review the recovered values against the retained original.</span></label><button class="primary" id="recover-draft" disabled>Recover saved draft</button>':''}<button class="secondary" id="reject-damaged">Reject damaged draft</button></section>`:'')+`<button class="secondary" id="recovery-back">Back to review queue</button>`;
  $('#recovery-back').onclick=()=>ctx.navigate('review');
  if(item.status!=='pending')return;
  const fail=error=>$('#recovery-error').innerHTML=notice(message(error.message),'danger');
  if(item.kind==='bill'){
    $('#recover-ack').onchange=e=>$('#recover-draft').disabled=!e.target.checked;
    $('#recover-draft').onclick=async()=>{try{await api(`/staged/${item.id}/recover`,{method:'POST',body:{revision:item.revision,acknowledge:$('#recover-ack').checked}});await ctx.openStage(item.id);}catch(e){fail(e);}};
  }
  $('#reject-damaged').onclick=async()=>{if(!confirm('Reject this damaged draft? The original source will remain in local history.'))return;try{await api(`/staged/${item.id}/reject`,{method:'POST',body:{}});await ctx.navigate('review');}catch(e){fail(e);}};
}
