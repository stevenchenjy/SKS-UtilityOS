import {api,message} from './api.js';
import {$,esc,title,header,field,selectField,notice,toast} from './ui.js';

export async function showCompleteness(container,ctx,selected){
  const [data,inventory]=await Promise.all([api(`/completeness${selected?'?month='+encodeURIComponent(selected):''}`),api('/inventory')]);
  if(!container.isConnected)return;
  const accounts=inventory.accounts.filter(a=>inventory.account_meters.some(link=>link.account_id===a.id));
  container.innerHTML=header('Bill completeness','Explicit invoice expectations, counted once per account statement.')+
    notice(`Experimental coverage view as of ${data.as_of}. A received document still needs review. Unconfigured services do not establish missing bills or zero use.`,'warning')+
    `<div class="action-row">${field('Invoice month','coverage-month',data.month,'month')}<button class="secondary" id="coverage-update">Show month</button></div>`+
    `<section class="coverage-counts">${Object.entries(data.counts).map(([key,value])=>`<div class="panel"><span>${esc(title(key))}</span><strong>${value}</strong></div>`).join('')}</section>`+
    `<section class="panel table-panel"><div class="table-scroll"><table><thead><tr><th>Account / service points</th><th>Cadence</th><th>Issue / grace deadline</th><th>State</th></tr></thead><tbody>${data.rows.map(row=>`<tr><td>${esc(row.provider)} · ${esc(row.account_alias)}<small>${esc(row.meter_code)}</small></td><td>${esc(title(row.cadence))}</td><td>${row.issue_date?`${esc(row.issue_date)}<small>Missing after ${esc(row.missing_after)}</small>`:row.scope==='legacy_account'?'Legacy month expectation':'No scheduled issue'}</td><td>${esc(title(row.state))}${row.also_under_review?' · replacement also under review':''}</td></tr>`).join('')}</tbody></table></div>${data.rows.length?'':notice('No configured expectations. Confirm an account and schedule below.')}</section>`+
    `<details class="panel"><summary>Confirm an expected account and service cadence</summary>
      <p>One expected statement covers this account’s service points. A schedule replaces its legacy meter expectations in this view; earlier decisions remain retained. Invoice issue dates do not set service-period lengths. Day 29–31 is clamped to month end.</p>
      <form id="coverage-config">
      ${selectField('Account / service relationship','coverage-account',[['','Select a confirmed account'],...accounts.map(a=>[String(a.id),`${a.provider} · ${a.alias}`])],'')}
      ${selectField('Expected cadence','cadence',[['monthly','Monthly bill'],['every_two_months','Every two months'],['delivery','Delivery-based invoice'],['irregular','Irregular bill']],'monthly')}
      <div class="form-grid two">${selectField('Anchor month for every-two-month bills','anchor_month',Array.from({length:12},(_,i)=>[String(i+1),new Date(2026,i,1).toLocaleString('en-US',{month:'long'})]),'1')}${field('Expected issue day','issue_day','15','number','min="1" max="31" required')}${field('Grace days after issue','grace_days','7','number','min="0" max="60" required')}${selectField('Manual retrieval plan (no automatic downloads)','retrieval_cadence',[['manual','When staff chooses'],['on_issue','After expected issue'],['weekly','Weekly staff check'],['monthly','Monthly staff check']],'manual')}${field('Effective from (inclusive)','effective_from',data.month+'-01','date','required')}${field('Effective to (inclusive, optional)','effective_to','','date')}</div>
      <p>Usage sampling comes from each usage file’s timestamps and measurement semantics; it is independent of this billing and retrieval plan.</p>
      <label class="check-label"><input type="checkbox" id="coverage-enabled" checked><span>Expectation is active</span></label>
      <details><summary>Account-specific month exceptions</summary><p>Add up to 24 exceptions. A skipped month is not missing. An extra or rescheduled issue stays in its chosen invoice month.</p><div id="schedule-exceptions"></div><button type="button" class="secondary" id="add-exception">Add month exception</button></details>
      ${field('Reason for coverage decision','coverage-reason','','text','required maxlength="500"')}
      <label class="check-label"><input type="checkbox" id="coverage-ack" required><span>I confirmed this account’s statement cadence and dates. This does not establish complete campus coverage.</span></label>
      <button class="primary" type="submit">Save expectation</button><div id="coverage-error" aria-live="polite"></div></form>
      <details><summary>Retained legacy meter expectations</summary><p>${data.configuration.length} legacy decisions retained. Existing monthly, delivery and irregular expectations remain in use until an account schedule replaces them.</p></details>
    </details>`;
  let exceptions=[];
  function renderExceptions(){
    $('#schedule-exceptions').innerHTML=exceptions.map((item,i)=>`<div class="panel" data-exception="${i}"><div class="form-grid two">${field('Exception month',`exception-month-${i}`,item.month,'month','required')}${selectField('Exception action',`exception-action-${i}`,[['yes','Expect a statement'],['no','Skip this month']],item.expected?'yes':'no')}${field('Exception issue date',`exception-date-${i}`,item.issue_date||'','date')}${field('Exception reason',`exception-reason-${i}`,item.reason,'text','required maxlength="500"')}</div><button type="button" class="text-button" data-remove-exception="${i}" aria-label="Remove exception ${i+1}">Remove exception</button></div>`).join('');
    container.querySelectorAll('[data-remove-exception]').forEach(b=>b.onclick=()=>{exceptions=collectExceptions();const index=Number(b.dataset.removeException);exceptions.splice(index,1);renderExceptions();($(`[data-remove-exception="${Math.min(index,exceptions.length-1)}"]`)||$('#add-exception')).focus();});
  }
  function collectExceptions(){return exceptions.map((_,i)=>({month:$(`[name=exception-month-${i}]`).value,expected:$(`[name=exception-action-${i}]`).value==='yes',issue_date:$(`[name=exception-date-${i}]`).value||null,reason:$(`[name=exception-reason-${i}]`).value}));}
  $('#add-exception').onclick=()=>{if(exceptions.length>=24)return;exceptions=collectExceptions();exceptions.push({month:data.month,expected:false,issue_date:null,reason:''});renderExceptions();$(`[name=exception-month-${exceptions.length-1}]`).focus();};
  $('#coverage-update').onclick=()=>ctx.refresh('completeness',$('[name=coverage-month]').value);
  $('[name=coverage-account]').onchange=e=>{
    const before=data.schedules.find(x=>x.account_id===Number(e.target.value));
    for(const [key,value] of Object.entries({cadence:'monthly',anchor_month:1,issue_day:15,grace_days:7,retrieval_cadence:'manual',effective_from:data.month+'-01',effective_to:''}))$(`[name=${key}]`).value=before?.[key]??value;
    $('#coverage-enabled').checked=before?.enabled??true;
    $('[name=coverage-reason]').value='';$('#coverage-ack').checked=false;
    exceptions=structuredClone(before?.exceptions||[]);renderExceptions();
  };
  $('[name=coverage-account]').required=true;
  $('#coverage-config').onsubmit=async e=>{
    e.preventDefault();
    const submit=$('button[type=submit]',e.currentTarget);submit.disabled=true;
    $('#coverage-update').disabled=true;$('[name=coverage-month]').disabled=true;
    try{
      const account_id=Number($('[name=coverage-account]').value),before=data.schedules.find(x=>x.account_id===account_id);
      if(!account_id)throw new Error('CONFIRMED_ACCOUNT_METER_RELATIONSHIP_REQUIRED');
      const body={scope:'account',account_id,revision:before?.revision||0,enabled:$('#coverage-enabled').checked,acknowledge:$('#coverage-ack').checked,exceptions:collectExceptions(),reason:$('[name=coverage-reason]').value};
      for(const key of ['anchor_month','issue_day','grace_days'])body[key]=Number($(`[name=${key}]`).value);
      for(const key of ['cadence','retrieval_cadence','effective_from','effective_to'])body[key]=$(`[name=${key}]`).value;
      await api('/completeness',{method:'POST',body});if(!container.isConnected)return;toast('Account expectation saved.');ctx.refresh('completeness',data.month);
    }catch(error){if(!container.isConnected)return;$('#coverage-error').innerHTML=notice(message(error.message),'danger');submit.disabled=false;$('#coverage-update').disabled=false;$('[name=coverage-month]').disabled=false;}
  };
}
