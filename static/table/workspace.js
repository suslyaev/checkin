(function () {
  const cfg = window.ATTENDLY_TABLE;
  if (!cfg) return;

  const statusBar = document.getElementById('status-bar');
  const footerStats = document.getElementById('footer-stats');
  const btnRefresh = document.getElementById('btn-refresh');
  const btnAdd = document.getElementById('btn-add-row');
  const btnSaveAll = document.getElementById('btn-save-all');
  const btnExport = document.getElementById('btn-export');

  const dirtyRows = new Set();
  const newRows = new Set();
  let table = null;
  const autocompleteCache = {};

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

  async function fetchAutocomplete(field, term) {
    const key = field + ':' + (term || '');
    if (autocompleteCache[key]) return autocompleteCache[key];
    const url = apiUrl('autocomplete/' + field + '/') + (term ? '?term=' + encodeURIComponent(term) : '');
    const res = await fetch(url);
    const data = await res.json();
    autocompleteCache[key] = data.results || [];
    return autocompleteCache[key];
  }

  function makeAutocompleteEditor(field) {
    return function (cell, onRendered, success, cancel) {
      const input = document.createElement('input');
      input.type = 'text';
      input.value = cell.getValue() || '';
      input.style.width = '100%';
      input.style.boxSizing = 'border-box';
      input.style.padding = '4px 6px';
      input.style.border = 'none';
      input.style.outline = 'none';

      const listDiv = document.createElement('div');
      listDiv.className = 'autocomplete-list';
      listDiv.style.display = 'none';

      let highlight = -1;

      function renderList(items) {
        listDiv.innerHTML = '';
        if (!items.length) {
          listDiv.style.display = 'none';
          return;
        }
        items.forEach((item, idx) => {
          const div = document.createElement('div');
          div.textContent = item.name;
          div.dataset.value = item.name;
          if (idx === highlight) div.classList.add('is-highlighted');
          div.addEventListener('mousedown', function (e) {
            e.preventDefault();
            success(item.name);
          });
          listDiv.appendChild(div);
        });
        listDiv.style.display = 'block';
      }

      async function updateList(term) {
        const items = await fetchAutocomplete(field, term);
        const filtered = term
          ? items.filter((i) => i.name.toLowerCase().includes(term.toLowerCase()))
          : items;
        highlight = -1;
        renderList(filtered);
      }

      input.addEventListener('input', function () {
        updateList(input.value.trim());
      });

      input.addEventListener('keydown', function (e) {
        const items = listDiv.querySelectorAll('div');
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          highlight = Math.min(highlight + 1, items.length - 1);
          items.forEach((el, i) => el.classList.toggle('is-highlighted', i === highlight));
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          highlight = Math.max(highlight - 1, 0);
          items.forEach((el, i) => el.classList.toggle('is-highlighted', i === highlight));
        } else if (e.key === 'Enter') {
          e.preventDefault();
          if (highlight >= 0 && items[highlight]) {
            success(items[highlight].dataset.value);
          } else {
            success(input.value);
          }
        } else if (e.key === 'Escape') {
          cancel();
        }
      });

      onRendered(function () {
        input.focus();
        input.select();
        document.body.appendChild(listDiv);
        const rect = input.getBoundingClientRect();
        listDiv.style.left = rect.left + 'px';
        listDiv.style.top = rect.bottom + window.scrollY + 'px';
        listDiv.style.minWidth = rect.width + 'px';
        updateList(input.value.trim());
      });

      input.addEventListener('blur', function () {
        setTimeout(function () {
          if (listDiv.parentNode) listDiv.parentNode.removeChild(listDiv);
          success(input.value);
        }, 150);
      });

      return input;
    };
  }

  function actionsFormatter(cell) {
    const row = cell.getRow();
    const data = row.getData();
    const wrap = document.createElement('div');
    wrap.className = 'zt-row-actions';

    const saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = 'zt-row-btn' + (dirtyRows.has(data._key) ? ' is-dirty' : '');
    saveBtn.title = 'Сохранить';
    saveBtn.textContent = '💾';
    saveBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      saveRow(row);
    });

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

    wrap.appendChild(saveBtn);
    wrap.appendChild(adminBtn);
    wrap.appendChild(delBtn);
    return wrap;
  }

  function markDirty(row) {
    const data = row.getData();
    dirtyRows.add(data._key);
    row.reformat();
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
        def.editor = makeAutocompleteEditor(col.ref);
      } else if (col.editor === 'list' && col.editorParams) {
        def.editor = 'list';
        def.editorParams = col.editorParams;
      } else if (col.editor === 'input' || col.editor === true) {
        def.editor = 'input';
      } else {
        def.editor = false;
      }

      if (def.editor && def.editor !== false) {
        def.cellEdited = function () {
          markDirty(this.getRow());
        };
      }

      return def;
    });
  }

  function rowKey(data) {
    return data.id ? 'id:' + data.id : data._key;
  }

  function prepareRows(rows) {
    return rows.map(function (r, i) {
      const copy = Object.assign({}, r);
      copy._key = copy.id ? 'id:' + copy.id : 'new:' + i;
      return copy;
    });
  }

  async function loadData() {
    setStatus('Загрузка…');
    const res = await fetch(apiUrl(cfg.dataset + '/'));
    const payload = await res.json();
    if (!res.ok) {
      setStatus(payload.error || 'Ошибка загрузки', 'error');
      return;
    }
    dirtyRows.clear();
    newRows.clear();
    const rows = prepareRows(payload.data || []);
    table.setData(rows);
    footerStats.textContent = 'Записей: ' + (payload.total ?? rows.length);
    setStatus('');
  }

  async function saveRow(row) {
    const data = Object.assign({}, row.getData());
    const key = data._key;
    delete data._key;
    delete data._actions;

    setStatus('Сохранение…');
    const res = await fetch(apiUrl(cfg.dataset + '/save/'), {
      method: 'POST',
      headers: csrfHeaders(),
      body: JSON.stringify(data),
    });
    const payload = await res.json();
    if (!res.ok) {
      setStatus(payload.error || 'Ошибка сохранения', 'error');
      return;
    }

    dirtyRows.delete(key);
    newRows.delete(key);
    const saved = payload.row;
    saved._key = 'id:' + saved.id;
    row.update(saved);
    row.reformat();
    setStatus('Сохранено', 'ok');
    setTimeout(function () { setStatus(''); }, 2000);
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
    const payload = await res.json();
    if (!res.ok) {
      setStatus(payload.error || 'Ошибка удаления', 'error');
      return;
    }
    dirtyRows.delete(data._key);
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
      await saveRow(row);
    }
  }

  function addEmptyRow() {
    const empty = { _key: 'new:' + Date.now() };
    cfg.gridConfig.columns.forEach(function (col) {
      if (col.field && col.field !== '_actions' && col.field !== 'id') {
        empty[col.field] = '';
      }
    });
    newRows.add(empty._key);
    dirtyRows.add(empty._key);
    table.addRow(empty, true);
  }

  function initTable() {
    table = new Tabulator('#attendly-table', {
      data: [],
      layout: 'fitDataStretch',
      height: '100%',
      placeholder: 'Нет данных',
      selectable: true,
      columns: buildColumns(),
      rowFormatter: function (row) {
        const el = row.getElement();
        if (dirtyRows.has(row.getData()._key)) {
          el.style.backgroundColor = '#fff8e6';
        }
      },
    });
    loadData();
  }

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
