(function () {
  'use strict';

  let DATA = null;
  let SERVER = null;
  /** @type {'server'|'marathons'|'overall'|number} */
  let current = 'marathons';
  /** @type {'month'|'overall'} */
  let participantView = 'month';
  let monthIndex = 0;
  let tableSort = { col: null, dir: 'asc' };

  const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

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

  function habitPct(fact, plan) {
    return plan ? Math.round(fact / plan * 1000) / 10 : 0;
  }

  function monthLabel(key) {
    const map = {
      '01': 'янв', '02': 'фев', '03': 'мар', '04': 'апр', '05': 'май', '06': 'июн',
      '07': 'июл', '08': 'авг', '09': 'сен', '10': 'окт', '11': 'ноя', '12': 'дек'
    };
    const p = key.split('-');
    return (map[p[1]] || p[1]) + ' ' + p[0];
  }

  function monthLabelLong(key) {
    const map = {
      '01': 'Январь', '02': 'Февраль', '03': 'Март', '04': 'Апрель', '05': 'Май', '06': 'Июнь',
      '07': 'Июль', '08': 'Август', '09': 'Сентябрь', '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
    };
    const p = key.split('-');
    return (map[p[1]] || p[1]) + ' ' + p[0];
  }

  function formatStatDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleString('ru-RU', {
      day: 'numeric', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  }

  function findParticipant(id) {
    return (DATA.participants || []).find(function (p) { return p.id === id; });
  }

  function navIdForUser(id) {
    return 'u:' + id;
  }

  function userIdFromNav(id) {
    if (typeof id === 'number') return id;
    if (String(id).indexOf('u:') === 0) return parseInt(String(id).slice(2), 10);
    return null;
  }

  function isParticipantView() {
    return typeof current === 'number' || String(current).indexOf('u:') === 0;
  }

  function currentUserId() {
    return typeof current === 'number' ? current : userIdFromNav(current);
  }

  const COLGROUP = '<colgroup>' +
    '<col class="col-num"><col class="col-habit"><col class="col-plan"><col class="col-fact"><col class="col-pct">' +
    '</colgroup>';

  function tableHead() {
    const habitCls = tableSort.col === 'habit' ? 'sortable ' + tableSort.dir : 'sortable';
    const pctCls = tableSort.col === 'pct' ? 'sortable ' + tableSort.dir : 'sortable';
    return '<thead><tr>' +
      '<th>№</th>' +
      '<th class="' + habitCls + '" data-sort="habit">Привычка</th>' +
      '<th>План (шт)</th>' +
      '<th>Факт (шт)</th>' +
      '<th class="' + pctCls + '" data-sort="pct">%</th>' +
      '</tr></thead>';
  }

  function sortHabits(habits) {
    if (!tableSort.col || !habits.length) return habits;
    const sorted = habits.slice().sort(function (a, b) {
      if (tableSort.col === 'habit') {
        const cmp = a.habit.localeCompare(b.habit, 'ru');
        return tableSort.dir === 'asc' ? cmp : -cmp;
      }
      const pa = habitPct(a.fact, a.plan);
      const pb = habitPct(b.fact, b.plan);
      if (pa !== pb) return tableSort.dir === 'asc' ? pa - pb : pb - pa;
      return a.habit.localeCompare(b.habit, 'ru');
    });
    return sorted.map(function (h, i) {
      return Object.assign({}, h, { num: i + 1 });
    });
  }

  function habitRows(habits) {
    return habits.map(function (h) {
      const p = habitPct(h.fact, h.plan);
      return '<tr>' +
        '<td class="num">' + h.num + '</td>' +
        '<td>' + escapeHtml(h.habit) + '</td>' +
        '<td>' + h.plan + '</td>' +
        '<td>' + h.fact + '</td>' +
        '<td class="pct ' + pctClass(p) + '">' + p + '%</td>' +
        '</tr>';
    }).join('');
  }

  function renderHabitsTables(block) {
    const main = sortHabits(block.habits || []);
    const star = block.star_habits && block.star_habits.length ? sortHabits(block.star_habits) : [];
    let html = '<div class="table-group"><table>' + COLGROUP + tableHead() + '<tbody>';
    html += habitRows(main);
    if (star.length) {
      html += '<tr class="section-row"><td colspan="5">Задачи со звёздочкой</td></tr>';
      html += habitRows(star);
    }
    html += '</tbody></table></div>';
    return html;
  }

  function analyzeHabits(habits) {
    if (!habits.length) return { strongest: [], weakest: [] };
    const items = habits.map(function (h) {
      return Object.assign({}, h, { pct: habitPct(h.fact, h.plan) });
    });
    const maxPct = Math.max.apply(null, items.map(function (h) { return h.pct; }));
    const minPct = Math.min.apply(null, items.map(function (h) { return h.pct; }));
    return {
      strongest: items.filter(function (h) { return h.pct === maxPct; }),
      weakest: items.filter(function (h) { return h.pct === minPct; })
    };
  }

  function formatHabitList(items) {
    return items.map(function (h) {
      return '«' + h.habit + '» (' + h.pct + '%)';
    }).join(', ');
  }

  function allHabitsForInsights(block) {
    return (block.habits || []).concat(block.star_habits || []);
  }

  function buildRecommendation(block, strongest, weakest, reportPct) {
    const tips = [];
    const all = allHabitsForInsights(block);
    const hp = habitPct(
      all.reduce(function (s, h) { return s + h.fact; }, 0),
      all.reduce(function (s, h) { return s + h.plan; }, 0)
    );

    if (reportPct < 80) {
      tips.push(
        'Отчётность ' + reportPct + '% — ниже целевых 80%. Зафиксируй одно и то же время для отчёта (например, перед сном), чтобы не терять дни.'
      );
    } else if (reportPct >= 95) {
      tips.push('Отчётность на высоте — это сильная дисциплина, на неё можно опереться при подтягивании слабых привычек.');
    }

    weakest.forEach(function (w) {
      if (w.pct >= 70) return;
      const gap = w.plan - w.fact;
      if (w.pct < 40) {
        tips.push(
          '«' + w.habit + '» выполнена лишь ' + w.pct + '% (' + w.fact + ' из ' + w.plan + '). Разбей на микро-шаг: сделай минимальную версию привычки 5 минут в день — важнее ритм, чем идеальный объём. Не хватает ~' + gap + ' отметок.'
        );
      } else {
        tips.push(
          '«' + w.habit + '» — зона роста (' + w.pct + '%). Добавь напоминание или привяжи привычку к уже стабильному действию (например, после утреннего отчёта).'
        );
      }
    });

    if (strongest.length && weakest.length && strongest[0].pct > weakest[0].pct) {
      tips.push(
        'Перенеси приём из сильной привычки «' + strongest[0].habit + '» на слабую: тот же слот времени, тот же формат отчёта в чате.'
      );
    }

    if (hp < 60 && tips.length < 2) {
      tips.push('Общий процент ниже 60% — на следующий цикл выбери 1–2 привычки в приоритет, остальные держи в поддерживающем режиме.');
    }

    if (!tips.length) {
      tips.push('Баланс хороший. Сохраняй текущий ритм и чуть усложни привычку с самым высоким процентом — там есть запас прочности.');
    }

    return tips.slice(0, 3).join(' ');
  }

  function renderInsights(block, reportPct) {
    const habits = allHabitsForInsights(block);
    const analyzed = analyzeHabits(habits);
    if (!analyzed.strongest.length) return '';
    const rec = buildRecommendation(block, analyzed.strongest, analyzed.weakest, reportPct);
    return '<div class="insights">' +
      '<p class="insight-line"><strong>Самая сильная привычка:</strong> ' + formatHabitList(analyzed.strongest) + '</p>' +
      '<p class="insight-line weak"><strong>Самая слабая привычка:</strong> ' + formatHabitList(analyzed.weakest) + '</p>' +
      '<div class="recommendation">' +
      '<div class="recommendation-title">Рекомендация</div>' +
      escapeHtml(rec) +
      '</div></div>';
  }

  function renderReportGrid(cal) {
    if (!cal || !cal.days || !cal.days.length) {
      return '<p class="hint">Нет календаря отчётов</p>';
    }
    const pad = cal.first_weekday || 0;
    const weekdayCells = WEEKDAYS.map(function (w) {
      return '<div class="report-weekday">' + w + '</div>';
    }).join('');
    let dayCells = '';
    for (let i = 0; i < pad; i++) {
      dayCells += '<div class="report-day pad" aria-hidden="true"></div>';
    }
    cal.days.forEach(function (d) {
      const cls = d.state || (d.has_report ? 'ok' : 'miss');
      const title = cls === 'future' ? 'Будущий день' : (d.has_report ? 'Отчёт есть' : 'Нет отчёта');
      dayCells += '<div class="report-day ' + cls + '" title="' + title + ' · день ' + d.day + '">' + d.day + '</div>';
    });
    return '<div class="report-calendar-grid">' + weekdayCells + dayCells + '</div>';
  }

  function card(label, value, suffix, cls) {
    const v = value != null ? value : '—';
    return '<div class="card">' +
      '<div class="card-label">' + escapeHtml(label) + '</div>' +
      '<div class="card-value' + (cls ? ' ' + cls : '') + '">' + v +
      (suffix ? '<small>' + suffix + '</small>' : '') + '</div></div>';
  }

  function smokeBadge(code) {
    if (!code) return '<span class="smoke-badge bad">—</span>';
    if (code >= 200 && code < 400) return '<span class="smoke-badge good">' + code + '</span>';
    return '<span class="smoke-badge bad">' + code + '</span>';
  }

  function metricPctClass(pct) {
    if (pct == null || pct === '') return '';
    const v = Number(pct);
    if (v >= 85) return 'bad';
    if (v >= 70) return 'warn';
    return 'good';
  }

  function formatLoad(load) {
    if (!load || !load.length) return '—';
    return load.map(function (x) { return Number(x).toFixed(2); }).join(' · ');
  }

  function renderServerCharts(history) {
    if (!history.length) return '';
    const rows = history.slice(-30);
    const maxDisk = 100;
    const maxRam = 100;
    const diskBars = rows.map(function (h) {
      const v = h.disk_used_pct != null ? h.disk_used_pct : 0;
      const hgt = Math.max(4, Math.round(v / maxDisk * 100));
      return '<div class="server-bar-wrap" title="' + escapeHtml(h.date + ': ' + v + '%') + '">' +
        '<div class="server-bar disk ' + metricPctClass(v) + '" style="height:' + hgt + '%"></div>' +
        '<span class="server-bar-label">' + escapeHtml(h.date.slice(5)) + '</span></div>';
    }).join('');
    const ramBars = rows.map(function (h) {
      const v = h.ram_used_pct != null ? h.ram_used_pct : 0;
      const hgt = Math.max(4, Math.round(v / maxRam * 100));
      return '<div class="server-bar-wrap" title="' + escapeHtml(h.date + ': ' + v + '%') + '">' +
        '<div class="server-bar ram ' + metricPctClass(v) + '" style="height:' + hgt + '%"></div>' +
        '<span class="server-bar-label">' + escapeHtml(h.date.slice(5)) + '</span></div>';
    }).join('');
    return (
      '<div class="server-charts">' +
      '<div class="server-chart-block">' +
      '<h3 class="section-title">Диск (% занято) — последние ' + rows.length + ' дн.</h3>' +
      '<div class="server-bars">' + diskBars + '</div></div>' +
      '<div class="server-chart-block">' +
      '<h3 class="section-title">RAM (% занято)</h3>' +
      '<div class="server-bars">' + ramBars + '</div></div>' +
      '</div>'
    );
  }

  function renderServer() {
    if (!SERVER) {
      return '<h2>Сервер</h2><p class="hint">Загрузка снимка…</p>';
    }
    const latest = SERVER.latest;
    if (!latest) {
      return (
        '<h2>Сервер</h2>' +
        '<p class="hint server-empty">Данные появятся после первого cron (ежедневно ~08:00 MSK). ' +
        'Скрипт: <code>scripts/build_server_health_snapshot.py</code></p>'
      );
    }
    const history = (SERVER.history || []).slice().sort(function (a, b) {
      return (b.date || '').localeCompare(a.date || '');
    });
    const containers = (latest.containers || []).map(function (c) {
      return '<li>' + escapeHtml(c) + '</li>';
    }).join('') || '<li class="subtle">—</li>';

    const tableRows = history.map(function (h) {
      return '<tr>' +
        '<td>' + escapeHtml(h.date || '—') + '</td>' +
        '<td class="pct ' + metricPctClass(h.disk_used_pct) + '">' + (h.disk_used_pct != null ? h.disk_used_pct + '%' : '—') + '</td>' +
        '<td>' + escapeHtml(h.disk_avail || '—') + '</td>' +
        '<td>' + escapeHtml(h.ram_used || '—') + ' / ' + escapeHtml(h.ram_avail || '—') + '</td>' +
        '<td>' + escapeHtml(h.swap_used || '—') + '</td>' +
        '<td>' + escapeHtml(formatLoad(h.load)) + '</td>' +
        '<td>' + smokeBadge(h.smoke && h.smoke.island) + ' ' + smokeBadge(h.smoke && h.smoke.stat) + '</td>' +
        '</tr>';
    }).join('');

    return (
      '<h2>Сервер</h2>' +
      '<p class="hint">VPS <strong>' + escapeHtml(SERVER.host || '—') + '</strong> · снимок ' +
      escapeHtml(formatStatDate(SERVER.updated_at)) + '</p>' +
      '<div class="cards">' +
      card('Диск', latest.disk_used_pct, '%', metricPctClass(latest.disk_used_pct)) +
      card('Свободно', latest.disk_avail, '', '') +
      card('RAM', (latest.ram_used || '—') + ' / ' + (latest.ram_avail || '—'), '', metricPctClass(latest.ram_used_pct)) +
      card('Swap', latest.swap_used, '', '') +
      card('Load', formatLoad(latest.load), '', '') +
      '</div>' +
      '<div class="cards server-smoke-cards">' +
      card('Smoke island', (latest.smoke && latest.smoke.island) || '—', '', (latest.smoke && latest.smoke.island >= 200 && latest.smoke.island < 400) ? 'good' : 'bad') +
      card('Smoke /stat/', (latest.smoke && latest.smoke.stat) || '—', '', (latest.smoke && latest.smoke.stat >= 200 && latest.smoke.stat < 400) ? 'good' : 'bad') +
      card('Docker images', latest.docker_images || '—', '', '') +
      '</div>' +
      '<h3 class="section-title">Контейнеры</h3><ul class="server-containers">' + containers + '</ul>' +
      renderServerCharts(history.slice().reverse()) +
      '<h3 class="section-title">История (' + history.length + ' дн., макс. 60)</h3>' +
      '<table class="server-history-table"><thead><tr>' +
      '<th>Дата</th><th>Диск</th><th>Свободно</th><th>RAM</th><th>Swap</th><th>Load</th><th>Smoke</th>' +
      '</tr></thead><tbody>' +
      (tableRows || '<tr><td colspan="7" class="hint">Нет записей</td></tr>') +
      '</tbody></table>'
    );
  }

  function renderMarathons() {
    const groups = DATA.marathons.year_groups || [];
    const rows = DATA.marathons.rows || {};
    const months = [];
    let headTop = '<tr><th rowspan="2">Показатель</th>';
    groups.forEach(function (g) {
      headTop += '<th colspan="' + g.months.length + '">' + escapeHtml(g.year) + '</th>';
      g.months.forEach(function (m) { months.push(m.key); });
    });
    headTop += '</tr>';
    const headBottom = '<tr>' + months.map(function (key) {
      return '<th>' + escapeHtml(monthLabel(key).split(' ')[0]) + '</th>';
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

    return '<h2>Марафоны</h2>' +
      '<p class="hint">Помесячная матрица по всем участникам из БД.</p>' +
      '<div class="cards">' +
      card('Участников с отчётами', DATA.totals.participants, '') +
      card('Месяцев в срезе', DATA.totals.months, '') +
      '</div>' +
      '<table class="matrix-table"><thead>' + headTop + headBottom + '</thead><tbody>' +
      metricRow('Кол-во участников', 'participants_count', false) +
      metricRow('Кол-во привычек', 'habits_count', false) +
      metricRow('% выполнения', 'completion_pct', true) +
      '</tbody></table>' +
      renderAppActiveUsers();
  }

  function renderAppActiveUsers() {
    const block = DATA.app_active || {};
    const rows = block.rows || [];
    const body = rows.map(function (r) {
      return '<tr>' +
        '<td><strong>' + escapeHtml(r.name) + '</strong></td>' +
        '<td>' + escapeHtml(formatStatDate(r.registered_at)) + '</td>' +
        '<td>' + r.dreams_count + '</td>' +
        '<td>' + r.steps_count + '</td>' +
        '<td>' + r.steps_marked + ' <span class="subtle">(' + r.mark_pct + '%)</span></td>' +
        '<td>' + escapeHtml(formatStatDate(r.last_seen_at)) + '</td>' +
        '</tr>';
    }).join('');

    return (
      '<h3 class="section-title">Активные участники приложения</h3>' +
      '<p class="hint">Ведут расписание в ЛК: есть мечта и шаги. Отметки ✓/− — показатель вовлечённости. ' +
      'Марафонские отчёты в чат — отдельно, не обязательны.</p>' +
      '<div class="cards">' +
      card('Активных в приложении', block.total != null ? block.total : rows.length, '') +
      card('С отчётами марафона', (DATA.totals && DATA.totals.participants) || 0, '') +
      '</div>' +
      '<table class="app-active-table"><thead><tr>' +
      '<th>Участник</th><th>Регистрация</th><th>Мечт</th><th>Шагов</th><th>Отметок</th><th>Был в ЛК</th>' +
      '</tr></thead><tbody>' +
      (body || '<tr><td colspan="6" class="hint">Нет активных участников</td></tr>') +
      '</tbody></table>'
    );
  }

  function renderGroupOverall() {
    const o = DATA.overall || {};
    const rows = (DATA.participants || []).map(function (p) {
      const ov = p.overall || {};
      const all = allHabitsForInsights(ov);
      const hp = habitPct(
        all.reduce(function (s, h) { return s + h.fact; }, 0),
        all.reduce(function (s, h) { return s + h.plan; }, 0)
      );
      return '<tr>' +
        '<td><strong>' + escapeHtml(p.name) + '</strong></td>' +
        '<td>' + p.marathons_completed + '</td>' +
        '<td>' + (ov.reports != null ? ov.reports : '—') + '</td>' +
        '<td class="pct ' + pctClass(ov.report_pct) + '">' + ov.report_pct + '%</td>' +
        '<td class="pct ' + pctClass(hp) + '">' + hp + '%</td>' +
        '</tr>';
    }).join('');

    return '<h2>Общая статистика</h2>' +
      '<div class="cards">' +
      card('Участников', o.participants, '') +
      card('Средний % сдачи отчётности', o.avg_report_pct, '%', pctClass(o.avg_report_pct)) +
      card('Средний % выполнения привычек', o.avg_habit_pct, '%', pctClass(o.avg_habit_pct)) +
      '</div>' +
      '<table><thead><tr>' +
      '<th>Участник</th><th>Марафонов</th><th>Отчётов</th><th>% отчётности</th><th>% привычек</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table>' +
      '<p class="hint">Сводка за весь период (' + escapeHtml(DATA.period.from) + ' … ' + escapeHtml(DATA.period.to) + ').</p>';
  }

  function renderParticipant() {
    const p = findParticipant(currentUserId());
    if (!p) return '<p class="err">Участник не найден</p>';

    const months = p.months || [];
    if (!months.length) return '<p class="hint">Нет данных по месяцам</p>';

    if (monthIndex < 0) monthIndex = 0;
    if (monthIndex >= months.length) monthIndex = months.length - 1;

    const monthKey = months[monthIndex];
    const monthBlock = (p.by_month || {})[monthKey] || {};
    const block = participantView === 'overall' ? (p.overall || {}) : monthBlock;
    const all = allHabitsForInsights(block);
    const hp = habitPct(
      all.reduce(function (s, h) { return s + h.fact; }, 0),
      all.reduce(function (s, h) { return s + h.plan; }, 0)
    );
    const reportPct = block.report_pct != null ? block.report_pct : 0;
    const reports = block.reports != null ? block.reports : '—';
    const daysInMonth = participantView === 'month' && monthBlock.report_calendar
      ? monthBlock.report_calendar.days_in_month
      : null;

    const viewTabs =
      '<div class="view-tabs" role="tablist">' +
      '<button type="button" class="view-tab' + (participantView === 'month' ? ' active' : '') + '" data-view="month">Месяц</button>' +
      '<button type="button" class="view-tab' + (participantView === 'overall' ? ' active' : '') + '" data-view="overall">Общее</button>' +
      '</div>';

    let monthNav = '';
    if (participantView === 'month') {
      const prevDisabled = monthIndex <= 0 ? ' disabled' : '';
      const nextDisabled = monthIndex >= months.length - 1 ? ' disabled' : '';
      monthNav =
        '<div class="month-nav">' +
        '<button type="button" class="month-nav-btn" data-dir="prev"' + prevDisabled + ' aria-label="Предыдущий месяц">‹</button>' +
        '<span class="month-nav-label">' + escapeHtml(monthLabelLong(monthKey)) + '</span>' +
        '<button type="button" class="month-nav-btn" data-dir="next"' + nextDisabled + ' aria-label="Следующий месяц">›</button>' +
        '<span class="month-nav-meta subtle">' + (monthIndex + 1) + ' / ' + months.length +
        (monthBlock.source ? ' · ' + (monthBlock.source === 'lk' ? 'ЛК' : 'чат/БД') : '') +
        '</span></div>';
    }

    const calendarCard = participantView === 'month'
      ? '<div class="card card-grid card-calendar">' + renderReportGrid(monthBlock.report_calendar) + '</div>'
      : '';

    return '<h2>' + escapeHtml(p.name) + '</h2>' +
      viewTabs +
      monthNav +
      '<div class="cards cards-participant">' +
      calendarCard +
      card('Марафонов', p.marathons_completed, '') +
      card('Отчётов', reports, daysInMonth ? '/' + daysInMonth : '') +
      card('% отчётности', reportPct, '%', pctClass(reportPct)) +
      card('% выполнения привычек', hp, '%', pctClass(hp)) +
      '</div>' +
      renderHabitsTables(block) +
      renderInsights(block, reportPct);
  }

  function render() {
    document.querySelectorAll('.nav-item').forEach(function (el) {
      const id = el.dataset.id;
      let active = false;
      if (id === 'server' && current === 'server') active = true;
      if (id === 'marathons' && current === 'marathons') active = true;
      if (id === 'overall' && current === 'overall') active = true;
      if (id && id.indexOf('u:') === 0 && currentUserId() === userIdFromNav(id)) active = true;
      el.classList.toggle('active', active);
    });

    const content = document.getElementById('content');
    if (!DATA) return;

    if (current === 'server') {
      content.innerHTML = renderServer();
      return;
    }
    if (isParticipantView()) {
      content.innerHTML = renderParticipant();
      return;
    }
    if (current === 'marathons') content.innerHTML = renderMarathons();
    else content.innerHTML = renderGroupOverall();
  }

  function buildNav() {
    const nav = document.getElementById('nav');
    let html = '<div class="nav-title">Разделы</div>';
    html += '<button type="button" class="nav-item' + (current === 'server' ? ' active' : '') + '" data-id="server">Сервер</button>';
    html += '<div class="nav-divider"></div>';
    html += '<div class="nav-title">Марафон</div>';
    html += '<button type="button" class="nav-item' + (current === 'marathons' ? ' active' : '') + '" data-id="marathons">Марафоны</button>';
    html += '<button type="button" class="nav-item' + (current === 'overall' ? ' active' : '') + '" data-id="overall">Общая</button>';
    html += '<div class="nav-divider"></div>';
    html += '<div class="nav-title">Участники</div>';
    (DATA.participants || []).forEach(function (p) {
      const nid = navIdForUser(p.id);
      const active = currentUserId() === p.id;
      html += '<button type="button" class="nav-item' + (active ? ' active' : '') + '" data-id="' + nid + '">' +
        escapeHtml(p.name) + '</button>';
    });
    nav.innerHTML = html;
  }

  function updateTopbar() {
    if (current === 'server' && SERVER && SERVER.updated_at) {
      document.getElementById('topbar-meta').textContent =
        'Сервер · ' + SERVER.updated_at;
      return;
    }
    document.getElementById('topbar-meta').textContent =
      'БД · ' + (DATA ? DATA.generated_at || '—' : '—');
  }

  function bindNav() {
    const nav = document.getElementById('nav');
    nav.onclick = function (e) {
      const btn = e.target.closest('.nav-item');
      if (!btn) return;
      tableSort = { col: null, dir: 'asc' };
      const id = btn.dataset.id;
      if (id === 'server' || id === 'marathons' || id === 'overall') {
        current = id;
      } else if (id.indexOf('u:') === 0) {
        current = userIdFromNav(id);
        participantView = 'month';
        const p = findParticipant(currentUserId());
        monthIndex = p && p.months.length ? p.months.length - 1 : 0;
      }
      render();
      updateTopbar();
    };
  }

  async function loadServer() {
    try {
      const resp = await fetch('data/server_health.json?_=' + Date.now(), { cache: 'no-store' });
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      SERVER = await resp.json();
    } catch (e) {
      SERVER = { latest: null, history: [], _error: String(e.message || e) };
    }
  }

  async function load() {
    const content = document.getElementById('content');
    try {
      const [marathonOk] = await Promise.all([
        fetch('/stat/api/snapshot.json?_=' + Date.now(), { cache: 'no-store' })
          .then(function (resp) {
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            return resp.json();
          }),
        loadServer(),
      ]);
      DATA = marathonOk;
      updateTopbar();
      buildNav();
      bindNav();
      render();
    } catch (e) {
      content.innerHTML =
        '<div class="err"><strong>Не удалось загрузить снимок статистики</strong><br>' +
        '<code>/stat/api/snapshot.json</code> (БД) или <code>python3 scripts/build_stat_snapshot.py</code><br><small>' +
        escapeHtml(String(e.message || e)) + '</small></div>';
    }
  }

  document.getElementById('content').addEventListener('click', function (e) {
    const th = e.target.closest('th[data-sort]');
    if (th && isParticipantView()) {
      const col = th.dataset.sort;
      if (tableSort.col === col) {
        tableSort.dir = tableSort.dir === 'asc' ? 'desc' : 'asc';
      } else {
        tableSort.col = col;
        tableSort.dir = 'asc';
      }
      render();
      return;
    }

    const viewTab = e.target.closest('.view-tab');
    if (viewTab && isParticipantView()) {
      participantView = viewTab.dataset.view;
      render();
      return;
    }

    const navBtn = e.target.closest('.month-nav-btn');
    if (navBtn && !navBtn.disabled && isParticipantView() && participantView === 'month') {
      const p = findParticipant(currentUserId());
      if (!p) return;
      if (navBtn.dataset.dir === 'prev' && monthIndex > 0) monthIndex -= 1;
      if (navBtn.dataset.dir === 'next' && monthIndex < p.months.length - 1) monthIndex += 1;
      tableSort = { col: null, dir: 'asc' };
      render();
    }
  });

  load();
})();
