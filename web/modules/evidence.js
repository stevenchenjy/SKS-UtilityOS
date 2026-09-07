import {$,$$,esc,title,field,notice} from './ui.js';
const headers={provider:'provider',account_alias:'account_identifier',invoice_number:'invoice_number',bill_date:'invoice_date',current_total:'invoice_total'};
const service={meter_code:'meter_identifier',building:'building',commodity:'utility_type',unit:'consumption_unit',period_start:'period_start',period_end:'period_end',usage:'consumption_quantity',current_charge:'current_charge',usage_role:'quantity_treatment',read_type:'reading_type'};
const label=key=>key.replace(/^services\.(\d+)\./,(_,i)=>`Service ${Number(i)+1} · `).replaceAll('_',' ');
const states={high_evidence:'High evidence · verify',needs_review:'Requires review',missing:'Missing from extraction',conflict:'Extraction conflict'};

export function evidencePanel(item){
  if(!item.intake)return '';
  const extraction=item.intake.extraction;
  return `<aside class="source-evidence panel" aria-label="Original document evidence"><h2>Original document</h2><p class="caption">${esc(title(extraction.pdf_kind))} · ${esc(title(extraction.layout_state))}</p>${extraction.template_version?`<p class="caption">Template: ${esc(extraction.template_version)}</p>`:''}<p class="caption">Select a field’s evidence button to see its source region. OCR and unknown layouts always require review.</p><div class="action-row"><label>Page <select id="evidence-page" aria-label="Source page">${extraction.pages.map(p=>`<option value="${p.number}">${p.number}</option>`).join('')}</select></label><label>Zoom <select id="evidence-zoom" aria-label="Source zoom"><option value="1">Fit width</option><option value="1.5">150%</option><option value="2">200%</option><option value="3">300%</option></select></label><button class="secondary compact" id="toggle-evidence">Hide source preview</button></div><div id="evidence-description" aria-live="polite"></div><div class="source-scroll" id="source-scroll"><canvas id="source-canvas" role="img" aria-label="Retained PDF page with selected evidence highlight"></canvas></div><p id="evidence-error" class="caption"></p><a href="/api/sources/${item.document_id}">Download unchanged original</a></aside>`;
}

export function detailPanel(item,readonly){
  if(!item.intake)return '';
  const info=item.intake;
  return `<details class="panel intake-details"><summary>Additional extracted bill details</summary><p class="caption">Demand, due dates, balances and charge components stay with the reviewed record. Current charges and service quantities above control ledger totals. Empty means absent; do not invent amounts.</p><div class="form-grid two">${info.detail_keys.map(key=>`<div data-detail="${esc(key)}">${field(label(key),`detail-${key}`,info.reviewed_values[key]??'','text',`${readonly?'disabled':''} maxlength="120"`)}<button type="button" class="text-button evidence-link" data-evidence="${esc(key)}">${info.differences.some(d=>d.field===key)?'Manually corrected · show original':esc(states[info.extraction.fields[key].state])}</button></div>`).join('')}</div></details>`;
}

export function collectDetails(item){
  if(!item.intake)return undefined;
  return Object.fromEntries($$('[data-detail]').map(node=>[node.dataset.detail,$('input',node).value]));
}

