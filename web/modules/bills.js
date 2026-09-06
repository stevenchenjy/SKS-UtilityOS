import {api} from './api.js';
import {$,$$,esc,exactDollars,title,header,empty,notice} from './ui.js';
export async function showBills(container,ctx){
  const bills=await api('/bills');
  container.innerHTML=header('Invoice ledger','Open a reviewed version, correct a bill, or inspect its retained history.')+notice('Reporting includes active versions only. Superseded and cancelled versions remain available here. Credits use separate negative charges; replacements contain the whole corrected invoice.')+`<label class="field"><span>Invoice state</span><select id="invoice-state"><option value="active">Active invoices</option><option value="all">All versions and cancellations</option></select></label><label class="field"><span>Find an invoice</span><input id="invoice-search" type="search" placeholder="Reference, account, provider or date"></label><div id="invoice-list"></div><div class="action-row"><button class="secondary" id="invoices-previous">Previous invoices</button><span id="invoice-page"></span><button class="secondary" id="invoices-next">Next invoices</button></div>`;
  let offset=0;
  function render(){
    const query=$('#invoice-search').value.toLocaleLowerCase().trim();
    const matches=bills.filter(b=>($('#invoice-state').value==='all'||b.status==='active')&&[b.invoice_number,b.provider,b.account_alias,b.bill_date].some(v=>v.toLocaleLowerCase().includes(query)));
    const rows=matches.slice(offset,offset+100);
    $('#invoice-page').textContent=matches.length?`${offset+1}–${offset+rows.length} of ${matches.length}`:'0 invoices';
    $('#invoices-previous').disabled=offset===0;$('#invoices-next').disabled=offset+100>=matches.length;
    $('#invoice-list').innerHTML=rows.length?`<section class="panel table-panel"><div class="table-scroll"><table><thead><tr><th>Reference / account</th><th>Date</th><th>State</th><th>Current charges</th><th></th></tr></thead><tbody>${rows.map(b=>`<tr><td><strong>${esc(b.invoice_number)}</strong><small>${esc(b.provider)} · ${esc(b.account_alias)}</small></td><td>${esc(b.bill_date)}</td><td>${esc(title(b.status))}</td><td>${exactDollars(b.current_total_cents)}</td><td><button class="secondary compact" data-invoice="${b.staged_id}">Open invoice</button></td></tr>`).join('')}</tbody></table></div></section>`:empty('No invoices in this view','Approve a reviewed source to add an active invoice.');
    $$('[data-invoice]').forEach(b=>b.onclick=()=>ctx.openStage(Number(b.dataset.invoice)));
  }
  const reset=()=>{offset=0;render();};
  $('#invoice-state').onchange=reset;$('#invoice-search').oninput=reset;
  $('#invoices-previous').onclick=()=>{offset=Math.max(0,offset-100);render();};
  $('#invoices-next').onclick=()=>{offset+=100;render();};render();
}
