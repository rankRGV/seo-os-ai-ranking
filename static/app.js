const sections = [
  ['Command Center','grid'], ['Clients / Sites','building'], ['Approvals','shield'], ['Opportunities','trend'],
  ['Command Queue','list'], ['Content Briefs','edit'], ['Prospects','target'], ['Activity Log','pulse'], ['Settings','settings']
];
let state = { section:'Command Center', client:'all', filter:'All', oppFilter:'All', oppDays:0, briefFilter:'All', schedView:'calendar', schedRange:'7', reportClient:null, data:null, prospectFilter:'all', prospectSearch:'', sidebarCollapsed:false };

const $ = sel => document.querySelector(sel);
function esc(s){ return String(s||'').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function safePath(url){ try { return new URL(url||'https://x').pathname } catch(e) { return url||''; } }
function safeHost(url){ try { return new URL(url||'https://x').hostname } catch(e) { return ''; } }
const fmt = n => Number(n || 0).toLocaleString();
const pct = n => `${Number(n || 0).toFixed(Math.abs(n) < 1 && n !== 0 ? 2 : 1)}%`;
const one = n => Number(n || 0).toFixed(1).replace(/\.0$/,'');
function icon(name, size=17){
  const paths = {
    grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    building:'<path d="M3 21h18"/><path d="M5 21V7l8-4v18"/><path d="M19 21V11l-6-4"/>',
    shield:'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    trend:'<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    list:'<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/>',
    calendar:'<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    edit:'<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    target:'<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    pulse:'<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    file:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
    settings:'<path d="M12 15.5A3.5 3.5 0 1 0 12 8a3.5 3.5 0 0 0 0 7.5Z"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21a2 2 0 1 1-4 0v-.09A1.7 1.7 0 0 0 8 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.4H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.6 8a1.7 1.7 0 0 0-.34-1.88l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V3a2 2 0 1 1 4 0v.09A1.7 1.7 0 0 0 15 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9c.2.38.5.7.9.9.33.17.7.25 1.1.25H21a2 2 0 1 1 0 4h-.09c-.4 0-.77.08-1.1.25-.4.2-.7.52-.9.9Z"/>',
    alert:'<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
    refresh:'<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
    bell:'<path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
    lock:'<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>'
  };
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.grid}</svg>`;
}

function clientName(id){
  if(id === 'all') return 'All Clients';
  const c = state.data?.clients.find(x => x.id === id);
  return c ? c.name : id;
}
function clientDot(id){ return 'muted'; }
function clientScoped(rows){
  if(state.client === 'all') return rows || [];
  return (rows || []).filter(row => row.client_id === state.client);
}
function strictClientLabel(){ return state.client === 'all' ? 'all clients' : clientName(state.client); }
function classForStatus(status){
  if(['approved','ok','active','complete','done','connected','ready'].includes(status)) return 'green';
  if(['needs_review','waiting','waiting_for_approval','setup_needed','needs_setup','needs_changes'].includes(status)) return 'amber';
  if(['rejected','failed','blocked'].includes(status)) return 'red';
  if(['new','running','backlog'].includes(status)) return 'blue';
  return 'purple';
}
function label(s){ return esc(String(s || '').replaceAll('_',' ')); }

async function api(path, opts={}){
  const res = await fetch(path, {headers:{'Content-Type':'application/json'}, ...opts});
  if(!res.ok) throw new Error(await res.text());
  return res.json();
}
async function load(client=state.client){
  state.client = client;
  state.data = await api(`/api/summary?client=${encodeURIComponent(client)}&days=${state.oppDays}`);
  render();
}

function renderNav(){
  $('#nav').innerHTML = sections.map(([name,ico]) => {
    const badge = name === 'Approvals' && state.data?.kpis?.pending_approvals ? `<span class="badge">${state.data.kpis.pending_approvals}</span>` : '';
    return `<button class="nav-item ${state.section===name?'active':''}" data-section="${name}"><span class="ico">${icon(ico,16)}</span>${name}${badge}</button>`;
  }).join('');
  document.querySelectorAll('.nav-item').forEach(b => b.onclick = () => { state.section=b.dataset.section; render(); });
}
function renderTabs(){
  const tabs = [`<span class="eyebrow">CLIENT</span><button class="pill ${state.client==='all'?'active':''}" data-client="all"><i></i>All Clients</button>`]
    .concat(state.data.clients.map(c => `<button class="pill ${state.client===c.id?'active':''}" data-client="${esc(c.id)}"><i></i>${esc(c.name)}</button>`));
  $('.client-tabs').innerHTML = tabs.join('') + `<button class="pill" data-section="Settings">+ Add Client</button>`;
  document.querySelectorAll('[data-client]').forEach(b => b.onclick = () => load(b.dataset.client));
  document.querySelector('[data-section="Settings"]').onclick = () => { state.section='Settings'; render(); };
}
function renderContext(){
  const d = state.data;
  $('#refreshed').textContent = `Refreshed ${new Date(d.generated_at).toLocaleString()}`;
  $('#contextName').textContent = clientName(state.client);
  const c = state.client === 'all' ? null : d.clients.find(x => x.id === state.client);
  $('#contextSubtitle').textContent = c ? `${c.domain} · Profile: ${c.hermes_profile} · ${c.channel_target}` : `${d.visible_clients.length} sites · Discord → Hermes → SEO OS Dashboard`;
  $('#contextMetrics').innerHTML = [
    ['Sites', d.kpis.sites_monitored], ['Tasks', d.kpis.open_tasks], ['Opps', d.kpis.high_impact_opportunities], ['Jobs', d.kpis.active_jobs]
  ].map(([k,v]) => `<span class="mini"><span>${k}</span><b>${v}</b></span>`).join('');
  $('#approvalCount').textContent = `${d.kpis.pending_approvals} pending`;
  $('#routingHealth').textContent = d.kpis.system_health === 'OK' ? 'Managed scheduler healthy' : 'Needs attention';
  $('#routingHealth').className = `soft ${d.kpis.system_health === 'OK' ? 'green' : 'red'}`;
  $('#sideHealth').textContent = d.kpis.system_health === 'OK' ? 'Healthy' : 'Issue';
  $('#sideStatusText').textContent = `${d.kpis.active_jobs} managed jobs · ${d.kpis.pending_approvals} approval${d.kpis.pending_approvals===1?'':'s'}`;
}

function page(title, subtitle, body){
  return `<div class="page-title"><h1>${title}</h1><p>${subtitle}</p></div>${body}`;
}
function kpi(label,value,note,iconName,color){
  return `<div class="card kpi"><div class="kicon ${color}">${icon(iconName,17)}</div><span class="label">${label}</span><strong class="value">${value}</strong><div class="note ${color.includes('green')?'delta good':''}">${note}</div></div>`;
}
function section(title, subtitle, iconName, color, count, body, action=''){
  return `<div class="card section-card"><div class="section-head"><div class="section-title"><span class="icon ${color}">${icon(iconName,17)}</span><div><h2>${title}</h2><p>${subtitle}</p></div></div>${action || (count!==undefined?`<span class="count ${color}">${count}</span>`:'')}</div>${body}</div>`;
}
function simpleTable(headers, rows){
  if(!rows.length) return $('#emptyState').innerHTML;
  return `<div class="table-wrap"><table><thead><tr>${headers.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
}

function commandCenter(){
  const d=state.data;
  const k=d.kpis;
  const kpis = `<div class="grid kpi-grid">
    ${kpi('Pending approvals', k.pending_approvals, k.pending_approvals ? 'needs human review' : 'nothing blocked', 'shield', k.pending_approvals?'amber':'green')}
    ${kpi('Open agent tasks', k.open_tasks, `across ${k.sites_monitored} site${k.sites_monitored===1?'':'s'}`, 'list', 'blue')}
    ${kpi('SEO opportunities', k.high_impact_opportunities, 'high priority', 'trend', 'green')}
    ${kpi('Managed jobs', k.active_jobs, 'SEO OS handles scheduling', 'calendar', 'blue')}
    ${kpi('Sites monitored', k.sites_monitored, 'client context active', 'building', 'purple')}
    ${kpi('System health', k.system_health, 'no failed jobs', 'pulse', k.system_health==='OK'?'green':'red')}
  </div>`;
  const needs = d.approvals.filter(a => ['needs_review','needs_changes'].includes(a.status)).slice(0,5).map(a => `<tr><td>${esc(clientName(a.client_id))}</td><td><strong>${esc(a.title)}</strong><div class="muted">${esc(a.requested_action)}</div></td><td><span class="tag purple">${label(a.type)}</span></td><td><span class="tag ${classForStatus(a.risk)}">${label(a.risk)}</span></td><td>${esc(a.evidence.slice(0,120))}...</td><td><button class="btn primary" data-open-approvals>Review</button></td></tr>`);
  const oppRows = d.opportunities.slice(0,6).map(o => `<tr><td>${esc(clientName(o.client_id))}</td><td><strong>${esc(safePath(o.page))}</strong><div class="url">${esc(o.page)}</div></td><td>${esc(o.problem)}</td><td><span class="tag ${classForStatus(o.priority)}">${label(o.priority)}</span></td><td>${fmt(o.impressions)}</td><td>${fmt(o.clicks)}</td><td>${pct(o.ctr)}</td><td>${Number(o.position).toFixed(1)}</td></tr>`);
  const healthRows = d.visible_clients.map(c => {
    const approvals = d.approvals.filter(a => a.client_id === c.id && a.status === 'needs_review').length;
    const tasks = d.tasks.filter(t => t.client_id === c.id && !['done','cancelled'].includes(t.status)).length;
    const opps = d.opportunities.filter(o => o.client_id === c.id).length;
    return `<tr><td><strong>${esc(c.name)}</strong><div class="muted">${esc(c.domain)}</div></td><td><span class="tag ${classForStatus(c.status)}">${c.health_score}% · ${label(c.status)}</span></td><td>${approvals}</td><td>${tasks}</td><td>${d.jobs.filter(j=>j.client_id===c.id).length}</td><td>${opps}</td><td>${esc(c.gsc_status)} / ${esc(c.ga4_status)}</td><td>${c.status==='setup'?'Connect GSC, GA4, review source':'<button class="link-action" data-client="${c.id}" data-section="Opportunities" style="font-size:12px;padding:0">Review top opportunity →</button>'}</td></tr>`;
  });
  const perf = `<div class="two-col">${d.metrics.map(m => `<div class="card perf-card"><h3><span class="dot ${clientDot(m.client_id)}"></span>${esc(clientName(m.client_id))}</h3><div class="perf-source"><span class="source-badge gsc">GSC</span></div><div class="perf-grid"><div class="perf-metric"><span>Clicks</span><strong>${fmt(m.clicks)}</strong><em class="delta ${m.clicks_delta>=0?'good':'bad'}">${m.clicks_delta>=0?'+':''}${fmt(m.clicks_delta)}</em></div><div class="perf-metric"><span>Impressions</span><strong>${fmt(m.impressions)}</strong><em class="delta ${m.impressions_delta>=0?'good':'bad'}">${m.impressions_delta>=0?'+':''}${fmt(m.impressions_delta)}</em></div><div class="perf-metric"><span>CTR</span><strong>${pct(m.ctr)}</strong><em class="delta ${m.ctr_delta>=0?'good':'bad'}">${m.ctr_delta>=0?'+':''}${one(m.ctr_delta)} pts</em></div><div class="perf-metric"><span>Avg rank</span><strong>${Number(m.avg_rank).toFixed(1)}</strong><em class="delta ${m.avg_rank_delta<=0?'good':'bad'}">${one(Math.abs(m.avg_rank_delta))} ${m.avg_rank_delta<=0?'better':'worse'}</em></div></div></div>`).join('')}</div>`;
  const activities = d.events.slice(0,7).map(e => `<tr><td>${new Date(e.created_at).toLocaleString()}</td><td>${esc(clientName(e.client_id))}</td><td><span class="tag blue">${label(e.source)}</span></td><td>${label(e.event_type)}</td><td>${esc(e.summary)}</td><td>${esc(e.next_action)}</td></tr>`);
  const healthBars = (d.client_health || []).map(h => {
    const score = h.score || 50;
    const status = h.status || 'yellow';
    const color = status === 'green' ? '#16a34a' : status === 'yellow' ? '#ca8a04' : '#dc2626';
    const pages = h.pages_ranking || 0;
    const highOpps = h.high_priority_opps || 0;
    return `<div class="health-row"><span class="health-name"><span class="dot ${clientDot(h.client_id)}"></span>${esc(clientName(h.client_id))}</span><div class="health-bar-bg"><div class="health-bar-fill" style="width:${score}%;background:${color}"></div></div><span class="health-score" style="color:${color}">${score}</span><span class="health-detail">${pages} pages · ${highOpps} high</span></div>`;
  }).join('');
  const healthWidget = `<div class="health-grid">${healthBars || '<div class="muted" style="font-size:13px">No health data yet. Run a data pull first.</div>'}</div>`;

  // GBP Health widget (local clients only)
  const gbpData = d.gbp_health || [];
  const gbpWidget = gbpData.length > 0 ? `<div class="gbp-health-grid">${gbpData.map(g => `
    <div class="gbp-card ${g.status}">
      <div class="gbp-header"><strong>${esc(g.name)}</strong><span class="tag ${g.status==='green'?'green':g.status==='yellow'?'amber':'red'}">${g.score}/100</span></div>
      <div class="gbp-metrics">
        <span>👁 ${g.views}</span>
        <span>📞 ${g.calls}</span>
        <span>🌐 ${g.website}</span>
        <span>🗺 ${g.directions}</span>
      </div>
      <div class="gbp-reviews">⭐ ${g.review_avg} (${g.review_count} reviews)</div>
    </div>
  `).join('')}</div>` : '<div class="muted" style="font-size:13px">No GBP data. Add GBP credentials or run demo check.</div>';

  // Opportunity Score widget
  const scores = d.opportunity_scores || [];
  const scoreWidget = scores.length > 0 ? `<div class="opp-score-grid">${scores.map(s => {
    const color = s.score >= 70 ? '#16a34a' : s.score >= 40 ? '#ca8a04' : '#dc2626';
    return `<div class="opp-score-card">
      <div class="opp-score-header"><strong>${esc(s.name)}</strong><span class="opp-score-value" style="color:${color}">${s.score}</span></div>
      <div class="opp-score-bar-bg"><div class="opp-score-bar-fill" style="width:${s.score}%;background:${color}"></div></div>
      <div class="opp-score-action">${esc(s.next_best_action)}</div>
    </div>`;
  }).join('')}</div>` : '<div class="muted" style="font-size:13px">No opportunity scores yet. Run a data pull first.</div>';

  // Health Trend widget (from client_health snapshots)
  const healthTrend = (d.client_health || []).filter(h => h.trend && h.trend.length > 1);
  const trendWidget = healthTrend.length > 0 ? `<div class="health-trend-grid">${healthTrend.map(h => {
    const points = h.trend.map(p => `${p.date},${p.score}`).join(' ');
    const latest = h.trend[h.trend.length-1].score;
    const first = h.trend[0].score;
    const diff = latest - first;
    const arrow = diff > 0 ? '↗' : diff < 0 ? '↘' : '→';
    const color = diff > 0 ? '#16a34a' : diff < 0 ? '#dc2626' : '#7E8C8A';
    return `<div class="health-trend-card">
      <div class="health-trend-header"><strong>${esc(clientName(h.client_id))}</strong><span style="color:${color};font-weight:800">${arrow} ${diff > 0 ? '+' : ''}${diff}</span></div>
      <div class="health-trend-spark">${h.trend.map(p => `<span class="trend-dot" style="height:${Math.max(4,p.score/5)}px;background:${color}" title="${p.date}: ${p.score}"></span>`).join('')}</div>
      <div class="health-trend-label">${h.trend.length} snapshots</div>
    </div>`;
  }).join('')}</div>` : '<div class="muted" style="font-size:13px">Health trend will appear after 2+ daily pulls.</div>';

  const body = `<div class="architecture"><span class="arch-pill blue">Discord</span><span class="arrow">→</span><span class="arch-pill green">Dashboard</span><span class="arrow">→</span><span class="arch-pill purple">Hermes Agents</span><span class="arrow">→</span><span class="arch-pill" style="background:#0f172a;color:#fff">Reports</span></div>${kpis}
    ${section('Opportunity Score','Composite 0-100 score per client — higher means more untapped potential','trend','green',undefined, scoreWidget)}
    ${section('Health Trend','Score change over time — ↗ improving, ↘ declining, → stable','pulse','blue',undefined, trendWidget)}
    ${section('Client Health','Overall SEO health per client — green thriving, yellow needs attention, red at-risk','activity','purple',undefined, healthWidget)}
    ${section('Google Business Profile','Local business health — views, actions, reviews for local clients','building','green',undefined, gbpWidget)}
    ${section('Needs Your Attention Today','Decisions and approvals the agents are waiting on','alert','red',`${needs.length} items`, simpleTable(['Client','Item','Type','Priority','Why it matters','Action'], needs))}
    <h2>28-Day Performance <span class="muted" style="font-size:13px;font-weight:500">GSC clicks and impressions</span></h2>${perf}
    ${section('High-Impact SEO Opportunities','High impressions, weak clicks — ranked by impressions','trend','green',undefined, simpleTable(['Client','Page','Problem','Priority','Impr.','Clicks','CTR','Pos.'], oppRows), '<button class="link-action" data-open-opps>View all →</button>')}
    ${section('Client Health Summary','Workload and next action per site','building','blue',undefined, simpleTable(['Client','Status','Appr.','Tasks','Jobs','Opps','Connections','Recommended next action'], healthRows))}
    ${commandPreviews(d)}
    ${section('Agent Activity','Important outcomes only — not a Discord transcript','pulse','mutedIcon',undefined, simpleTable(['Time','Client','Source','Type','What happened','Next action'], activities))}
    ${section('Quick Actions','Send updates to Discord, trigger data refresh, and manage notifications','settings','blue',undefined, '<button class="btn primary" id="notifyDiscordBtn">Send to Discord</button> <button class="btn" id="createThreadBtn">Create Client Thread</button> <button class="btn" id="ga4PullBtn">Pull GA4 Now</button> <button class="btn" id="gscPullBtn">Pull GSC Now</button> <span class="muted" style="font-size:12px">Last GA4 pull: <span id="lastGa4Pull">—</span> · Last GSC pull: <span id="lastGscPull">—</span></span>')}`;
  setTimeout(()=>document.querySelectorAll('[data-open-approvals]').forEach(b=>b.onclick=()=>{state.section='Approvals';render()}),0);
  setTimeout(()=>document.querySelectorAll('[data-open-opps]').forEach(b=>b.onclick=()=>{state.section='Opportunities';render()}),0);
  setTimeout(()=>document.querySelectorAll('[data-section="Opportunities"]').forEach(b=>b.onclick=()=>{if(b.dataset.client){load(b.dataset.client)}else{state.section='Opportunities';render()}}),0);
  setTimeout(()=>document.querySelectorAll('[data-open-schedule]').forEach(b=>b.onclick=()=>{state.section='Schedule';render()}),0);
  return page('SEO Command Center','AI agents, SEO data, approvals, schedules, and client work in one operating layer.', body);
}

function commandPreviews(d){
  const appr = d.approvals.slice(0,3).map(a => `<div class="preview-row"><span class="dot ${clientDot(a.client_id)}"></span><div><strong>${esc(a.title)}</strong><small>${esc(clientName(a.client_id))} · ${label(a.type)}</small></div><span class="tag ${classForStatus(a.status)}">${label(a.status)}</span></div>`).join('');
  const jobs = d.jobs.slice(0,5).map(j => `<div class="preview-row"><span class="dot ${classForStatus(j.status)}"></span><div><strong>${esc(j.name)}</strong><small>${esc(clientName(j.client_id))}</small></div><div class="preview-time"><strong>${esc(j.next_run)}</strong><small>${esc(j.cadence)}</small></div></div>`).join('');
  return `<div class="preview-grid"><div>${section('Approval Inbox','Agent recommendations awaiting decision','shield','purple',undefined,`<div class="preview-list">${appr}</div>`, '<button class="link-action" data-open-approvals>Open →</button>')}</div><div>${section('Next Scheduled Work','Upcoming managed agent jobs','calendar','blue',undefined,`<div class="preview-list">${jobs}</div>`, '<button class="link-action" data-open-schedule>All →</button>')}</div></div>`;
}

function clientsView(){
  const cards = state.data.visible_clients.map(c => `<div class="card client-card"><h3>${esc(c.name)}</h3><div class="client-meta">${esc(c.domain)} · ${esc(c.role)}</div><div class="health"><i style="width:${c.health_score}%"></i></div><div class="connection-list"><div><span>Hermes profile</span><strong>${esc(c.hermes_profile)}</strong></div><div><span>Discord</span><strong>${esc(c.channel_target)}</strong></div><div><span>GSC</span><strong>${label(c.gsc_status)}</strong></div><div><span>GA4</span><strong>${label(c.ga4_status)}</strong></div><div><span>review source</span><strong>${label(c.zernio_status)}</strong></div><div><span>Repo</span><strong>${label(c.repo_status)}</strong></div></div></div>`).join('');
  return page('Clients / Sites','Each client maps to a Hermes profile, workspace, data sources, and approval policy.', `<div class="grid client-grid">${cards}</div>`);
}

function approvalsView(){
  const filters=['All','Needs review','Approved'];
  const fhtml = `<div class="warning">🔒 <strong>Production changes remain approval-gated.</strong> Approving here updates state and creates a bounded task only. Publishing, deploys, redirects, noindex, canonicals, deletions, and outreach require separate explicit approval.</div><div class="filters">${filters.map(f=>`<button class="btn filter ${state.filter===f?'active':''}" data-filter="${f}">${f}</button>`).join('')}</div>`;
  let rows = state.data.approvals;
  if(state.filter==='Needs review') rows = rows.filter(a=>a.status==='needs_review');
  if(state.filter==='Approved') rows = rows.filter(a=>a.status==='approved');
  const cards = rows.map(a => `<div class="card approval-card"><div class="approval-top"><span class="tag purple">${label(a.type)}</span><span class="tag ${clientDot(a.client_id)}">${esc(clientName(a.client_id))}</span><span class="tag ${classForStatus(a.status)}">${label(a.status)}</span><span class="tag ${classForStatus(a.risk)}">${label(a.risk)} risk</span></div><h3>${esc(a.title)}</h3><p><strong>Requested action:</strong> ${esc(a.requested_action)}</p><div class="evidence"><strong>Evidence</strong><br>${esc(a.evidence)}<br><br><strong>Safety:</strong> ${esc(a.production_gate)}</div>${a.source_url?`<div class="url">${esc(a.source_url)}</div>`:''}<div class="btn-row" style="margin-top:16px">${a.status==='needs_review'?`<button class="btn primary" data-decision="approved" data-id="${a.id}">Approve</button><button class="btn" data-decision="needs_changes" data-id="${a.id}">Request Changes</button><button class="btn danger" data-decision="rejected" data-id="${a.id}">Reject</button>`:`<span class="tag ${classForStatus(a.status)}">${label(a.status)}</span>`}<button class="btn blue">Discord</button></div></div>`).join('') || $('#emptyState').innerHTML;
  setTimeout(()=>{
    document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{state.filter=b.dataset.filter;render()});
    document.querySelectorAll('[data-decision]').forEach(b=>b.onclick=()=>decide(b.dataset.id,b.dataset.decision));
  },0);
  return page('Approvals','Human approval gate for strategy, content, publishing, outreach, and technical SEO.', fhtml + `<div class="approval-grid">${cards}</div>`);
}
async function decide(id, decision){
  try{
    const payload = await api(`/api/approvals/${id}/decision`, {method:'POST', body:JSON.stringify({decision, note:'Set from SEO OS dashboard prototype'})});
    state.data = payload.summary; toast(`Approval marked ${decision.replaceAll('_',' ')}`); render();
  }catch(e){ toast('Decision failed', true); console.error(e); }
}

