/**
 * JP-001 Duplicate Application Manager — Stitch Web UI Controller
 */

// Global State
const state = {
  currentView: 'dashboard',
  activeScanId: null,
  scanPollInterval: null,
  searchDebounceTimer: null,
  selectedAppForQuarantine: null,
};

// ============================================================================
// Initialization & Navigation
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  loadDashboardData();
  setupQuarantineCheckbox();
});

function setupNavigation() {
  const buttons = document.querySelectorAll('.nav-btn');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      const viewName = btn.dataset.view;
      switchView(viewName);
    });
  });
}

function switchView(viewName) {
  state.currentView = viewName;

  // Update nav buttons
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === viewName);
  });

  // Switch view section
  document.querySelectorAll('.view-section').forEach(sec => {
    sec.classList.toggle('active', sec.id === `view-${viewName}`);
  });

  // Fetch relevant data
  if (viewName === 'dashboard') loadDashboardData();
  else if (viewName === 'duplicates') loadDuplicates();
  else if (viewName === 'applications') loadApplications();
  else if (viewName === 'quarantine') loadQuarantine();
  else if (viewName === 'rules') loadRules();
  else if (viewName === 'audit') loadAuditLogs();
}

// ============================================================================
// Utilities & Formatters
// ============================================================================

function formatBytes(bytes) {
  if (bytes === 0 || !bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(isoString) {
  if (!isoString) return '—';
  const d = new Date(isoString);
  return d.toLocaleString();
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function getBadgeClassForCategory(category) {
  switch (category) {
    case 'Development': return 'badge-dev';
    case 'Media & Graphics': return 'badge-media';
    case 'Games & Entertainment': return 'badge-games';
    case 'Documents & Productivity': return 'badge-docs';
    case 'Utilities & Tools': return 'badge-utils';
    default: return 'badge-uncat';
  }
}

// ============================================================================
// 1. Dashboard View Logic
// ============================================================================

async function loadDashboardData() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) throw new Error('Failed to fetch stats');
    const stats = await res.json();

    document.getElementById('kpi-total-apps').textContent = stats.total_applications || 0;
    document.getElementById('kpi-total-scanned-size').textContent = `${formatBytes(stats.total_scanned_bytes)} scanned`;
    document.getElementById('kpi-dup-groups').textContent = stats.duplicate_groups_count || 0;
    document.getElementById('kpi-dup-instances').textContent = `${stats.duplicate_applications_count} duplicate instances`;
    document.getElementById('kpi-reclaimable-space').textContent = formatBytes(stats.reclaimable_bytes);
    document.getElementById('kpi-quarantined-count').textContent = stats.quarantined_count || 0;

    // Latest scan status
    const statusBadge = document.getElementById('latest-scan-status');
    const detailsPara = document.getElementById('latest-scan-details');
    if (stats.latest_scan) {
      statusBadge.textContent = stats.latest_scan.status.toUpperCase();
      statusBadge.className = `badge ${stats.latest_scan.status === 'completed' ? 'badge-docs' : stats.latest_scan.status === 'running' ? 'badge-dev' : 'badge-games'}`;
      detailsPara.textContent = `Files seen: ${stats.latest_scan.files_seen} | Apps found: ${stats.latest_scan.apps_found} | Duplicates: ${stats.latest_scan.duplicates_found} | Errors: ${stats.latest_scan.error_count}`;

      if (stats.latest_scan.status === 'running') {
        startScanPolling(stats.latest_scan.id);
      }
    } else {
      statusBadge.textContent = 'NO SCANS';
      detailsPara.textContent = 'No scans executed yet.';
    }

    // Load category breakdown for table
    loadCategoryBreakdownTable();
  } catch (err) {
    console.error('Error loading dashboard stats:', err);
  }
}