export function bindEvidence(item){
  if(!item.intake)return;
  const extraction=item.intake.extraction,info=item.intake;
  let selected=null,image=null,serial=0;
  const canvas=$('#source-canvas'),scroll=$('#source-scroll'),description=$('#evidence-description');
  const pageSelect=$('#evidence-page'),zoom=$('#evidence-zoom'),errorNode=$('#evidence-error'),toggle=$('#toggle-evidence');
  zoom.value=window.innerWidth<600?'2':'1.5';
  function draw(){
    if(!image||!canvas.isConnected)return;
    canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
    const context=canvas.getContext('2d');context.drawImage(image,0,0);
    const page=extraction.pages.find(p=>p.number===Number(pageSelect.value));
    if(selected?.page===page.number&&selected.bbox){
      const [x0,y0,x1,y1]=selected.bbox,scaleX=canvas.width/page.width,scaleY=canvas.height/page.height;
      context.fillStyle='rgba(255,190,55,0.25)';context.strokeStyle='#b25500';context.lineWidth=3;
      context.fillRect(x0*scaleX,y0*scaleY,(x1-x0)*scaleX,(y1-y0)*scaleY);
      context.strokeRect(x0*scaleX,y0*scaleY,(x1-x0)*scaleX,(y1-y0)*scaleY);
    }
    canvas.style.width=`${Number(zoom.value)*100}%`;
    if(selected?.page===page.number&&selected.bbox){
      requestAnimationFrame(()=>{scroll.scrollTop=Math.max(0,selected.bbox[1]/page.height*canvas.offsetHeight-60);});
    }
  }
  async function loadPage(){
    const page=extraction.pages.find(p=>p.number===Number(pageSelect.value));
    if(!page){errorNode.textContent='Preview unavailable. Use the unchanged original and manual entry.';return;}
    const generation=++serial;errorNode.textContent='Rendering locally…';
    const next=new Image();next.onload=()=>{if(generation!==serial||!canvas.isConnected)return;image=next;draw();errorNode.textContent='Page rendered locally. Source bytes are unchanged.';};
    next.onerror=()=>{if(generation===serial)errorNode.textContent='Preview unavailable. Download the original for review.';};
    next.src=`/api/sources/${item.document_id}/pages/${page.number}?rotation=${page.rotation}`;
  }
  function select(path){
    selected=extraction.fields[path];
    if(!selected)return;
    description.innerHTML=`<p><strong>${esc(title(label(path)))}</strong><br>${esc(states[selected.state])}</p><p class="evidence-raw">Source: ${esc(selected.raw??'No source value found')}<br>Proposed: ${esc(selected.value??'Missing')}</p><details><summary class="caption">${esc(selected.method)}${selected.page?` · Page ${selected.page}`:''} · extraction provenance</summary><p class="caption">${esc(selected.parser_version)}</p></details>`;
    if(selected.page){
      scroll.hidden=false;toggle.textContent='Hide source preview';
      if(pageSelect.value!==String(selected.page)){pageSelect.value=String(selected.page);loadPage();}else draw();
    }
    if(window.innerWidth<900)description.scrollIntoView({block:'start',behavior:'instant'});
  }
  for(const input of $$('input,select',$('#bill-editor'))){
    const line=input.closest('[data-line]');
    let key=line?`services.${line.dataset.line}.${service[input.name]}`:headers[input.name];
    if(line&&input.name==='usage'&&$('[name=usage_role]',line)?.value==='delivery')key=`services.${line.dataset.line}.delivery_quantity`;
    const evidence=extraction.fields[key];if(!evidence)continue;
    const button=document.createElement('button');button.type='button';button.className='text-button evidence-link';button.dataset.evidence=key;
    const corrected=info.differences.some(d=>d.field===key);
    button.textContent=corrected?'Manually corrected · show original':states[evidence.state];
    button.dataset.state=corrected?'corrected':evidence.state;input.parentElement.append(button);
    if(!input.disabled)input.addEventListener('input',()=>{button.textContent='Edited · show original';button.dataset.state='corrected';});
  }
  $$('[data-evidence]').forEach(button=>button.onclick=e=>{e.preventDefault();select(button.dataset.evidence);});
  $$('[data-detail] input:not(:disabled)').forEach(input=>input.addEventListener('input',()=>{
    $('[data-evidence]',input.closest('[data-detail]')).textContent='Edited · show original';
  }));
  pageSelect.onchange=()=>{selected=null;loadPage();};zoom.onchange=draw;
  toggle.onclick=()=>{scroll.hidden=!scroll.hidden;toggle.textContent=scroll.hidden?'Show source preview':'Hide source preview';};
  loadPage();select('invoice_total');
}