function opportunitiesView(){
  const filters = ['All','High','Medium','Low','Low CTR','SERP gap','Content refresh'];
  const dayRanges = [{label:'All time',days:0},{label:'7 days',days:7},{label:'28 days',days:28},{label:'90 days',days:90}];
  let opps = state.data.opportunities;
  if(state.oppFilter === 'High') opps = opps.filter(o => o.priority === 'high');
  else if(state.oppFilter === 'Medium') opps = opps.filter(o => o.priority === 'medium');
  else if(state.oppFilter === 'Low') opps = opps.filter(o => o.priority === 'low');
  else if(state.oppFilter !== 'All') opps = opps.filter(o => o.opportunity_type === state.oppFilter);
  const chips = `<div class="opp-chips">${filters.map(f=>`<button class="opp-chip ${state.oppFilter===f?'active':''}" data-opp-filter="${f}">${f}</button>`).join('')}</div>`;
  const dayChips = `<div class="opp-chips" style="margin-top:6px">${dayRanges.map(r=>`<button class="opp-chip ${state.oppDays===r.days?'active':''}" data-opp-days="${r.days}">${r.label}</button>`).join('')}</div>`;
  const rows = opps.map((o,i) => {
    const trendIcon = o.trend_direction === '↑' ? '↑' : o.trend_direction === '↓' ? '↓' : '→';
    const trendClass = o.trend === 'clicks_up' ? 'good' : o.trend === 'clicks_down' ? 'bad' : 'muted';
    const baselineNote = o.baseline_clicks ? ` (was ${o.baseline_clicks})` : '';
    let sourceBadge = '';
    try {
      const ev = JSON.parse(o.evidence_json || '{}');
      if (ev.source === 'gsc_pull') sourceBadge = '<span class="tag green" style="margin-left:4px;font-size:10px;padding:2px 6px">GSC</span>';
      else if (ev.source === 'ga4_pull') sourceBadge = '<span class="tag blue" style="margin-left:4px;font-size:10px;padding:2px 6px">GA4</span>';
    } catch(e) {}
    return `<tr><td class="rank-cell">${i+1}</td><td><span class="client-cell"><span class="dot ${clientDot(o.client_id)}"></span>${esc(clientName(o.client_id))}</span></td><td class="mono opp-page">${esc(safePath(o.page))}</td><td class="muted">${esc(o.problem)}${baselineNote}${sourceBadge}</td><td><span class="tag ${classForStatus(o.priority)}">${label(o.priority)}</span></td><td style="text-align:right;font-variant-numeric:tabular-nums">${fmt(o.impressions)}</td><td style="text-align:right;font-variant-numeric:tabular-nums">${fmt(o.clicks)}</td><td style="text-align:right;font-weight:600;font-variant-numeric:tabular-nums">${pct(o.ctr)}</td><td style="text-align:right;font-variant-numeric:tabular-nums">${Number(o.position).toFixed(1)}</td><td class="muted" style="max-width:240px">${esc(o.recommended_workflow)}</td><td><span class="tag ${classForStatus(o.status)}">${label(o.status)}</span></td><td style="text-align:center;font-weight:800;color:${trendClass==='good'?'#166337':trendClass==='bad'?'#C0392B':'#7E8C8A'}">${trendIcon}</td></tr>`;
  });
  setTimeout(()=>{
    document.querySelectorAll('[data-opp-filter]').forEach(b=>b.onclick=()=>{state.oppFilter=b.dataset.oppFilter;render()});
    document.querySelectorAll('[data-opp-days]').forEach(b=>b.onclick=()=>{state.oppDays=parseInt(b.dataset.oppDays)||0;render()});
  },0);
  return `<div class="opp-title"><h1>SEO Opportunities</h1><p>The opportunity pipeline from Search Console — pages with high impressions but weak clicks, CTR, or ranking position.</p></div>${chips}${dayChips}<div class="card section-card"><div class="table-wrap"><table><thead><tr><th style="text-align:center">#</th><th>Client</th><th>Page</th><th>Problem</th><th>Priority</th><th style="text-align:right">Impr.</th><th style="text-align:right">Clicks</th><th style="text-align:right">CTR</th><th style="text-align:right">Pos.</th><th>Recommended workflow</th><th>Status</th><th style="text-align:center">Trend</th></tr></thead><tbody>${rows.join('') || `<tr><td colspan="12" class="empty">No opportunities for this filter.</td></tr>`}</tbody></table></div></div>`;
}
function contentBriefsView(){
  const d = state.data;
  const briefs = d.content_briefs || [];
  const filters = ['All','High','Medium','Low'];
  let filtered = briefs;
  if(state.briefFilter === 'High') filtered = filtered.filter(b => b.priority === 'high');
  else if(state.briefFilter === 'Medium') filtered = filtered.filter(b => b.priority === 'medium');
  else if(state.briefFilter === 'Low') filtered = filtered.filter(b => b.priority === 'low');
  const chips = `<div class="opp-chips">${filters.map(f=>`<button class="opp-chip ${state.briefFilter===f?'active':''}" data-brief-filter="${f}">${f}</button>`).join('')}</div>`;
  const rows = filtered.map((b,i) => {
    const icon = b.priority === 'high' ? '🔴' : b.priority === 'medium' ? '🟡' : '⚪';
    return `<tr><td class="rank-cell">${i+1}</td><td><span class="client-cell"><span class="dot ${clientDot(b.client_id)}"></span>${esc(clientName(b.client_id))}</span></td><td class="muted" style="max-width:220px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(b.query)}">${esc(b.query)}</td><td style="text-align:right;font-variant-numeric:tabular-nums">${b.avg_position ? Number(b.avg_position).toFixed(1) : '—'}</td><td style="text-align:right;font-variant-numeric:tabular-nums">${fmt(b.impressions)}</td><td style="text-align:right;font-variant-numeric:tabular-nums">${pct(b.avg_ctr)}</td><td class="muted" style="font-size:12px;max-width:280px">${esc(b.brief)}</td><td class="mono" style="font-size:12px;color:#1D4ED8;max-width:240px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(b.suggested_title)}">${esc(b.suggested_title)}</td></tr>`;
  });
  setTimeout(()=>document.querySelectorAll('[data-brief-filter]').forEach(b=>b.onclick=()=>{state.briefFilter=b.dataset.briefFilter;render()}),0);
  return page('Content Briefs','Auto-generated content opportunities from GSC search data — keywords with traction but weak signals.', section('Content Opportunities','Keywords ranking 4-20 with decent impressions but weak CTR — ready for content creation or optimization.','edit','purple',`${briefs.length} briefs`, simpleTable(['#','Client','Query','Pos.','Impr.','CTR','Opportunity','Suggested Title'], rows), '<button class="btn" id="refreshBriefsBtn">Refresh Briefs</button>'));
}
function gscView(){
  const d = state.data;
  const gsc = d.gsc || [];
  const total = d.gsc_total || {queries:0, clicks:0, impressions:0};
  const stats = `<div class="stat-row"><span><b>${total.queries}</b> queries tracked</span><span><b>${total.clicks}</b> total clicks</span><span><b>${total.impressions}</b> impressions</span><span><b>${strictClientLabel()}</b></span></div>`;
  const rows = gsc.map((r,i) => `<tr><td class="rank-cell">${i+1}</td><td><span class="client-cell"><span class="dot ${clientDot(r.client_id)}"></span>${esc(clientName(r.client_id))}</span></td><td class="muted" style="max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(r.query)}">${esc(r.query)}</td><td class="mono opp-page" style="max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(r.page)}">${esc(safePath(r.page))}</td><td style="text-align:right;font-variant-numeric:tabular-nums">${fmt(r.clicks)}</td><td style="text-align:right;font-variant-numeric:tabular-nums">${fmt(r.impressions)}</td><td style="text-align:right;font-weight:600;font-variant-numeric:tabular-nums">${pct(r.ctr)}</td><td style="text-align:right;font-variant-numeric:tabular-nums">${Number(r.position).toFixed(1)}</td></tr>`);
  return page('GSC Search Keywords','Search queries driving traffic to your site from Google Search Console.', section('Top Keywords by Impressions','Click data from Google — what searches bring visitors to your pages','🔍','green',gsc.length, simpleTable(['#','Client','Query','Page','Clicks','Impressions','CTR','Position'], rows), '<button class="btn" id="gscPullBtn" style="margin-top:12px">Pull GSC Data Now</button>'));
}
function tasksView(){
  const rows = state.data.tasks.map(t => `<tr><td>${esc(clientName(t.client_id))}</td><td><strong>${esc(t.title)}</strong><div class="url">${esc(t.page_asset)}</div></td><td><span class="tag ${classForStatus(t.priority)}">${label(t.priority)}</span></td><td><span class="tag ${classForStatus(t.status)}">${label(t.status)}</span></td><td>${esc(t.owner_profile)}</td><td>${esc(t.source)}</td><td>${esc(t.next_action)}</td></tr>`);
  return page('Agent Tasks','Bounded execution queue created from opportunities and approvals.', section('Execution Queue','Dashboard approvals create tasks, not direct production changes','☰','blue',rows.length, simpleTable(['Client','Task','Priority','Status','Owner','Source','Next action'], rows)));
}

