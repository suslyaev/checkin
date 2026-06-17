/* Фильтры в заголовках колонок Tabulator */
window.AttendlyHeaderFilters = (function () {
  let activePopupClose = null;

  function detachPopupClose() {
    if (activePopupClose) {
      document.removeEventListener('click', activePopupClose);
      activePopupClose = null;
    }
  }

  function attachPopupClose(popup, trigger, closeFn) {
    detachPopupClose();
    activePopupClose = function (e) {
      if (popup.contains(e.target) || trigger.contains(e.target)) return;
      closeFn();
      detachPopupClose();
    };
    setTimeout(function () {
      document.addEventListener('click', activePopupClose);
    }, 0);
  }

  function textContains(headerValue, rowValue) {
    if (headerValue === null || headerValue === undefined || headerValue === '') return true;
    return String(rowValue || '').toLowerCase().includes(String(headerValue).toLowerCase());
  }

  function multiSelect(headerValue, rowValue) {
    if (!headerValue || !headerValue.length) return true;
    const v = rowValue === null || rowValue === undefined ? '' : String(rowValue);
    return headerValue.indexOf(v) !== -1;
  }

  function normalizeOptions(options) {
    return (options || []).map(function (opt) {
      if (opt && typeof opt === 'object') {
        return { value: String(opt.value), label: String(opt.label || opt.value) };
      }
      return { value: String(opt), label: String(opt) };
    });
  }

  function createMultiSelect(getOptionsFn) {
    return function (cell, onRendered, success) {
      const container = document.createElement('div');
      container.className = 'zt-hf-ms';

      const trigger = document.createElement('button');
      trigger.type = 'button';
      trigger.className = 'zt-hf-ms-trigger';

      let selected = new Set();
      const initial = cell.getValue();
      if (Array.isArray(initial)) {
        initial.forEach(function (v) { selected.add(String(v)); });
      }

      function optionValues(options) {
        return options.map(function (o) { return o.value; });
      }

      function syncSuccess(options) {
        const values = optionValues(options);
        const arr = values.filter(function (v) { return selected.has(v); });
        if (!arr.length || arr.length === values.length) {
          success('');
        } else {
          success(arr);
        }
      }

      function updateTrigger(options) {
        const values = optionValues(options);
        const n = values.filter(function (v) { return selected.has(v); }).length;
        if (!n || n === values.length) {
          trigger.textContent = 'Все';
          trigger.classList.remove('is-partial');
        } else {
          trigger.textContent = n + ' / ' + values.length;
          trigger.classList.add('is-partial');
        }
      }

      let popup = null;

      function closePopup() {
        detachPopupClose();
        if (popup && popup.parentNode) popup.parentNode.removeChild(popup);
        popup = null;
      }

      function openPopup() {
        closePopup();
        const options = normalizeOptions(getOptionsFn());
        popup = document.createElement('div');
        popup.className = 'zt-hf-ms-popup';

        const tools = document.createElement('div');
        tools.className = 'zt-hf-ms-tools';

        const btnAll = document.createElement('button');
        btnAll.type = 'button';
        btnAll.textContent = 'Все';
        btnAll.addEventListener('click', function (e) {
          e.stopPropagation();
          selected = new Set(optionValues(options));
          syncSuccess(options);
          updateTrigger(options);
          closePopup();
        });

        const btnClear = document.createElement('button');
        btnClear.type = 'button';
        btnClear.textContent = 'Сбросить';
        btnClear.addEventListener('click', function (e) {
          e.stopPropagation();
          selected.clear();
          syncSuccess(options);
          updateTrigger(options);
          closePopup();
        });

        tools.appendChild(btnAll);
        tools.appendChild(btnClear);
        popup.appendChild(tools);

        const list = document.createElement('div');
        list.className = 'zt-hf-ms-list';
        options.forEach(function (opt) {
          const row = document.createElement('label');
          row.className = 'zt-hf-ms-item';
          const cb = document.createElement('input');
          cb.type = 'checkbox';
          cb.checked = selected.has(opt.value);
          cb.addEventListener('change', function () {
            if (cb.checked) selected.add(opt.value);
            else selected.delete(opt.value);
            syncSuccess(options);
            updateTrigger(options);
          });
          row.appendChild(cb);
          row.appendChild(document.createTextNode(opt.label));
          list.appendChild(row);
        });
        popup.appendChild(list);

        document.body.appendChild(popup);
        const rect = trigger.getBoundingClientRect();
        popup.style.left = rect.left + 'px';
        popup.style.top = (rect.bottom + 2) + 'px';
        popup.style.minWidth = Math.max(rect.width, 180) + 'px';

        popup.addEventListener('click', function (e) { e.stopPropagation(); });
        attachPopupClose(popup, trigger, closePopup);
      }

      trigger.addEventListener('click', function (e) {
        e.stopPropagation();
        if (popup) closePopup();
        else openPopup();
      });

      onRendered(function () {
        const options = normalizeOptions(getOptionsFn());
        if (!initial || (Array.isArray(initial) && !initial.length)) {
          selected = new Set(optionValues(options));
        }
        updateTrigger(options);
      });

      container.appendChild(trigger);
      return container;
    };
  }

  function closeActivePopup() {
    detachPopupClose();
    document.querySelectorAll('.zt-hf-ms-popup').forEach(function (el) {
      if (el.parentNode) el.parentNode.removeChild(el);
    });
  }

  return {
    textContains: textContains,
    multiSelect: multiSelect,
    createMultiSelect: createMultiSelect,
    closeActivePopup: closeActivePopup,
  };
})();
