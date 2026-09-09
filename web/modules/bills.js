import {api} from './api.js';
import {$,$$,esc,exactDollars,title,monthLabel,header,empty,notice} from './ui.js';
export async function showBills(container,ctx,filters){
  const selected={building:'all',month:'',state:'active',search:'',...ctx.billsFilters,...filters};
  const query=new URLSearchParams({building:selected.building});
  if(selected.month)query.set('month',selected.month);
  const [bills,inventory]=await Promise.all([api(`/bills?${query}`),api('/inventory')]);
  if(!container.isConnected)return;
  ctx.billsFilters=selected;
  const options=[{id:'all',name:'All buildings'},...inventory.buildings.map(b=>({...b,id:String(b.id)})),{id:'unassigned',name:'Unassigned / shared'}];
  const label=options.find(b=>b.id===selected.building)?.name||'All buildings',scoped=selected.building!=='all';
  container.innerHTML=header('Invoice ledger','Open a reviewed version, correct a bill, or inspect its retained history.')+notice('Reporting includes active versions only. Superseded and cancelled versions remain available here. Credits use separate negative charges; replacements contain the whole corrected invoice.')+
    `<div class="invoice-filters"><label class="field"><span>Building</span><select id="invoice-building" aria-label="Building">${options.map(b=>`<option value="${esc(b.id)}" ${b.id===selected.building?'selected':''}>${esc(b.name)}</option>`).join('')}</select></label><label class="field"><span>Invoice month</span><input id="invoice-month" type="month" value="${esc(selected.month||'')}"></label><label class="field"><span>Invoice state</span><select id="invoice-state" aria-label="Invoice state"><option value="active" ${selected.state==='active'?'selected':''}>Active invoices</option><option value="all" ${selected.state==='all'?'selected':''}>All versions and cancellations</option></select></label><label class="field"><span>Find an invoice</span><input id="invoice-search" type="search" value="${esc(selected.search)}" placeholder="Reference, account, provider or date"></label></div><div class="action-row"><button class="secondary compact" id="clear-invoice-filters">Clear filters</button><button class="text-button" id="invoice-overview">View building overview</button></div><p class="caption" id="invoice-scope">${esc(label)} · ${selected.month?esc(monthLabel(selected.month)):'All invoice months'}. ${scoped?'Building charges include matching service lines only; the full invoice may also cover other buildings. Current meter mappings apply to every retained version.':'Current charges are the full invoice total.'}</p><div id="invoice-list"></div><div class="action-row"><button class="secondary" id="invoices-previous">Previous invoices</button><span id="invoice-page" aria-live="polite"></span><button class="secondary" id="invoices-next">Next invoices</button></div>`;
  let offset=0;
  function render(){
    selected.search=$('#invoice-search').value;selected.state=$('#invoice-state').value;
    const query=selected.search.toLocaleLowerCase().trim();
    const matches=bills.filter(b=>(selected.state==='all'||b.status==='active')&&[b.invoice_number,b.provider,b.account_alias,b.bill_date].some(v=>v.toLocaleLowerCase().includes(query)));
    const rows=matches.slice(offset,offset+100);
    $('#invoice-page').textContent=matches.length?`${offset+1}–${offset+rows.length} of ${matches.length}`:'0 invoices';
    $('#invoices-previous').disabled=offset===0;$('#invoices-next').disabled=offset+100>=matches.length;
    $('#invoice-list').innerHTML=rows.length?`<section class="panel table-panel"><div class="table-scroll"><table><thead><tr><th>Reference / account</th><th>Date</th><th>State</th>${scoped?'<th class="numeric">Building charges</th>':''}<th class="numeric">${scoped?'Full invoice total':'Current charges'}</th><th></th></tr></thead><tbody>${rows.map(b=>`<tr><td><strong>${esc(b.invoice_number)}</strong><small>${esc(b.provider)} · ${esc(b.account_alias)}</small></td><td>${esc(b.bill_date)}</td><td>${esc(title(b.status))}</td>${scoped?`<td class="numeric">${exactDollars(b.matched_total_cents)}</td>`:''}<td class="numeric">${exactDollars(b.current_total_cents)}</td><td><button class="secondary compact" data-invoice="${b.staged_id}">Open invoice</button></td></tr>`).join('')}</tbody></table></div></section>`:empty('No invoices match these filters','Change the building, month, state or search text, or clear the filters to see all active invoices.');
    $$('[data-invoice]').forEach(b=>b.onclick=()=>ctx.openStage(Number(b.dataset.invoice)));
  }
  const reset=()=>{offset=0;render();};
  const change=patch=>ctx.refresh('bills',{...selected,...patch});
  $('#invoice-state').onchange=reset;$('#invoice-search').oninput=reset;
  $('#invoice-building').onchange=e=>change({building:e.target.value});
  $('#invoice-month').onchange=e=>{if(e.target.validity.valid)change({month:e.target.value});};
  $('#clear-invoice-filters').onclick=()=>change({building:'all',month:'',state:'active',search:''});
  $('#invoice-overview').onclick=()=>ctx.navigate('overview',{building:selected.building,month:selected.month||null});
  $('#invoices-previous').onclick=()=>{offset=Math.max(0,offset-100);render();};
  $('#invoices-next').onclick=()=>{offset+=100;render();};render();
}