function contentView(){
  const d = state.data;
  const contentOpps = clientScoped(d.opportunities).filter(o => ['Content refresh','SERP gap','Striking distance','Low CTR'].includes(o.opportunity_type));
  const stageFor = o => o.status === 'task_created' ? 'Review' : o.status === 'needs_approval' ? 'Brief' : o.opportunity_type === 'Content refresh' ? 'Ideas' : 'Drafting';
  const stages = ['Ideas','Brief','Drafting','Review','Published / Monitor'];
  const colors = {'Ideas':'blue','Brief':'purple','Drafting':'amber','Review':'green','Published / Monitor':'muted'};
  const byStage = Object.fromEntries(stages.map(stage => [stage, []]));
  contentOpps.forEach(o => byStage[stageFor(o)].push(o));
  const activeCount = contentOpps.length;
  const gatedCount = contentOpps.filter(o => ['needs_approval','task_created'].includes(o.status)).length;
  const stats = `<div class="stat-row"><span><b>${activeCount}</b> active content items</span><span><b>${gatedCount}</b> approval-gated</span><span><b>${strictClientLabel()}</b></span><span><b>0</b> auto-publish actions</span></div>`;
  const board = `<div class="kanban-board">${stages.map(stage => `<div class="kanban-col"><div class="kanban-head"><span class="dot ${colors[stage]}"></span><strong>${stage}</strong><span>${byStage[stage].length}</span></div>${byStage[stage].map(o => `<div class="kanban-card"><span class="tag ${colors[stage]==='muted'?'blue':colors[stage]}">${label(o.opportunity_type)}</span><h3>${esc(safePath(o.page))}</h3><p>${esc(o.recommended_workflow)}</p><div class="kanban-meta"><span class="dot ${clientDot(o.client_id)}"></span>${esc(clientName(o.client_id))}<small>Approval-gated</small></div></div>`).join('') || '<div class="empty">No client items.</div>'}</div>`).join('')}</div>`;
  const rows = contentOpps.map(o => `<tr><td>${esc(clientName(o.client_id))}</td><td><strong>${esc(safePath(o.page))}</strong><div class="url">${esc(o.page)}</div></td><td>${label(o.opportunity_type)}</td><td><span class="tag ${classForStatus(o.priority)}">${label(o.priority)}</span></td><td>${esc(o.recommended_workflow)}</td><td><span class="tag amber">Needs approval before publish</span></td></tr>`);
  return page('Content Pipeline',`Client-scoped content and refresh work for ${strictClientLabel()}. Drafts are approval-gated before any page goes live.`, stats + board + section('Content Opportunities','Refresh existing URLs first. Avoid duplicate or cannibalizing content.','edit','purple',rows.length, simpleTable(['Client','Page','Content work','Priority','Recommended workflow','Gate'], rows)));
}
function ctrView(){
  const lowCtrOpps = clientScoped(state.data.opportunities).filter(o => o.opportunity_type === 'Low CTR' || Number(o.ctr || 0) < 2).slice(0, 12);
  const cards = lowCtrOpps.length ? `<div class="ctr-grid">${lowCtrOpps.map(o=>`<div class="card ctr-card"><div class="approval-top"><span class="tag ${classForStatus(o.status)}">${label(o.status)}</span><span class="tag ${clientDot(o.client_id)}">${esc(clientName(o.client_id))}</span></div><h3>${esc(safePath(o.page))}</h3><div class="muted">Current CTR: ${pct(o.ctr)} · Avg position ${Number(o.position).toFixed(1)}</div><div class="proposed"><small>Recommended title/meta test workflow</small><p>${esc(o.recommended_workflow)}</p></div><div class="metric-strip"><div><b>${pct(o.ctr)}</b><span>Start CTR</span></div><div><b>${fmt(o.clicks)}</b><span>Clicks</span></div><div><b>${fmt(o.impressions)}</b><span>Impr.</span></div></div><div class="ctr-footer"><span>${esc(o.problem)}</span><button class="btn primary" data-open-approvals>Request approval</button></div></div>`).join('')}</div>` : `<div class="card"><div class="empty">No CTR tests or low-CTR opportunities for ${esc(strictClientLabel())}.</div></div>`;
  setTimeout(()=>document.querySelectorAll('[data-open-approvals]').forEach(b=>b.onclick=()=>{state.section='Approvals';render()}),0);
  return page('CTR Tests',`Client-scoped title and meta tests for ${strictClientLabel()}. Hermes suggests a test, the user approves, baseline metrics lock, then SEO OS monitors the winner.`, cards);
}
function scheduleButton(label, active, attrs){
  return `<button class="seg-btn ${active?'active':''}" ${attrs}>${label}</button>`;
}
function scheduleView(){
  const showCal = state.schedView !== 'list';
  const range7 = state.schedRange !== '30';
  const rows = state.data.jobs.map(j => `<tr><td><span class="client-cell"><span class="dot ${clientDot(j.client_id)}"></span>${esc(clientName(j.client_id))}</span></td><td><strong>${esc(j.name)}</strong></td><td>${esc(j.cadence)}</td><td><strong>${esc(j.next_run)}</strong></td><td><span class="muted">${esc(j.last_run)}</span></td><td><span class="tag ${classForStatus(j.status)}">${label(j.status)}</span></td></tr>`);
  const scheduleRows = section('Managed Jobs','Recurring work list view from the design handoff.','calendar','blue',rows.length, simpleTable(['Client','Job','Cadence','Next run','Last run','Status'], rows));
  const jobs = state.data.jobs;
  const weekDays = [
    {short:'Mon', num:'19', events:[jobs.find(j=>j.id==='job_dw_data'), jobs.find(j=>j.id==='job_ai_data')]},
    {short:'Tue', num:'20', events:[jobs.find(j=>j.id==='job_dw_opp')]},
    {short:'Wed', num:'21', events:[jobs.find(j=>j.id==='job_reviews')]},
    {short:'Thu', num:'22', events:[jobs.find(j=>j.id==='job_dw_data')]},
    {short:'Fri', num:'23', events:[jobs.find(j=>j.id==='job_ai_data')]},
    {short:'Sat', num:'24', events:[]},
    {short:'Sun', num:'25', events:[]}
  ];
  const week = `<div class="sched-week">${weekDays.map((d,i)=>`<div class="sched-day"><div class="sched-day-head ${i===0?'today':''}"><span>${d.short}</span><b>${d.num}</b></div>${d.events.filter(Boolean).map(j=>`<div class="sched-card ${j.status==='setup_needed'?'behind':''}"><div>${esc(j.next_run.includes('Tonight') ? j.next_run.replace('Tonight ','') : j.next_run)}</div><p>${esc(j.name)}</p><span><i class="dot ${clientDot(j.client_id)}"></i>${esc(clientName(j.client_id))}</span></div>`).join('') || '<div class="sched-empty">—</div>'}</div>`).join('')}</div>`;
  const monthCells = Array.from({length:35}, (_,i) => {
    const day = i + 1;
    const event = day===2 ? jobs[0] : day===3 ? jobs[2] : day===5 ? jobs[1] : day===9 ? jobs[3] : null;
    return `<div class="month-cell ${day>30?'muted-cell':''}"><div class="month-num">${day<=30?day:''}</div>${event?`<div class="month-bar"><b>${esc(event.next_run.split(' ').pop())}</b> ${esc(event.name)}</div>`:''}</div>`;
  }).join('');
  const month = `<div class="month-cal"><div class="month-dow">${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(h=>`<div>${h}</div>`).join('')}</div><div class="month-grid">${monthCells}</div></div>`;
  const setupNeeded = jobs.filter(j=>j.status==='setup_needed');
  const overdue = setupNeeded.length ? `<div class="sched-overdue">${icon('calendar',15)}<span><b>${setupNeeded.length} setup-needed job${setupNeeded.length===1?'':'s'} —</b> ${esc(setupNeeded.map(j=>j.name).join(', '))}</span></div>` : '';
  const header = `<div class="sched-page-head"><div><h1>Schedule</h1><p>Recurring agent work for the week ahead. Job IDs and scripts stay inside Hermes.</p></div><div class="sched-controls">${showCal?`<div class="segmented">${scheduleButton('7 days', range7, 'data-sched-range="7"')}${scheduleButton('30 days', !range7, 'data-sched-range="30"')}</div>`:''}<div class="segmented">${scheduleButton('Calendar', showCal, 'data-sched-view="calendar"')}${scheduleButton('List', !showCal, 'data-sched-view="list"')}</div></div></div>`;
  setTimeout(()=>{
    document.querySelectorAll('[data-sched-view]').forEach(b=>b.onclick=()=>{state.schedView=b.dataset.schedView;render()});
    document.querySelectorAll('[data-sched-range]').forEach(b=>b.onclick=()=>{state.schedRange=b.dataset.schedRange;render()});
  },0);
  return header + overdue + (showCal ? (range7 ? week : month) : scheduleRows);
}
function activityView(){
  const rows = state.data.events.map(e => `<tr><td>${new Date(e.created_at).toLocaleString()}</td><td>${esc(clientName(e.client_id))}</td><td><span class="tag blue">${label(e.source)}</span></td><td>${label(e.event_type)}</td><td><span class="tag ${classForStatus(e.status)}">${label(e.status)}</span></td><td>${esc(e.summary)}</td><td>${esc(e.next_action)}</td></tr>`);
  return page('Activity Log','Important operational outcomes only. Not a Discord transcript.', section('Timeline','Requests, decisions, refreshes, blockers, artifacts, and next actions','⌁','purple',rows.length, simpleTable(['Time','Client','Source','Type','Status','What happened','Next action'], rows)));
}
function reportProfileCard(c){
  const m = state.data.metrics.find(x => x.client_id === c.id) || {clicks:0, clicks_delta:0};
  const delta = Number(m.clicks_delta || 0);
  return `<button class="report-profile-card" data-report-client="${esc(c.id)}"><span class="dot big ${clientDot(c.id)}"></span><div><strong>${esc(c.name)}</strong><span class="mono">${esc(c.domain)}</span></div><div class="report-headline"><b>${fmt(m.clicks)}</b><em class="delta ${delta>=0?'good':'bad'}">${delta>=0?'+':''}${fmt(delta)}</em><small>clicks · 28d</small></div><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#AAB5B3" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg></button>`;
}
function reportsIndex(){
  const profiles = state.data.visible_clients.map(reportProfileCard).join('');
  const reportRows = state.data.artifacts.map(a => `<tr><td><span class="client-cell"><span class="dot ${clientDot(a.client_id)}"></span>${esc(clientName(a.client_id))}</span></td><td><strong>${esc(a.title)}</strong></td><td><span class="tag purple">${label(a.artifact_type)}</span></td><td><span class="muted">${new Date(a.updated_at).toLocaleString()}</span></td><td><span class="tag ${classForStatus(a.status)}">${label(a.status)}</span></td><td style="text-align:right"><button class="open-report-btn">Open ${icon('file',12)}</button></td></tr>`);
  const body = `<div class="reports-title"><h1>Reports & Artifacts</h1><p>Open a website profile for a full performance snapshot, or browse generated reports and recent agent runs below.</p></div><div class="report-label">Website profiles</div><div class="report-profile-grid">${profiles}</div><div class="report-label">All reports & runs</div><div class="card section-card"><div class="table-wrap"><table><thead><tr><th>Client</th><th>Title</th><th>Type</th><th>Updated</th><th>Status</th><th style="text-align:right">Open</th></tr></thead><tbody>${reportRows.join('')}</tbody></table></div></div>`;
  setTimeout(()=>document.querySelectorAll('[data-report-client]').forEach(b=>b.onclick=()=>{state.reportClient=b.dataset.reportClient;render()}),0);
  return body;
}
function reportsDetail(){
  const c = state.data.clients.find(x => x.id === state.reportClient) || state.data.visible_clients[0];
  const m = state.data.metrics.find(x => x.client_id === c.id) || {clicks:0,clicks_delta:0,impressions:0,impressions_delta:0,ctr:0,ctr_delta:0,avg_rank:0,avg_rank_delta:0,conversions:0};
  const metricCards = [
    ['Clicks', fmt(m.clicks), `${m.clicks_delta>=0?'+':''}${fmt(m.clicks_delta)}`, m.clicks_delta>=0],
    ['Impressions', fmt(m.impressions), `${m.impressions_delta>=0?'+':''}${fmt(m.impressions_delta)}`, m.impressions_delta>=0],
    ['CTR', pct(m.ctr), `${m.ctr_delta>=0?'+':''}${m.ctr_delta} pts`, m.ctr_delta>=0],
    ['Avg position', Number(m.avg_rank).toFixed(1), `${Math.abs(m.avg_rank_delta)} ${m.avg_rank_delta<=0?'better':'worse'}`, m.avg_rank_delta<=0],
    ['Conversions', fmt(m.conversions), 'tracked', true]
  ].map(([label,value,delta,good]) => `<div class="snap-metric"><span>${label}</span><b>${value}</b><em class="delta ${good?'good':'bad'}">${delta}</em></div>`).join('');
  const opps = state.data.opportunities.filter(o=>o.client_id===c.id).slice(0,5);
  const topPages = opps.map(o=>`<tr><td class="mono" style="color:#1D4ED8;font-weight:600">${esc(safePath(o.page))}</td><td style="text-align:right">${fmt(o.impressions)}</td><td style="text-align:right">${fmt(o.clicks)}</td><td style="text-align:right;font-weight:600">${pct(o.ctr)}</td><td style="text-align:right">${Number(o.position).toFixed(1)}</td></tr>`);
  const health = [['Search Console',c.gsc_status],['Analytics',c.ga4_status],['Repository',c.repo_status],['review source',c.zernio_status],['Hermes profile',c.hermes_profile],['Workspace',c.workspace]].map(([k,v])=>`<div class="health-row"><span class="dot ${String(v).includes('connected')?'green':'amber'}"></span><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('');
  const body = `<button class="back-report" data-back-reports>${icon('list',14)}All reports</button><div class="snapshot-head"><div><h1>${esc(c.name)} — SEO Snapshot</h1><p><span class="mono">${esc(c.domain)}</span> · ${esc(m.period_label || 'Last 28 days')}</p></div><button class="export-report">${icon('file',14)}Export report</button></div><div class="snap-metrics">${metricCards}</div><div class="snapshot-grid"><div class="card chart-card"><div><span>Clicks · last 28 days</span><em class="delta ${m.clicks_delta>=0?'good':'bad'}">${m.clicks_delta>=0?'+':''}${fmt(m.clicks_delta)}</em></div><svg viewBox="0 0 100 100" preserveAspectRatio="none"><polyline points="0,78 12,72 25,66 38,70 50,52 62,43 75,39 88,28 100,20" fill="none" stroke="#1F7A43" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"></polyline><polyline points="0,100 0,78 12,72 25,66 38,70 50,52 62,43 75,39 88,28 100,20 100,100" fill="#1F7A43" fill-opacity=".1" stroke="none"></polyline></svg></div><div class="card site-health"><div class="report-label" style="margin:0 0 6px">Site health</div>${health}</div></div><div class="card section-card"><div class="report-table-title">Top pages by impressions</div>${simpleTable(['Page','Impressions','Clicks','CTR','Avg position'], topPages)}</div>`;
  setTimeout(()=>document.querySelector('[data-back-reports]')?.addEventListener('click',()=>{state.reportClient=null;render()}),0);
  return body;
}
function reportsView(){
  return state.reportClient ? reportsDetail() : reportsIndex();
}
function settingsView(){
  const s=state.data.settings;
  const clientRows = state.data.clients.map(c => `<div class="delete-client-row"><div><strong>${esc(c.name)}</strong><span>${esc(c.domain)} · ${esc(c.hermes_profile)} · ${esc(c.client_type||'local')}</span></div><button class="btn danger" data-delete-client="${esc(c.id)}">Delete client</button></div>`).join('');
  const body = `<div class="grid" style="grid-template-columns:1.1fr .9fr"><div class="card settings-card"><h3>Add new client</h3><p>Onboard a new client. A Hermes profile, workspace, and dashboard row are created automatically. Then connect GSC + GA4.</p><div style="display:flex;flex-direction:column;gap:8px"><label>Client ID *</label><input class="modal-input" id="acId" placeholder="e.g. edel-roofing" /><label>Business name *</label><input class="modal-input" id="acName" placeholder="e.g. Edel Roofing" /><label>Domain *</label><input class="modal-input" id="acDomain" placeholder="https://edelroofing.com" /><label>Role / niche</label><input class="modal-input" id="acRole" placeholder="e.g. Roofing contractor" /><label>Client type</label><select class="modal-input" id="acType"><option value="local">Local business (GBP, map pack)</option><option value="national">National / e-commerce (no GBP)</option></select><button class="btn primary" id="addClientSubmit">Create client</button></div></div><div class="card settings-card"><h3>Connection status</h3><div class="connection-list"><div><span>Scheduler</span><strong>${esc(s.scheduler_mode)}</strong></div><div><span>Model policy</span><strong>Cheap by default</strong></div><div><span>Approval safety</span><strong>State first, production later</strong></div></div></div><div class="card settings-card" style="grid-column:1/-1"><h3>Safe action policy</h3><p>${esc(s.safe_actions)}</p><p><strong>Model policy:</strong> ${esc(s.model_policy)}</p><p><strong>Product setup goal:</strong> ${esc(s.onboarding_goal)}</p></div><div class="card settings-card danger-zone" style="grid-column:1/-1"><h3>Danger zone: delete client</h3><p>Settings-only destructive control. This removes the client and client-scoped prototype rows from SQLite. Production v1 should archive/export first, then require a stronger confirmation.</p><div class="delete-client-list">${clientRows}</div></div></div>`;
  setTimeout(()=>{
    document.querySelectorAll('[data-delete-client]').forEach(b=>b.onclick=()=>deleteClient(b.dataset.deleteClient));
    const submit = document.getElementById('addClientSubmit');
    if(submit) submit.onclick = showAddClientModal;
  },0);
  return page('Settings & Routing','Client routing, data integrations, model policy, and safe action rules.', body);
}

async function showAddClientModal(){
  const id = document.getElementById('acId')?.value?.trim() || '';
  const name = document.getElementById('acName')?.value?.trim() || '';
  let domain = document.getElementById('acDomain')?.value?.trim() || '';
  const role = document.getElementById('acRole')?.value?.trim() || 'SEO client';
  const client_type = document.getElementById('acType')?.value || 'local';
  if(!id || !name || !domain){ toast('Client ID, name, and domain are required', true); return; }
  if(!domain.startsWith('http')){ domain = 'https://' + domain; }
  try{
    const r = await api(`/api/clients/${encodeURIComponent(id)}/create`, {method:'POST', body:JSON.stringify({id, name, domain, role, client_type})});
    if(r.ok){
      toast(`Client "${name}" created ✓`);
      state.client = 'all';
      state.data = r.summary;
      render();
    } else {
      toast(r.error || 'Failed to create client', true);
    }
  }catch(e){ toast('Create client failed', true); console.error(e); }
}

async function deleteClient(clientId){
  const client = state.data.clients.find(c => c.id === clientId);
  if(!client) return;
  const ok = window.confirm(`Delete ${client.name} from SEO OS? This removes its prototype tasks, jobs, approvals, opportunities, reports, and activity rows. Type DELETE in the next prompt to confirm.`);
  if(!ok) return;
  const typed = window.prompt(`Type DELETE to permanently remove ${client.name} from this prototype:`);
  if(typed !== 'DELETE') { toast('Client deletion cancelled'); return; }
  try{
    const payload = await api(`/api/clients/${encodeURIComponent(clientId)}/delete`, {method:'POST', body:JSON.stringify({confirm:'DELETE'})});
    state.client = 'all';
    state.data = payload.summary;
    toast(`Deleted client: ${client.name}`);
    render();
  }catch(e){ toast('Client deletion failed', true); console.error(e); }
}

function commandQueueView(){
  const d = state.data;
  const queue = d.opportunity_queue || [];
  const filters = ['All','High','Medium','Low'];
  const fhtml = `<div class="filters">${filters.map(f=>`<button class="btn filter ${state.filter===f?'active':''}" data-filter="${f}">${f}</button>`).join('')}</div>`;
  let rows = queue;
  if(state.filter==='High') rows = rows.filter(q=>q.impact==='High');
  if(state.filter==='Medium') rows = rows.filter(q=>q.impact==='Medium');
  if(state.filter==='Low') rows = rows.filter(q=>q.impact==='Low');
  const tableRows = rows.map(q => `<tr><td><span class="client-cell"><span class="dot ${clientDot(q.client_id)}"></span>${esc(q.business)}</span></td><td><span class="tag ${q.type==='Opportunity'?'blue':q.type==='GSC'?'green':q.type==='GBP'?'purple':'amber'}">${esc(q.type_label)}</span></td><td><strong>${esc(q.opportunity)}</strong><div class="muted" style="font-size:11px">${esc(q.evidence)}</div></td><td><span class="tag ${q.impact==='High'?'red':q.impact==='Medium'?'amber':'green'}">${esc(q.impact)}</span></td><td><span class="tag ${q.effort==='Low'?'green':q.effort==='Medium'?'amber':'red'}">${esc(q.effort)}</span></td><td class="muted" style="max-width:200px">${esc(q.next_action)}</td><td><span class="tag ${classForStatus(q.status)}">${label(q.status)}</span></td></tr>`);
  setTimeout(()=>document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{state.filter=b.dataset.filter;render()}),0);
  return page('Command Queue','Unified action list — SERP gaps, GBP gaps, and opportunities sorted by impact','All priorities, one queue.', fhtml + section('Queue',`${rows.length} items`,'list','blue',rows.length, simpleTable(['Client','Type','Opportunity','Impact','Effort','Next Action','Status'], tableRows)));
}

