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
  const sideDrawer = document.getElementById('zt-side-drawer');
  const panelColumns = document.getElementById('zt-panel-columns');
  const panelFilter = document.getElementById('zt-panel-filter');
  const columnsList = document.getElementById('zt-columns-list');
  const columnsSearch = document.getElementById('zt-columns-search');
  const btnColumnsShowAll = document.getElementById('zt-columns-show-all');
  const btnColumnsHideAll = document.getElementById('zt-columns-hide-all');
  const btnColumnsReset = document.getElementById('zt-columns-reset');
  const filterQuery = document.getElementById('zt-filter-query');
  const filterFieldsHint = document.getElementById('zt-filter-fields');
  const filterCount = document.getElementById('zt-filter-count');
  const footerFiltered = document.getElementById('footer-filtered');
  const btnFilterApply = document.getElementById('zt-filter-apply');
  const btnFilterReset = document.getElementById('zt-filter-reset');

  const dirtyRows = new Set();
  const pendingDeleteRows = new Set();
  const rowSnapshots = new Map();
  const columnDefaults = new Map();
  const autocompleteCache = {};
  const undoStack = [];
  let table = null;
  let selectedRow = null;
  let activeSidePanel = null;
  let activeFilterQuery = '';
  const DEBUG = localStorage.getItem('attendly_table_debug') === '1';

  function dbg() {
    if (!DEBUG) return;
    const args = Array.prototype.slice.call(arguments);
    args.unshift('[attendly-table]');
    console.log.apply(console, args);
  }

  function shouldSkipBlurCommit(target) {
    if (!target) return false;
    return !!(
      target.closest('.autocomplete-list') ||
      target.closest('.zt-cell-dropdown') ||
      target.closest('.zt-cell-clear')
    );
  }

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
    if (pendingDeleteRows.has(key)) return true;
    const snap = rowSnapshots.get(key);
    if (!snap) return false;
    return JSON.stringify(cleanRowData(row.getData())) !== JSON.stringify(snap);
  }

  function pendingChangeCount() {
    const keys = new Set(dirtyRows);
    pendingDeleteRows.forEach(function (k) { keys.add(k); });
    return keys.size;
  }

  function getRefFields() {
    const refs = [];
    (cfg.gridConfig.columns || []).forEach(function (col) {
      if (col.ref) refs.push(col.ref);
    });
    return refs;
  }

  function cleanupOrphanAutocompleteLists() {
    document.querySelectorAll('body > .autocomplete-list').forEach(function (el) {
      if (el.parentNode) el.parentNode.removeChild(el);
    });
  }

  function attachClearButton(wrap, input) {
    const clearBtn = document.createElement('button');
    clearBtn.type = 'button';
    clearBtn.className = 'zt-cell-clear';
    clearBtn.textContent = '×';
    clearBtn.title = 'Очистить';
    clearBtn.addEventListener('mousedown', function (e) {
      e.preventDefault();
      input.value = '';
      input.focus();
    });
    wrap.appendChild(clearBtn);
    return clearBtn;
  }

  function toDateTimeLocalValue(value) {
    if (!value) return '';
    const s = String(value).trim();
    const m = s.match(/^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})/);
    return m ? m[1] + 'T' + m[2] : s.replace(' ', 'T').substring(0, 16);
  }

  function fromDateTimeLocalValue(value) {
    if (!value) return '';
    return String(value).trim().replace('T', ' ');
  }

  function createDateTimeEditor() {
    return function (cell, onRendered, success, cancel) {
      const wrap = document.createElement('div');
      wrap.className = 'zt-cell-editor';
      wrap.addEventListener('mousedown', function (e) { e.stopPropagation(); });
      const input = document.createElement('input');
      input.type = 'datetime-local';
      input.value = toDateTimeLocalValue(cell.getValue());
      wrap.appendChild(input);
      attachClearButton(wrap, input);

      let closed = false;

      function finish() {
        if (closed) return;
        closed = true;
        success(fromDateTimeLocalValue(input.value));
      }

      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          finish();
        } else if (e.key === 'Escape') {
          closed = true;
          cancel();
        }
      });

      input.addEventListener('blur', function (e) {
        const related = e.relatedTarget;
        setTimeout(function () {
          if (closed) return;
          if (shouldSkipBlurCommit(related) || shouldSkipBlurCommit(document.activeElement)) {
            return;
          }
          finish();
        }, 150);
      });

      input.addEventListener('change', function () {
        finish();
      });

      onRendered(function () {
        input.focus();
        if (input.showPicker) {
          try { input.showPicker(); } catch (err) { /* ignore */ }
        }
      });

      return wrap;
    };
  }

  function createTextInputEditor() {
    return function (cell, onRendered, success, cancel) {
      const wrap = document.createElement('div');
      wrap.className = 'zt-cell-editor';
      wrap.addEventListener('mousedown', function (e) { e.stopPropagation(); });
      const input = document.createElement('input');
      input.type = 'text';
      input.value = cell.getValue() || '';
      wrap.appendChild(input);
      attachClearButton(wrap, input);

      let closed = false;

      function finish() {
        if (closed) return;
        closed = true;
        success(input.value);
      }

      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          finish();
        } else if (e.key === 'Escape') {
          closed = true;
          cancel();
        }
      });

      input.addEventListener('blur', function (e) {
        const related = e.relatedTarget;
        setTimeout(function () {
          if (closed) return;
          if (shouldSkipBlurCommit(related) || shouldSkipBlurCommit(document.activeElement)) {
            return;
          }
          finish();
        }, 150);
      });

      onRendered(function () {
        input.focus();
        input.select();
      });

      return wrap;
    };
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

  function attachDropdownButton(wrap, input, openList) {
    const dropBtn = document.createElement('button');
    dropBtn.type = 'button';
    dropBtn.className = 'zt-cell-dropdown';
    dropBtn.textContent = '▾';
    dropBtn.title = 'Открыть список';
    dropBtn.addEventListener('mousedown', function (e) {
      e.preventDefault();
      e.stopPropagation();
      input.focus();
      openList();
    });
    wrap.appendChild(dropBtn);
    return dropBtn;
  }

  function createAutocompleteEditor(field) {
    return function (cell, onRendered, success, cancel) {
      const wrap = document.createElement('div');
      wrap.className = 'zt-cell-editor zt-cell-editor--autocomplete';
      wrap.addEventListener('mousedown', function (e) { e.stopPropagation(); });
      const input = document.createElement('input');
      input.type = 'text';
      input.value = cell.getValue() || '';
      wrap.appendChild(input);
      attachClearButton(wrap, input);

      const listDiv = document.createElement('div');
      listDiv.className = 'autocomplete-list';
      listDiv.style.display = 'none';

      let closed = false;
      let openedAt = 0;
      let scrollParent = null;
      let scrollHandler = null;

      function positionList() {
        const rect = input.getBoundingClientRect();
        listDiv.style.position = 'fixed';
        listDiv.style.left = rect.left + 'px';
        listDiv.style.top = (rect.bottom + 2) + 'px';
        listDiv.style.width = Math.max(rect.width, 200) + 'px';
        listDiv.style.right = 'auto';
      }

      function bindScroll() {
        if (scrollHandler) return;
        const cellEl = cell.getElement();
        scrollParent = cellEl ? cellEl.closest('.tabulator-tableholder') : null;
        scrollHandler = function () { positionList(); };
        if (scrollParent) scrollParent.addEventListener('scroll', scrollHandler);
        window.addEventListener('resize', scrollHandler);
      }

      function unbindScroll() {
        if (scrollParent && scrollHandler) {
          scrollParent.removeEventListener('scroll', scrollHandler);
        }
        if (scrollHandler) {
          window.removeEventListener('resize', scrollHandler);
        }
        scrollHandler = null;
        scrollParent = null;
      }

      function removeList() {
        listDiv.style.display = 'none';
        unbindScroll();
        if (listDiv.parentNode === document.body) {
          listDiv.parentNode.removeChild(listDiv);
        }
      }

      function finishEdit(value) {
        if (closed) return;
        closed = true;
        removeList();
        dbg('finishEdit', field, value);
        success(value);
      }

      function filterItems(items, query) {
        const q = (query || '').trim().toLowerCase();
        if (!q) return items.slice();
        return items.filter(function (item) {
          return item.name.toLowerCase().includes(q);
        });
      }

      function openList(browseAll) {
        fetchAutocomplete(field, '').then(function () {
          const all = getCachedItems(field);
          const items = browseAll ? all.slice() : filterItems(all, input.value);
          showList(items, input.value, { browseAll: !!browseAll });
        });
      }

      function showList(items, inputValue, options) {
        options = options || {};
        listDiv.innerHTML = '';
        const value = (inputValue || '').trim();
        const valueLower = value.toLowerCase();
        const hasExactMatch = items.some(function (item) {
          return item.name === value || item.name.toLowerCase() === valueLower;
        });

        if (value) {
          const clearItem = document.createElement('div');
          clearItem.className = 'autocomplete-list-clear';
          clearItem.textContent = '× Очистить';
          clearItem.onmousedown = function (e) {
            e.preventDefault();
            finishEdit('');
          };
          listDiv.appendChild(clearItem);
        }

        if (value && !hasExactMatch && !options.browseAll) {
          const createItem = document.createElement('div');
          createItem.className = 'autocomplete-list-create';
          createItem.textContent = '➕ Создать «' + value + '»';
          createItem.onmousedown = function (e) {
            e.preventDefault();
            finishEdit(value);
          };
          listDiv.appendChild(createItem);
        }

        let selectedEl = null;
        items.forEach(function (item) {
          const div = document.createElement('div');
          div.textContent = item.name;
          if (value && (item.name === value || item.name.toLowerCase() === valueLower)) {
            div.className = 'is-selected';
            selectedEl = div;
          }
          div.onmousedown = function (e) {
            e.preventDefault();
            finishEdit(item.name);
          };
          listDiv.appendChild(div);
        });

        if (items.length || value) {
          if (listDiv.parentNode !== document.body) {
            document.body.appendChild(listDiv);
            listDiv.addEventListener('mousedown', function (ev) { ev.preventDefault(); });
          }
          positionList();
          bindScroll();
          listDiv.style.display = 'block';
          if (selectedEl) {
            selectedEl.scrollIntoView({ block: 'nearest' });
          }
        } else {
          listDiv.style.display = 'none';
        }
      }

      attachDropdownButton(wrap, input, function () { openList(true); });

      input.addEventListener('input', function () {
        showList(filterItems(getCachedItems(field), input.value), input.value);
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

      input.addEventListener('blur', function (e) {
        const related = e.relatedTarget;
        setTimeout(function () {
          if (closed) return;
          if (Date.now() - openedAt < 50) {
            dbg('blur: skip — just opened');
            return;
          }
          if (shouldSkipBlurCommit(related) || shouldSkipBlurCommit(document.activeElement)) {
            dbg('blur: skip — focus in list');
            return;
          }
          finishEdit(input.value);
        }, 150);
      });

      onRendered(function () {
        openedAt = Date.now();
        const cellEl = cell.getElement();
        if (cellEl) {
          cellEl.style.overflow = 'visible';
          cellEl.style.position = 'relative';
          cellEl.style.zIndex = '50';
        }
        setTimeout(function () {
          input.focus();
          if (input.value) {
            const len = input.value.length;
            input.setSelectionRange(len, len);
          } else {
            input.select();
          }
          openList(true);
        }, 0);
      });

      return wrap;
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
    const count = pendingChangeCount();
    const hasPending = count > 0;
    btnApply.disabled = !hasPending;
    btnCancel.disabled = !hasPending;
    btnUndo.disabled = undoStack.length === 0;
    btnApply.classList.toggle('is-active', hasPending);
    btnCancel.classList.toggle('is-active', hasPending);
    btnFilter.classList.toggle('is-active', activeSidePanel === 'filter' || !!activeFilterQuery);
    btnColumns.classList.toggle('is-active', activeSidePanel === 'columns');
    const parts = [];
    if (dirtyRows.size) parts.push('изменено: ' + dirtyRows.size);
    if (pendingDeleteRows.size) parts.push('к удалению: ' + pendingDeleteRows.size);
    footerDirty.textContent = parts.length ? parts.join(', ') : '';
  }

  function refreshRowStyle(row) {
    const el = row.getElement();
    if (!el) return;
    const key = row.getData()._key;
    const isDelete = pendingDeleteRows.has(key);
    const isDirty = dirtyRows.has(key) && !isDelete;
    const isSelected = row === selectedRow;
    el.classList.toggle('zt-row-pending-delete', isDelete);
    el.classList.toggle('zt-row-dirty', isDirty);
    el.classList.toggle('zt-row-selected', isSelected);
  }

  function pushUndo(action) {
    undoStack.push(action);
    if (undoStack.length > 50) undoStack.shift();
    updateToolbar();
  }

  function markDirty(row) {
    const key = row.getData()._key;
    if (pendingDeleteRows.has(key)) return;
    if (!dirtyRows.has(key)) {
      pushUndo({ type: 'row', key: key, snapshot: Object.assign({}, rowSnapshots.get(key)) });
    }
    dirtyRows.add(key);
    refreshRowStyle(row);
    updateToolbar();
  }

  function clearDirty(row) {
    const key = row.getData()._key;
    dirtyRows.delete(key);
    pendingDeleteRows.delete(key);
    storeSnapshot(row);
    refreshRowStyle(row);
    updateToolbar();
  }

  function onCellEditFinished(cell) {
    const row = cell.getRow();
    selectRow(row);
    if (pendingDeleteRows.has(row.getData()._key)) return;
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
    const key = data._key;
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
    delBtn.title = pendingDeleteRows.has(key) ? 'Снять пометку удаления' : 'Пометить к удалению';
    delBtn.textContent = '✕';
    delBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      toggleDeleteRow(row);
    });

    wrap.appendChild(adminBtn);
    wrap.appendChild(delBtn);
    return wrap;
  }

  function getRefFilterOptions(field, ref) {
    const names = new Set();
    getCachedItems(ref).forEach(function (item) {
      if (item.name) names.add(item.name);
    });
    if (table) {
      table.getData().forEach(function (row) {
        if (row[field]) names.add(row[field]);
      });
    }
    return Array.from(names).sort(function (a, b) {
      return a.localeCompare(b, 'ru');
    });
  }

  function getStatusFilterOptions() {
    const sv = cfg.gridConfig.statusValues || {};
    return Object.keys(sv).map(function (key) {
      return { value: key, label: sv[key] };
    });
  }

  function applyHeaderFilter(def, col) {
    if (!col.field || col.field === '_actions' || col.field === 'id') return;
    const HF = window.AttendlyHeaderFilters;
    if (!HF) return;

    if (col.editor === 'autocomplete' && col.ref) {
      const field = col.field;
      const ref = col.ref;
      def.headerFilter = HF.createMultiSelect(function () {
        return getRefFilterOptions(field, ref);
      });
      def.headerFilterFunc = HF.multiSelect;
      return;
    }

    if (col.editor === 'status') {
      def.headerFilter = HF.createMultiSelect(getStatusFilterOptions);
      def.headerFilterFunc = HF.multiSelect;
      return;
    }

    if (col.editor === 'list' && col.editorParams) {
      def.headerFilter = HF.createMultiSelect(function () {
        const vals = col.editorParams.values;
        if (Array.isArray(vals)) return vals;
        if (vals && typeof vals === 'object') {
          return Object.keys(vals).map(function (k) {
            return { value: k, label: vals[k] };
          });
        }
        return [];
      });
      def.headerFilterFunc = HF.multiSelect;
      return;
    }

    def.headerFilter = 'input';
    def.headerFilterFunc = HF.textContains;
    def.headerFilterLiveFilter = true;
    def.headerFilterPlaceholder = '…';
  }

  function columnTitleFormatter(title) {
    return function () {
      if (!title) return '';
      return '<span class="zt-col-label">' + title + '</span>';
    };
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

      if (col.title) {
        def.titleFormatter = columnTitleFormatter(col.title);
      }

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
      } else if (col.editor === 'datetime') {
        def.editor = createDateTimeEditor();
      } else if (col.editor === 'input' || col.editor === true) {
        def.editor = createTextInputEditor();
      } else {
        def.editor = false;
      }

      applyHeaderFilter(def, col);

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
    if (!row) return;
    if (selectedRow === row) return;
    const prev = selectedRow;
    selectedRow = row;
    if (prev) refreshRowStyle(prev);
    refreshRowStyle(row);
  }

  function rekeyRow(row, oldKey, saved) {
    saved._key = 'id:' + saved.id;
    dirtyRows.delete(oldKey);
    pendingDeleteRows.delete(oldKey);
    rowSnapshots.delete(oldKey);
    row.update(saved);
    rowSnapshots.set(saved._key, cleanRowData(saved));
    return saved._key;
  }

  async function loadData() {
    if (pendingChangeCount() && !confirm('Есть несохранённые изменения. Синхронизировать и потерять их?')) {
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
    pendingDeleteRows.clear();
    undoStack.length = 0;
    selectedRow = null;
    activeFilterQuery = '';
    if (filterQuery) filterQuery.value = '';
    const rows = prepareRows(payload.data || []);
    await table.setData(rows);
    table.clearFilter();
    snapshotAllRows();
    captureColumnDefaults();
    table.getRows().forEach(refreshRowStyle);
    updateFilterStats(table.getDataCount('active'));
    footerStats.textContent = 'Записей: ' + (payload.total ?? rows.length);
    setStatus('Синхронизировано', 'ok');
    setTimeout(function () { setStatus(''); }, 1500);
    updateToolbar();
  }

  async function saveRow(row) {
    const data = cleanRowData(row.getData());
    const oldKey = row.getData()._key;
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
    rekeyRow(row, oldKey, payload.row);
    clearDirty(row);
    row.reformat();
    return true;
  }

  async function executeDelete(row) {
    const data = row.getData();
    const key = data._key;

    if (!data.id) {
      dirtyRows.delete(key);
      pendingDeleteRows.delete(key);
      rowSnapshots.delete(key);
      if (selectedRow === row) selectedRow = null;
      row.delete();
      return true;
    }

    const res = await fetch(apiUrl(cfg.dataset + '/delete/'), {
      method: 'POST',
      headers: csrfHeaders(),
      body: JSON.stringify({ id: data.id }),
    });
    if (!res.ok) {
      const payload = await res.json();
      setStatus(payload.error || 'Ошибка удаления', 'error');
      return false;
    }
    dirtyRows.delete(key);
    pendingDeleteRows.delete(key);
    rowSnapshots.delete(key);
    if (selectedRow === row) selectedRow = null;
    row.delete();
    return true;
  }

  async function applyAllChanges() {
    const rows = table.getRows().filter(function (r) {
      const key = r.getData()._key;
      return dirtyRows.has(key) || pendingDeleteRows.has(key);
    });
    if (!rows.length) {
      setStatus('Нет несохранённых изменений');
      return;
    }

    const deleteCount = rows.filter(function (r) {
      return pendingDeleteRows.has(r.getData()._key);
    }).length;
    if (deleteCount && !confirm('Применить изменения? Будет удалено записей: ' + deleteCount)) {
      return;
    }

    for (const row of rows) {
      const key = row.getData()._key;
      let ok;
      if (pendingDeleteRows.has(key)) {
        ok = await executeDelete(row);
      } else {
        ok = await saveRow(row);
      }
      if (!ok) return;
    }

    undoStack.length = 0;
    updateToolbar();
    setStatus('Изменения применены', 'ok');
    setTimeout(function () { setStatus(''); }, 2000);
  }

  function cancelRow(row) {
    const data = row.getData();
    const key = data._key;
    const snap = rowSnapshots.get(key);

    if (pendingDeleteRows.has(key)) {
      pendingDeleteRows.delete(key);
      if (snap && rowHasChanges(row)) {
        dirtyRows.add(key);
      } else {
        dirtyRows.delete(key);
      }
      refreshRowStyle(row);
      row.reformat();
      updateToolbar();
      return;
    }

    if (!data.id) {
      dirtyRows.delete(key);
      pendingDeleteRows.delete(key);
      rowSnapshots.delete(key);
      if (selectedRow === row) selectedRow = null;
      row.delete();
      updateToolbar();
      return;
    }

    if (snap) row.update(Object.assign({}, snap, { _key: key }));
    clearDirty(row);
    row.reformat();
  }

  function cancelAllChanges() {
    if (!pendingChangeCount()) return;
    if (pendingChangeCount() > 1 && !confirm('Отменить все несохранённые изменения?')) {
      return;
    }
    const keys = new Set(dirtyRows);
    pendingDeleteRows.forEach(function (k) { keys.add(k); });
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
        pendingDeleteRows.delete(action.key);
        rowSnapshots.delete(action.key);
        if (selectedRow === row) selectedRow = null;
        row.delete();
      } else {
        row.update(Object.assign({}, action.snapshot, { _key: action.key }));
        clearDirty(row);
        row.reformat();
      }
    } else if (action.type === 'add') {
      const row = findRowByKey(action.key);
      if (row) cancelRow(row);
    } else if (action.type === 'delete') {
      const row = findRowByKey(action.key);
      if (row) {
        pendingDeleteRows.delete(action.key);
        dirtyRows.delete(action.key);
        refreshRowStyle(row);
        row.reformat();
      }
    }
    updateToolbar();
    setStatus('Действие отменено');
    setTimeout(function () { setStatus(''); }, 1500);
  }

  function toggleDeleteRow(row) {
    const key = row.getData()._key;

    if (pendingDeleteRows.has(key)) {
      pendingDeleteRows.delete(key);
      dirtyRows.delete(key);
      refreshRowStyle(row);
      row.reformat();
      updateToolbar();
      return;
    }

    if (!dirtyRows.has(key)) {
      pushUndo({ type: 'delete', key: key, snapshot: Object.assign({}, rowSnapshots.get(key)) });
      if (!rowSnapshots.has(key)) storeSnapshot(row);
    }

    pendingDeleteRows.add(key);
    dirtyRows.add(key);
    refreshRowStyle(row);
    row.reformat();
    updateToolbar();
    setStatus('Строка помечена к удалению — нажмите «Применить»');
    setTimeout(function () { setStatus(''); }, 2500);
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

  function captureColumnDefaults() {
    columnDefaults.clear();
    table.getColumns().forEach(function (col) {
      const field = col.getField();
      if (!field) return;
      columnDefaults.set(field, {
        visible: col.getDefinition().visible !== false,
        title: col.getDefinition().title || field,
      });
    });
  }

  function closeSidePanel() {
    activeSidePanel = null;
    sideDrawer.hidden = true;
    panelColumns.hidden = true;
    panelFilter.hidden = true;
    updateToolbar();
  }

  function openSidePanel(name) {
    if (activeSidePanel === name) {
      closeSidePanel();
      return;
    }
    activeSidePanel = name;
    sideDrawer.hidden = false;
    panelColumns.hidden = name !== 'columns';
    panelFilter.hidden = name !== 'filter';
    if (name === 'columns') buildColumnsPanel();
    if (name === 'filter') initFilterPanel();
    updateToolbar();
  }

  function toggleColumnsPanel() {
    openSidePanel('columns');
  }

  function toggleFilterPanel() {
    openSidePanel('filter');
  }

  function initFilterPanel() {
    if (!filterQuery) return;
    if (!filterQuery.value && cfg.gridConfig.filterExampleWhere) {
      filterQuery.placeholder = cfg.gridConfig.filterExampleWhere;
    }
    if (filterFieldsHint && cfg.gridConfig.filterFields) {
      filterFieldsHint.textContent = 'Поля: ' + cfg.gridConfig.filterFields.join(', ');
    }
    updateFilterStats(table ? table.getDataCount('active') : 0);
  }

  function resolveFilterField(data, field) {
    return data[field];
  }

  function updateFilterStats(visibleCount) {
    const total = table ? table.getDataCount() : 0;
    const text = 'Найдено: ' + visibleCount;
    if (filterCount) filterCount.textContent = text;
    if (footerFiltered) {
      footerFiltered.textContent = activeFilterQuery ? text + ' / ' + total : '';
    }
  }

  function normalizeFilterQuery(query) {
    let q = query;
    const labels = cfg.gridConfig.statusValues || {};
    Object.keys(labels).forEach(function (key) {
      const label = labels[key];
      q = q.split("'" + label + "'").join("'" + key + "'");
      q = q.split('"' + label + '"').join("'" + key + "'");
    });
    return q;
  }

  function applyQueryFilter() {
    const conditions = filterQuery ? filterQuery.value.trim() : '';
    activeFilterQuery = conditions;
    if (!conditions) {
      table.clearFilter();
      updateFilterStats(table.getDataCount());
      updateToolbar();
      setStatus('Фильтр сброшен');
      setTimeout(function () { setStatus(''); }, 1200);
      return;
    }
    const compiled = window.AttendlyQueryFilter.compile(
      normalizeFilterQuery(conditions),
      resolveFilterField
    );
    if (!compiled) {
      setStatus('Не удалось разобрать запрос. Используйте WHERE …', 'error');
      return;
    }
    table.setFilter(function (data) {
      return compiled(data);
    });
    updateFilterStats(table.getDataCount('active'));
    updateToolbar();
    setStatus('Фильтр применён', 'ok');
    setTimeout(function () { setStatus(''); }, 1500);
  }

  function resetQueryFilter() {
    activeFilterQuery = '';
    if (filterQuery) filterQuery.value = '';
    if (table) {
      table.clearFilter();
      updateFilterStats(table.getDataCount());
    }
    updateToolbar();
    setStatus('Фильтр сброшен');
    setTimeout(function () { setStatus(''); }, 1200);
  }

  function buildColumnsPanel() {
    if (!columnsList || !table) return;
    const term = (columnsSearch && columnsSearch.value || '').toLowerCase();
    columnsList.innerHTML = '';
    table.getColumns().forEach(function (col) {
      const field = col.getField();
      if (!field || field === '_actions') return;
      const title = col.getDefinition().title || field;
      if (term && title.toLowerCase().indexOf(term) === -1 && field.toLowerCase().indexOf(term) === -1) {
        return;
      }
      const item = document.createElement('div');
      item.className = 'zt-col-item';
      const eye = document.createElement('button');
      eye.type = 'button';
      eye.className = 'zt-col-eye' + (col.isVisible() ? ' is-visible' : ' is-hidden');
      eye.title = col.isVisible() ? 'Скрыть колонку' : 'Показать колонку';
      eye.innerHTML = col.isVisible()
        ? '<svg viewBox="0 0 24 24"><path d="M12 5C7 5 2.7 8.1 1 12c1.7 3.9 6 7 11 7s9.3-3.1 11-7c-1.7-3.9-6-7-11-7zm0 11a4 4 0 1 1 0-8 4 4 0 0 1 0 8z"/></svg>'
        : '<svg viewBox="0 0 24 24"><path d="M12 6c3 0 5.6 1.6 7.4 4-1 1.4-2.2 2.5-3.6 3.2l1.5 1.5c2-1.1 3.6-2.7 4.8-4.7C19.3 7.1 16 4 12 4c-1 0-2 .2-2.9.5l1.6 1.6C11.4 6 11.7 6 12 6zM2.7 2.7 1.3 4.1l2.2 2.2C2.7 7.7 1.7 9.7 1 12c1.7 3.9 6 7 11 7 1.6 0 3.1-.3 4.5-.9l2.7 2.7 1.4-1.4L2.7 2.7zM7.5 9.9l1.6 1.6c.1-.3.2-.6.2-1 0-1.1.9-2 2-2 .4 0 .7.1 1 .2l1.5 1.5c-.3-.8-1-1.4-1.9-1.4-1.1 0-2 .9-2 2 0 .2 0 .4.1.5z"/></svg>';
      eye.addEventListener('click', function (e) {
        e.stopPropagation();
        if (col.isVisible()) col.hide(); else col.show();
        buildColumnsPanel();
      });
      const name = document.createElement('span');
      name.className = 'zt-col-name';
      name.textContent = title;
      item.appendChild(eye);
      item.appendChild(name);
      columnsList.appendChild(item);
    });
  }

  function setAllColumnsVisible(visible) {
    table.getColumns().forEach(function (col) {
      const field = col.getField();
      if (!field || field === '_actions') return;
      if (visible) col.show(); else col.hide();
    });
    buildColumnsPanel();
  }

  function resetColumnsVisibility() {
    table.getColumns().forEach(function (col) {
      const field = col.getField();
      if (!field) return;
      const def = columnDefaults.get(field);
      if (!def) return;
      if (def.visible) col.show(); else col.hide();
    });
    buildColumnsPanel();
  }

  function resetTableLayout() {
    resetColumnsVisibility();
    table.setLayout('fitDataStretch');
    setStatus('Настройки сброшены');
    setTimeout(function () { setStatus(''); }, 1500);
  }

  function initTable() {
    table = new Tabulator('#attendly-table', {
      data: [],
      layout: 'fitDataStretch',
      height: '100%',
      rowHeight: 32,
      virtualDom: false,
      placeholder: 'Нет данных',
      selectable: false,
      editTriggerEvent: 'click',
      columns: buildColumns(),
      rowFormatter: function (row) { refreshRowStyle(row); },
    });

    table.on('cellEditing', function (cell) {
      dbg('cellEditing', cell.getField(), cell.getRow().getPosition());
      cleanupOrphanAutocompleteLists();
      if (window.AttendlyHeaderFilters && window.AttendlyHeaderFilters.closeActivePopup) {
        window.AttendlyHeaderFilters.closeActivePopup();
      }
      const row = cell.getRow();
      selectRow(row);
      if (!dirtyRows.has(row.getData()._key) && !pendingDeleteRows.has(row.getData()._key)) {
        storeSnapshot(row);
      }
    });

    table.on('cellEdited', function (cell) {
      onCellEditFinished(cell);
    });

    table.on('cellClick', function (e, cell) {
      if (cell.getField() === '_actions') return;
      if (e.target.closest('.zt-row-btn')) return;
      const colDef = cell.getColumn().getDefinition();
      if (!colDef.editor) {
        selectRow(cell.getRow());
      }
    });

    table.on('dataFiltered', function (filters, rows) {
      updateFilterStats(rows.length);
    });

    loadData();
  }

  btnFilter.addEventListener('click', function (e) {
    e.stopPropagation();
    toggleFilterPanel();
  });
  btnColumns.addEventListener('click', function (e) {
    e.stopPropagation();
    toggleColumnsPanel();
  });
  sideDrawer.addEventListener('click', function (e) {
    e.stopPropagation();
  });
  sideDrawer.querySelectorAll('[data-close-drawer]').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      closeSidePanel();
    });
  });
  if (columnsSearch) {
    columnsSearch.addEventListener('input', buildColumnsPanel);
  }
  btnColumnsShowAll.addEventListener('click', function () { setAllColumnsVisible(true); });
  btnColumnsHideAll.addEventListener('click', function () { setAllColumnsVisible(false); });
  btnColumnsReset.addEventListener('click', resetColumnsVisibility);
  btnFilterApply.addEventListener('click', applyQueryFilter);
  btnFilterReset.addEventListener('click', resetQueryFilter);
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
    if (!activeSidePanel) return;
    if (sideDrawer.contains(e.target)) return;
    if (btnColumns.contains(e.target) || btnFilter.contains(e.target)) return;
    closeSidePanel();
  });

  closeSidePanel();
  initTable();
})();
