import {showInbox} from './modules/inbox.js';
import {showCompleteness} from './modules/completeness.js';
import {api,setCsrf,message} from './modules/api.js';
import {$,$$,esc,icon,toast,openDialog,closeDialog,notice} from './modules/ui.js';
import {showBills} from './modules/bills.js';
import {showOverview} from './modules/overview.js';
import {showReview,showStage} from './modules/review.js';
import {showInventory} from './modules/inventory.js';
import {showIntervals} from './modules/intervals.js';
import {showSupport} from './modules/support.js';
let meta,route='overview',renderGeneration=0,renderBusy=false;
const views={inbox:showInbox,completeness:showCompleteness,overview:showOverview,bills:showBills,review:showReview,inventory:showInventory,intervals:showIntervals,support:showSupport};
const nav=[['overview','Overview'],['bills','Invoice ledger'],['inbox','Utility Inbox'],['completeness','Bill completeness'],['review','Review queue'],['inventory','Utility inventory'],['intervals','Interval data'],['support','Privacy & support']];
const context={get mode(){return meta.mode;},navigate,refresh,openStage,openImport,updatePending(count){const n=$('#pending-count');if(n)n.textContent=count;}};

async function boot(){
  try{
    meta=await api('/meta');
    if(meta.authenticated){const session=await api('/session');setCsrf(session.csrf);shell();navigate('overview');}else{login();}
  }catch(error){$('#app').innerHTML=notice('The local service could not be reached. Start the application from the launcher and reload.','danger');}
}
function login(){
  $('#app').innerHTML=`<main class="login-screen"><div class="login-card"><div class="brand-symbol">${icon('inventory')}</div><h1>SKS UtilityOS</h1><p class="login-subtitle">A local home for campus utility bills.</p>${meta.mode==='demo'?notice('Synthetic demonstration. Every building, meter, and amount in this workspace is fictional.','warning'):notice('Staff workspace. Your local app passphrase is separate from all utility portal credentials.')}
  <form id="login-form">${meta.mode==='demo'?'':`<label class="field"><span>Local app passphrase</span><input type="password" id="password" autocomplete="current-password" required minlength="12" maxlength="256"></label>`}<div id="login-error"></div><button class="primary wide" type="submit">${meta.mode==='demo'?'Open synthetic demo':'Unlock local workspace'}</button></form><p class="caption">Version ${esc(meta.version)} · Runs on this computer · No portal access</p></div></main>`;
  $('#login-form').onsubmit=async e=>{e.preventDefault();const button=$('button',e.currentTarget);button.disabled=true;try{const result=await api('/login',{method:'POST',body:{password:meta.mode==='demo'?'synthetic-demo-only':$('#password').value}});setCsrf(result.csrf);shell();navigate('overview');}catch(error){$('#login-error').innerHTML=notice(message(error.message),'danger');button.disabled=false;}};
}
function shell(){
  $('#app').innerHTML=`<div class="app-shell"><aside class="sidebar"><a class="brand" href="#overview"><span class="brand-symbol">${icon('inventory')}</span><span>UtilityOS<small>STORM KING · LOCAL PILOT</small></span></a><nav aria-label="Main navigation">${nav.map(([id,label])=>`<button data-nav="${id}">${icon(id)}<span>${label}</span>${id==='review'?'<span class="nav-count" id="pending-count">0</span>':''}</button>`).join('')}</nav><div class="sidebar-bottom"><div class="local-status"><i></i> Local-only workspace</div><small>Version ${esc(meta.version)}</small><button id="logout">${icon('logout')} Lock workspace</button></div></aside><div class="main-column"><header class="topbar"><span>Campus operations <span class="slash">/</span> Utility ledger</span><span class="mode-label ${meta.mode==='demo'?'demo':''}">${meta.mode==='demo'?'Synthetic demo':'Staff workspace'}</span></header>${meta.mode==='demo'?'<div class="demo-banner">Demonstration data only. All buildings, providers, and amounts shown here are fictional.</div>':''}<main id="content" tabindex="-1"></main></div></div>`;
  $$('[data-nav]').forEach(button=>button.onclick=()=>navigate(button.dataset.nav));
  $('.brand').onclick=e=>{e.preventDefault();navigate('overview');};
  $('#logout').onclick=async()=>{await api('/logout',{method:'POST',body:{}});setCsrf('');login();};
}
async function navigate(next){route=next;await refresh(next);}
async function refresh(next,arg){
  if(renderBusy)return;
  renderBusy=true;
  route=next;
  $$('[data-nav]').forEach(button=>{button.classList.toggle('active',button.dataset.nav===next);if(button.dataset.nav===next)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');});
  const target=$('#content'),generation=++renderGeneration;
  if(!target)return;
  target.innerHTML='<p class="loading">Loading local records...</p>';
  $$('[data-nav]').forEach(button=>button.disabled=true);
  try{await views[next](target,context,arg);if(generation===renderGeneration)document.title=`${nav.find(n=>n[0]===next)?.[1]||'Ledger'} | SKS UtilityOS`;}
  catch(error){handleError(error,target);}
  finally{renderBusy=false;$$('[data-nav]').forEach(button=>button.disabled=false);}
}
async function openStage(id){
  const target=$('#content');
  try{await showStage(target,context,id);window.scrollTo(0,0);}
  catch(error){handleError(error,target);}
}
function handleError(error,target){if(error.status===401){toast('Local session expired.',true);login();}else{target.innerHTML=notice(message(error.message),'danger');}}
function openImport(){
  openDialog(`<div class="modal-heading"><div><h2>Import a source file</h2><p>The file stays in this local workspace.</p></div><button class="close-button" data-close aria-label="Close import">×</button></div><form id="import-form"><label class="dropzone" id="dropzone">${icon('upload')}<strong>Choose or drop CSV, XML, or PDF files</strong><span>Maximum 8 MB per file · Up to 25 files per batch</span><input type="file" id="import-file" accept=".csv,.xml,.pdf" multiple required aria-label="Source file"></label><div class="file-help"><p><strong>CSV:</strong> Use the supplied bill template. Each line retains its service period and unit.</p><p><strong>XML:</strong> The current parser accepts incremental electricity in the supported Green Button format.</p><p><strong>PDF:</strong> Local text extraction and optional OCR propose fields with source evidence. Staff review is always required.</p></div>${meta.mode==='demo'?'<label class="check-label"><input type="checkbox" id="synthetic-confirm" required><span>I confirm this file contains synthetic data only.</span></label>':''}<div id="import-error"></div><div class="action-row"><button class="primary" type="submit">Import for review</button><span class="muted">Totals update after approval.</span></div></form><div class="sample-links"><span>Try a synthetic source</span><a href="/api/samples/demo-import.csv">CSV invoice</a><a href="/api/samples/demo-intervals.xml">Electricity XML</a><a href="/api/samples/demo-invoice.pdf">PDF invoice</a><a href="/api/samples/blank-bill-template.csv">Blank template</a><a href="/api/intake-samples/electricity-digital.pdf">Extractable fictional PDF</a><a href="/api/intake-samples/electricity-scan.pdf">Fictional scan (optional OCR)</a><a href="/api/intake-samples/layout-v2.pdf">Fictional layout v2</a></div>`);
  const input=$('#import-file');
  const zone=$('#dropzone');
  const picked=()=>{if(input.files.length)$('strong',zone).textContent=input.files.length===1?input.files[0].name:`${input.files.length} files selected`;};
  input.onchange=picked;
  zone.ondragover=e=>{e.preventDefault();zone.classList.add('dragging');};
  zone.ondragleave=()=>zone.classList.remove('dragging');
  zone.ondrop=e=>{e.preventDefault();zone.classList.remove('dragging');input.files=e.dataTransfer.files;picked();};
  $('#import-form').onsubmit=async e=>{
    e.preventDefault();const files=[...input.files];if(!files.length)return;
    const target=$('#import-error'),button=$('button[type=submit]',e.currentTarget),dialog=$('dialog');
    if(files.length>25){target.innerHTML=notice('Choose up to 25 files per batch.','danger');return;}
    button.disabled=true;input.disabled=true;
    const synthetic=meta.mode==='demo'&&$('#synthetic-confirm').checked,results=[];
    for(const file of files){
      target.innerHTML=notice(`Processing ${results.length+1} of ${files.length}: ${file.name}`);
      try{
        if(file.size>8*1024*1024)throw new Error('FILE_EXCEEDS_8_MB');
        const result=await api(files.length===1?'/import':'/intake',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Filename':encodeURIComponent(file.name),'X-Synthetic-Data':String(synthetic)},body:file});
        results.push({...result,filename:file.name});
      }catch(error){results.push({filename:file.name,state:'failed_safely',code:error.message,count:0,staged_ids:[]});}
    }
    if(!dialog.isConnected)return;
    if(files.length===1&&results[0].count){closeDialog();toast(`${results[0].count} item(s) added for review.`);if(results[0].count===1)await openStage(results[0].staged_ids[0]);else await navigate('review');}
    else if(files.length===1){target.innerHTML=notice(message(results[0].code),'danger');button.disabled=false;input.disabled=false;}
    else{target.innerHTML=results.map(row=>`<p>${esc(row.filename)} · ${esc(row.state.replaceAll('_',' '))}${row.code?` · ${esc(message(row.code))}`:''}</p>`).join('')+'<button type="button" class="secondary" id="open-intake-results">Open Utility Inbox</button>';button.hidden=true;$('#open-intake-results').onclick=()=>{closeDialog();navigate('inbox');};}
  };
}
window.addEventListener('unhandledrejection',()=>toast('A local action failed. Reload and reproduce the issue with synthetic data.',true));
boot();
