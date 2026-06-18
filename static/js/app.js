/* ── Contract Manager — Frontend JS ───────────────────────────── */

const BASE_PATH = document.body.dataset.basePath || '/projects/contract-manager-eval';
const VERSION = document.body.dataset.version || '0.0.1';

// ── Token helper ───────────────────────────────────────────────
function getToken() {
  const match = document.cookie.match(/(?:^|;\s*)access_token=([^;]*)/);
  return match ? match[1] : null;
}

// ── API helpers ────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = options.headers || {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  // Don't set Content-Type for FormData (browser sets with boundary)
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }
  const resp = await fetch(path, { ...options, headers });
  if (resp.status === 204) return null; // No content
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
  return data;
}

// ── Flash message ──────────────────────────────────────────────
function showFlash(msg, type = 'error') {
  const el = document.getElementById('flash-messages');
  if (!el) return;
  el.innerHTML = `<div class="alert alert-${type}">${msg}</div>`;
  setTimeout(() => { el.innerHTML = ''; }, 5000);
}

// ── Logout ─────────────────────────────────────────────────────
function setupLogout() {
  const btn = document.getElementById('logout-btn');
  if (!btn) return;
  btn.addEventListener('click', () => {
    document.cookie = 'access_token=; path=/; max-age=0';
    window.location.href = BASE_PATH + '/login';
  });
}

// ── Contract search/filter ─────────────────────────────────────
function setupContractFilters() {
  const statusFilter = document.getElementById('filter-status');
  const searchInput = document.getElementById('search-input');
  if (!statusFilter && !searchInput) return;

  function applyFilters() {
    const params = new URLSearchParams();
    if (statusFilter && statusFilter.value) params.set('status', statusFilter.value);
    if (searchInput && searchInput.value) params.set('q', searchInput.value);
    const qs = params.toString();
    window.location.href = BASE_PATH + '/contracts' + (qs ? '?' + qs : '');
  }

  if (statusFilter) statusFilter.addEventListener('change', applyFilters);
  if (searchInput) {
    let debounce;
    searchInput.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(applyFilters, 400);
    });
  }
}

// ── Attachment upload ──────────────────────────────────────────
function setupAttachmentUpload() {
  const fileInput = document.getElementById('attachment-file');
  const uploadBtn = document.getElementById('attachment-upload-btn');
  if (!fileInput || !uploadBtn) return;

  uploadBtn.addEventListener('click', async () => {
    const file = fileInput.files[0];
    if (!file) { showFlash('请选择文件'); return; }

    const contractId = uploadBtn.dataset.contractId;
    const formData = new FormData();
    formData.append('file', file);

    try {
      await apiFetch(`/api/contracts/${contractId}/attachments`, {
        method: 'POST',
        body: formData,
      });
      window.location.reload();
    } catch (e) {
      showFlash('上传失败: ' + e.message);
    }
  });
}

// ── Attachment delete ──────────────────────────────────────────
function setupAttachmentDelete() {
  document.querySelectorAll('.delete-attachment').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      if (!confirm('确定删除此附件？')) return;

      const contractId = btn.dataset.contractId;
      const attachmentId = btn.dataset.attachmentId;

      try {
        await apiFetch(`/api/contracts/${contractId}/attachments/${attachmentId}`, {
          method: 'DELETE',
        });
        window.location.reload();
      } catch (err) {
        showFlash('删除失败: ' + err.message);
      }
    });
  });
}

// ── Contract delete ────────────────────────────────────────────
function setupContractDelete() {
  const btn = document.getElementById('delete-contract-btn');
  if (!btn) return;

  btn.addEventListener('click', async () => {
    if (!confirm('确定删除此合同？此操作不可恢复。')) return;

    const contractId = btn.dataset.contractId;
    try {
      await apiFetch(`/api/contracts/${contractId}`, { method: 'DELETE' });
      window.location.href = BASE_PATH + '/contracts';
    } catch (err) {
      showFlash('删除失败: ' + err.message);
    }
  });
}

// ── Contract transition ────────────────────────────────────────
function setupTransitionButtons() {
  document.querySelectorAll('.transition-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const action = btn.dataset.action;
      const label = btn.dataset.label || action;
      if (!confirm(`确定执行「${label}」操作？`)) return;

      const contractId = btn.dataset.contractId;
      try {
        await apiFetch(`/api/contracts/${contractId}/transition`, {
          method: 'POST',
          body: JSON.stringify({ action }),
        });
        window.location.reload();
      } catch (err) {
        showFlash('操作失败: ' + err.message);
      }
    });
  });
}

// ── Form validation ────────────────────────────────────────────
function setupFormValidation() {
  const form = document.querySelector('form[data-validate]');
  if (!form) return;

  form.addEventListener('submit', (e) => {
    const requiredFields = form.querySelectorAll('[required]');
    let valid = true;
    requiredFields.forEach(field => {
      if (!field.value.trim()) {
        field.style.borderColor = 'var(--danger)';
        valid = false;
      } else {
        field.style.borderColor = '';
      }
    });
    if (!valid) {
      e.preventDefault();
      showFlash('请填写所有必填字段');
    }
  });
}

// ── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setupLogout();
  setupContractFilters();
  setupAttachmentUpload();
  setupAttachmentDelete();
  setupContractDelete();
  setupTransitionButtons();
  setupFormValidation();
});