async function loadCategoryBreakdownTable() {
  try {
    const [appsRes, dupsRes] = await Promise.all([
      fetch('/api/apps?limit=1000'),
      fetch('/api/duplicates?limit=1000')
    ]);

    const apps = await appsRes.json();
    const dups = await dupsRes.json();

    const categoryMap = {};
    apps.forEach(app => {
      const cat = app.category || 'Uncategorized';
      if (!categoryMap[cat]) {
        categoryMap[cat] = { count: 0, size: 0, dupCount: 0, waste: 0 };
      }
      categoryMap[cat].count += 1;
      categoryMap[cat].size += app.total_size;
    });

    dups.forEach(grp => {
      const cat = grp.category || 'Uncategorized';
      if (!categoryMap[cat]) {
        categoryMap[cat] = { count: 0, size: 0, dupCount: 0, waste: 0 };
      }
      categoryMap[cat].dupCount += grp.member_count;
      categoryMap[cat].waste += grp.reclaimable_size;
    });

    const tbody = document.querySelector('#dashboard-category-table tbody');
    tbody.innerHTML = '';

    const categories = Object.keys(categoryMap).sort();
    if (categories.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No scan data available.</td></tr>';
      return;
    }

    categories.forEach(cat => {
      const data = categoryMap[cat];
      const row = document.createElement('tr');
      row.innerHTML = `
        <td><span class="badge ${getBadgeClassForCategory(cat)}">${cat}</span></td>
        <td>${data.count}</td>
        <td>${formatBytes(data.size)}</td>
        <td>${data.dupCount}</td>
        <td style="color: ${data.waste > 0 ? 'var(--accent-warning)' : 'inherit'};">${formatBytes(data.waste)}</td>
      `;
      tbody.appendChild(row);
    });
  } catch (err) {
    console.error('Error loading category table:', err);
  }
}

// ============================================================================
// 2. Duplicate Review Logic
// ============================================================================

