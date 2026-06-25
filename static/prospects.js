// Prospects module — SEO OS Dashboard
// Adds a "Prospects" tab with full CRM functionality

(function(){
  // Add Prospects tab to navigation (after renderNav runs)
  function addProspectsTab(){
    // The nav items are rendered by renderNav() into <nav id="nav">
    // We hook into renderNav to add our tab after the original nav is built
    if(!window._originalRenderNav) {
      window._originalRenderNav = window.renderNav;
      window.renderNav = function(){
        window._originalRenderNav();
        const nav = document.getElementById('nav');
        if(nav && !document.querySelector('[data-section="Prospects"]')) {
          const btn = document.createElement('button');
          btn.className = 'nav-item';
          btn.setAttribute('data-section', 'Prospects');
          btn.innerHTML = '<span class="ico">🎯</span> Prospects';
          nav.appendChild(btn);
        }
      };
    }
  }

  // ─── Utility ──────────────────────────────────────────────────────────

  function esc(s){ return String(s||'').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

  function fmt(n){ return Number(n||0).toLocaleString(); }

  // ─── DM Opener ────────────────────────────────────────────────────────

  async function copyDMOpener(prospectId){
    try {
      const r = await api('/api/prospects/dm_opener?id=' + encodeURIComponent(prospectId));
      if(r.ok && r.opener) {
        await navigator.clipboard.writeText(r.opener);
        toast('DM opener copied to clipboard ✓');
      } else { toast('Failed to generate DM opener', true); }
    } catch(e){ toast('Copy failed', true); }
  }

  // ─── Inline Edit ──────────────────────────────────────────────────────

  function inlineEdit(prospectId, field, currentVal, type='text'){
    const el = document.querySelector(`[data-prospect="${prospectId}"][data-field="${field}"]`);
    if(!el) return;
    
    if(type === 'select') {
      const options = {
        status: ['new', 'contacted', 'replied', 'pitched', 'closed_won', 'closed_lost', 'not_interested'],
        pipeline_stage: ['new', 'contacted', 'pitched', 'negotiation', 'closed_won', 'closed_lost'],
        channel: ['fb_dm', 'email', 'phone', 'linkedin', 'in_person'],
      };
      const opts = (options[field] || []).map(v => 
        `<option value="${v}" ${v === currentVal ? 'selected' : ''}>${v.replace(/_/g,' ')}</option>`
      ).join('');
      el.innerHTML = `<select class="inline-select" data-save="${prospectId}" data-field="${field}">${opts}</select>`;
    } else {
      el.innerHTML = `<input class="inline-input" type="${type}" value="${esc(currentVal)}" data-save="${prospectId}" data-field="${field}" />`;
    }

    const input = el.querySelector('select, input');
    if(!input) return;
    input.focus();
    
    const save = async () => {
      const newVal = input.type === 'number' ? parseInt(input.value) || 0 : input.value;
      await api('/api/prospects/update', {
        method: 'POST',
        body: JSON.stringify({ id: prospectId, [field]: newVal })
      });
      el.textContent = field === 'pipeline_stage' || field === 'status' 
        ? String(newVal).replace(/_/g,' ') 
        : (type === 'number' ? fmt(newVal) || '0' : newVal || '');
      toast('Updated ✓');
      bindProspectsView(); // Re-bind events
    };
    
    input.addEventListener('blur', save);
    input.addEventListener('keydown', (e) => {
      if(e.key === 'Enter') save();
      if(e.key === 'Escape') { el.textContent = currentVal; }
    });
  }

  // ─── Log Activity Modal ───────────────────────────────────────────────

  function showActivityModal(prospectId){
    const prospect = (window._prospectData || []).find(p => p.id === prospectId);
    const name = prospect ? prospect.name : 'Prospect';
    
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.innerHTML = `
      <div class="prospect-modal">
        <div class="modal-head">
          <h3>Log Activity — ${esc(name)}</h3>
          <button class="modal-close" data-close-modal>×</button>
        </div>
        <div class="modal-body">
          <label>Activity Type</label>
          <select id="activityType" class="modal-input">
            <option value="call">Phone Call</option>
            <option value="fb_dm">FB DM</option>
            <option value="email">Email</option>
            <option value="message">Text Message</option>
            <option value="linkedin">LinkedIn</option>
            <option value="in_person">In Person</option>
            <option value="research">Research</option>
            <option value="note">General Note</option>
          </select>
          <label>Note</label>
          <textarea id="activityNote" class="modal-input" rows="3" placeholder="What happened?"></textarea>
          <button class="btn primary" id="saveActivity">Log Activity</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    
    modal.querySelector('[data-close-modal]').onclick = () => modal.remove();
    modal.querySelector('#saveActivity').onclick = async () => {
      const type = document.getElementById('activityType').value;
      const note = document.getElementById('activityNote').value;
      await api('/api/prospects/log_activity', {
        method: 'POST',
        body: JSON.stringify({ prospect_id: prospectId, activity_type: type, note: note })
      });
      toast('Activity logged ✓');
      modal.remove();
      bindProspectsView();
    };
  }

  // ─── Create New Prospect ──────────────────────────────────────────────

  function showCreateModal(){
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.innerHTML = `
      <div class="prospect-modal">
        <div class="modal-head">
          <h3>New Prospect</h3>
          <button class="modal-close" data-close-modal>×</button>
        </div>
        <div class="modal-body">
          <label>Business Name *</label>
          <input class="modal-input" id="newName" placeholder="e.g. Edel Roofing" />
          <label>Phone</label>
          <input class="modal-input" id="newPhone" placeholder="(956) 555-1234" />
          <label>Email</label>
          <input class="modal-input" id="newEmail" type="email" placeholder="owner@example.com" />
          <label>Website</label>
          <input class="modal-input" id="newWebsite" placeholder="https://example.com" />
          <label>Keyword</label>
          <input class="modal-input" id="newKeyword" placeholder="e.g. roofing contractor" />
          <label>City</label>
          <input class="modal-input" id="newCity" placeholder="e.g. Edinburg" />
          <label>Niche</label>
          <input class="modal-input" id="newNiche" placeholder="e.g. Roofing" />
          <label>Current Rank (1-10)</label>
          <input class="modal-input" id="newRank" type="number" min="1" max="10" placeholder="4" />
          <label>Score (1-100)</label>
          <input class="modal-input" id="newScore" type="number" min="1" max="100" placeholder="7" />
          <label>Channel</label>
          <select class="modal-input" id="newChannel">
            <option value="fb_dm">FB DM</option>
            <option value="email">Email</option>
            <option value="phone">Phone</option>
            <option value="linkedin">LinkedIn</option>
            <option value="in_person">In Person</option>
          </select>
          <label>Notes</label>
          <textarea class="modal-input" id="newNotes" rows="2" placeholder="Any relevant info..."></textarea>
          <button class="btn primary" id="saveNewProspect">Create Prospect</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    
    modal.querySelector('[data-close-modal]').onclick = () => modal.remove();
    modal.querySelector('#saveNewProspect').onclick = async () => {
      const name = document.getElementById('newName').value.trim();
      if(!name) { toast('Business name is required', true); return; }
      
      const data = {
        name: name,
        phone: document.getElementById('newPhone').value.trim(),
        email: document.getElementById('newEmail').value.trim(),
        website: document.getElementById('newWebsite').value.trim(),
        keyword: document.getElementById('newKeyword').value.trim(),
        city: document.getElementById('newCity').value.trim(),
        niche: document.getElementById('newNiche').value.trim(),
        rank: document.getElementById('newRank').value,
        score: document.getElementById('newScore').value,
        channel: document.getElementById('newChannel').value,
        notes: document.getElementById('newNotes').value.trim(),
      };
      
      const r = await api('/api/prospects/create', { method: 'POST', body: JSON.stringify(data) });
      if(r.ok) {
        toast('Prospect created ✓');
        modal.remove();
        load().then(() => render());
      } else {
        toast('Failed to create prospect', true);
      }
    };
  }

  // ─── Render Prospects View ─────────────────────────────────────────────

  function prospectsView(){
    const d = state.data;
    const prospects = (window._prospectData || []);
    const stats = window._prospectStats || { total: prospects.length, by_status: {}, by_pipeline: {}, by_city: {} };
    
    // Calculate stats from current data
    prospects.forEach(p => {
      stats.by_status[p.status] = (stats.by_status[p.status] || 0) + 1;
      stats.by_pipeline[p.pipeline_stage] = (stats.by_pipeline[p.pipeline_stage] || 0) + 1;
      if(p.city) stats.by_city[p.city] = (stats.by_city[p.city] || 0) + 1;
    });

    // Pipeline summary
    const stages = ['new', 'contacted', 'pitched', 'negotiation', 'closed_won', 'closed_lost'];
    const stageLabels = {new: 'New', contacted: 'Contacted', pitched: 'Pitched', negotiation: 'Negotiation', closed_won: 'Closed-Won', closed_lost: 'Closed-Lost'};
    const pipelineBar = `<div class="pipeline-bar">${stages.map(s => `
      <div class="pipeline-stage ${stats.by_pipeline[s] ? 'active' : ''}">
        <div class="pipeline-count">${stats.by_pipeline[s] || 0}</div>
        <div class="pipeline-label">${stageLabels[s]}</div>
      </div>
    `).join('')}</div>`;

    // Status chips
    const statusChips = Object.keys(stats.by_status).map(s => 
      `<span class="prospect-chip status-${s}">${s.replace(/_/g,' ')}: ${stats.by_status[s]}</span>`
    ).join('');

    // Table rows
    const rows = prospects.map(p => `
      <tr data-prospect-row="${p.id}">
        <td><strong>${esc(p.name)}</strong></td>
        <td>${esc(p.keyword)}</td>
        <td>${esc(p.city)}</td>
        <td>${esc(p.niche)}</td>
        <td class="rank-cell">${p.rank || '—'}</td>
        <td class="score-cell">${p.score || '—'}</td>
        <td><a href="${esc(p.website)}" target="_blank" class="mono" style="font-size:11px">${esc(new URL(p.website || 'https://x').hostname)}</a></td>
        <td>
          <span class="tag ${p.status === 'closed_won' ? 'green' : p.status === 'closed_lost' ? 'red' : p.status === 'contacted' ? 'blue' : 'muted'}">${(p.status||'').replace(/_/g,' ')}</span>
        </td>
        <td>
          <span class="tag ${p.pipeline_stage === 'closed_won' ? 'green' : p.pipeline_stage === 'closed_lost' ? 'red' : 'blue'}">${(p.pipeline_stage||'').replace(/_/g,' ')}</span>
        </td>
        <td class="prospect-actions">
          <button class="icon-btn" data-dm-opener="${p.id}" title="Copy FB DM opener">📋</button>
          <button class="icon-btn" data-log-activity="${p.id}" title="Log activity">📝</button>
          <button class="icon-btn" data-advance="${p.id}" title="Advance pipeline">→</button>
          <button class="icon-btn" data-delete-prospect="${p.id}" title="Delete">✕</button>
        </td>
      </tr>
    `).join('');

    return page('Prospects', 'Your prospecting pipeline — better than a Google sheet.', 
      `${pipelineBar}
      <div class="prospect-stats">${statusChips}</div>
      <div class="prospect-toolbar">
        <button class="btn primary" id="addProspectBtn">+ Add Prospect</button>
        <input class="search-input" id="prospectSearch" placeholder="Search name, keyword, city..." />
      </div>
      <div class="card section-card">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Business</th><th>Keyword</th><th>City</th><th>Niche</th>
                <th>Rank</th><th>Score</th><th>Website</th>
                <th>Status</th><th>Pipeline</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>${rows || '<tr><td colspan="10" class="empty">No prospects yet. Click "Add Prospect" to get started.</td></tr>'}</tbody>
          </table>
        </div>
      </div>`
    );
  }

  // ─── Bind Events ──────────────────────────────────────────────────────

  function bindProspectsView(){
    // Add prospect
    const addBtn = document.getElementById('addProspectBtn');
    if(addBtn) addBtn.onclick = showCreateModal;

    // Search
    const searchInput = document.getElementById('prospectSearch');
    if(searchInput) {
      searchInput.oninput = debounce((e) => {
        load({ q: e.target.value }).then(() => render());
      }, 300);
    }

    // DM Opener buttons
    document.querySelectorAll('[data-dm-opener]').forEach(btn => {
      btn.onclick = () => copyDMOpener(btn.dataset.dmOpener);
    });

    // Log activity buttons
    document.querySelectorAll('[data-log-activity]').forEach(btn => {
      btn.onclick = () => showActivityModal(btn.dataset.logActivity);
    });

    // Advance pipeline buttons
    document.querySelectorAll('[data-advance]').forEach(btn => {
      btn.onclick = async () => {
        const stages = ['new', 'contacted', 'pitched', 'negotiation', 'closed_won'];
        const r = await api('/api/prospects/detail?id=' + encodeURIComponent(btn.dataset.advance));
        if(r.ok) {
          const current = r.pipeline_stage || 'new';
          const idx = stages.indexOf(current);
          const next = stages[Math.min(idx + 1, stages.length - 1)];
          await api('/api/prospects/update', {
            method: 'POST',
            body: JSON.stringify({ id: btn.dataset.advance, pipeline_stage: next })
          });
          toast(`Advanced to ${next} ✓`);
          load().then(() => render());
        }
      };
    });

    // Delete buttons
    document.querySelectorAll('[data-delete-prospect]').forEach(btn => {
      btn.onclick = async () => {
        if(!confirm('Delete this prospect permanently?')) return;
        await api('/api/prospects/delete', {
          method: 'POST',
          body: JSON.stringify({ id: btn.dataset.deleteProspect })
        });
        toast('Prospect deleted');
        load().then(() => render());
      };
    });
  }

  function debounce(fn, ms){
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
  }

  // ─── Register View ────────────────────────────────────────────────────

  // Expose prospectsView and bindProspectsView globally BEFORE registerProspectsView
  window.prospectsView = prospectsView;
  window.bindProspectsView = bindProspectsView;

  function registerProspectsView(){
    // Wait for app.js to define renderView, then add our tab
    const tryRegister = () => {
      if(typeof window.renderView === 'function') {
        // Store original
        if(!window._originalRenderView) {
          window._originalRenderView = window.renderView;
        }
        // Replace with extended version
        window.renderView = function(){
          const map = {
            'Command Center': commandCenter,
            'Clients / Sites': clientsView,
            'Approvals': approvalsView,
            'Opportunities': opportunitiesView,
            'GSC Keywords': gscView,
            'Prospects': window.prospectsView,
            'Agent Tasks': tasksView,
            'Content': contentView,
            'Schedule': scheduleView,
            'CTR Tests': ctrView,
            'Activity Log': activityView,
            'Reports': reportsView,
            'Settings': settingsView
          };
          $('#view').innerHTML = (map[state.section] || commandCenter)();
          // Bind prospect events if on that tab
          if(state.section === 'Prospects' && window.bindProspectsView) {
            window.bindProspectsView();
          }
        };
      } else {
        // renderView not defined yet, retry
        setTimeout(tryRegister, 50);
      }
    };
    tryRegister();
  }

  // ─── Init ─────────────────────────────────────────────────────────────

  // Load prospects data asynchronously on page load
  async function initProspectsData(){
    try {
      const r = await api('/api/prospects/list');
      if(r.ok) {
        window._prospectData = r.prospects || [];
        window._prospectStats = { total: r.total, by_status: r.by_status, by_pipeline: r.by_pipeline, by_city: r.by_city };
      }
    } catch(e) { console.error('Failed to load prospects:', e); }
  }

  // Add tab to navigation when DOM is ready
  if(document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      addProspectsTab();
      registerProspectsView();
      initProspectsData();
    });
  } else {
    addProspectsTab();
    registerProspectsView();
    initProspectsData();
  }
})();