function outreachCardsView(){
  const prospects = (window._prospectData || []);
  if(prospects.length === 0) return page('Outreach Cards','One-click pitch generator — rank + competitor gaps + channel recommendation.','<div class="empty">No prospects yet. Add prospects manually or import from Google Sheets.</div>');
  const cards = prospects.map(p => {
    const rank = p.rank || '—';
    const score = p.score || '—';
    const channel = p.channel || 'FB DM';
    const pitch = `Hey! I was searching for "${p.keyword || 'your service'}" in ${p.city || 'your area'} and came across ${p.name}. You're ranking #${rank} — I can help you get to top 3. Mind if I send a quick free audit?`;
    return `<div class="card outreach-card">
      <div class="outreach-header"><strong>${esc(p.name)}</strong><span class="tag blue">${esc(channel)}</span></div>
      <div class="outreach-meta"><span>📍 ${esc(p.city||'—')}</span><span>🏷 ${esc(p.niche||'—')}</span><span>📊 Rank: ${esc(rank)}</span><span>⭐ Score: ${esc(score)}</span></div>
      <div class="outreach-pitch">${esc(pitch)}</div>
      <div class="outreach-actions"><button class="btn primary" data-copy-pitch="${p.id}">📋 Copy Pitch</button><button class="btn" data-dm-opener="${p.id}">📨 DM Opener</button></div>
    </div>`;
  }).join('');
  setTimeout(()=>{
    document.querySelectorAll('[data-copy-pitch]').forEach(b=>b.onclick=async()=>{
      const p = prospects.find(x=>x.id===b.dataset.copyPitch);
      if(p){
        const pitch = `Hey! I was searching for "${p.keyword||'your service'}" in ${p.city||'your area'} and came across ${p.name}. You're ranking #${p.rank||'—'} — I can help you get to top 3. Mind if I send a quick free audit?`;
        await navigator.clipboard.writeText(pitch);
        toast('Pitch copied ✓');
      }
    });
    document.querySelectorAll('[data-dm-opener]').forEach(btn => { btn.onclick = async () => { try { const r = await api('/api/prospects/dm_opener?id=' + btn.dataset.dmOpener); if(r.ok && r.opener) { await navigator.clipboard.writeText(r.opener); toast('DM opener copied ✓'); } } catch(e) { toast('Copy failed', true); } }; });
  },0);
  return page('Outreach Cards','One-click pitch generator for your prospects — copy and send.','<div class="outreach-grid">' + cards + '</div>');
}

