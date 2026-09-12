export const $ = (selector, scope = document) => scope.querySelector(selector);
export const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
export const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
const wholeCurrency = new Intl.NumberFormat('en-US', { style:'currency', currency:'USD', maximumFractionDigits:0 });
const exactCurrency = new Intl.NumberFormat('en-US', { style:'currency', currency:'USD' });
export const dollars = cents => wholeCurrency.format((cents || 0) / 100);
export const exactDollars = cents => exactCurrency.format((cents || 0) / 100);
// Group a decimal string without passing stored quantities through binary floats.
export function quantity(value) {
  let raw=String(value ?? '0');
  const exponent=raw.match(/^(-?)(\d+)(?:\.(\d+))?[eE]([+-]?\d+)$/);
  if(exponent){
    const [,sign,whole,fraction='',power]=exponent,point=whole.length+Number(power),digits=whole+fraction;
    if(Math.abs(Number(power))>100)return '—';
    raw=sign+(point<=0?'0.'+'0'.repeat(-point)+digits:point>=digits.length?digits+'0'.repeat(point-digits.length):digits.slice(0,point)+'.'+digits.slice(point));
  }
  const match=raw.match(/^(-?)(\d+)(?:\.(\d+))?$/);
  if(!match)return '—';
  const [,sign,whole,fraction='']=match,tail=fraction.replace(/0+$/,'');
  return sign+whole.replace(/^0+(?=\d)/,'').replace(/\B(?=(\d{3})+(?!\d))/g,',')+(tail?'.'+tail:'');
}
export const title = value => String(value || '').replaceAll('_',' ').replace(/\b\w/g, c => c.toUpperCase());
export function monthLabel(value, short=false) { return value ? new Date(`${value}-15T12:00:00Z`).toLocaleDateString('en-US',{month:short?'short':'long',year:'numeric',timeZone:'UTC'}) : 'No approved bills'; }
export const localTime = epoch => new Date(epoch*1000).toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'});
const paths = {
 overview:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
 review:'M7 3h10v3H7z M7 4H4v17h16V4h-3 M8 12l2 2 5-5 M8 18h8',
 inventory:'M3 21h18 M5 21V7l7-4 7 4v14 M9 9h1 M14 9h1 M9 13h1 M14 13h1 M10 21v-4h4v4',
 intervals:'M3 20h18 M4 15l4-6 4 4 4-9 4 4',
 support:'M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6z M8 12l3 3 5-6',
 upload:'M12 16V3 M7 8l5-5 5 5 M4 16v5h16v-5',
 arrow:'M5 12h14 M14 7l5 5-5 5',
 logout:'M10 4H4v16h6 M9 12h12 M17 8l4 4-4 4'
};
export function icon(name) { return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="${paths[name] || paths.overview}"/></svg>`; }
export function notice(text, tone='info') { return `<div class="notice ${tone}">${esc(text)}</div>`; }
export function toast(text, error=false) { const node=$('#toast'); node.textContent=text; node.className=`visible${error?' error':''}`; clearTimeout(node._timer); node._timer=setTimeout(()=>node.className='',6000); }
export function header(heading, description, action='') { return `<div class="page-heading"><div><h1>${esc(heading)}</h1><p>${esc(description)}</p></div>${action}</div>`; }
export function empty(heading, description, action='') { return `<div class="empty-state">${icon('inventory')}<h2>${esc(heading)}</h2><p>${esc(description)}</p>${action}</div>`; }
export function field(label,name,value='',type='text',extra='') { return `<label class="field"><span>${esc(label)}</span><input name="${esc(name)}" type="${type}" value="${esc(value)}" ${type==='password'||/\bautocomplete\s*=/.test(extra)?'':'autocomplete="off"'} ${extra}></label>`; }
export function selectField(label,name,options,value) { return `<label class="field"><span>${esc(label)}</span><select name="${esc(name)}">${options.map(([v,label])=>`<option value="${esc(v)}" ${v===value?'selected':''}>${esc(label)}</option>`).join('')}</select></label>`; }
export function openDialog(html) {
  $('#modal-root').innerHTML=`<dialog class="modal">${html}</dialog>`;
  const dialog=$('dialog'),heading=$('h2',dialog);
  if(heading){heading.id=heading.id||'dialog-title';dialog.setAttribute('aria-labelledby',heading.id);}
  dialog.addEventListener('click',e=>{
    if(e.target!==dialog)return;
    const rect=dialog.getBoundingClientRect();
    if(e.clientX<rect.left||e.clientX>rect.right||e.clientY<rect.top||e.clientY>rect.bottom)dialog.close();
  });
  dialog.addEventListener('close',()=>dialog.remove());
  dialog.showModal();
  $('[data-close]',dialog)?.addEventListener('click',closeDialog);
}
export function closeDialog() { $('dialog')?.close(); }
