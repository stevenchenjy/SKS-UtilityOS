import {api} from './api.js';
import {$,$$,esc,dollars,exactDollars,quantity,title,monthLabel,header,empty,icon} from './ui.js';

function trendChart(rows,selected) {
  if (!rows.length) return '';
  const compact=window.innerWidth<=700;
  const recent=rows.filter(r=>r.month<=selected).slice(compact?-5:-8);
  const high=Math.max(0,...recent.map(r=>r.cents));
  const low=Math.min(0,...recent.map(r=>r.cents));
  const range=Math.max(1,high-low);
  const width=compact?460:760,height=246,left=compact?83:60,top=30,plot=155;
  const y=value=>top+(high-value)/range*plot;
  const zero=y(0),spacing=(width-left-25)/recent.length;
  // Keep zero visible and avoid colliding labels when a small credit sits beside larger charges.
  const ticks=[...new Set([0,high,low,(high+low)/2])].reduce((shown,value)=>shown.every(other=>Math.abs(y(value)-y(other))>=18)?[...shown,value]:shown,[]).sort((a,b)=>a-b);
  return `<svg class="trend" viewBox="0 0 ${width} ${height}" role="img" aria-label="Approved current charges by invoice month; credits extend below zero">
    ${ticks.map(value=>`<line x1="${left}" y1="${y(value)}" x2="${width-15}" y2="${y(value)}" class="chart-grid"/><text x="${left-10}" y="${y(value)+4}" text-anchor="end" class="chart-axis">${esc(dollars(value))}</text>`).join('')}
    ${recent.map((r,i)=>{const x=left+i*spacing+spacing*.18,bar=Math.abs(y(r.cents)-zero);return `<rect x="${x}" y="${r.cents>=0?y(r.cents):zero}" width="${spacing*.6}" height="${bar}" rx="3" class="${r.month===selected?'chart-bar current':'chart-bar'}"><title>${esc(monthLabel(r.month))}: ${esc(exactDollars(r.cents))}</title></rect><text x="${x+spacing*.3}" y="217" text-anchor="middle" class="chart-label">${esc(monthLabel(r.month,true).split(' ')[0])}<tspan x="${x+spacing*.3}" dy="17">${esc(r.month.slice(0,4))}</tspan></text>`;}).join('')}
  </svg>`;
}
export async function showOverview(container,ctx,filters) {
  const saved=ctx.overviewFilters||{building:'all'};
  const selected={...saved,...(typeof filters==='string'?{month:filters}:filters||{})};
  const query=new URLSearchParams({building:selected.building});
  if(selected.month)query.set('month',selected.month);
  const data=await api(`/overview?${query}`);
  if(!container.isConnected)return;
  ctx.overviewFilters={building:data.scope.id,month:data.selected_month};
  ctx.updatePending(data.stats.pending);
  const scoped=data.scope.id!=='all',label=data.scope.name;
  const history=data.monthly.filter(r=>r.month<=data.selected_month).slice(window.innerWidth<=700?-5:-8);
  const change=patch=>ctx.refresh('overview',{...ctx.overviewFilters,...patch});
  container.innerHTML=header(scoped?label:'Campus utilities','Reviewed bills, organized in one local ledger.',`<button class="primary" id="import-main">${icon('upload')} Import a bill</button>`)+
    `<div class="overview-toolbar building-toolbar"><label class="field"><span>Building</span><select id="building-filter" aria-label="Building">${data.buildings.map(b=>`<option value="${esc(b.id)}" ${b.id===data.scope.id?'selected':''}>${esc(b.name)}</option>`).join('')}</select></label><label class="field"><span>Invoice month</span><select id="month-filter" aria-label="Invoice month" ${!data.months.length?'disabled':''}>${data.months.length?data.months.map(m=>`<option value="${m}" ${m===data.selected_month?'selected':''}>${esc(monthLabel(m))}</option>`).join(''):'<option>No approved bills</option>'}</select></label>${scoped?'<button class="secondary compact" id="clear-building">All buildings</button>':''}<span class="muted toolbar-note">USD · approved active records</span></div>`+
    `<div class="scope-heading"><p id="report-scope"><strong>${esc(label)}</strong> · ${esc(monthLabel(data.selected_month))}</p><button class="text-button" id="building-invoices">View matching invoices ${icon('arrow')}</button></div>`+
    `<div class="metrics"><section><p>Current charges</p><strong id="scope-total">${exactDollars(data.total_cents)}</strong><span>${data.invoice_count} active invoices in this view</span></section><section><p>Recorded service points</p><strong>${data.scope_stats.meters}<small> meters / fuel points</small></strong><span>${data.scope_stats.accounts} accounts with active invoices · all months</span></section><section><p>Awaiting review · whole ledger</p><strong>${data.stats.pending}<small> items</small></strong><button class="text-button" id="review-shortcut">Open review queue ${icon('arrow')}</button></section></div>`+
    (data.monthly.length?`<div class="analysis-grid"><section class="panel trend-panel"><div class="section-heading"><h2>Utility spending</h2><span class="muted">${esc(label)}</span></div>${trendChart(data.monthly,data.selected_month)}<p class="caption">Invoice months through ${esc(monthLabel(data.selected_month))}. Full current charges appear in the invoice month; prior balances and payments are excluded.</p><details class="trend-values"><summary>View exact monthly totals</summary><table><thead><tr><th>Invoice month</th><th>Active invoices</th><th class="numeric">Charges</th></tr></thead><tbody>${history.map(r=>`<tr><td>${esc(monthLabel(r.month))}</td><td>${r.bills}${r.bills===0?' · No approved bills':''}</td><td class="numeric">${exactDollars(r.cents)}</td></tr>`).join('')}</tbody></table></details></section><section class="panel utility-breakdown"><div class="section-heading"><h2>By utility</h2><span class="muted">Selected month</span></div>${data.cost_by_commodity.length?data.cost_by_commodity.map(item=>`<div class="utility-row"><span><i class="utility-dot ${esc(item.commodity)}"></i>${esc(title(item.commodity))}</span><strong>${exactDollars(item.cents)}</strong></div>`).join(''):'<p class="caption">No approved bills for this building and month. Coverage has not been established.</p>'}<div class="total-row"><span>Reviewed total</span><strong>${exactDollars(data.total_cents)}</strong></div><p class="caption">Separate supply and delivery charges can share one meter. Consumption is recorded once.</p></section></div>
    <div class="analysis-grid lower-grid"><section class="panel"><div class="section-heading"><h2>${scoped?'Service points in this view':'Spending by building'}</h2><span class="muted">${esc(monthLabel(data.selected_month,true))}</span></div>${scoped?servicePoints(data):buildingTable(data)}<p class="caption">${scoped?'Current meter mappings apply to all invoice months. A point with no approved bill is not evidence of zero use.':'Select a building to inspect its charges and quantities. Shared meters stay unassigned until Facilities confirms a defensible mapping.'}</p><button class="text-button" id="building-inventory">Inspect utility inventory ${icon('arrow')}</button></section><section class="panel"><div class="section-heading"><h2>Recorded quantities</h2></div>${data.quantities.length?data.quantities.map(item=>`<div class="quantity-row"><div>${esc(title(item.commodity))}<small>${item.role==='delivery'?'Purchased volume':'Billed consumption'}</small></div><strong>${quantity(item.value)} <small>${esc(item.unit)}</small></strong></div>`).join(''):'<p class="caption">No recorded quantities in this view. Charges-only invoices do not add consumption.</p>'}<p class="caption">Quantities cover the original service periods on this month’s invoices. Different units remain separate. Imported interval readings are viewed separately in Interval data.</p></section></div>`:
    empty('No approved bills in this ledger','Import a sample CSV and review it to populate the dashboard.'))+
    `<footer class="page-footer"><span>${data.scope_stats.approved_bills} active invoices · ${esc(label)} · all months</span><span>Complete campus coverage has not been established.</span></footer>`;
  $('#import-main').onclick=ctx.openImport;
  $('#review-shortcut').onclick=()=>ctx.navigate('review');
  $('#month-filter').onchange=e=>change({month:e.target.value});
  $('#building-filter').onchange=e=>change({building:e.target.value});
  if($('#clear-building'))$('#clear-building').onclick=()=>change({building:'all'});
  $$('[data-building-view]',container).forEach(button=>button.onclick=()=>change({building:button.dataset.buildingView}));
  $('#building-invoices').onclick=()=>ctx.navigate('bills',{...ctx.overviewFilters,state:'active',search:''});
  if($('#building-inventory'))$('#building-inventory').onclick=()=>ctx.navigate('inventory');
}
function buildingTable(data){
  if(!data.cost_by_building.length)return '<p class="caption">No approved invoices in the selected month.</p>';
  const positive=data.cost_by_building.reduce((sum,item)=>sum+Math.max(0,item.cents),0);
  return `<div class="table-scroll"><table><thead><tr><th>Building</th><th>Share of positive net charges</th><th class="numeric">Charges</th></tr></thead><tbody>${data.cost_by_building.map(item=>`<tr><td><button class="text-button building-link" data-building-view="${esc(item.building_id)}">${esc(item.building)}</button></td><td><progress max="${Math.max(1,positive)}" value="${Math.max(0,item.cents)}" aria-label="${esc(item.building)} share of positive net charges"></progress></td><td class="numeric">${exactDollars(item.cents)}</td></tr>`).join('')}</tbody></table></div>`;
}
function servicePoints(data){
  if(!data.service_points.length)return '<p class="caption">No service points currently map to this building. Inspect Utility inventory to review its mappings.</p>';
  return `<div class="service-point-list">${data.service_points.map(point=>`<div class="service-point"><div><strong>${esc(point.code)}</strong><small>${esc(title(point.commodity))} · ${point.invoices} active invoices</small></div><div class="numeric"><strong>${exactDollars(point.cents)}</strong>${point.quantities.map(q=>`<small>${quantity(q.value)} ${esc(point.unit)} · ${q.role==='delivery'?'purchased':'billed'}</small>`).join('')}${!point.invoices?'<small>No approved bill this month</small>':!point.quantities.length?'<small>Charges only</small>':''}</div></div>`).join('')}</div>`;
}
