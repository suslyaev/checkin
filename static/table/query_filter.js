/* Простой парсер WHERE для клиентской фильтрации (ZenTable-подобный SELECT). */
window.AttendlyQueryFilter = (function () {
  function extractWhere(query) {
    const q = (query || '').trim();
    if (!q) return '';

    const selectMatch = q.match(/\bwhere\b([\s\S]+)$/i);
    if (selectMatch) {
      let where = selectMatch[1].trim();
      where = where.replace(/\s+\b(order\s+by|limit|offset)\b[\s\S]*$/i, '');
      return where.trim();
    }

    if (/^(and|or|\w+\s*(=|!=|<>|like|not\s+like|>|<|>=|<=))/i.test(q)) {
      return q;
    }
    return '';
  }

  function unquote(value) {
    const v = (value || '').trim();
    if ((v.startsWith("'") && v.endsWith("'")) || (v.startsWith('"') && v.endsWith('"'))) {
      return v.slice(1, -1);
    }
    return v;
  }

  function splitTopLevel(text, sepRegex) {
    const parts = [];
    let depth = 0;
    let current = '';
    const upper = text.toUpperCase();
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (ch === '(') depth++;
      if (ch === ')') depth = Math.max(0, depth - 1);
      if (depth === 0) {
        const slice = upper.slice(i);
        const m = slice.match(sepRegex);
        if (m && m.index === 0) {
          if (current.trim()) parts.push(current.trim());
          current = '';
          i += m[0].length - 1;
          continue;
        }
      }
      current += ch;
    }
    if (current.trim()) parts.push(current.trim());
    return parts;
  }

  function parseCondition(cond) {
    let c = cond.trim();
    if (c.startsWith('(') && c.endsWith(')')) {
      c = c.slice(1, -1).trim();
    }

    const nullMatch = c.match(/^(\w+)\s+is\s+(not\s+)?null$/i);
    if (nullMatch) {
      return {
        field: nullMatch[1],
        op: nullMatch[2] ? 'isnotnull' : 'isnull',
        value: null,
      };
    }

    const likeMatch = c.match(/^(\w+)\s+(not\s+)?like\s+(.+)$/i);
    if (likeMatch) {
      return {
        field: likeMatch[1],
        op: likeMatch[2] ? 'notlike' : 'like',
        value: unquote(likeMatch[3]),
      };
    }

    const cmpMatch = c.match(/^(\w+)\s*(=|!=|<>|>=|<=|>|<)\s*(.+)$/i);
    if (cmpMatch) {
      let op = cmpMatch[2].toLowerCase();
      if (op === '<>') op = '!=';
      return {
        field: cmpMatch[1],
        op: op,
        value: unquote(cmpMatch[3]),
      };
    }

    return null;
  }

  function likeMatch(value, pattern) {
    const escaped = pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp('^' + escaped.replace(/%/g, '.*').replace(/_/g, '.') + '$', 'i');
    return regex.test(value);
  }

  function compareValues(left, op, right) {
    const l = left === null || left === undefined ? '' : String(left);
    const r = right === null || right === undefined ? '' : String(right);

    if (op === 'like') return likeMatch(l, r);
    if (op === 'notlike') return !likeMatch(l, r);
    if (op === 'isnull') return l === '';
    if (op === 'isnotnull') return l !== '';

    const ln = parseFloat(l);
    const rn = parseFloat(r);
    const bothNumeric = l !== '' && r !== '' && !isNaN(ln) && !isNaN(rn);

    if (bothNumeric) {
      if (op === '=') return ln === rn;
      if (op === '!=') return ln !== rn;
      if (op === '>') return ln > rn;
      if (op === '<') return ln < rn;
      if (op === '>=') return ln >= rn;
      if (op === '<=') return ln <= rn;
    }

    const lc = l.toLowerCase();
    const rc = r.toLowerCase();
    if (op === '=') return lc === rc;
    if (op === '!=') return lc !== rc;
    if (op === '>') return lc > rc;
    if (op === '<') return lc < rc;
    if (op === '>=') return lc >= rc;
    if (op === '<=') return lc <= rc;
    return false;
  }

  function evalGroup(data, expr, resolveField) {
    const orParts = splitTopLevel(expr, /^\s+OR\s+/i);
    if (orParts.length > 1) {
      return orParts.some(function (part) { return evalGroup(data, part, resolveField); });
    }

    const andParts = splitTopLevel(expr, /^\s+AND\s+/i);
    return andParts.every(function (part) {
      if (part.includes(' AND ') || part.includes(' OR ') || (part.startsWith('(') && part.endsWith(')'))) {
        return evalGroup(data, part, resolveField);
      }
      const cond = parseCondition(part);
      if (!cond) return true;
      const raw = resolveField ? resolveField(data, cond.field) : data[cond.field];
      return compareValues(raw, cond.op, cond.value);
    });
  }

  function compile(query, resolveField) {
    const where = extractWhere(query);
    if (!where) return null;
    return function (data) {
      try {
        return evalGroup(data, where, resolveField);
      } catch (e) {
        console.error('Filter error', e);
        return true;
      }
    };
  }

  return { extractWhere, compile };
})();
