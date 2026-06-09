(function () {
  const cfg = window.ATTENDLY_TABLE;
  if (!cfg) return;

  const statusBar = document.getElementById('status-bar');
  const footerStats = document.getElementById('footer-stats');
  const btnApplyRow = document.getElementById('btn-apply-row');
  const btnCancelRow = document.getElementById('btn-cancel-row');
  const btnReloadRow = document.getElementById('btn-reload-row');
  const btnRefresh = document.getElementById('btn-refresh');
  const btnAdd = document.getElementById('btn-add-row');
  const btnSaveAll = document.getElementById('btn-save-all');
  const btnExport = document.getElementById('btn-export');

  const dirtyRows = new Set();
  const rowSnapshots = new Map();
  const autocompleteCache = {};
  let table = null;
  let selectedRow = null;

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
    const data = row.getData();
    rowSnapshots.set(data._key, cleanRowData(data));
  }

  function snapshotAllRows() {
    rowSnapshots.clear();
    if (!table) return;
    table.getRows().forEach(storeSnapshot);
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
    const res = await fetch(url, { headers: { 'X-CSRFToken': cfg.csrfToken } });
    const data = await res.json();
    const results = data.results || [];
    if (!term) {
      autocompleteCache[cacheKey] = results;
      autocompleteCache[field] = results;
    }
    return results;
  }

  async function preloadAutocomplete() {
    const fields = getRefFields();
    await Promise.all(fields.map(function (field) {
      return fetchAutocomplete(field, '');
    }));
  }

  function listValuesForRef(ref) {
    const items = autocompleteCache[ref] || autocompleteCache[ref + '::all'] || [];
    const names = items.map(function (item) { return item.name; });
    return [''].concat(names);
  }

  function makeListEditor(ref) {
    return {
      editor: 'list',
      editorParams: {
        values: function () {
          return listValuesForRef(ref);
        },
        autocomplete: true,
        listOnEmpty: true,
        freetext: true,
        allowEmpty: true,
      },
    };
  }

  function updateRowToolbar() {
    const row = selectedRow;
    const key = row ? row.getData()._key : null;
    const dirty = key && dirtyRows.has(key);
    const hasId = row && row.getData().id;

    btnApplyRow.disabled = !dirty;
    btnCancelRow.disabled = !dirty;
    btnReloadRow.disabled = !dirty || !hasId;

    btnApplyRow.classList.toggle('is-active', !!dirty);
    btnCancelRow.classList.toggle('is-active', !!dirty);
    btnReloadRow.classList.toggle('is-active', !!(dirty && hasId));
  }

  function refreshRowStyle(row) {
    const el = row.getElement();
    if (!el) return;
    const dirty = dirtyRows.has(row.getData()._key);
    el.classList.toggle('zt-row-dirty', dirty);
    if (dirty) {
      el.style.backgroundColor = '#fff8e6';
    } else {
      el.style.backgroundColor = '';
    }
  }

  function markDirty(row) {
    dirtyRows.add(row.getData()._key);
    refreshRowStyle(row);
    updateRowToolbar();
  }

  function clearDirty(row) {
    const data = row.getData();
    dirtyRows.delete(data._key);
    storeSnapshot(row);
    refreshRowStyle(row);
    updateRowToolbar();
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
    if (data.id) {
      const urlTpl = cfg.dataset === 'contacts' ? cfg.adminUrls.contact : cfg.adminUrls.event;
      if (urlTpl) adminBtn.href = urlTpl.replace('{id}', data.id);
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

      if (col.field === '_actions') {
        def.formatter = actionsFormatter;
        def.headerSort = false;
        def.editor = false;
        return def;
      }

      if (col.editor === 'autocomplete' && col.ref) {
        Object.assign(def, makeListEditor(col.ref));
      } else if (col.editor === 'list' && col.editorParams) {
        def.editor = 'list';
        def.editorParams = col.editorParams;
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

  function selectRow(row) {
    if (selectedRow && selectedRow !== row) {
      selectedRow.deselect();
    }
    selectedRow = row;
    if (row) row.select();
    updateRowToolbar();
  }

  async function loadData() {
    if (dirtyRows.size && !confirm('Есть несохранённые изменения. Обновить таблицу и потерять их?')) {
      return;
    }
    setStatus('Загрузка…');
    await preloadAutocomplete();
    const res = await fetch(apiUrl(cfg.dataset + '/'));
    const payload = await res.json();
    if (!res.ok) {
      setStatus(payload.error || 'Ошибка загрузки', 'error');
      return;
    }
    dirtyRows.clear();
    selectedRow = null;
    const rows = prepareRows(payload.data || []);
    await table.setData(rows);
    snapshotAllRows();
    footerStats.textContent = 'Записей: ' + (payload.total ?? rows.length);
    setStatus('');
    updateRowToolbar();
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
    setStatus('Сохранено', 'ok');
    setTimeout(function () { setStatus(''); }, 2000);
    return true;
  }

  async function cancelRow(row) {
    const data = row.getData();
    const snap = rowSnapshots.get(data._key);

    if (!data.id) {
      dirtyRows.delete(data._key);
      rowSnapshots.delete(data._key);
      if (selectedRow === row) {
        selectedRow = null;
        updateRowToolbar();
      }
      row.delete();
      setStatus('Новая строка отменена');
      return;
    }

    if (snap) {
      const restored = Object.assign({}, snap, { _key: data._key });
      row.update(restored);
    }
    clearDirty(row);
    setStatus('Изменения отменены');
    setTimeout(function () { setStatus(''); }, 2000);
  }

  async function reloadRowFromServer(row) {
    const data = row.getData();
    if (!data.id) return;

    setStatus('Загрузка строки…');
    const res = await fetch(apiUrl(cfg.dataset + '/' + data.id + '/'));
    const payload = await res.json();
    if (!res.ok) {
      setStatus(payload.error || 'Ошибка загрузки строки', 'error');
      return;
    }

    const fresh = payload.row;
    fresh._key = 'id:' + fresh.id;
    row.update(fresh);
    clearDirty(row);
    setStatus('Строка обновлена с сервера', 'ok');
    setTimeout(function () { setStatus(''); }, 2000);
  }

  async function deleteRow(row) {
    const data = row.getData();
    if (!data.id) {
      row.delete();
      if (selectedRow === row) {
        selectedRow = null;
        updateRowToolbar();
      }
      return;
    }
    if (!confirm('Удалить запись #' + data.id + '?')) return;

    const res = await fetch(apiUrl(cfg.dataset + '/delete/'), {
      method: 'POST',
      headers: csrfHeaders(),
      body: JSON.stringify({ id: data.id }),
    });
    const payload = await res.json();
    if (!res.ok) {
      setStatus(payload.error || 'Ошибка удаления', 'error');
      return;
    }
    dirtyRows.delete(data._key);
    rowSnapshots.delete(data._key);
    if (selectedRow === row) {
      selectedRow = null;
      updateRowToolbar();
    }
    row.delete();
    setStatus('Удалено', 'ok');
    setTimeout(function () { setStatus(''); }, 2000);
  }

  async function saveAllDirty() {
    const rows = table.getRows().filter(function (r) {
      return dirtyRows.has(r.getData()._key);
    });
    if (!rows.length) {
      setStatus('Нет несохранённых изменений');
      return;
    }
    for (const row of rows) {
      const ok = await saveRow(row);
      if (!ok) break;
    }
  }

  function addEmptyRow() {
    const empty = { _key: 'new:' + Date.now() };
    cfg.gridConfig.columns.forEach(function (col) {
      if (col.field && col.field !== '_actions' && col.field !== 'id') {
        empty[col.field] = '';
      }
    });
    dirtyRows.add(empty._key);
    table.addRow(empty, true).then(function (row) {
      rowSnapshots.set(empty._key, cleanRowData(empty));
      refreshRowStyle(row);
      selectRow(row);
    });
  }

  function getSelectedOrWarn() {
    if (!selectedRow) {
      setStatus('Сначала выберите строку в таблице');
      return null;
    }
    return selectedRow;
  }

  function initTable() {
    table = new Tabulator('#attendly-table', {
      data: [],
      layout: 'fitDataStretch',
      height: '100%',
      placeholder: 'Нет данных',
      selectable: 1,
      columns: buildColumns(),
      cellEdited: function (cell) {
        markDirty(cell.getRow());
      },
      rowFormatter: function (row) {
        refreshRowStyle(row);
      },
    });

    table.on('cellEditing', function (cell) {
      const row = cell.getRow();
      if (!dirtyRows.has(row.getData()._key)) {
        storeSnapshot(row);
      }
    });

    table.on('rowClick', function (e, row) {
      selectRow(row);
    });

    table.on('rowSelected', function (row) {
      selectedRow = row;
      updateRowToolbar();
    });

    table.on('rowDeselected', function (row) {
      if (selectedRow === row) {
        selectedRow = null;
        updateRowToolbar();
      }
    });

    loadData();
  }

  btnApplyRow.addEventListener('click', function () {
    const row = getSelectedOrWarn();
    if (row) saveRow(row);
  });

  btnCancelRow.addEventListener('click', function () {
    const row = getSelectedOrWarn();
    if (row) cancelRow(row);
  });

  btnReloadRow.addEventListener('click', function () {
    const row = getSelectedOrWarn();
    if (row) reloadRowFromServer(row);
  });

  btnRefresh.addEventListener('click', loadData);
  btnAdd.addEventListener('click', addEmptyRow);
  btnSaveAll.addEventListener('click', saveAllDirty);

  if (cfg.gridConfig.exportUrl) {
    btnExport.hidden = false;
    btnExport.addEventListener('click', function () {
      window.location.href = cfg.gridConfig.exportUrl;
    });
  }

  initTable();
})();
