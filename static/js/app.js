/* ══════════════════════════════════════════════════════════════════════
   Contract Manager — Frontend Scripts v0.0.1
   ══════════════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  /* ── Configuration ────────────────────────────────────────────────── */

  var BASE_PATH = (document.body && document.body.dataset.basePath) || '/projects/contract-manager-eval';
  var VERSION = (document.body && document.body.dataset.version) || '0.0.1';

  // Expose for inline template scripts
  window.BASE_PATH = BASE_PATH;

  /* ── Token Management (cookie + localStorage) ──────────────────────── */

  function getToken() {
    // Try localStorage first, then cookie
    var local = localStorage.getItem('access_token');
    if (local) return local;
    var match = document.cookie.match(/(?:^|;\s*)access_token=([^;]*)/);
    return match ? match[1] : null;
  }

  function setToken(token) {
    localStorage.setItem('access_token', token);
  }

  function clearToken() {
    localStorage.removeItem('access_token');
    document.cookie = 'access_token=; path=/; max-age=0';
  }

  /* ── Core API Helper ──────────────────────────────────────────────── */

  async function apiFetch(path, options) {
    options = options || {};
    var token = getToken();
    var headers = options.headers || {};
    if (token) headers['Authorization'] = 'Bearer ' + token;
    // Don't set Content-Type for FormData (browser sets with boundary)
    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }
    // Prefix all API paths with BASE_PATH (e.g. /api/... → /projects/contract-manager-eval/api/...)
    if (!path.startsWith(BASE_PATH)) {
      path = BASE_PATH + path;
    }
    var resp = await fetch(path, {
      method: options.method || 'GET',
      headers: headers,
      body: options.body || undefined,
    });
    if (resp.status === 401) {
      clearToken();
      window.location.href = BASE_PATH + '/login';
      throw new Error('Unauthorized');
    }
    if (resp.status === 204) return null;
    var contentType = resp.headers.get('content-type') || '';
    if (contentType.indexOf('application/json') !== -1) {
      var data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || 'HTTP ' + resp.status);
      return data;
    }
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    return resp;
  }

  // Expose core fetch for inline template scripts
  window.apiFetch = apiFetch;

  /* ── Named API Wrappers ───────────────────────────────────────────── */

  window.apiGet = function (url) {
    return apiFetch(url, { method: 'GET' });
  };

  window.apiPost = function (url, data, isFormData) {
    var opts = { method: 'POST' };
    if (data) {
      opts.body = isFormData ? data : JSON.stringify(data);
    }
    return apiFetch(url, opts);
  };

  window.apiPut = function (url, data) {
    return apiFetch(url, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  };

  window.apiDelete = function (url) {
    return apiFetch(url, { method: 'DELETE' });
  };

  /* ── Flash Message ────────────────────────────────────────────────── */

  window.showFlash = function (msg, type) {
    type = type || 'error';
    var el = document.getElementById('flash-messages');
    if (!el) {
      el = document.createElement('div');
      el.id = 'flash-messages';
      el.style.cssText = 'position:fixed;top:68px;right:16px;z-index:2000;max-width:360px;';
      document.body.appendChild(el);
    }
    var div = document.createElement('div');
    div.className = 'alert alert-' + type;
    div.textContent = msg;
    el.appendChild(div);
    setTimeout(function () {
      div.style.opacity = '0';
      div.style.transition = 'opacity 0.3s';
      setTimeout(function () { div.remove(); }, 300);
    }, 4000);
  };

  /* ── Compatibility alias ──────────────────────────────────────────── */

  // showFlash is on window — inline scripts call it in global scope

  /* ── Serialize Form to Object ─────────────────────────────────────── */

  window.serializeForm = function (form) {
    var obj = {};
    var elements = form.querySelectorAll('input, select, textarea');
    for (var i = 0; i < elements.length; i++) {
      var el = elements[i];
      if (!el.name) continue;
      if (el.type === 'file') continue;
      if (el.type === 'checkbox' && !el.checked) continue;
      var value = el.value;
      if (value === '' && el.hasAttribute('data-optional')) value = null;
      obj[el.name] = value;
    }
    return obj;
  };

  /* ── Handle Form Submit (JSON API) ────────────────────────────────── */

  window.handleFormSubmit = function (event, url, method, redirectUrl) {
    event.preventDefault();
    var form = event.target;
    var submitBtn = form.querySelector('button[type="submit"]');
    var originalText = submitBtn ? submitBtn.textContent : '';
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = '提交中...';
    }

    var errors = form.querySelectorAll('.form-error');
    for (var i = 0; i < errors.length; i++) errors[i].textContent = '';

    var fileInput = form.querySelector('input[type="file"]');
    var isFormData = !!(fileInput && fileInput.files && fileInput.files.length > 0);

    var body;
    if (isFormData) {
      body = new FormData(form);
    } else {
      body = window.serializeForm(form);
    }

    var req;
    if (method === 'DELETE') req = window.apiDelete(url);
    else if (method === 'PUT') req = window.apiPut(url, body);
    else req = window.apiPost(url, body, isFormData);

    req.then(function () {
      if (redirectUrl) {
        window.location.href = redirectUrl;
      } else {
        window.showFlash('操作成功', 'success');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = originalText;
        }
      }
    }).catch(function (err) {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
      }
      window.showFlash(err.message || '操作失败', 'error');
    });

    return false;
  };

  /* ── Status Transition Dialog ─────────────────────────────────────── */

  window.showTransitionDialog = function (contractId, currentStatus, validTargets) {
    var existing = document.getElementById('transition-dialog');
    if (existing) existing.remove();

    var overlay = document.createElement('div');
    overlay.id = 'transition-dialog';
    overlay.style.cssText =
      'position:fixed;top:0;left:0;width:100%;height:100%;' +
      'background:rgba(0,0,0,0.4);display:flex;align-items:center;' +
      'justify-content:center;z-index:3000;';

    var box = document.createElement('div');
    box.style.cssText =
      'background:#fff;border-radius:8px;padding:24px;width:360px;' +
      'max-width:90vw;box-shadow:0 8px 32px rgba(0,0,0,0.2);';

    var title = document.createElement('h3');
    title.textContent = '状态流转';
    title.style.cssText = 'margin-bottom:16px;font-size:16px;';

    var select = document.createElement('select');
    select.style.cssText =
      'width:100%;padding:8px 12px;border:1px solid #d1d5db;' +
      'border-radius:6px;font-size:14px;margin-bottom:16px;';

    var labels = {
      pending: '提交审批',
      signed: '签署',
      terminated: '终止',
      expired: '设为过期',
      draft: '退回草稿',
    };

    validTargets.forEach(function (t) {
      var opt = document.createElement('option');
      opt.value = typeof t === 'string' ? t : t.value;
      opt.textContent = labels[opt.value] || opt.value;
      select.appendChild(opt);
    });

    var btnGroup = document.createElement('div');
    btnGroup.style.cssText = 'display:flex;gap:8px;justify-content:flex-end;';

    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn btn-outline';
    cancelBtn.textContent = '取消';
    cancelBtn.onclick = function () { overlay.remove(); };

    var confirmBtn = document.createElement('button');
    confirmBtn.className = 'btn btn-primary';
    confirmBtn.textContent = '确认';

    confirmBtn.onclick = function () {
      var target = select.value;
      confirmBtn.disabled = true;
      confirmBtn.textContent = '处理中...';
      window.apiPost('/api/contracts/' + contractId + '/transition', { action: target })
        .then(function () { overlay.remove(); window.location.reload(); })
        .catch(function (err) { window.showFlash(err.message || '状态流转失败', 'error'); overlay.remove(); });
    };

    btnGroup.appendChild(cancelBtn);
    btnGroup.appendChild(confirmBtn);
    box.appendChild(title);
    box.appendChild(select);
    box.appendChild(btnGroup);
    overlay.appendChild(box);
    document.body.appendChild(overlay);

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) overlay.remove();
    });
  };

  /* ── Delete Confirmation Helper ───────────────────────────────────── */

  window.confirmDelete = function (url, message) {
    message = message || '确定要删除吗？此操作不可撤销。';
    if (!confirm(message)) return;
    window.apiDelete(url).then(function () {
      window.location.reload();
    }).catch(function (err) {
      window.showFlash(err.message || '删除失败', 'error');
    });
  };

  /* ── Attachment Upload Preview ────────────────────────────────────── */

  window.updateFilePreview = function (input) {
    var preview = document.getElementById('file-preview');
    if (!preview) return;
    preview.innerHTML = '';
    if (input.files && input.files.length > 0) {
      var file = input.files[0];
      var sizeMB = (file.size / (1024 * 1024)).toFixed(1);
      preview.textContent = '已选择: ' + file.name + ' (' + sizeMB + ' MB)';
      preview.style.color = '#16a34a';
    }
  };

  /* ── Logout ───────────────────────────────────────────────────────── */

  window.doLogout = function () {
    clearToken();
    window.location.href = BASE_PATH + '/login';
  };

  function setupLogout() {
    var btn = document.getElementById('logout-btn');
    if (!btn) return;
    btn.addEventListener('click', window.doLogout);
  }

  /* ── Contract Search / Filter ─────────────────────────────────────── */

  function setupContractFilters() {
    var statusFilter = document.getElementById('filter-status');
    var searchInput = document.getElementById('search-input');
    if (!statusFilter && !searchInput) return;

    function applyFilters() {
      var params = new URLSearchParams();
      if (statusFilter && statusFilter.value) params.set('status', statusFilter.value);
      if (searchInput && searchInput.value) params.set('q', searchInput.value);
      var qs = params.toString();
      window.location.href = BASE_PATH + '/contracts' + (qs ? '?' + qs : '');
    }

    if (statusFilter) statusFilter.addEventListener('change', applyFilters);
    if (searchInput) {
      var debounce;
      searchInput.addEventListener('input', function () {
        clearTimeout(debounce);
        debounce = setTimeout(applyFilters, 400);
      });
    }
  }

  /* ── Attachment Upload ────────────────────────────────────────────── */

  function setupAttachmentUpload() {
    var fileInput = document.getElementById('attachment-file');
    var uploadBtn = document.getElementById('attachment-upload-btn');
    if (!fileInput || !uploadBtn) return;

    uploadBtn.addEventListener('click', async function () {
      var file = fileInput.files[0];
      if (!file) { showFlash('请选择文件'); return; }

      var contractId = uploadBtn.dataset.contractId;
      var formData = new FormData();
      formData.append('file', file);

      try {
        await apiFetch('/api/contracts/' + contractId + '/attachments', {
          method: 'POST',
          body: formData,
        });
        window.location.reload();
      } catch (e) {
        showFlash('上传失败: ' + e.message);
      }
    });
  }

  /* ── Attachment Delete ────────────────────────────────────────────── */

  function setupAttachmentDelete() {
    document.querySelectorAll('.delete-attachment').forEach(function (btn) {
      btn.addEventListener('click', async function (e) {
        e.preventDefault();
        if (!confirm('确定删除此附件？')) return;
        var contractId = btn.dataset.contractId;
        var attachmentId = btn.dataset.attachmentId;
        try {
          await apiFetch('/api/contracts/' + contractId + '/attachments/' + attachmentId, {
            method: 'DELETE',
          });
          window.location.reload();
        } catch (err) {
          showFlash('删除失败: ' + err.message);
        }
      });
    });
  }

  /* ── Contract Delete ──────────────────────────────────────────────── */

  function setupContractDelete() {
    var btn = document.getElementById('delete-contract-btn');
    if (!btn) return;
    btn.addEventListener('click', async function () {
      if (!confirm('确定删除此合同？此操作不可恢复。')) return;
      var contractId = btn.dataset.contractId;
      try {
        await apiFetch('/api/contracts/' + contractId, { method: 'DELETE' });
        window.location.href = BASE_PATH + '/contracts';
      } catch (err) {
        showFlash('删除失败: ' + err.message);
      }
    });
  }

  /* ── Contract Transition ──────────────────────────────────────────── */

  function setupTransitionButtons() {
    document.querySelectorAll('.transition-btn').forEach(function (btn) {
      btn.addEventListener('click', async function () {
        var action = btn.dataset.action;
        var label = btn.dataset.label || action;
        if (!confirm('确定执行「' + label + '」操作？')) return;
        var contractId = btn.dataset.contractId;
        try {
          await apiFetch('/api/contracts/' + contractId + '/transition', {
            method: 'POST',
            body: JSON.stringify({ action: action }),
          });
          window.location.reload();
        } catch (err) {
          showFlash('操作失败: ' + err.message);
        }
      });
    });
  }

  /* ── Form Validation ──────────────────────────────────────────────── */

  function setupFormValidation() {
    var form = document.querySelector('form[data-validate]');
    if (!form) return;
    form.addEventListener('submit', function (e) {
      var requiredFields = form.querySelectorAll('[required]');
      var valid = true;
      requiredFields.forEach(function (field) {
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

  /* ── Init ─────────────────────────────────────────────────────────── */

  document.addEventListener('DOMContentLoaded', function () {
    setupLogout();
    setupContractFilters();
    setupAttachmentUpload();
    setupAttachmentDelete();
    setupContractDelete();
    setupTransitionButtons();
    setupFormValidation();
  });

})();