async function loadDuplicates() {
  const container = document.getElementById('duplicate-groups-container');
  container.innerHTML = '<p style="color: var(--text-muted);">Loading duplicate groups...</p>';

  try {
    const res = await fetch('/api/duplicates?limit=500');
    if (!res.ok) throw new Error('Failed to fetch duplicates');
    const duplicateGroups = await res.json();

    if (duplicateGroups.length === 0) {
      container.innerHTML = `
        <div class="glass-panel" style="text-align: center; padding: 3rem 1rem;">
          <h3>✨ No Duplicate Applications Found</h3>
          <p style="color: var(--text-muted); margin-top: 0.5rem;">All discovered applications in the catalog have unique content fingerprints.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = '';
    duplicateGroups.forEach((grp, idx) => {
      const card = document.createElement('div');
      card.className = 'dup-card';

      let membersHtml = '';
      grp.members.forEach((m, mIdx) => {
        membersHtml += `
          <div class="dup-member-item">
            <div class="dup-member-info">
              <div style="font-weight: 600; display: flex; align-items: center; gap: 0.5rem;">
                <span>[Copy #${mIdx + 1}] ${m.name}</span>
                <span class="badge ${getBadgeClassForCategory(m.category)}">${m.category}</span>
              </div>
              <div class="dup-member-path">${m.path}</div>
              <div style="font-size: 0.75rem; color: var(--text-muted);">Size: ${formatBytes(m.total_size)} | Discovered: ${formatDate(m.created_at)}</div>
            </div>
            <div>
              <button class="btn btn-danger btn-sm" onclick="openQuarantineModal('${m.id}')">🛡️ Quarantine Copy</button>
            </div>
          </div>
        `;
      });

      card.innerHTML = `
        <div class="dup-card-header">
          <div>
            <h3 style="font-size: 1.1rem;">Duplicate Set #${idx + 1} (${grp.member_count} Copies)</h3>
            <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">
              Fingerprint: <span class="dup-fingerprint">${grp.fingerprint.slice(0, 24)}...</span> | Redundant Waste: <strong style="color: var(--accent-warning);">${formatBytes(grp.reclaimable_size)}</strong>
            </div>
          </div>
        </div>
        <div class="dup-members-list">
          ${membersHtml}
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = `<p style="color: var(--accent-danger);">Failed to load duplicates: ${err.message}</p>`;
  }
}

// ============================================================================
// 3. Applications Catalog Logic
// ============================================================================

function debounceAppSearch() {
  clearTimeout(state.searchDebounceTimer);
  state.searchDebounceTimer = setTimeout(loadApplications, 300);
}

async function loadApplications() {
  const tbody = document.querySelector('#applications-table tbody');
  const search = document.getElementById('app-search-input').value.trim();
  const category = document.getElementById('app-category-filter').value;

  tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Loading applications...</td></tr>';

  try {
    let url = `/api/apps?limit=500`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (category) url += `&category=${encodeURIComponent(category)}`;

    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch applications');
    const apps = await res.json();

    if (apps.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No applications found matching search criteria.</td></tr>';
      return;
    }

    tbody.innerHTML = '';
    apps.forEach(app => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-weight: 600;">${app.name}</td>
        <td><span class="badge ${getBadgeClassForCategory(app.category)}">${app.category}</span></td>
        <td style="font-family: monospace; font-size: 0.8rem; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${app.path}</td>
        <td>${formatBytes(app.total_size)}</td>
        <td>${app.file_count}</td>
        <td><span class="dup-fingerprint">${app.content_fingerprint.slice(0, 12)}...</span></td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="openQuarantineModal('${app.id}')">Quarantine</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="color: var(--accent-danger); text-align: center;">Error loading catalog: ${err.message}</td></tr>`;
  }
}

// ============================================================================
// 4. Quarantine Management Logic
// ============================================================================

async function loadQuarantine() {
  const tbody = document.querySelector('#quarantine-table tbody');
  tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">Loading quarantine records...</td></tr>';

  try {
    const res = await fetch('/api/removals');
    if (!res.ok) throw new Error('Failed to fetch quarantine actions');
    const actions = await res.json();

    const quarantineItems = actions.filter(a => a.action === 'quarantine');

    if (quarantineItems.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No quarantined applications.</td></tr>';
      return;
    }

    tbody.innerHTML = '';
    quarantineItems.forEach(item => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-family: monospace; font-size: 0.8rem;">${item.original_path}</td>
        <td style="font-family: monospace; font-size: 0.8rem; color: var(--text-muted);">${item.quarantine_path || '—'}</td>
        <td><span class="badge ${item.status === 'completed' ? 'badge-docs' : 'badge-games'}">${item.status.toUpperCase()}</span></td>
        <td>${formatDate(item.created_at)}</td>
        <td>
          ${item.status === 'completed' ? `<button class="btn btn-success btn-sm" onclick="handleRestore('${item.id}')">🔄 Restore</button>` : '—'}
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="color: var(--accent-danger); text-align: center;">Error: ${err.message}</td></tr>`;
  }
}

async function handleRestore(actionId) {
  try {
    const res = await fetch(`/api/removals/${actionId}/restore`, { method: 'POST' });
    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || 'Restoration failed');
    }
    showToast('Application restored successfully!', 'success');
    loadQuarantine();
    loadDashboardData();
  } catch (err) {
    showToast(`Restore error: ${err.message}`, 'error');
  }
}

// ============================================================================
// 5. Categorization Rules Logic
// ============================================================================

async function loadRules() {
  const tbody = document.querySelector('#rules-table tbody');
  tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Loading rules...</td></tr>';

  try {
    const res = await fetch('/api/rules');
    if (!res.ok) throw new Error('Failed to fetch rules');
    const rules = await res.json();

    if (rules.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No rules defined.</td></tr>';
      return;
    }

    tbody.innerHTML = '';
    rules.forEach(rule => {
      const cond = rule.conditions || {};
      const summaryParts = [];
      if (cond.extensions && cond.extensions.length) summaryParts.push(`Exts: ${cond.extensions.join(', ')}`);
      if (cond.keywords && cond.keywords.length) summaryParts.push(`Keywords: ${cond.keywords.join(', ')}`);
      if (cond.path_patterns && cond.path_patterns.length) summaryParts.push(`Paths: ${cond.path_patterns.join(', ')}`);

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-weight: 700;">${rule.priority}</td>
        <td style="font-weight: 600;">${rule.name}</td>
        <td><span class="badge ${getBadgeClassForCategory(rule.category)}">${rule.category}</span></td>
        <td style="font-size: 0.75rem; color: var(--text-muted); max-width: 320px;">${summaryParts.join(' | ') || 'None'}</td>
        <td>
          <button class="btn btn-sm ${rule.enabled ? 'btn-success' : 'btn-secondary'}" onclick="toggleRuleEnabled('${rule.id}', ${!rule.enabled})">
            ${rule.enabled ? 'Enabled' : 'Disabled'}
          </button>
        </td>
        <td>
          <button class="btn btn-danger btn-sm" onclick="handleDeleteRule('${rule.id}')">Delete</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="color: var(--accent-danger); text-align: center;">Error: ${err.message}</td></tr>`;
  }
}

async function toggleRuleEnabled(ruleId, newStatus) {
  try {
    const res = await fetch(`/api/rules/${ruleId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: newStatus }),
    });
    if (!res.ok) throw new Error('Failed to update rule');
    showToast(`Rule ${newStatus ? 'enabled' : 'disabled'}`, 'info');
    loadRules();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
}

async function handleDeleteRule(ruleId) {
  if (!confirm('Are you sure you want to delete this categorization rule?')) return;
  try {
    const res = await fetch(`/api/rules/${ruleId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete rule');
    showToast('Rule deleted successfully', 'success');
    loadRules();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
}

function openNewRuleModal() {
  document.getElementById('rule-modal-title').textContent = 'Add Categorization Rule';
  document.getElementById('form-rule').reset();
  document.getElementById('rule-id').value = '';
  openModal('modal-rule');
}

async function handleSaveRule(e) {
  e.preventDefault();
  const name = document.getElementById('rule-name').value.trim();
  const category = document.getElementById('rule-category').value.trim();
  const priority = parseInt(document.getElementById('rule-priority').value, 10) || 50;

  const rawExts = document.getElementById('rule-extensions').value;
  const rawKeywords = document.getElementById('rule-keywords').value;
  const rawPatterns = document.getElementById('rule-patterns').value;

  const conditions = {
    extensions: rawExts.split(',').map(s => s.trim()).filter(Boolean),
    keywords: rawKeywords.split(',').map(s => s.trim()).filter(Boolean),
    path_patterns: rawPatterns.split(',').map(s => s.trim()).filter(Boolean),
  };

  try {
    const res = await fetch('/api/rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, category, priority, conditions, enabled: true }),
    });
    if (!res.ok) throw new Error('Failed to create rule');
    showToast('Rule created successfully!', 'success');
    closeModal('modal-rule');
    loadRules();
  } catch (err) {
    showToast(`Error saving rule: ${err.message}`, 'error');
  }
}

// ============================================================================
// 6. Audit Trail Logic
// ============================================================================

async function loadAuditLogs() {
  const tbody = document.querySelector('#audit-table tbody');
  tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">Loading audit logs...</td></tr>';

  try {
    const res = await fetch('/api/audit?limit=200');
    if (!res.ok) throw new Error('Failed to fetch audit logs');
    const logs = await res.json();

    if (logs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No audit entries found.</td></tr>';
      return;
    }

    tbody.innerHTML = '';
    logs.forEach(item => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-size: 0.8rem; color: var(--text-muted);">${formatDate(item.created_at)}</td>
        <td><span class="badge badge-dev">${item.action}</span></td>
        <td>${item.entity_type}</td>
        <td style="font-family: monospace; font-size: 0.75rem;">${item.entity_id || '—'}</td>
        <td style="font-family: monospace; font-size: 0.75rem; color: var(--text-muted); max-width: 350px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${JSON.stringify(item.details)}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="color: var(--accent-danger); text-align: center;">Error: ${err.message}</td></tr>`;
  }
}

// ============================================================================
// Scan Execution & Polling
// ============================================================================

function openScanModal() {
  openModal('modal-scan');
}

async function handleStartScan(e) {
  e.preventDefault();
  const rawRoots = document.getElementById('scan-root-paths').value;
  const roots = rawRoots.split('\n').map(r => r.trim()).filter(Boolean);

  if (roots.length === 0) {
    showToast('Please enter at least one root directory path.', 'error');
    return;
  }

  try {
    const res = await fetch('/api/scans', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ roots }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Scan failed to start');
    }

    const scanJob = await res.json();
    closeModal('modal-scan');
    showToast('Scan initiated successfully!', 'success');
    startScanPolling(scanJob.id);
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
}

function startScanPolling(scanJobId) {
  clearInterval(state.scanPollInterval);
  state.activeScanId = scanJobId;

  const progressBar = document.getElementById('scan-progress-bar-container');
  const progressFill = document.getElementById('scan-progress-bar-fill');
  progressBar.style.display = 'block';
  progressFill.style.width = '15%';

  state.scanPollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/scans/${scanJobId}`);
      if (!res.ok) return;
      const scan = await res.json();

      document.getElementById('latest-scan-status').textContent = scan.status.toUpperCase();
      document.getElementById('latest-scan-details').textContent = `Files seen: ${scan.files_seen} | Apps: ${scan.apps_found} | Duplicates: ${scan.duplicates_found} | Errors: ${scan.error_count}`;

      if (scan.status === 'running') {
        progressFill.style.width = '65%';
      } else if (scan.status === 'completed') {
        progressFill.style.width = '100%';
        clearInterval(state.scanPollInterval);
        showToast('Scan completed successfully!', 'success');
        setTimeout(() => {
          progressBar.style.display = 'none';
          loadDashboardData();
        }, 1200);
      } else if (scan.status === 'failed' || scan.status === 'cancelled') {
        clearInterval(state.scanPollInterval);
        progressBar.style.display = 'none';
        showToast(`Scan ${scan.status}: ${scan.error_message || ''}`, 'error');
        loadDashboardData();
      }
    } catch (err) {
      console.error('Scan polling error:', err);
    }
  }, 1000);
}

// ============================================================================
// Quarantine Modal & Safe Execution Workflow
// ============================================================================

async function openQuarantineModal(appId) {
  state.selectedAppForQuarantine = appId;
  const previewBody = document.getElementById('quarantine-preview-body');
  const confirmBtn = document.getElementById('btn-execute-quarantine');
  const checkbox = document.getElementById('quarantine-confirm-checkbox');

  checkbox.checked = false;
  confirmBtn.disabled = true;
  previewBody.innerHTML = '<p style="color: var(--text-muted);">Generating safety preview...</p>';
  openModal('modal-quarantine-confirm');

  try {
    const res = await fetch('/api/removals/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ application_id: appId }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Preview generation failed');
    }

    const preview = await res.json();

    let warningsHtml = '';
    if (preview.warnings && preview.warnings.length) {
      warningsHtml = `
        <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid var(--accent-danger); border-radius: var(--radius-sm); padding: 0.75rem; margin-top: 0.75rem;">
          <strong style="color: var(--accent-danger);">⚠️ Warnings Detected:</strong>
          <ul style="margin-left: 1.25rem; font-size: 0.8rem; margin-top: 0.25rem;">
            ${preview.warnings.map(w => `<li>${w}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    previewBody.innerHTML = `
      <div style="background: rgba(0,0,0,0.3); padding: 1rem; border-radius: var(--radius-sm); font-size: 0.875rem;">
        <div style="margin-bottom: 0.5rem;"><strong>Application:</strong> ${preview.name}</div>
        <div style="margin-bottom: 0.5rem; font-family: monospace; font-size: 0.8rem;"><strong>Source:</strong> ${preview.original_path}</div>
        <div style="margin-bottom: 0.5rem; font-family: monospace; font-size: 0.8rem; color: var(--accent-info);"><strong>Destination:</strong> ${preview.quarantine_destination}</div>
        <div><strong>Reclaimable Disk Space:</strong> ${formatBytes(preview.total_size)} (${preview.file_count} files)</div>
      </div>
      ${warningsHtml}
    `;
  } catch (err) {
    previewBody.innerHTML = `<p style="color: var(--accent-danger);">Failed to load preview: ${err.message}</p>`;
  }
}

function setupQuarantineCheckbox() {
  const checkbox = document.getElementById('quarantine-confirm-checkbox');
  const confirmBtn = document.getElementById('btn-execute-quarantine');
  if (checkbox && confirmBtn) {
    checkbox.addEventListener('change', () => {
      confirmBtn.disabled = !checkbox.checked;
    });
  }
}

async function executeQuarantineConfirmed() {
  if (!state.selectedAppForQuarantine) return;
  const appId = state.selectedAppForQuarantine;

  try {
    const res = await fetch('/api/removals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ application_id: appId, confirm: true }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Quarantine execution failed');
    }

    closeModal('modal-quarantine-confirm');
    showToast('Application moved to quarantine storage successfully!', 'success');

    // Refresh views
    if (state.currentView === 'duplicates') loadDuplicates();
    else if (state.currentView === 'applications') loadApplications();
    loadDashboardData();
  } catch (err) {
    showToast(`Quarantine Error: ${err.message}`, 'error');
  }
}

// Modal helper functions
function openModal(modalId) {
  const m = document.getElementById(modalId);
  if (m) m.classList.add('active');
}

function closeModal(modalId) {
  const m = document.getElementById(modalId);
  if (m) m.classList.remove('active');
}
