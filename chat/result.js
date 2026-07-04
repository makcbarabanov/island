(function () {
  'use strict';

  const STORAGE_KEY = 'marathon-chat-labels-v2';
  const TYPE_LABELS = { simple: 'простое', manifest: 'манифест', report: 'отчёт' };

  let DATA = null;
  let labels = {};
  let comments = {};
  let filtered = [];
  let sortCol = 'date';
  let sortDir = 'asc';

  const OPINION_ORDER = { manifest: 0, report: 1, simple: 2 };

  function loadLocal() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const o = JSON.parse(raw);
      labels = o.labels || {};
      comments = o.comments || {};
    } catch (_) { /* ignore */ }
  }

  function saveLocal() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ labels, comments, savedAt: new Date().toISOString() }));
    updateSaveStatus('Локально сохранено', 'status-ok');
  }

  async function loadServerLabels() {
    try {
      const r = await fetch('/api/chat-labels');
      if (!r.ok) return;
      const o = await r.json();
      if (o.labels) labels = Object.assign({}, o.labels, labels);
      if (o.comments) comments = Object.assign({}, o.comments, comments);
    } catch (_) { /* offline */ }
  }

  async function saveServer() {
    const body = {
      version: 1,
      updated_at: new Date().toISOString(),
      labels,
      comments,
    };
    const r = await fetch('/api/chat-labels', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    saveLocal();
    updateSaveStatus('Сохранено на сервер (chat/labels.json)', 'status-ok');
  }

  function downloadJson() {
    const body = {
      version: 1,
      exported_at: new Date().toISOString(),
      labels,
      comments,
      stats: countStats(),
    };
    const blob = new Blob([JSON.stringify(body, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'marathon-labels-' + new Date().toISOString().slice(0, 10) + '.json';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function importJson(file) {
    const reader = new FileReader();
    reader.onload = function () {
      try {
        const o = JSON.parse(reader.result);
        labels = Object.assign({}, labels, o.labels || {});
        comments = Object.assign({}, comments, o.comments || {});
        saveLocal();
        applyFilters();
        updateSaveStatus('Импорт выполнен', 'status-ok');
      } catch (e) {
        updateSaveStatus('Ошибка импорта: ' + e.message, 'status-err');
      }
    };
    reader.readAsText(file, 'utf-8');
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function getLabel(id) {
    return labels[String(id)] || null;
  }

  function setLabel(id, type) {
    const key = String(id);
    if (!type) delete labels[key];
    else labels[key] = type;
    saveLocal();
    updateStats();
    if (sortCol === 'simple' || sortCol === 'report' || sortCol === 'manifest') {
      sortFiltered();
      renderTable();
    } else {
      refreshRowStyles(id);
    }
  }

  function setComment(id, text) {
    const key = String(id);
    const t = (text || '').trim();
    if (!t) delete comments[key];
    else comments[key] = t;
    saveLocal();
  }

  function matchesFilters(msg) {
    const q = document.getElementById('search').value.trim().toLowerCase();
    const author = document.getElementById('filter-author').value;
    const month = document.getElementById('filter-month').value;
    const opinion = document.getElementById('filter-opinion').value;
    const manual = document.getElementById('filter-manual').value;
    const onlyUnlabeled = document.getElementById('only-unlabeled').checked;
    const onlyMismatch = document.getElementById('only-mismatch').checked;

    if (author && msg.author !== author) return false;
    if (month && msg.monthKey !== month) return false;
    if (opinion && msg.opinion !== opinion) return false;
    const lab = getLabel(msg.id);
    if (manual === '__none' && lab) return false;
    if (manual && manual !== '__none' && lab !== manual) return false;
    if (onlyUnlabeled && lab) return false;
    if (onlyMismatch && (!lab || lab === msg.opinion)) return false;
    if (q) {
      const hay = (msg.datetime + ' ' + msg.author + ' ' + msg.text).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }

  function applyFilters() {
    filtered = DATA.messages.filter(matchesFilters);
    sortFiltered();
    renderTable();
    updateStats();
  }

  function labelRank(msgId, type) {
    const lab = getLabel(msgId);
    if (lab === type) return 0;
    if (!lab) return 1;
    return 2;
  }

  function sortFiltered() {
    if (!sortCol) return;
    const dir = sortDir === 'asc' ? 1 : -1;
    filtered.sort(function (a, b) {
      let cmp = 0;
      if (sortCol === 'date') {
        cmp = (a.date + ' ' + a.datetime).localeCompare(b.date + ' ' + b.datetime);
      } else if (sortCol === 'author') {
        cmp = a.author.localeCompare(b.author, 'ru');
        if (!cmp) cmp = String(a.id).localeCompare(String(b.id));
      } else if (sortCol === 'opinion') {
        cmp = (OPINION_ORDER[a.opinion] ?? 9) - (OPINION_ORDER[b.opinion] ?? 9);
        if (!cmp) cmp = TYPE_LABELS[a.opinion].localeCompare(TYPE_LABELS[b.opinion], 'ru');
      } else if (sortCol === 'simple' || sortCol === 'report' || sortCol === 'manifest') {
        cmp = labelRank(a.id, sortCol) - labelRank(b.id, sortCol);
      }
      return cmp * dir;
    });
    updateSortHeaders();
  }

  function updateSortHeaders() {
    document.querySelectorAll('th.sortable').forEach(function (th) {
      th.classList.remove('asc', 'desc');
      if (th.dataset.sort === sortCol) th.classList.add(sortDir);
    });
  }

  function onSortHeader(col) {
    if (sortCol === col) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    else { sortCol = col; sortDir = 'asc'; }
    sortFiltered();
    renderTable();
  }

  function countStats() {
    const manual = { simple: 0, manifest: 0, report: 0, total: 0 };
    let mismatch = 0;
    for (const m of DATA.messages) {
      const lab = getLabel(m.id);
      if (lab) {
        manual.total++;
        manual[lab] = (manual[lab] || 0) + 1;
        if (lab !== m.opinion) mismatch++;
      }
    }
    return { manual, mismatch };
  }

  function updateStats() {
    const s = countStats();
    const el = document.getElementById('stats');
    const o = DATA.stats.opinions;
    el.innerHTML =
      'Сообщений: <b>' + DATA.stats.messages + '</b> · ' +
      'показано: <b>' + filtered.length + '</b> · ' +
      'размечено: <b>' + s.manual.total + '</b> · ' +
      'расхождений с мнением: <b>' + s.mismatch + '</b><br>' +
      'Мнение (авто): простое ' + o.simple + ', манифест ' + o.manifest + ', отчёт ' + o.report + ' · ' +
      'Твоя разметка: простое ' + (s.manual.simple || 0) + ', манифест ' + (s.manual.manifest || 0) + ', отчёт ' + (s.manual.report || 0) +
      ' · <span class="muted">Июнь 2026 исключён (june.html). Полный список — прокрутка вниз; сузить — фильтры.</span>';
  }

  function updateSaveStatus(text, cls) {
    const el = document.getElementById('save-status');
    el.textContent = text;
    el.className = cls || '';
  }

  function checkboxCell(id, type, current) {
    const checked = current === type ? ' checked' : '';
    return '<td class="cb-col"><input type="checkbox" data-id="' + id + '" data-type="' + type + '"' + checked + '></td>';
  }

  function renderTable() {
    const tbody = document.getElementById('tbody');
    tbody.innerHTML = '<tr><td colspan="8" class="stats">Рисую ' + filtered.length + ' строк…</td></tr>';

    window.requestAnimationFrame(function () {
      const rows = filtered.map(function (msg) {
        const manual = getLabel(msg.id);
        const mismatch = manual && manual !== msg.opinion;
        const match = manual && manual === msg.opinion;
        let trClass = '';
        if (mismatch) trClass = ' class="mismatch"';
        else if (match) trClass = ' class="labeled-match"';
        const parts = msg.datetime.split(' ');
        const comment = comments[String(msg.id)] || '';
        return '<tr' + trClass + ' data-id="' + msg.id + '">' +
          '<td class="date-col"><div>' + escapeHtml(parts[0]) + '</div><div class="time-part">' + escapeHtml(parts[1] || '') + '</div></td>' +
          '<td class="author-col" title="' + escapeHtml(msg.authorRaw) + '">' + escapeHtml(msg.author) + '</td>' +
          '<td class="msg-col"><div class="msg-text">' + escapeHtml(msg.text) + '</div></td>' +
          checkboxCell(msg.id, 'simple', manual) +
          checkboxCell(msg.id, 'report', manual) +
          checkboxCell(msg.id, 'manifest', manual) +
          '<td class="comment-col"><input type="text" data-comment="' + msg.id + '" value="' + escapeHtml(comment) + '" placeholder="исключение…"></td>' +
          '<td class="opinion-col"><span class="opinion-badge ' + msg.opinion + '">' + TYPE_LABELS[msg.opinion] + '</span></td>' +
          '</tr>';
      }).join('');
      tbody.innerHTML = rows;
    });
  }

  function refreshRowStyles(id) {
    const tr = document.querySelector('tr[data-id="' + id + '"]');
    if (!tr) return;
    const msg = DATA.messages.find(function (m) { return m.id === id; });
    if (!msg) return;
    const manual = getLabel(id);
    tr.classList.toggle('mismatch', !!(manual && manual !== msg.opinion));
    tr.classList.toggle('labeled-match', !!(manual && manual === msg.opinion));
    tr.querySelectorAll('input[data-type]').forEach(function (cb) {
      cb.checked = cb.dataset.type === manual;
    });
  }

  function fillSelects() {
    const authorSel = document.getElementById('filter-author');
    DATA.authors.forEach(function (a) {
      const opt = document.createElement('option');
      opt.value = a;
      opt.textContent = a;
      authorSel.appendChild(opt);
    });
    const monthSel = document.getElementById('filter-month');
    DATA.months.forEach(function (m) {
      const opt = document.createElement('option');
      opt.value = m;
      opt.textContent = m;
      monthSel.appendChild(opt);
    });
  }

  function bindEvents() {
    ['search', 'filter-author', 'filter-month', 'filter-opinion', 'filter-manual'].forEach(function (id) {
      document.getElementById(id).addEventListener('change', applyFilters);
      document.getElementById(id).addEventListener('input', applyFilters);
    });
    document.getElementById('only-unlabeled').addEventListener('change', applyFilters);
    document.getElementById('only-mismatch').addEventListener('change', applyFilters);

    document.querySelector('thead').addEventListener('click', function (e) {
      const th = e.target.closest('th.sortable');
      if (th && th.dataset.sort) onSortHeader(th.dataset.sort);
    });

    document.getElementById('tbody').addEventListener('change', function (e) {
      const cb = e.target.closest('input[data-type]');
      if (cb) {
        const id = cb.dataset.id;
        setLabel(id, cb.checked ? cb.dataset.type : null);
        return;
      }
      const cm = e.target.closest('input[data-comment]');
      if (cm) setComment(cm.dataset.comment, cm.value);
    });

    document.getElementById('tbody').addEventListener('blur', function (e) {
      const cm = e.target.closest('input[data-comment]');
      if (cm) setComment(cm.dataset.comment, cm.value);
    }, true);

    document.getElementById('btn-save').addEventListener('click', function () {
      saveServer().catch(function (err) {
        updateSaveStatus('Сервер: ' + err.message + ' (осталось в localStorage)', 'status-err');
      });
    });
    document.getElementById('btn-download').addEventListener('click', downloadJson);
    document.getElementById('btn-import').addEventListener('click', function () {
      document.getElementById('import-input').click();
    });
    document.getElementById('import-input').addEventListener('change', function (e) {
      if (e.target.files[0]) importJson(e.target.files[0]);
      e.target.value = '';
    });
  }

  async function init() {
    const main = document.querySelector('main');
    try {
      const r = await fetch('/chat/result-data.json?_=' + Date.now());
      if (!r.ok) throw new Error('HTTP ' + r.status + ' — запустите scripts/build_chat_labeling_data.py');
      DATA = await r.json();
      loadLocal();
      await loadServerLabels();
      fillSelects();
      bindEvents();
      applyFilters();
      document.getElementById('meta').textContent =
        'Период: ' + (DATA.period && DATA.period.from ? DATA.period.from : '—') +
        ' … ' + (DATA.period && DATA.period.to ? DATA.period.to : '—') +
        ' · источник: ' + DATA.source + ' · сгенерировано ' + (DATA.generated_at || '—');
    } catch (err) {
      main.innerHTML = '<div class="err-box"><b>Не удалось загрузить данные</b><br>' + escapeHtml(err.message) + '</div>';
    }
  }

  init();
})();
