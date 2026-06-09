(function () {
  const cfg = window.ATTENDLY_TABLE;
  if (!cfg) return;

  const statusBar = document.getElementById('status-bar');
  const footerStats = document.getElementById('footer-stats');
  const footerDirty = document.getElementById('footer-dirty');
  const btnFilter = document.getElementById('btn-filter');
  const btnColumns = document.getElementById('btn-columns');
  const btnSync = document.getElementById('btn-sync');
  const btnAdd = document.getElementById('btn-add-row');
  const btnUndo = document.getElementById('btn-undo');
  const btnApply = document.getElementById('btn-apply');
  const btnCancel = document.getElementById('btn-cancel');
  const btnExport = document.getElementById('btn-export');
  const btnSettings = document.getElementById('btn-settings');
  const columnsPanel = document.getElementById('zt-columns-panel');
  const columnsList = document.getElementById('zt-columns-list');
  const columnsClose = document.getElementById('zt-columns-close');

  const dirtyRows = new Set();
  const rowSnapshots = new Map();
  const autocompleteCache = {};
  const undoStack = [];
  let table = null;
  let selectedRow = null;
  let filtersEnabled = false;

  function setStatus(msg, type) {
    statusBar.textContent = msg || '';
    statusBar.className = 'zt-status-bar' + (type ? ' is-' + type : '');
  }

  function apiUrl(path) {
    return '/table/api/' + path;
  }

  function csrfHeaders() {
    return {
      'Content-Type': 'application/json',
      'X-CSRFToken': cfg.csrfToken,
    };
  }

  function cleanRowData(data) {
    const copy = Object.assign({}, data);
    delete copy._key;
    delete copy._actions;
    return copy;
  }

  function storeSnapshot(row) {
    rowSnapshots.set(row.getData()._key, cleanRowData(row.getData()));
  }

  function snapshotAllRows() {
    rowSnapshots.clear();
    if (!table) return;
    table.getRows().forEach(storeSnapshot);
  }

  function rowHasChanges(row) {
    const key = row.getData()._key;
    const snap = rowSnapshots.get(key);
    if (!snap) return false;
    return JSON.stringify(cleanRowData(row.getData())) !== JSON.stringify(snap);
  }

  function getRefFields() {
    const refs = [];
    (cfg.gridConfig.columns || []).forEach(function (col) {
      if (col.ref) refs.push(col.ref);
    });
    return refs;
  }

  async function fetchAutocomplete(field, term) {
    const cacheKey = field + '::all';
    if (!term && autocompleteCache[cacheKey]) {
      return autocompleteCache[cacheKey];
    }
    const url = apiUrl('autocomplete/' + field + '/') + (term ? '?term=' + encodeURIComponent(term) : '');
    const res = await fetch(url, {
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': cfg.csrfToken },
    });
    if (!res.ok) return [];
    const data = await res.json();
    const results = data.results || [];
    if (!term) {
      autocompleteCache[cacheKey] = results;
      autocompleteCache[field] = results;
    }
    return results;
  }

  async function preloadAutocomplete() {
    await Promise.all(getRefFields().map(function (field) {
      return fetchAutocomplete(field, '');
    }));
  }

  function getCachedItems(field) {
    return autocompleteCache[field] || autocompleteCache[field + '::all'] || [];
  }

  function createAutocompleteEditor(field) {
    return function (cell, onRendered, success, cancel) {
      const input = document.createElement('input');
      input.type = 'text';
      input.value = cell.getValue() || '';
      input.style.width = '100%';
      input.style.padding = '4px 6px';
      input.style.boxSizing = 'border-box';
      input.style.border = 'none';
      input.style.outline = 'none';

      const listDiv = document.createElement('div');
      listDiv.className = 'autocomplete-list';
      listDiv.style.display = 'none';

      let closed = false;
      let scrollHandler = null;

      function positionList() {
        const rect = input.getBoundingClientRect();
        listDiv.style.left = rect.left + 'px';
        listDiv.style.top = (rect.bottom + 2) + 'px';
        listDiv.style.width = Math.max(rect.width, 180) + 'px';
      }

      function removeList() {
        listDiv.style.display = 'none';
        if (listDiv.parentNode) listDiv.parentNode.removeChild(listDiv);
        if (scrollHandler) {
          window.removeEventListener('scroll', scrollHandler, true);
          scrollHandler = null;
        }
      }

      function finishEdit(value) {
        if (closed) return;
        closed = true;
        removeList();
        success(value);
        onCellEditFinished(cell);
      }

      function showList(items, inputValue) {
        listDiv.innerHTML = '';
        const value = (inputValue || '').trim();
        if (value) {
          const createItem = document.createElement('div');
          createItem.textContent = '➕ Создать «' + value + '»';
          createItem.style.background = '#e8f4f8';
          createItem.style.fontWeight = 'bold';
          createItem.onmousedown = function (e) {
            e.preventDefault();
            finishEdit(value);
          };
          listDiv.appendChild(createItem);
        }
        items.forEach(function (item) {
          const div = document.createElement('div');
          div.textContent = item.name;
          div.onmousedown = function (e) {
            e.preventDefault();
            finishEdit(item.name);
          };
          listDiv.appendChild(div);
        });
        if (items.length || value) {
          positionList();
          listDiv.style.display = 'block';
        } else {
          listDiv.style.display = 'none';
        }
      }

      input.addEventListener('focus', function () {
        fetchAutocomplete(field, '').then(function () {
          const q = input.value.toLowerCase();
          const items = getCachedItems(field).filter(function (item) {
            return !q || item.name.toLowerCase().includes(q);
          });
          showList(items, input.value);
        });
      });

      input.addEventListener('input', function () {
        const q = input.value.toLowerCase();
        const items = getCachedItems(field).filter(function (item) {
          return !q || item.name.toLowerCase().includes(q);
        });
        showList(items, input.value);
      });

      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          finishEdit(input.value);
        } else if (e.key === 'Escape') {
          closed = true;
          removeList();
          cancel();
        }
      });

      input.addEventListener('blur', function () {
        setTimeout(function () {
          if (closed) return;
          finishEdit(input.value);
        }, 200);
      });

      onRendered(function () {
        input.focus();
        input.select();
        document.body.appendChild(listDiv);
        scrollHandler = function () { positionList(); };
        window.addEventListener('scroll', scrollHandler, true);
        fetchAutocomplete(field, '').then(function () {
          showList(getCachedItems(field), input.value);
        });
      });

      return input;
    };
  }

  function normalizeListEditorParams(params) {
    const editorParams = Object.assign({ autocomplete: false }, params || {});
    if (Array.isArray(editorParams.values)) {
      const map = {};
      editorParams.values.forEach(function (v) { map[v] = v; });
      editorParams.values = map;
    }
    return editorParams;
  }

  function updateToolbar() {
    const hasDirty = dirtyRows.size > 0;
    btnApply.disabled = !hasDirty;
    btnCancel.disabled = !hasDirty;
    btnUndo.disabled = undoStack.length === 0;
    btnApply.classList.toggle('is-active', hasDirty);
    btnCancel.classList.toggle('is-active', hasDirty);
    btnFilter.classList.toggle('is-active', filtersEnabled);
    footerDirty.textContent = hasDirty ? ('Изменено: ' + dirtyRows.size) : '';
  }

  function refreshRowStyle(row) {
    const el = row.getElement();
    if (!el) return;
    el.classList.toggle('zt-row-dirty', dirtyRows.has(row.getData()._key));
  }

  function pushUndo(action) {
    undoStack.push(action);
    if (undoStack.length > 50) undoStack.shift();
    updateToolbar();
  }

  function markDirty(row) {
    const key = row.getData()._key;
    if (!dirtyRows.has(key)) {
      pushUndo({ type: 'row', key: key, snapshot: Object.assign({}, rowSnapshots.get(key)) });
    }
    dirtyRows.add(key);
    refreshRowStyle(row);
    updateToolbar();
  }

  function clearDirty(row) {
    dirtyRows.delete(row.getData()._key);
    storeSnapshot(row);
    refreshRowStyle(row);
    updateToolbar();
  }

  function onCellEditFinished(cell) {
    const row = cell.getRow();
    selectRow(row);
    if (rowHasChanges(row)) {
      markDirty(row);
    } else if (dirtyRows.has(row.getData()._key)) {
      clearDirty(row);
    }
  }

  function adminUrlForRow(data) {
    const urls = cfg.adminUrls || {};
    if (cfg.dataset === 'actions' && data.id) return urls.action.replace('{id}', data.id);
    if (cfg.dataset === 'contacts' && data.id) return urls.contact.replace('{id}', data.id);
    if (cfg.dataset === 'events' && data.id) return urls.event.replace('{id}', data.id);
    if (cfg.dataset === 'companies' && data.id) return urls.company.replace('{id}', data.id);
    if (cfg.dataset === 'categories' && data.id) return urls.category.replace('{id}', data.id);
    if (cfg.dataset === 'type_guests' && data.id) return urls.type_guest.replace('{id}', data.id);
    return null;
  }

  function actionsFormatter(cell) {
    const row = cell.getRow();
    const data = row.getData();
    const wrap = document.createElement('div');
    wrap.className = 'zt-row-actions';

    const adminBtn = document.createElement('a');
    adminBtn.className = 'zt-row-btn';
    adminBtn.title = 'Открыть в админке';
    adminBtn.textContent = '↗';
    const url = adminUrlForRow(data);
    if (url) {
      adminBtn.href = url;
      adminBtn.target = '_blank';
    } else {
      adminBtn.style.opacity = '0.3';
      adminBtn.href = '#';
      adminBtn.addEventListener('click', function (e) { e.preventDefault(); });
    }

    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'zt-row-btn is-delete';
    delBtn.title = 'Удалить';
    delBtn.textContent = '✕';
    delBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      deleteRow(row);
    });

    wrap.appendChild(adminBtn);
    wrap.appendChild(delBtn);
    return wrap;
  }

  function buildColumns() {
    return cfg.gridConfig.columns.map(function (col) {
      const def = {
        title: col.title,
        field: col.field,
        width: col.width,
        visible: col.visible !== false,
        frozen: col.frozen || false,
        headerSort: col.field !== '_actions',
      };

      if (col.field !== '_actions' && col.field !== 'id') {
        def.tooltip = true;
      }

      if (col.field === '_actions') {
        def.formatter = actionsFormatter;
        def.headerSort = false;
        def.editor = false;
        return def;
      }

      if (col.editor === 'autocomplete' && col.ref) {
        def.editor = createAutocompleteEditor(col.ref);
      } else if (col.editor === 'status') {
        const values = cfg.gridConfig.statusValues || {};
        def.editor = 'list';
        def.editorParams = normalizeListEditorParams({ values: values });
        def.formatter = function (cell) {
          const v = cell.getValue();
          return values[v] || v || '';
        };
      } else if (col.editor === 'list' && col.editorParams) {
        def.editor = 'list';
        def.editorParams = normalizeListEditorParams(col.editorParams);
      } else if (col.editor === 'input' || col.editor === true) {
        def.editor = 'input';
      } else {
        def.editor = false;
      }

      return def;
    });
  }

  function prepareRows(rows) {
    return rows.map(function (r, i) {
      const copy = Object.assign({}, r);
      copy._key = copy.id ? 'id:' + copy.id : 'new:' + i;
      return copy;
    });
  }

  function findRowByKey(key) {
    return table.getRows().find(function (r) { return r.getData()._key === key; }) || null;
  }

  function selectRow(row) {
    if (selectedRow && selectedRow !== row) selectedRow.deselect();
    selectedRow = row;
    if (row) row.select();
  }

  async function loadData() {
    if (dirtyRows.size && !confirm('Есть несохранённые изменения. Синхронизировать и потерять их?')) {
      return;
    }
    setStatus('Синхронизация…');
    await preloadAutocomplete();
    const res = await fetch(apiUrl(cfg.dataset + '/'), { credentials: 'same-origin' });
    const payload = await res.json();
    if (!res.ok) {
      setStatus(payload.error || 'Ошибка загрузки', 'error');
      return;
    }
    dirtyRows.clear();
    undoStack.length = 0;
    selectedRow = null;
    const rows = prepareRows(payload.data || []);
    await table.setData(rows);
    snapshotAllRows();
    table.getRows().forEach(refreshRowStyle);
    footerStats.textContent = 'Записей: ' + (payload.total ?? rows.length);
    setStatus('Синхронизировано', 'ok');
    setTimeout(function () { setStatus(''); }, 1500);
    updateToolbar();
  }

  async function saveRow(row) {
    const data = cleanRowData(row.getData());
    const key = row.getData()._key;
    setStatus('Сохранение…');
    const res = await fetch(apiUrl(cfg.dataset + '/save/'), {
      method: 'POST',
      headers: csrfHeaders(),
      body: JSON.stringify(data),
    });
    const payload = await res.json();
    if (!res.ok) {
      setStatus(payload.error || 'Ошибка сохранения', 'error');
      return false;
    }
    const saved = payload.row;
    saved._key = 'id:' + saved.id;
    if (key !== saved._key) {
      dirtyRows.delete(key);
      rowSnapshots.delete(key);
    }
    row.update(saved);
    clearDirty(row);
    return true;
  }

  async function applyAllChanges() {
    const rows = table.getRows().filter(function (r) { return dirtyRows.has(r.getData()._key); });
    if (!rows.length) {
      setStatus('Нет несохранённых изменений');
      return;
    }
    for (const row of rows) {
      const ok = await saveRow(row);
      if (!ok) return;
    }
    undoStack.length = 0;
    updateToolbar();
    setStatus('Изменения применены', 'ok');
    setTimeout(function () { setStatus(''); }, 2000);
  }

  function cancelRow(row) {
    const data = row.getData();
    const snap = rowSnapshots.get(data._key);
    if (!data.id) {
      dirtyRows.delete(data._key);
      rowSnapshots.delete(data._key);
      if (selectedRow === row) selectedRow = null;
      row.delete();
      updateToolbar();
      return;
    }
    if (snap) row.update(Object.assign({}, snap, { _key: data._key }));
    clearDirty(row);
  }

  function cancelAllChanges() {
    if (!dirtyRows.size) return;
    if (dirtyRows.size > 1 && !confirm('Отменить все несохранённые изменения (' + dirtyRows.size + ')?')) {
      return;
    }
    const keys = Array.from(dirtyRows);
    keys.forEach(function (key) {
      const row = findRowByKey(key);
      if (row) cancelRow(row);
    });
    undoStack.length = 0;
    updateToolbar();
    setStatus('Изменения отменены');
    setTimeout(function () { setStatus(''); }, 2000);
  }

  function undoLastAction() {
    const action = undoStack.pop();
    if (!action) return;
    if (action.type === 'row') {
      const row = findRowByKey(action.key);
      if (!row) { updateToolbar(); return; }
      if (!action.snapshot || !action.snapshot.id) {
        dirtyRows.delete(action.key);
        rowSnapshots.delete(action.key);
        if (selectedRow === row) selectedRow = null;
        row.delete();
      } else {
        row.update(Object.assign({}, action.snapshot, { _key: action.key }));
        clearDirty(row);
      }
    } else if (action.type === 'add') {
      const row = findRowByKey(action.key);
      if (row) cancelRow(row);
    }
    updateToolbar();
    setStatus('Действие отменено');
    setTimeout(function () { setStatus(''); }, 1500);
  }

  async function deleteRow(row) {
    const data = row.getData();
    if (!data.id) {
      row.delete();
      return;
    }
    if (!confirm('Удалить запись #' + data.id + '?')) return;
    const res = await fetch(apiUrl(cfg.dataset + '/delete/'), {
      method: 'POST',
      headers: csrfHeaders(),
      body: JSON.stringify({ id: data.id }),
    });
    if (!res.ok) {
      const payload = await res.json();
      setStatus(payload.error || 'Ошибка удаления', 'error');
      return;
    }
    dirtyRows.delete(data._key);
    rowSnapshots.delete(data._key);
    if (selectedRow === row) selectedRow = null;
    row.delete();
    updateToolbar();
    setStatus('Удалено', 'ok');
    setTimeout(function () { setStatus(''); }, 2000);
  }

  function addEmptyRow() {
    const key = 'new:' + Date.now();
    const empty = { _key: key };
    cfg.gridConfig.columns.forEach(function (col) {
      if (col.field && col.field !== '_actions' && col.field !== 'id') {
        empty[col.field] = '';
      }
    });
    rowSnapshots.set(key, cleanRowData(empty));
    table.addRow(empty, true).then(function (row) {
      dirtyRows.add(key);
      pushUndo({ type: 'add', key: key });
      refreshRowStyle(row);
      selectRow(row);
      updateToolbar();
    });
  }

  function toggleFilters() {
    filtersEnabled = !filtersEnabled;
    table.getColumns().forEach(function (col) {
      const field = col.getField();
      if (!field || field === '_actions' || field === 'id') return;
      col.updateDefinition({ headerFilter: filtersEnabled ? 'input' : false });
    });
    updateToolbar();
  }

  function buildColumnsPanel() {
    columnsList.innerHTML = '';
    table.getColumns().forEach(function (col) {
      const field = col.getField();
      if (!field || field === '_actions') return;
      const label = document.createElement('label');
      label.className = 'zt-col-toggle';
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = col.isVisible();
      cb.addEventListener('change', function () {
        if (cb.checked) col.show(); else col.hide();
      });
      label.appendChild(cb);
      label.appendChild(document.createTextNode(col.getDefinition().title || field));
      columnsList.appendChild(label);
    });
  }

  function toggleColumnsPanel() {
    if (columnsPanel.hidden) {
      buildColumnsPanel();
      columnsPanel.hidden = false;
    } else {
      columnsPanel.hidden = true;
    }
  }

  function resetTableLayout() {
    table.getColumns().forEach(function (col) { col.show(); });
    table.setLayout('fitDataStretch');
    setStatus('Настройки сброшены');
    setTimeout(function () { setStatus(''); }, 1500);
  }

  function initTable() {
    table = new Tabulator('#attendly-table', {
      data: [],
      layout: 'fitDataStretch',
      height: '100%',
      placeholder: 'Нет данных',
      selectable: 1,
      columns: buildColumns(),
      rowFormatter: function (row) { refreshRowStyle(row); },
    });

    table.on('cellEditing', function (cell) {
      const row = cell.getRow();
      selectRow(row);
      if (!dirtyRows.has(row.getData()._key)) {
        storeSnapshot(row);
      }
    });

    table.on('cellEdited', function (cell) {
      onCellEditFinished(cell);
    });

    table.on('rowClick', function (e, row) {
      if (e.target.closest('.zt-row-btn')) return;
      selectRow(row);
    });

    loadData();
  }

  btnFilter.addEventListener('click', toggleFilters);
  btnColumns.addEventListener('click', toggleColumnsPanel);
  columnsClose.addEventListener('click', function () { columnsPanel.hidden = true; });
  btnSync.addEventListener('click', loadData);
  btnAdd.addEventListener('click', addEmptyRow);
  btnUndo.addEventListener('click', undoLastAction);
  btnApply.addEventListener('click', applyAllChanges);
  btnCancel.addEventListener('click', cancelAllChanges);
  btnSettings.addEventListener('click', resetTableLayout);

  if (cfg.gridConfig.exportUrl) {
    btnExport.hidden = false;
    btnExport.addEventListener('click', function () {
      window.location.href = cfg.gridConfig.exportUrl;
    });
  }

  document.addEventListener('click', function (e) {
    if (!columnsPanel.hidden && !columnsPanel.contains(e.target) && e.target !== btnColumns) {
      columnsPanel.hidden = true;
    }
  });

  initTable();
})();
