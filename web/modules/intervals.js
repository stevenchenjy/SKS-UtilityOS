import {api} from './api.js';
import {$,esc,quantity,localTime,header,empty,notice} from './ui.js';
export async function showIntervals(container,ctx,meter){
  const data=await api(`/intervals${meter?`?meter=${encodeURIComponent(meter)}`:''}`);
  container.innerHTML=header('Interval data','Historical readings from staff-imported files.',`<button id="import-intervals" class="primary">Import an XML file</button>`)+
    notice('Live monitoring is disconnected. The utility determines the file’s reading frequency and delivery delay. Imported intervals never add to bill totals.')+
    (data.selected?`<div class="overview-toolbar"><label for="meter-select">Meter</label><select id="meter-select">${data.channels.map(c=>`<option value="${esc(c.code)}" ${c.id===data.selected.id?'selected':''}>${esc(c.code)} · ${esc(c.building||'Unassigned / shared')}</option>`).join('')}</select></div><section class="panel"><div class="section-heading"><h2>Imported energy profile</h2><span class="muted">${data.total_readings} stored readings</span></div>${chart(data.readings)}<p class="caption">Chart shows the latest ${Math.min(data.readings.length,200)} of ${data.total_readings} stored readings. Values are interval energy (kWh). Gaps between readings are not filled.</p></section><section class="panel table-panel"><div class="section-heading"><h2>Reading details</h2><span class="muted">Latest 20 · America/New_York</span></div><div class="table-scroll"><table><thead><tr><th>Interval starts</th><th>Duration</th><th class="numeric">Energy</th><th>Source quality code</th></tr></thead><tbody>${data.readings.slice(-20).reverse().map(r=>`<tr><td>${esc(localTime(r.start_utc))}</td><td>${r.duration_s/60} minutes</td><td class="numeric">${quantity(r.quantity)} kWh</td><td>${esc(r.quality)}</td></tr>`).join('')}</tbody></table></div></section>`:empty('No interval readings approved','Use the synthetic XML to test parsing and meter mapping. Real supplier files remain a later staff-authorized step.'));
  $('#import-intervals').onclick=ctx.openImport;
  if($('#meter-select'))$('#meter-select').onchange=e=>ctx.refresh('intervals',e.target.value);
}
function chart(readings){
  const rows=readings.slice(-200);
  if(!rows.length)return '';
  const first=rows[0].start_utc,last=rows.at(-1).start_utc+rows.at(-1).duration_s,max=Math.max(...rows.map(r=>Number(r.quantity)),1);
  return `<svg viewBox="0 0 960 220" class="interval-chart" role="img" aria-label="Imported electricity energy per interval"><line x1="40" y1="180" x2="940" y2="180" class="chart-grid"/>${rows.map(r=>{const x=40+(r.start_utc-first)/(last-first)*900,w=Math.max(1,r.duration_s/(last-first)*900*.85),height=Number(r.quantity)/max*145;return `<rect x="${x}" y="${180-height}" width="${w}" height="${height}" class="chart-bar current"><title>${esc(localTime(r.start_utc))}: ${quantity(r.quantity)} kWh</title></rect>`;}).join('')}<text x="40" y="207" class="chart-label">${esc(localTime(first))}</text><text x="940" y="207" text-anchor="end" class="chart-label">${esc(localTime(last))}</text></svg>`;
}
