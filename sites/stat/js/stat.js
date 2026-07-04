(function () {
  'use strict';

  let SNAPSHOT = null;
  let LEGACY = null;
  let current = 'today';
  let tableSort = { col: 'users_count', dir: 'desc' };

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function pctClass(v) {
    if (v == null) return '';
    if (v >= 70) return 'good';
    if (v >= 40) return 'mid';
    return 'low';
  }

  function formatDate(iso) {
    if (!iso) return '—';
    const p = iso.split('-');
    if (p.length !== 3) return iso;
    return p[2] + '.' + p[1] + '.' + p[0];
  }

  function monthLabel(key) {
    const map = {
      '01': 'янв', '02': 'фев', '03': 'мар', '04': 'апр', '05': 'май', '06': 'июн',
      '07': 'июл', '08': 'авг', '09': 'сен', '10': 'окт', '11': 'ноя', '12': 'дек'
    };
    return map[key.split('-')[1]] || key;
  }

  function card(label, value, suffix, cls) {
    const v = value != null ? value : '—';
    return '<div class="card"><div class="card-label">' + escapeHtml(label) +
      '</div><div class="card-value' + (cls ? ' ' + cls : '') + '">' + v +
      (suffix ? '<small>' + suffix + '</small>' : '') + '</div></div>';
  }

  function renderToday() {
    const t = SNAPSHOT.today || {};
    const m = SNAPSHOT.marathon || {};
    const chips = [];
    (t.active_names || []).forEach(function (n) {
      chips.push('<span class="chip ok">' + escapeHtml(n) + '</span>');
    });
    (t.missing_names || []).forEach(function (n) {
      chips.push('<span class="chip miss">' + escapeHtml(n) + ' — нет отчёта</span>');
    });

    return (
      '<h2>Сегодня</h2>' +
      '<div class="digest">' + escapeHtml(t.digest || 'Нет данных за сегодня') + '</div>' +
      '<div class="cards">' +
      card('Активных', t.active, '') +
      card('Сдали отчёт', t.reported, '') +
      card('Без отчёта', t.missing, '') +
      card('Успеваемость шагов', t.avg_steps_pct, '%', pctClass(t.avg_steps_pct)) +
      '</div>' +
      (chips.length ? '<div class="chips">' + chips.join('') + '</div>' : '') +
      '<div class="faq" style="margin-top:20px">' +
      '<h3>Что здесь является SSOT</h3>' +
      '<ul>' +
      '<li><strong>Сегодня:</strong> только БД личного кабинета.</li>' +
      '<li><strong>Legacy-история:</strong> визуальная сверка по чату и твоей ручной разметке до миграции в БД.</li>' +
      '<li>Текущий цикл: ' + escapeHtml(m.label || '—') + ' · день ' + (m.cycle_day || '—') + '.</li>' +
      '</ul></div>'
    );
  }

  function renderParticipants() {
    const rows = (LEGACY.participants || []).map(function (p) {
      return '<tr>' +
        '<td><strong>' + escapeHtml(p.name) + '</strong></td>' +
        '<td class="subtle">' + escapeHtml((p.raw_names || []).join(' | ')) + '</td>' +
        '<td>' + escapeHtml((p.months || []).map(monthLabel).join(', ')) + '</td>' +
        '<td>' + p.reports_count + '</td>' +
        '<td>' + p.manifests_count + '</td>' +
        '</tr>';
    }).join('');

    return (
      '<h2>Участники</h2>' +
      '<p class="hint">Участник = человек, который хотя бы один раз сделал отчёт. Здесь же проверяем склейку имён до миграции в БД.</p>' +
      '<div class="cards">' +
      card('Уникальных участников', LEGACY.totals.participants, '') +
      card('Источник правды', LEGACY.source_truth || '—', '') +
      '</div>' +
      '<table><thead><tr><th>Участник</th><th>Исходные имена из чата</th><th>Месяцы</th><th>Отчётов</th><th>Манифестов</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table>'
    );
  }

  function renderMarathons() {
    const groups = LEGACY.marathons.year_groups || [];
    const rows = LEGACY.marathons.rows || {};
    const months = [];
    let headTop = '<tr><th rowspan="2">Показатель</th>';
    groups.forEach(function (g) {
      headTop += '<th colspan="' + g.months.length + '">' + escapeHtml(g.year) + '</th>';
      g.months.forEach(function (m) { months.push(m.key); });
    });
    headTop += '</tr>';
    const headBottom = '<tr>' + months.map(function (key) {
      return '<th>' + escapeHtml(monthLabel(key)) + '</th>';
    }).join('') + '</tr>';

    function metricRow(label, key, isPct) {
      const cells = months.map(function (monthKey) {
        const value = rows[key] ? rows[key][monthKey] : null;
        if (isPct) {
          return '<td class="pct ' + pctClass(value) + '">' + (value == null ? '—' : value + '%') + '</td>';
        }
        return '<td>' + (value == null ? '—' : value) + '</td>';
      }).join('');
      return '<tr><td><strong>' + escapeHtml(label) + '</strong></td>' + cells + '</tr>';
    }

    return (
      '<h2>Марафоны</h2>' +
      '<p class="hint">Июнь 2026 берём готовым из <code>june.html</code>. Остальные месяцы — по твоей ручной разметке; привычки считаются по точному тексту.</p>' +
      '<table class="matrix-table"><thead>' + headTop + headBottom + '</thead><tbody>' +
      metricRow('Кол-во участников', 'participants_count', false) +
      metricRow('Кол-во привычек', 'habits_count', false) +
      metricRow('% выполнения за месяц', 'completion_pct', true) +
      '</tbody></table>'
    );
  }

  function sortLegacyHabits(habits) {
    const col = tableSort.col;
    const dir = tableSort.dir === 'asc' ? 1 : -1;
    const sorted = habits.slice().sort(function (a, b) {
      if (col === 'habit') {
        return a.habit.localeCompare(b.habit, 'ru') * dir;
      }
      return ((a[col] || 0) - (b[col] || 0)) * dir || a.habit.localeCompare(b.habit, 'ru');
    });
    return sorted;
  }

  function renderHabits() {
    const habits = sortLegacyHabits(LEGACY.habits || []);
    const rows = habits.map(function (h) {
      return '<tr>' +
        '<td>' + escapeHtml(h.habit) + '</td>' +
        '<td>' + h.users_count + '</td>' +
        '<td>' + h.done + '</td>' +
        '<td>' + h.not_done + '</td>' +
        '</tr>';
    }).join('');

    return (
      '<h2>Привычки</h2>' +
      '<p class="hint">Уникальные привычки по точному тексту. Если похожие формулировки окажутся разными сущностями, склеим следующим шагом после визуальной проверки.</p>' +
      '<div class="cards">' +
      card('Уникальных привычек', LEGACY.totals.habits, '') +
      card('Участников с отчётами', LEGACY.totals.participants, '') +
      '</div>' +
      '<table><thead><tr>' +
      '<th class="sortable' + (tableSort.col === 'habit' ? ' ' + tableSort.dir : '') + '" data-sort="habit">Привычка</th>' +
      '<th class="sortable' + (tableSort.col === 'users_count' ? ' ' + tableSort.dir : '') + '" data-sort="users_count">Пользователей (шт)</th>' +
      '<th class="sortable' + (tableSort.col === 'done' ? ' ' + tableSort.dir : '') + '" data-sort="done">Сделано</th>' +
      '<th class="sortable' + (tableSort.col === 'not_done' ? ' ' + tableSort.dir : '') + '" data-sort="not_done">Не сделано</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table>'
    );
  }

  function renderHistory() {
    return (
      '<h2>Источники</h2>' +
      '<div class="cards">' +
      card('Legacy-месяцев', LEGACY.totals.months, '') +
      card('Legacy-участников', LEGACY.totals.participants, '') +
      card('Снимок ЛК', SNAPSHOT.generated_at || '—', '') +
      '</div>' +
      '<div class="faq">' +
      '<h3>Что дальше</h3>' +
      '<ul>' +
      '<li>Сначала визуально сверяем участников, месяцы и привычки.</li>' +
      '<li>Потом переносим legacy в staging-слой БД.</li>' +
      '<li>После миграции источником правды становится только БД.</li>' +
      '</ul></div>'
    );
  }

  function render() {
    document.querySelectorAll('.nav-item').forEach(function (el) {
      el.classList.toggle('active', el.dataset.id === current);
    });
    const content = document.getElementById('content');
    if (!SNAPSHOT || !LEGACY) return;
    if (current === 'today') content.innerHTML = renderToday();
    else if (current === 'participants') content.innerHTML = renderParticipants();
    else if (current === 'marathons') content.innerHTML = renderMarathons();
    else if (current === 'habits') content.innerHTML = renderHabits();
    else content.innerHTML = renderHistory();
  }

  function buildNav() {
    const nav = document.getElementById('nav');
    const items = [
      ['today', 'Сегодня'],
      ['participants', 'Участники'],
      ['marathons', 'Марафоны'],
      ['habits', 'Привычки'],
      ['history', 'Источники'],
    ];
    nav.innerHTML = '<div class="nav-title">Разделы</div>' + items.map(function (item, i) {
      const active = i === 0 ? ' active' : '';
      return '<button type="button" class="nav-item' + active + '" data-id="' + item[0] + '">' + item[1] + '</button>';
    }).join('');
    nav.addEventListener('click', function (e) {
      const btn = e.target.closest('.nav-item');
      if (!btn) return;
      current = btn.dataset.id;
      render();
    });
  }

  function updateTopbar() {
    const meta = document.getElementById('topbar-meta');
    meta.textContent =
      'ЛК: ' + (SNAPSHOT.generated_at || '—') +
      ' · legacy: ' + (LEGACY.generated_at || '—') +
      ' · источник legacy: ' + (LEGACY.source_truth || '—');
  }

  async function load() {
    const content = document.getElementById('content');
    try {
      const [snapshotResp, legacyResp] = await Promise.all([
        fetch('data/marathon_snapshot.json?_=' + Date.now()),
        fetch('data/legacy_overview.json?_=' + Date.now()),
      ]);
      if (!snapshotResp.ok) throw new Error('snapshot HTTP ' + snapshotResp.status);
      if (!legacyResp.ok) throw new Error('legacy HTTP ' + legacyResp.status);
      SNAPSHOT = await snapshotResp.json();
      LEGACY = await legacyResp.json();
      updateTopbar();
      buildNav();
      render();
    } catch (e) {
      content.innerHTML =
        '<div class="err"><strong>Не удалось загрузить данные.</strong><br>' +
        '<code>python3 scripts/build_marathon_snapshot.py</code><br>' +
        '<code>python3 scripts/build_legacy_marathon_overview.py</code><br><small>' +
        escapeHtml(String(e.message || e)) + '</small></div>';
    }
  }

  document.getElementById('content').addEventListener('click', function (e) {
    const th = e.target.closest('th[data-sort]');
    if (!th || current !== 'habits') return;
    const col = th.dataset.sort;
    if (tableSort.col === col) tableSort.dir = tableSort.dir === 'asc' ? 'desc' : 'asc';
    else {
      tableSort.col = col;
      tableSort.dir = col === 'habit' ? 'asc' : 'desc';
    }
    render();
  });

  load();
})();
