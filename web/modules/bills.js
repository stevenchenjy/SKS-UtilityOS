import {api} from './api.js';
import {$,$$,esc,exactDollars,title,header,empty,notice} from './ui.js';
export async function showBills(container,ctx){
  const bills=await api('/bills');
  container.innerHTML=header('Invoice ledger','Open a reviewed version, correct a bill, or inspect its retained history.')+notice('Reporting includes active versions only. Superseded and cancelled versions remain available here. Credits use separate negative charges; replacements contain the whole corrected invoice.')+`<label class="field"><span>Invoice state</span><select id="invoice-state"><option value="active">Active invoices</option><option value="all">All versions and cancellations</option></select></label><div id="invoice-list"></div>`;
  function render(){
    const rows=bills.filter(b=>$('#invoice-state').value==='all'||b.status==='active');
    $('#invoice-list').innerHTML=rows.length?`<section class="panel table-panel"><div class="table-scroll"><table><thead><tr><th>Reference / account</th><th>Date</th><th>State</th><th>Current charges</th><th></th></tr></thead><tbody>${rows.map(b=>`<tr><td><strong>${esc(b.invoice_number)}</strong><small>${esc(b.provider)} · ${esc(b.account_alias)}</small></td><td>${esc(b.bill_date)}</td><td>${esc(title(b.status))}</td><td>${exactDollars(b.current_total_cents)}</td><td><button class="secondary compact" data-invoice="${b.staged_id}">Open invoice</button></td></tr>`).join('')}</tbody></table></div></section>`:empty('No invoices in this view','Approve a reviewed source to add an active invoice.');
    $$('[data-invoice]').forEach(b=>b.onclick=()=>ctx.openStage(Number(b.dataset.invoice)));
  }
  $('#invoice-state').onchange=render;render();
}
