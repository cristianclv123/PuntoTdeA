(function () {
  const API = {
    faqs: '/api/knowledge/faqs/',
    articles: '/api/knowledge/articles/',
    categories: '/api/knowledge/categories/',
  };

  const ICON_PENCIL = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/></svg>';
  const ICON_TRASH = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 11v6"/><path d="M14 11v6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>';

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
  }

  async function apiRequest(url, options) {
    options = options || {};
    const headers = Object.assign({ 'X-CSRFToken': getCookie('csrftoken') }, options.headers || {});
    if (options.body && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }
    const resp = await fetch(url, Object.assign({}, options, { headers }));
    if (!resp.ok) {
      let data = {};
      try { data = await resp.json(); } catch (_) { /* no body */ }
      const message = data.detail || Object.values(data).flat().join(' ') || `Error ${resp.status}`;
      throw new Error(message);
    }
    if (resp.status === 204) return null;
    return resp.json();
  }

  let categories = [];
  let currentItems = [];
  const state = { tab: 'faqs', category: '', search: '' };

  function categoryName(id) {
    const found = categories.find((c) => c.id === id);
    return found ? found.name : '—';
  }

  async function loadCategories() {
    categories = await apiRequest(API.categories);
    const datalist = document.getElementById('category-options');
    if (datalist) {
      datalist.innerHTML = categories.map((c) => `<option value="${escapeHtml(c.name)}"></option>`).join('');
    }
  }

  async function resolveCategoryId(name) {
    const trimmed = (name || '').trim();
    const existing = categories.find((c) => c.name.toLowerCase() === trimmed.toLowerCase());
    if (existing) return existing.id;
    const created = await apiRequest(API.categories, { method: 'POST', body: JSON.stringify({ name: trimmed }) });
    categories.push(created);
    return created.id;
  }

  function matchesSearch(tab, item, term) {
    const haystack = tab === 'faqs' ? `${item.question} ${item.answer}` : `${item.title} ${item.summary}`;
    return haystack.toLowerCase().includes(term.toLowerCase());
  }

  function faqRow(item) {
    const statusPill = item.is_active
      ? '<span class="pill pill-success">Activa</span>'
      : '<span class="pill pill-neutral">Inactiva</span>';
    return `
      <div class="data-table-row" data-row-id="${item.id}">
        <div class="col-flex" style="font-weight:500;">${escapeHtml(item.question)}</div>
        <div class="col-fixed-160"><span class="tag">${escapeHtml(categoryName(item.category))}</span></div>
        <div class="col-fixed-110">${statusPill}</div>
        <div class="row-actions" style="width:80px; flex-shrink:0;">
          <button type="button" class="icon-btn" data-edit="${item.id}" title="Editar">${ICON_PENCIL}</button>
          <button type="button" class="icon-btn" data-delete="${item.id}" title="Eliminar">${ICON_TRASH}</button>
        </div>
      </div>`;
  }

  function articleRow(item) {
    const statusPill = item.published
      ? '<span class="pill pill-success">Publicado</span>'
      : '<span class="pill pill-neutral">Borrador</span>';
    return `
      <div class="data-table-row" data-row-id="${item.id}">
        <div class="col-flex" style="font-weight:500;">${escapeHtml(item.title)}</div>
        <div class="col-fixed-160"><span class="tag">${escapeHtml(categoryName(item.category))}</span></div>
        <div class="col-fixed-110">${statusPill}</div>
        <div class="row-actions" style="width:80px; flex-shrink:0;">
          <button type="button" class="icon-btn" data-edit="${item.id}" title="Editar">${ICON_PENCIL}</button>
          <button type="button" class="icon-btn" data-delete="${item.id}" title="Eliminar">${ICON_TRASH}</button>
        </div>
      </div>`;
  }

  function confirmDeleteHtml(id) {
    return `
      <span style="font-size:12px; color:var(--text-secondary);">¿Eliminar?</span>
      <button type="button" class="btn-ghost" style="padding:4px 8px;" data-confirm-delete="${id}">Sí</button>
      <button type="button" class="btn-ghost" style="padding:4px 8px;" data-cancel-delete>No</button>`;
  }

  async function loadList(tab) {
    const container = document.querySelector(`[data-list="${tab}"]`);
    if (!container) return;
    container.innerHTML = '<div class="data-table-row" style="color:var(--text-muted);">Cargando...</div>';
    const params = new URLSearchParams();
    if (state.category) params.set('category', state.category);
    const items = await apiRequest(`${API[tab]}?${params.toString()}`);
    currentItems = state.search ? items.filter((item) => matchesSearch(tab, item, state.search)) : items;
    if (!currentItems.length) {
      container.innerHTML = '<div class="data-table-row" style="color:var(--text-muted);">Sin resultados.</div>';
      return;
    }
    container.innerHTML = currentItems.map((item) => (tab === 'faqs' ? faqRow(item) : articleRow(item))).join('');
  }

  function openDialog(tab, item) {
    const dialog = document.getElementById(tab === 'faqs' ? 'faq-dialog' : 'article-dialog');
    const form = dialog.querySelector('form');
    form.reset();
    form.querySelector('[data-form-error]').hidden = true;
    form.elements.id.value = item ? item.id : '';
    dialog.querySelector('[data-dialog-title]').textContent = item
      ? (tab === 'faqs' ? 'Editar pregunta' : 'Editar artículo')
      : (tab === 'faqs' ? 'Nueva pregunta' : 'Nuevo artículo');
    if (item) {
      if (tab === 'faqs') {
        form.elements.question.value = item.question;
        form.elements.answer.value = item.answer;
        form.elements.category_name.value = categoryName(item.category);
        form.elements.is_active.checked = item.is_active;
      } else {
        form.elements.title.value = item.title;
        form.elements.summary.value = item.summary || '';
        form.elements.content.value = item.content;
        form.elements.category_name.value = categoryName(item.category);
        form.elements.tags.value = (item.tags || []).join(', ');
        form.elements.published.checked = item.published;
      }
    }
    dialog.showModal();
  }

  async function handleSubmit(tab, event) {
    event.preventDefault();
    const form = event.target;
    const errorEl = form.querySelector('[data-form-error]');
    errorEl.hidden = true;
    const id = form.elements.id.value;
    try {
      const categoryId = await resolveCategoryId(form.elements.category_name.value);
      let payload;
      if (tab === 'faqs') {
        payload = {
          question: form.elements.question.value.trim(),
          answer: form.elements.answer.value.trim(),
          category: categoryId,
          is_active: form.elements.is_active.checked,
        };
      } else {
        const published = form.elements.published.checked;
        payload = {
          title: form.elements.title.value.trim(),
          summary: form.elements.summary.value.trim(),
          content: form.elements.content.value.trim(),
          category: categoryId,
          tags: form.elements.tags.value.split(',').map((t) => t.trim()).filter(Boolean),
          published,
          status: published ? 'published' : 'draft',
        };
      }
      const url = id ? `${API[tab]}${id}/` : API[tab];
      await apiRequest(url, { method: id ? 'PATCH' : 'POST', body: JSON.stringify(payload) });
      form.closest('dialog').close();
      await loadList(tab);
    } catch (err) {
      errorEl.textContent = err.message || 'No se pudo guardar.';
      errorEl.hidden = false;
    }
  }

  async function deleteItem(tab, id) {
    await apiRequest(`${API[tab]}${id}/`, { method: 'DELETE' });
    await loadList(tab);
  }

  function showImportResult(ok, message) {
    const el = document.querySelector('[data-import-result]');
    el.hidden = false;
    el.className = ok ? 'km-import-result km-import-result--ok' : 'km-import-result km-import-result--error';
    el.textContent = message;
  }

  async function handleImport(file) {
    const tab = state.tab;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const result = await apiRequest(`${API[tab]}import_excel/`, { method: 'POST', body: formData });
      const summary = `Creados: ${result.created} · Actualizados: ${result.updated} · Omitidos: ${result.skipped}`;
      showImportResult(true, result.errors.length ? `${summary} · ${result.errors.join(' | ')}` : summary);
      await loadCategories();
      await loadList(tab);
    } catch (err) {
      showImportResult(false, err.message || 'No se pudo importar el archivo.');
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const root = document.querySelector('.knowledge-manage');
    if (!root) return;

    loadCategories().then(() => loadList(state.tab));

    root.querySelectorAll('.km-tab').forEach((btn) => {
      btn.addEventListener('click', () => {
        root.querySelectorAll('.km-tab').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        state.tab = btn.dataset.tab;
        root.querySelectorAll('.km-panel').forEach((p) => { p.hidden = p.dataset.panel !== state.tab; });
        root.querySelector('[data-create-label]').textContent = state.tab === 'faqs' ? 'Nueva pregunta' : 'Nuevo artículo';
        document.querySelector('[data-import-result]').hidden = true;
        loadList(state.tab);
      });
    });

    root.querySelector('[data-category-filter]').addEventListener('click', (event) => {
      const tab = event.target.closest('.category-tab');
      if (!tab) return;
      root.querySelectorAll('[data-category-filter] .category-tab').forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      state.category = tab.dataset.category;
      loadList(state.tab);
    });

    root.querySelector('[data-search]').addEventListener('input', (event) => {
      state.search = event.target.value;
      loadList(state.tab);
    });

    root.querySelector('[data-open-create]').addEventListener('click', () => openDialog(state.tab, null));

    document.querySelectorAll('[data-form]').forEach((form) => {
      form.addEventListener('submit', (event) => handleSubmit(form.dataset.form, event));
    });

    document.querySelectorAll('[data-close-dialog]').forEach((btn) => {
      btn.addEventListener('click', () => btn.closest('dialog').close());
    });

    root.querySelectorAll('[data-list]').forEach((container) => {
      container.addEventListener('click', (event) => {
        const tab = container.dataset.list;
        const editBtn = event.target.closest('[data-edit]');
        const deleteBtn = event.target.closest('[data-delete]');
        const confirmYes = event.target.closest('[data-confirm-delete]');
        const confirmNo = event.target.closest('[data-cancel-delete]');

        if (editBtn) {
          const item = currentItems.find((i) => String(i.id) === editBtn.dataset.edit);
          if (item) openDialog(tab, item);
        } else if (deleteBtn) {
          const row = deleteBtn.closest('[data-row-id]');
          row.querySelector('.row-actions').innerHTML = confirmDeleteHtml(deleteBtn.dataset.delete);
        } else if (confirmYes) {
          deleteItem(tab, confirmYes.dataset.confirmDelete);
        } else if (confirmNo) {
          loadList(tab);
        }
      });
    });

    const importInput = root.querySelector('[data-import-input]');
    importInput.addEventListener('change', (event) => {
      const file = event.target.files[0];
      if (file) handleImport(file);
      event.target.value = '';
    });
  });
})();