function renderView(){
  const map = {'Command Center':commandCenter,'Clients / Sites':clientsView,'Approvals':approvalsView,'Opportunities':opportunitiesView,'Command Queue':commandQueueView,'GSC Keywords':gscView,'Content Briefs':contentBriefsView,'Prospects':prospectsView,'Activity Log':activityView,'Settings':settingsView};
  $('#view').innerHTML = (map[state.section] || commandCenter)();
  if(state.section === 'Prospects' && window.bindProspectsView) window.bindProspectsView();
}
function render(){ renderNav(); renderTabs(); renderContext(); renderView(); bindNotifyBtn(); bindSidebarToggle(); }
function bindSidebarToggle(){
  const btn = $('#sidebarToggle');
  if(btn) btn.onclick = () => {
    state.sidebarCollapsed = !state.sidebarCollapsed;
    const app = $('#app');
    if(state.sidebarCollapsed){ app.classList.add('sidebar-collapsed'); app.classList.remove('sidebar-open'); }
    else { app.classList.remove('sidebar-collapsed'); }
  };
}
function toast(msg, error=false){
  const el=document.createElement('div'); el.className=`toast ${error?'error':''}`; el.textContent=msg; document.body.appendChild(el); setTimeout(()=>el.remove(),2600);
}
function bindNotifyBtn(){
  const btn = $('#notifyDiscordBtn');
  if(btn){
    btn.onclick = async () => {
      const cName = clientName(state.client);
      const kpis = state.data.kpis;
      const msg = `📊 **SEO OS Update — ${cName}**\n\nSites monitored: ${kpis.sites_monitored} | Open tasks: ${kpis.open_tasks} | High-impact opps: ${kpis.high_impact_opportunities} | Active jobs: ${kpis.active_jobs}\n\n⚠️ ${kpis.pending_approvals} pending approval(s) need your review.`;
      try { await api('/api/discord/notify',{method:'POST',body:JSON.stringify({message:msg,client_id:state.client})}); toast('Sent to Discord ✓'); }
      catch(e){ toast('Discord send failed', true); console.error(e); }
    };
  }
  const threadBtn = $('#createThreadBtn');
  if(threadBtn){
    threadBtn.onclick = async () => {
      if(state.client === 'all'){ toast('Select a specific client first', true); return; }
      try {
        const r = await api('/api/discord/thread',{method:'POST',body:JSON.stringify({client_id:state.client})});
        if(r.thread_id) toast(`Thread created: ${r.thread_name} ✓`);
        else toast(r.message || 'Thread exists', true);
      }catch(e){ toast('Thread creation failed', true); console.error(e); }
    };
  }
  const gscBtn = $('#gscPullBtn');
  if(gscBtn){
    gscBtn.onclick = async () => {
      try { const r = await api('/api/gsc/pull',{method:'POST',body:JSON.stringify({client_id:state.client})}); toast('GSC data pulled ✓'); load().catch(()=>{}); }
      catch(e){ toast('GSC pull failed', true); console.error(e); }
    };
  }
  const ga4Btn = $('#ga4PullBtn');
  if(ga4Btn){
    ga4Btn.onclick = async () => {
      try { const r = await api('/api/refresh',{method:'POST',body:JSON.stringify({client_id:state.client})}); toast('GA4 data pulled ✓'); load().catch(()=>{}); }
      catch(e){ toast('GA4 pull failed', true); console.error(e); }
    };
  }
  // Show last pull timestamps
  const events = state.data.events || [];
  const lastGa4 = events.find(e => e.source === 'ga4_pull');
  const lastGsc = events.find(e => e.source === 'gsc_pull');
  const lastGa4El = $('#lastGa4Pull');
  const lastGscEl = $('#lastGscPull');
  if(lastGa4El && lastGa4) lastGa4El.textContent = new Date(lastGa4.created_at).toLocaleString();
  if(lastGscEl && lastGsc) lastGscEl.textContent = new Date(lastGsc.created_at).toLocaleString();
}
$('#refreshBtn').onclick = async () => {
  try { const r = await api('/api/refresh',{method:'POST',body:JSON.stringify({client_id:state.client})}); state.data=r.summary; toast('Dashboard data refreshed'); render(); }
  catch(e){ toast('Refresh failed', true); console.error(e); }
};
load().catch(e => { console.error(e); $('#view').innerHTML = `<div class="warning">Could not load SEO OS data. Is server.py running?</div>`; });

