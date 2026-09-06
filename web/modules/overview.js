import {api} from './api.js';
import {$,esc,dollars,exactDollars,quantity,title,monthLabel,header,empty,icon} from './ui.js';

function trendChart(rows) {
  if (!rows.length) return '';
  const compact=window.innerWidth<=700;
  const recent=rows.slice(compact?-5:-8);
  const high=Math.max(0,...recent.map(r=>r.cents));
  const low=Math.min(0,...recent.map(r=>r.cents));
  const range=Math.max(1,high-low);
  const width=compact?460:760,height=232,left=compact?83:60,top=30,plot=155;
  const y=value=>top+(high-value)/range*plot;
  const zero=y(0),spacing=(width-left-25)/recent.length;
  // Keep zero visible and avoid colliding labels when a small credit sits beside larger charges.
  const ticks=[...new Set([0,high,low,(high+low)/2])].reduce((shown,value)=>shown.every(other=>Math.abs(y(value)-y(other))>=18)?[...shown,value]:shown,[]).sort((a,b)=>a-b);
  return `<svg class="trend" viewBox="0 0 ${width} ${height}" role="img" aria-label="Approved current charges by invoice month; credits extend below zero">
    ${ticks.map(value=>`<line x1="${left}" y1="${y(value)}" x2="${width-15}" y2="${y(value)}" class="chart-grid"/><text x="${left-10}" y="${y(value)+4}" text-anchor="end" class="chart-axis">${esc(dollars(value))}</text>`).join('')}
    ${recent.map((r,i)=>{const x=left+i*spacing+spacing*.18,bar=Math.max(1,Math.abs(y(r.cents)-zero));return `<rect x="${x}" y="${r.cents>=0?y(r.cents):zero}" width="${spacing*.6}" height="${bar}" rx="3" class="${i===recent.length-1?'chart-bar current':'chart-bar'}"><title>${esc(monthLabel(r.month))}: ${esc(exactDollars(r.cents))}</title></rect><text x="${x+spacing*.3}" y="217" text-anchor="middle" class="chart-label">${esc(monthLabel(r.month,true).split(' ')[0])}</text>`;}).join('')}
  </svg>`;
}
export async function showOverview(container,ctx,month) {
  const data=await api(`/overview${month?`?month=${encodeURIComponent(month)}`:''}`);
  ctx.updatePending(data.stats.pending);
  container.innerHTML=header('Campus utilities','Reviewed bills, organized in one local ledger.',`<button class="primary" id="import-main">${icon('upload')} Import a bill</button>`)+
    `<div class="overview-toolbar"><span>Invoice month</span><select id="month-filter" aria-label="Invoice month">${data.months.length?data.months.map(m=>`<option value="${m}" ${m===data.selected_month?'selected':''}>${esc(monthLabel(m))}</option>`).join(''):'<option>No approved bills</option>'}</select><span class="muted toolbar-note">USD · current charges · approved records only</span></div>`+
    `<div class="metrics"><section><p>Current charges</p><strong>${dollars(data.total_cents)}</strong><span>${esc(monthLabel(data.selected_month))}</span></section><section><p>Awaiting review</p><strong>${data.stats.pending}<small> items</small></strong><button class="text-button" id="review-shortcut">Open review queue ${icon('arrow')}</button></section><section><p>Recorded service points</p><strong>${data.stats.meters}<small> meters / fuel points</small></strong><span>${data.stats.buildings} buildings · ${data.stats.accounts} accounts</span></section></div>`+
    (data.monthly.length?`<div class="analysis-grid"><section class="panel trend-panel"><div class="section-heading"><h2>Utility spending</h2><span class="muted">By invoice month</span></div>${trendChart(data.monthly)}<p class="caption">Full current charges appear in the invoice month. Prior balances and payments are excluded.</p></section><section class="panel utility-breakdown"><div class="section-heading"><h2>By utility</h2></div>${data.cost_by_commodity.map(item=>`<div class="utility-row"><span><i class="utility-dot ${esc(item.commodity)}"></i>${esc(title(item.commodity))}</span><strong>${dollars(item.cents)}</strong></div>`).join('')}<div class="total-row"><span>Reviewed total</span><strong>${dollars(data.total_cents)}</strong></div><p class="caption">Separate supply and delivery charges can share one meter. Consumption is recorded once.</p></section></div>
    <div class="analysis-grid lower-grid"><section class="panel"><div class="section-heading"><h2>Spending by building</h2><span class="muted">${esc(monthLabel(data.selected_month,true))}</span></div><table><thead><tr><th>Building</th><th>Share of positive charges</th><th class="numeric">Charges</th></tr></thead><tbody>${data.cost_by_building.map(item=>`<tr><td>${esc(item.building)}</td><td><progress max="${Math.max(1,data.cost_by_building.reduce((sum,item)=>sum+Math.max(0,item.cents),0))}" value="${Math.max(0,item.cents)}" aria-label="${esc(item.building)} share"></progress></td><td class="numeric">${exactDollars(item.cents)}</td></tr>`).join('')}</tbody></table><p class="caption">Shared meters stay unassigned until Facilities confirms a defensible allocation.</p></section><section class="panel"><div class="section-heading"><h2>Recorded quantities</h2></div>${data.quantities.map(item=>`<div class="quantity-row"><div>${esc(title(item.commodity))}<small>${item.role==='delivery'?'Purchased volume':'Billed consumption'}</small></div><strong>${quantity(item.value)} <small>${esc(item.unit)}</small></strong></div>`).join('')}<p class="caption">Quantities cover the original service periods on this month’s invoices. Different units remain separate.</p></section></div>`:
    empty('Start with one reviewed bill','Import a sample CSV to try the workflow. In staff mode, approved source records will populate this view.'))+
    `<footer class="page-footer"><span>${data.stats.approved_bills} approved invoices in this local ledger</span><span>Complete campus coverage has not been established.</span></footer>`;
  $('#import-main').onclick=ctx.openImport;
  $('#review-shortcut').onclick=()=>ctx.navigate('review');
  $('#month-filter').onchange=e=>ctx.refresh('overview',e.target.value);
}
