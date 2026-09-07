import {api,message} from './api.js';
import {$,$$,esc,exactDollars,title,field,selectField,notice,toast,openDialog,closeDialog} from './ui.js';

export function lifecyclePanel(item){
  const bill=item.bill;
  const origin=item.original_bill;
  const replacementState=item.status==='pending'?(origin?.status==='active'?'The original continues to count until this full replacement is approved.':'The original is no longer active. Choose the current version or reject this draft.'):item.status==='approved'?'Approval superseded the original; earlier versions are excluded from reporting.':'This rejected draft did not replace the original.';
  let html=origin?notice(`Replacement of ${origin.invoice_number} (${exactDollars(origin.current_total_cents)}). ${replacementState} Reason: ${item.correction_reason}`,item.status==='pending'?'warning':'info'):'';
  if(item.status==='pending')return html+`<section class="panel"><h2>Saved review</h2><p>Save partial entry before leaving this page. Saved revisions remain in private history.</p><div class="action-row"><button class="secondary" id="save-draft">Save draft</button><button class="secondary" id="link-rebill">${origin?'Change replacement link':'Use as replacement / rebill'}</button></div><p class="caption">For an independent credit, keep this as a separate invoice with negative charges and zero quantity on charges-only lines. Replacements contain the full corrected invoice, not only the difference.</p><div id="lifecycle-error"></div></section>`;
  if(!bill)return html+notice('This review is closed. The source and saved revisions are retained.');
  html+=`<section class="panel"><h2>Invoice history · ${esc(title(bill.status))}</h2>`+notice(bill.status==='active'?'This version contributes to reporting. A correction creates a new draft for full review.':`This version is ${bill.status} and contributes no charges or quantities to current reporting.`)+
    `<div class="table-scroll"><table><thead><tr><th>Version / reference</th><th>State</th><th>Charges</th><th></th></tr></thead><tbody>${bill.versions.map(v=>`<tr><td>${v.id} · ${esc(v.invoice_number)}</td><td>${esc(title(v.status))}</td><td>${exactDollars(v.current_total_cents)}</td><td><button class="secondary compact" data-version="${v.staged_id}">View version ${v.id}</button></td></tr>`).join('')}</tbody></table></div>`+
    `<ul>${bill.history.map(h=>`<li>${esc(h.at)} · ${esc(title(h.action))}${h.reason?` · ${esc(h.reason)}`:''}</li>`).join('')}</ul>`+
    (bill.status==='active'?`<div class="action-row"><button class="primary" id="start-correction">Correct approved invoice</button><button class="secondary" id="cancel-invoice">Cancel invoice</button></div><p class="caption">A correction reuses the retained source for a transcription fix. For a new supplier document, import it first and choose “Use as replacement / rebill.” Cancellation removes this whole invoice from reporting; it does not create a financial credit or undo a prior replacement.</p>`:'')+`<div id="lifecycle-error"></div></section>`;
  return html;
}

export function bindLifecycle(item,ctx,collect,details=()=>undefined){
  const fail=error=>{const target=$('#lifecycle-error');if(target)target.innerHTML=notice(message(error.message),'danger');else toast(message(error.message),true);};
  $$('[data-version]').forEach(b=>b.onclick=()=>ctx.openStage(Number(b.dataset.version)));
  if(item.status==='pending'){
    $('#save-draft').onclick=async()=>{try{await api(`/staged/${item.id}/draft`,{method:'POST',body:{payload:collect(),intake_details:details(),revision:item.revision,correction_of:item.correction_of,reason:item.correction_reason}});toast('Draft saved locally.');await ctx.openStage(item.id);}catch(e){fail(e);}};
    $('#link-rebill').onclick=async()=>{try{
      const bills=(await api('/bills')).filter(b=>b.status==='active');
      openDialog(`<h2>Choose the invoice being replaced</h2>${notice('Approval replaces the entire selected invoice. Check provider, account, reference, total, and every service line. A separate credit should stay independent.','warning')}<form id="replacement-form">${selectField('Original active invoice','original',[['','Independent invoice / credit'],...bills.map(b=>[String(b.id),`${b.provider} · ${b.account_alias} · ${b.invoice_number} · ${exactDollars(b.current_total_cents)}`])],String(item.correction_of||''))}${field('Reason for replacement','reason',item.correction_reason,'text','maxlength="500"')}<div id="replacement-error"></div><div class="action-row"><button class="primary" type="submit">Save replacement link</button><button type="button" class="secondary" data-close>Close</button></div></form>`);
      $('#replacement-form').onsubmit=async e=>{e.preventDefault();try{await api(`/staged/${item.id}/draft`,{method:'POST',body:{payload:collect(),intake_details:details(),revision:item.revision,correction_of:$('[name=original]').value?Number($('[name=original]').value):null,reason:$('[name=reason]').value}});closeDialog();await ctx.openStage(item.id);}catch(error){$('#replacement-error').innerHTML=notice(message(error.message),'danger');}};
    }catch(e){fail(e);}};
  }
  if(item.bill?.status==='active'){
    const action=cancel=>{
      openDialog(`<h2>${cancel?'Cancel this invoice':'Start a correction'}</h2>${notice(`${item.payload.invoice_number} · ${exactDollars(item.bill.current_total_cents)}. ${cancel?'The entire active invoice will leave reporting. Previous versions stay excluded. The source and audit history remain available.':'The original continues to count until you review and approve the full replacement.'}`,cancel?'warning':'info')}<form id="invoice-action">${field('Reason','reason','','text','required maxlength="500"')}${cancel?'<label class="check-label"><input id="cancel-confirm" type="checkbox" required><span>I confirm that this whole invoice should be excluded from reporting.</span></label>':''}${cancel&&ctx.mode==='staff'?field('Confirm local app passphrase','current_passphrase','','password','autocomplete="current-password" maxlength="256"'):''}<div id="action-error"></div><div class="action-row"><button class="primary" type="submit">${cancel?'Confirm cancellation':'Create correction draft'}</button><button type="button" class="secondary" data-close>Close</button></div></form>`);
      $('#invoice-action').onsubmit=async e=>{e.preventDefault();try{const result=await api(`/bills/${item.bill.id}/${cancel?'cancel':'correct'}`,{method:'POST',body:{reason:$('[name=reason]').value,acknowledge:cancel?$('#cancel-confirm').checked:false,current_passphrase:$('[name=current_passphrase]')?.value}});closeDialog();await ctx.openStage(cancel?item.id:result.staged_id);toast(cancel?'Invoice cancelled. History retained.':'Correction draft created.');}catch(error){$('#action-error').innerHTML=notice(message(error.message),'danger');}};
    };
    $('#start-correction').onclick=()=>action(false);
    $('#cancel-invoice').onclick=()=>action(true);
  }
}