/* ═══════════════════════════════════════════════════════════════════════════
   PROSPECTS MODULE — Inline in app.js for reliability
   ═══════════════════════════════════════════════════════════════════════════ */

function prospectsView(){
  const allProspects = (window._prospectData || []);
  const stats = window._prospectStats || { by_status: {}, by_pipeline: {}, by_city: {} };
  const currentFilter = state.prospectFilter || 'all';
  const searchQ = state.prospectSearch || '';

  // Filter prospects
  let prospects = allProspects;
  if (currentFilter !== 'all') {
    prospects = prospects.filter(p => (p.status || 'new') === currentFilter);
  }
  if (searchQ) {
    const q = searchQ.toLowerCase();
    prospects = prospects.filter(p =>
      (p.name||'').toLowerCase().includes(q) ||
      (p.keyword||'').toLowerCase().includes(q) ||
      (p.city||'').toLowerCase().includes(q) ||
      (p.niche||'').toLowerCase().includes(q)
    );
  }

  // Status filter chips
  const statuses = Object.keys(stats.by_status);
  const allCount = allProspects.length;
  const filterChips = `<div class="prospect-filters">
    <button class="filter-chip ${currentFilter==='all'?'active':''}" data-prospect-filter="all">All (${allCount})</button>
    ${statuses.map(s => `<button class="filter-chip ${currentFilter===s?'active':''}" data-prospect-filter="${s}">${s.replace(/_/g,' ')} (${stats.by_status[s]})</button>`).join('')}
  </div>`;

  const stages = ['new', 'contacted', 'pitched', 'negotiation', 'closed_won', 'closed_lost'];
  const stageLabels = {new:'New',contacted:'Contacted',pitched:'Pitched',negotiation:'Negotiation',closed_won:'Closed-Won',closed_lost:'Closed-Lost'};
  const pipelineBar = `<div class="pipeline-bar">${stages.map(s => `<div class="pipeline-stage ${stats.by_pipeline[s] ? 'active' : ''}"><div class="pipeline-count">${stats.by_pipeline[s] || 0}</div><div class="pipeline-label">${stageLabels[s]}</div></div>`).join('')}</div>`;

  const statusOptions = ['new','contacted','pitched','negotiation','closed_won','closed_lost','not_interested','wrong_city','engaged','message_sent','replied','active'];
  const channelOptions = ['FB DM','FB DM Sent','Call','Email','Email + FB','LinkedIn','In Person'];

  const rows = prospects.map(p => {
    const statusSel = `<select class="status-select" data-status-change="${p.id}" data-current="${p.status||'new'}">${statusOptions.map(s => `<option value="${s}" ${(p.status||'new')===s?'selected':''}>${s.replace(/_/g,' ')}</option>`).join('')}</select>`;
    const channelSel = `<select class="channel-select" data-channel-change="${p.id}">${channelOptions.map(c => `<option value="${c}" ${(p.channel||'FB DM')===c?'selected':''}>${c}</option>`).join('')}</select>`;
    return `<tr>
      <td><strong>${esc(p.name)}</strong></td>
      <td>${esc(p.keyword)}</td>
      <td>${esc(p.city)}</td>
      <td>${esc(p.niche)}</td>
      <td class="rank-cell">${p.rank||'—'}</td>
      <td class="score-cell">${p.score||'—'}</td>
      <td class="website-cell">${p.website ? `<a href="${esc(p.website)}" target="_blank" rel="noopener" class="website-link" title="${esc(p.website)}">${esc(safeHost(p.website)||p.website.replace(/^https?:\/\//,''))}</a>` : '—'}</td>
      <td>${statusSel}</td>
      <td>${channelSel}</td>
      <td><span class="tag ${p.pipeline_stage==='closed_won'?'green':p.pipeline_stage==='closed_lost'?'red':'blue'}">${(p.pipeline_stage||'new').replace(/_/g,' ')}</span></td>
      <td class="prospect-actions">
        <button class="icon-btn reach-out-btn" data-reach-out="${p.id}" title="Generate outreach message">📨</button>
        <button class="icon-btn" data-log-activity="${p.id}" title="Log activity">📝</button>
        <button class="icon-btn" data-advance="${p.id}" title="Advance pipeline">→</button>
        <button class="icon-btn" data-delete-prospect="${p.id}" title="Delete">✕</button>
      </td>
    </tr>`;
  }).join('');

  return page('Prospects', `Showing ${prospects.length} of ${allProspects.length} prospects.`, `${pipelineBar}${filterChips}<div class="prospect-toolbar"><button class="btn primary" id="addProspectBtn">+ Add Prospect</button><input class="search-input" id="prospectSearch" placeholder="Search name, keyword, city..." value="${esc(searchQ)}" /></div><div class="card section-card"><div class="table-wrap"><table><thead><tr><th>Business</th><th>Keyword</th><th>City</th><th>Niche</th><th>Local Rank</th><th>Score</th><th>Website</th><th>Status</th><th>Channel</th><th>Pipeline</th><th>Actions</th></tr></thead><tbody>${rows || '<tr><td colspan="11" class="empty">No prospects match this filter.</td></tr>'}</tbody></table></div></div>`);
}

function showReachOutModal(prospectId){
  const p = (window._prospectData || []).find(x => x.id === prospectId);
  if(!p) return;

  const rank = p.rank || '—';
  const keyword = p.keyword || 'your service';
  const city = p.city || 'your area';
  const name = p.name;
  const channel = p.channel || 'FB DM';

  // Generate messages based on channel
  const fbDM = `Hey! Your business showed up when I was searching for "${keyword}" in ${city}. I noticed you're ranking #${rank} on Google — I can help you get to top 3. Mind if I send over a quick free audit? No pitch, just the data.`;
  const email = `Subject: Quick question about your Google ranking\n\nHey there,\n\nYour business showed up when I was searching for "${keyword}" in ${city}. I noticed you're ranking #${rank} on Google's map pack.\n\nI help local businesses get more calls from Google. I put together a quick free audit showing exactly what it would take to get you into the top 3.\n\nWorth a look?\n\n— Eddie`;
  const call = `Hi, this is Eddie with RankRGV. I was searching for "${keyword}" in ${city} and your business came up — I noticed you're ranking #${rank} on Google. I help local businesses get more calls from Google map pack. I've got a quick free audit that shows exactly what to do to get to top 3. Got 2 minutes?`;
  const linkedin = `Hey! Your business came up when I was researching "${keyword}" in ${city}. I noticed you're ranking #${rank} on Google — I help local businesses get more calls from Google. Would you be open to a quick free audit?`;

  const messages = { 'FB DM': fbDM, 'Email': email, 'Call': call, 'LinkedIn': linkedin };
  const currentMsg = messages[channel] || fbDM;

  const modal = document.createElement('div');
  modal.className = 'modal-backdrop';
  modal.innerHTML = `<div class="prospect-modal reach-out-modal">
    <div class="modal-head"><h3>📨 Reach Out</h3><button class="modal-close" data-close-modal>×</button></div>
    <div class="modal-body">
      <div class="reach-out-tabs">
        <button class="reach-tab ${channel==='FB DM'?'active':''}" data-msg-type="FB DM">DM</button>
        <button class="reach-tab ${channel==='Email'?'active':''}" data-msg-type="Email">Email</button>
        <button class="reach-tab ${channel==='Call'?'active':''}" data-msg-type="Call">Call Script</button>
        <button class="reach-tab ${channel==='LinkedIn'?'active':''}" data-msg-type="LinkedIn">LinkedIn</button>
      </div>
      <textarea class="reach-out-msg" id="reachOutMsg">${esc(currentMsg)}</textarea>
      <div class="reach-out-actions">
        <button class="btn primary" id="copyReachOut">📋 Copy Message</button>
        <button class="btn" id="markSent">✓ Mark as Sent</button>
      </div>
      <div class="reach-out-status">
        <label>Status after sending:</label>
        <select id="postSendStatus">
          <option value="contacted">Contacted</option>
          <option value="message_sent">Message Sent</option>
          <option value="engaged">Engaged</option>
          <option value="pitched">Pitched</option>
        </select>
      </div>
    </div>
  </div>`;
  document.body.appendChild(modal);

  modal.querySelector('[data-close-modal]').onclick = () => modal.remove();

  // Tab switching
  modal.querySelectorAll('.reach-tab').forEach(tab => {
    tab.onclick = () => {
      modal.querySelectorAll('.reach-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const type = tab.dataset.msgType;
      const msgs = { 'FB DM': fbDM, 'Email': email, 'Call': call, 'LinkedIn': linkedin };
      modal.querySelector('#reachOutMsg').value = msgs[type] || fbDM;
    };
  });

  modal.querySelector('#copyReachOut').onclick = async () => {
    const msg = modal.querySelector('#reachOutMsg').value;
    await navigator.clipboard.writeText(msg);
    toast('Message copied ✓');
  };

  modal.querySelector('#markSent').onclick = async () => {
    const newStatus = modal.querySelector('#postSendStatus').value;
    await api('/api/prospects/update', { method: 'POST', body: JSON.stringify({ id: prospectId, status: newStatus }) });
    // Update local data
    if(p) p.status = newStatus;
    toast(`Status → ${newStatus.replace(/_/g,' ')} ✓`);
    modal.remove();
    render();
  };
}

function showCreateModal(){
  const modal = document.createElement('div');
  modal.className = 'modal-backdrop';
  modal.innerHTML = `<div class="prospect-modal"><div class="modal-head"><h3>New Prospect</h3><button class="modal-close" data-close-modal>×</button></div><div class="modal-body"><label>Business Name *</label><input class="modal-input" id="newName" placeholder="e.g. Edel Roofing" /><label>Phone</label><input class="modal-input" id="newPhone" placeholder="(956) 555-1234" /><label>Email</label><input class="modal-input" id="newEmail" type="email" placeholder="owner@example.com" /><label>Website</label><input class="modal-input" id="newWebsite" placeholder="https://example.com" /><label>Keyword</label><input class="modal-input" id="newKeyword" placeholder="e.g. roofing contractor" /><label>City</label><input class="modal-input" id="newCity" placeholder="e.g. Edinburg" /><label>Niche</label><input class="modal-input" id="newNiche" placeholder="e.g. Roofing" /><label>Current Rank (1-10)</label><input class="modal-input" id="newRank" type="number" min="1" max="10" placeholder="4" /><label>Score (1-100)</label><input class="modal-input" id="newScore" type="number" min="1" max="100" placeholder="7" /><label>Channel</label><select class="modal-input" id="newChannel"><option value="FB DM">FB DM</option><option value="Email">Email</option><option value="Call">Call</option><option value="LinkedIn">LinkedIn</option></select><label>Notes</label><textarea class="modal-input" id="newNotes" rows="2" placeholder="Any relevant info..."></textarea><button class="btn primary" id="saveNewProspect">Create Prospect</button></div></div>`;
  document.body.appendChild(modal);
  modal.querySelector('[data-close-modal]').onclick = () => modal.remove();
  modal.querySelector('#saveNewProspect').onclick = async () => {
    const name = document.getElementById('newName').value.trim();
    if(!name) { toast('Business name is required', true); return; }
    const data = { name, phone: document.getElementById('newPhone').value.trim(), email: document.getElementById('newEmail').value.trim(), website: document.getElementById('newWebsite').value.trim(), keyword: document.getElementById('newKeyword').value.trim(), city: document.getElementById('newCity').value.trim(), niche: document.getElementById('newNiche').value.trim(), rank: document.getElementById('newRank').value, score: document.getElementById('newScore').value, channel: document.getElementById('newChannel').value, notes: document.getElementById('newNotes').value.trim() };
    const r = await api('/api/prospects/create', { method: 'POST', body: JSON.stringify(data) });
    if(r.ok) { toast('Prospect created ✓'); modal.remove(); load().then(() => render()); }
    else { toast('Failed to create prospect', true); }
  };
}

function showActivityModal(prospectId){
  const modal = document.createElement('div');
  modal.className = 'modal-backdrop';
  modal.innerHTML = `<div class="prospect-modal"><div class="modal-head"><h3>Log Activity</h3><button class="modal-close" data-close-modal>×</button></div><div class="modal-body"><label>Activity Type</label><select class="modal-input" id="activityType"><option value="call">Phone Call</option><option value="fb_dm">FB DM</option><option value="email">Email</option><option value="message">Text Message</option><option value="linkedin">LinkedIn</option><option value="in_person">In Person</option><option value="research">Research</option><option value="note">General Note</option></select><label>Note</label><textarea class="modal-input" id="activityNote" rows="3" placeholder="What happened?"></textarea><button class="btn primary" id="saveActivity">Log Activity</button></div></div>`;
  document.body.appendChild(modal);
  modal.querySelector('[data-close-modal]').onclick = () => modal.remove();
  modal.querySelector('#saveActivity').onclick = async () => {
    const type = document.getElementById('activityType').value;
    const note = document.getElementById('activityNote').value;
    await api('/api/prospects/log_activity', { method: 'POST', body: JSON.stringify({ prospect_id: prospectId, activity_type: type, note: note }) });
    toast('Activity logged ✓'); modal.remove(); load().then(() => render());
  };
}

function bindProspectsView(){
  const addBtn = document.getElementById('addProspectBtn');
  if(addBtn) addBtn.onclick = showCreateModal;

  // Search (client-side filter)
  const searchInput = document.getElementById('prospectSearch');
  if(searchInput) searchInput.oninput = debounceFn((e) => {
    state.prospectSearch = e.target.value;
    render();
  }, 300);

  // Status filter chips
  document.querySelectorAll('[data-prospect-filter]').forEach(btn => {
    btn.onclick = () => {
      state.prospectFilter = btn.dataset.prospectFilter;
      render();
    };
  });

  // Status dropdown change
  document.querySelectorAll('[data-status-change]').forEach(sel => {
    sel.onchange = async () => {
      const newStatus = sel.value;
      const oldStatus = sel.dataset.current;
      if (newStatus === oldStatus) return;
      sel.disabled = true;
      try {
        const r = await api('/api/prospects/update', {
          method: 'POST',
          body: JSON.stringify({ id: sel.dataset.statusChange, status: newStatus })
        });
        if (r.ok) {
          // Update local data
          const p = window._prospectData.find(x => x.id === sel.dataset.statusChange);
          if (p) p.status = newStatus;
          sel.dataset.current = newStatus;
          // Update stats
          window._prospectStats.by_status[oldStatus] = (window._prospectStats.by_status[oldStatus] || 1) - 1;
          window._prospectStats.by_status[newStatus] = (window._prospectStats.by_status[newStatus] || 0) + 1;
          toast(`Status → ${newStatus.replace(/_/g,' ')} ✓`);
          render();
        } else {
          sel.value = oldStatus;
          toast('Update failed', true);
        }
      } catch(e) {
        sel.value = oldStatus;
        toast('Update failed', true);
      } finally {
        sel.disabled = false;
      }
    };
  });

  document.querySelectorAll('[data-dm-opener]').forEach(btn => { btn.onclick = async () => { try { const r = await api('/api/prospects/dm_opener?id=' + btn.dataset.dmOpener); if(r.ok && r.opener) { await navigator.clipboard.writeText(r.opener); toast('DM opener copied ✓'); } } catch(e) { toast('Copy failed', true); } }; });
  document.querySelectorAll('[data-reach-out]').forEach(btn => { btn.onclick = () => showReachOutModal(btn.dataset.reachOut); });
  document.querySelectorAll('[data-log-activity]').forEach(btn => { btn.onclick = () => showActivityModal(btn.dataset.logActivity); });
  document.querySelectorAll('[data-advance]').forEach(btn => { btn.onclick = async () => { const stages = ['new', 'contacted', 'pitched', 'negotiation', 'closed_won']; const r = await api('/api/prospects/detail?id=' + btn.dataset.advance); if(r.ok) { const current = r.pipeline_stage || 'new'; const idx = stages.indexOf(current); const next = stages[Math.min(idx + 1, stages.length - 1)]; await api('/api/prospects/update', { method: 'POST', body: JSON.stringify({ id: btn.dataset.advance, pipeline_stage: next }) }); toast(`Advanced to ${next} ✓`); load().then(() => render()); } }; });
  document.querySelectorAll('[data-delete-prospect]').forEach(btn => { btn.onclick = async () => { if(!confirm('Delete this prospect permanently?')) return; await api('/api/prospects/delete', { method: 'POST', body: JSON.stringify({ id: btn.dataset.deleteProspect }) }); toast('Prospect deleted'); load().then(() => render()); }; });
  document.querySelectorAll('[data-channel-change]').forEach(sel => { sel.onchange = async () => { const newChannel = sel.value; try { await api('/api/prospects/update', { method: 'POST', body: JSON.stringify({ id: sel.dataset.channelChange, channel: newChannel }) }); const p = window._prospectData.find(x => x.id === sel.dataset.channelChange); if(p) p.channel = newChannel; toast(`Channel → ${newChannel} ✓`); } catch(e) { toast('Channel update failed', true); } }; });
}

function debounceFn(fn, ms){ let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); }; }

async function initProspectsData(){
  try { const r = await api('/api/prospects/list'); if(r.ok) { window._prospectData = r.prospects || []; window._prospectStats = { total: r.total, by_status: r.by_status, by_pipeline: r.by_pipeline, by_city: r.by_city }; } } catch(e) { console.error('Failed to load prospects:', e); }
}

// Load prospects data on page load
initProspectsData();


