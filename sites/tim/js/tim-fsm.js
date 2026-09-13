/**
 * Tim onboarding FSM — экраны 1–9 по SSOT (фин.zip).
 * Не интерпретировать дизайн: сцены/позиции из assets.js.
 */
(function () {
  const A = window.TIM_ASSETS;
  const PWA_KEY = "tim_pwa_offer_done";
  const CONTACTS_DRAFT_KEY = "tim_contact_channels";

  const state = {
    screen: 1,
    name: "",
    city: "",
    surname: "",
    phone: "",
    password: "",
    user: null,
    contacts: {
      max: "",
      telegram: "",
      vk: "",
      ok: "",
      facebook: "",
      other: [], // [{label, value}]
    },
    activeChannel: "telegram",
    dreamText: "",
    /** Корзина мечт: строго по одной, без парсера */
    dreamBasket: [],
    editingIndex: null, // null = новая; number = правка существующей
    busy: false,
    deferredInstall: null,
    videoWatched: false,
    pendingDreamSave: false,
    pendingDreams: null,
  };

  const els = {
    stage: document.getElementById("tim-stage"),
    canvas: document.getElementById("tim-canvas"),
    screen: document.getElementById("tim-screen"),
    scene: document.getElementById("tim-scene"),
    plaque: document.getElementById("tim-plaque"),
    tagline: document.getElementById("tim-tagline"),
    bubbleImg: document.getElementById("tim-bubble-img"),
    bubbleHtml: document.getElementById("tim-bubble-html"),
    card: document.getElementById("tim-card"),
    body: document.getElementById("tim-card-body"),
    error: document.getElementById("tim-error"),
    headerLogin: document.getElementById("btn-header-login"),
    logo: document.getElementById("tim-logo"),
  };

  /**
   * Режим корзины:
   * - combined (по умолчанию): ввод + список на экране 3, без прыжка
   * - split: старый 3 ↔ 8; URL ?basket_ui=split или localStorage tim_basket_ui=split
   */
  function basketUiMode() {
    try {
      const q = new URLSearchParams(location.search || "");
      const fromUrl = (q.get("basket_ui") || "").trim().toLowerCase();
      if (fromUrl === "split" || fromUrl === "combined") return fromUrl;
      const fromLs = (localStorage.getItem("tim_basket_ui") || "").trim().toLowerCase();
      if (fromLs === "split" || fromLs === "combined") return fromLs;
    } catch (_) {}
    return "combined";
  }

  function isBasketCombined() {
    return basketUiMode() !== "split";
  }

  let designW = (A && A.DESIGN_WIDTH) || 941;
  let designH = (A && A.DESIGN_HEIGHT) || 1672;

  /** Масштаб artboard только по ширине stage. Высота stage = scene×scale. */
  function fitTimCanvas() {
    if (!els.stage || !els.canvas) return;
    const stageW = els.stage.clientWidth || 1;
    const scale = stageW / designW;
    els.canvas.style.width = designW + "px";
    els.canvas.style.height = designH + "px";
    els.canvas.style.transform = "scale(" + scale + ")";
    els.stage.style.height = Math.round(designH * scale) + "px";
    els.stage.style.minHeight = "";
  }

  function apiBase() {
    const custom = typeof window.ISLAND_API_BASE === "string" ? window.ISLAND_API_BASE.trim() : "";
    return custom ? custom.replace(/\/$/, "") : "";
  }

  function lkUrl() {
    return "/index.html";
  }

  function readSavedUser() {
    try {
      const u = JSON.parse(localStorage.getItem("savedUser") || "null");
      return u && u.id ? u : null;
    } catch (_) {
      return null;
    }
  }

  function saveUser(user) {
    try {
      localStorage.setItem("savedUser", JSON.stringify(user));
    } catch (_) {}
    state.user = user;
  }

  function setError(msg) {
    if (!msg) {
      els.error.textContent = "";
      els.error.classList.remove("is-visible");
      return;
    }
    els.error.textContent = msg;
    els.error.classList.add("is-visible");
  }

  function digitsOnly(v) {
    return String(v || "").replace(/\D/g, "");
  }

  function fullPhone(digits) {
    let d = digitsOnly(digits);
    if (d.charAt(0) === "8") d = d.slice(1);
    return "+7" + d;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function applyScene(screen) {
    const key = screen;
    const baked = !!(A.BAKED_SCENE && A.BAKED_SCENE[key]);
    const design = A.designFor ? A.designFor(key) : { w: A.DESIGN_WIDTH, h: A.DESIGN_HEIGHT };
    designW = design.w || 941;
    designH = design.h || 1672;

    els.screen.dataset.screen = String(screen === "login" ? "login" : screen);
    els.screen.dataset.baked = baked ? "1" : "0";

    if ((key === 8 || key === "8") && A.confirmSceneForCount) {
      els.scene.src = A.confirmSceneForCount(state.dreamBasket.length || 1);
    } else {
      els.scene.src = A.SCENE[key] || A.SCENE[1];
    }
    els.scene.setAttribute("width", String(designW));
    els.scene.setAttribute("height", String(designH));

    const layout = (A.CARD_LAYOUT && A.CARD_LAYOUT[key]) || { left: 61, top: 850, width: 819 };
    let top = layout.top;
    // combined: при непустой корзине поднимаем карточку, чтобы влезли поле + список
    if (
      isBasketCombined() &&
      (key === 3 || key === "3") &&
      state.dreamBasket &&
      state.dreamBasket.length
    ) {
      top = Math.min(top, 980);
    }
    els.card.style.left = layout.left + "px";
    els.card.style.top = top + "px";
    els.card.style.width = layout.width + "px";

    if (baked) {
      els.bubbleImg.hidden = true;
      els.bubbleHtml.hidden = true;
      els.plaque.hidden = true;
      els.tagline.hidden = true;
      if (els.logo) els.logo.hidden = true;
    } else {
      if (els.logo) els.logo.hidden = false;
      const bubble = A.BUBBLE[key];
      if (bubble) {
        els.bubbleHtml.hidden = true;
        els.bubbleImg.hidden = false;
        els.bubbleImg.src = bubble;
      } else {
        els.bubbleImg.hidden = true;
        els.bubbleHtml.hidden = true;
      }
      els.plaque.hidden = false;
      els.plaque.src = A.DECOR.plaque;
      els.tagline.hidden = false;
      els.tagline.src = A.DECOR.tagline;
    }
    if (els.headerLogin) {
      els.headerLogin.hidden = !(key === 1 || key === "1");
    }
    fitTimCanvas();
  }

  function go(screen) {
    state.screen = screen;
    setError("");
    applyScene(screen);
    renderCard();
  }

  function btn(label, opts) {
    const o = opts || {};
    const cls = [
      "tim-btn",
      o.ghost ? "tim-btn--ghost" : "",
      o.soft ? "tim-btn--soft" : "",
      o.noarrow ? "tim-btn--noarrow" : "",
      o.locked ? "tim-btn--locked" : "",
    ]
      .filter(Boolean)
      .join(" ");
    if (o.href) {
      return '<a class="' + cls + '" href="' + o.href + '">' + escapeHtml(label) + "</a>";
    }
    return (
      '<button type="button" class="' +
      cls +
      '" data-act="' +
      escapeHtml(o.act || "") +
      '"' +
      (o.disabled ? " disabled" : "") +
      ">" +
      escapeHtml(label) +
      "</button>"
    );
  }

  function field(id, label, value, type) {
    return (
      '<div class="tim-field"><label for="' +
      id +
      '">' +
      escapeHtml(label) +
      '</label><input id="' +
      id +
      '" type="' +
      (type || "text") +
      '" value="' +
      escapeHtml(value || "") +
      '"></div>'
    );
  }

  /** Экран 1: подпись в placeholder; для города — список подсказок */
  function fieldPh(id, placeholder, value, opts) {
    opts = opts || {};
    const wrapClass = opts.citySuggest ? "tim-field tim-field--city" : "tim-field";
    let html =
      '<div class="' +
      wrapClass +
      '"><label class="tim-sr-only" for="' +
      id +
      '">' +
      escapeHtml(placeholder) +
      '</label><input id="' +
      id +
      '" type="text" placeholder="' +
      escapeHtml(placeholder) +
      '" value="' +
      escapeHtml(value || "") +
      '" autocomplete="' +
      (opts.citySuggest ? "off" : "given-name") +
      '"';
    if (opts.citySuggest) {
      html += ' aria-autocomplete="list" aria-controls="f-city-suggest"';
    }
    html += ">";
    if (opts.citySuggest) {
      html += '<ul class="tim-city-suggest" id="f-city-suggest" role="listbox" hidden></ul>';
    }
    html += "</div>";
    return html;
  }

  function renderCard() {
    const s = state.screen;
    let html = "";

    if (s === 1) {
      html =
        fieldPh("f-name", "Имя", state.name) +
        fieldPh("f-city", "Город", state.city, { citySuggest: true }) +
        btn("Познакомиться", { act: "hello-next" });
    } else if (s === 2) {
      const cfg = A.ABOUT_VIDEO || {};
      const hasVideo = !!(cfg.src && cfg.src.trim());
      const watched = !!state.videoWatched;
      html =
        '<div class="tim-video" id="tim-video-wrap">' +
        (hasVideo
          ? '<video id="about-video" controls playsinline preload="metadata" src="' +
            escapeHtml(cfg.src) +
            '"' +
            (cfg.poster ? ' poster="' + escapeHtml(cfg.poster) + '"' : "") +
            "></video>"
          : '<button type="button" class="tim-video__ph" id="btn-video-stub" data-act="video-stub">' +
            escapeHtml(cfg.placeholderLabel || "Видео скоро появится") +
            "</button>") +
        "</div>" +
        btn("к Мечтам!", {
          act: "invite-next",
          noarrow: true,
          locked: !watched,
        });
    } else if (s === 3) {
      html = renderDreamCompose();
    } else if (s === 4) {
      html =
        field("f-name", "Имя", state.name) +
        field("f-city", "Город", state.city) +
        field("f-surname", "Фамилия*", state.surname) +
        '<div class="tim-field"><label for="f-phone">Номер телефона*</label><div class="tim-phone-row"><span class="tim-phone-code">+7</span><input id="f-phone" inputmode="numeric" value="' +
        escapeHtml(digitsOnly(state.phone).replace(/^8/, "")) +
        '" placeholder="9001234567"></div></div>' +
        field("f-password", "Пароль*", state.password, "password") +
        btn(state.busy ? "Регистрация…" : "Зарегистрироваться", { act: "register", disabled: state.busy });
    } else if (s === 5) {
      html = renderContacts();
    } else if (s === 6) {
      html =
        '<h2>Установить как приложение?</h2><p class="lead">Так Остров будет всегда под рукой. Предложение один раз — потом можно найти установку в профиле.</p>' +
        btn("Установить", { act: "pwa-install", noarrow: true }) +
        btn("Открыть в браузере", { act: "pwa-browser", soft: true, noarrow: true }) +
        '<button type="button" class="tim-link" data-act="pwa-later">Позже</button>';
    } else if (s === 7) {
      html = renderDreamCompose();
    } else if (s === 8) {
      if (isBasketCombined()) {
        // combined: экран 8 не используем — сразу поле+список
        html = renderDreamCompose();
        // синхронизируем data-screen визуально через go на следующем тике нельзя — подменим
        state.screen = 3;
        applyScene(3);
      } else {
        html = renderBasketList();
      }
    } else if (s === 9) {
      html =
        '<div class="success-actions">' +
        btn("Добавить ещё мечту", { act: "again-dream", soft: true, noarrow: true }) +
        btn("Посмотреть мои мечты", { href: lkUrl(), soft: true, noarrow: true }) +
        btn("Посмотреть видеоинструкции", { act: "video-soon", soft: true, noarrow: true }) +
        btn("Перейти в приложение", { href: lkUrl() }) +
        "</div>";
    } else if (s === "login") {
      html =
        '<h2>Вход</h2>' +
        '<div class="tim-field"><label for="f-phone">Телефон</label><div class="tim-phone-row"><span class="tim-phone-code">+7</span><input id="f-phone" inputmode="numeric" value="' +
        escapeHtml(digitsOnly(state.phone).replace(/^8/, "")) +
        '"></div></div>' +
        field("f-password", "Пароль", "", "password") +
        btn(state.busy ? "Вход…" : "Войти", { act: "login", disabled: state.busy }) +
        '<button type="button" class="tim-link" data-act="back-hello">К знакомству</button>';
    }

    els.body.innerHTML = html;
    bindCard();
  }

  function renderContacts() {
    const chans = [
      ["max", "MAX"],
      ["telegram", "TG"],
      ["vk", "VK"],
      ["ok", "OK"],
      ["facebook", "FB"],
      ["other", "Ещё"],
    ];
    let icons = '<div class="tim-channels">';
    chans.forEach(function (c) {
      const id = c[0];
      const filled =
        id === "other"
          ? state.contacts.other.length > 0
          : !!(state.contacts[id] && String(state.contacts[id]).trim());
      const cls =
        "tim-ch" + (state.activeChannel === id ? " is-active" : "") + (filled ? " is-filled" : "");
      icons +=
        '<button type="button" class="' +
        cls +
        '" data-act="ch-' +
        id +
        '">' +
        escapeHtml(c[1]) +
        "</button>";
    });
    icons += "</div>";

    const active = state.activeChannel;
    let fields = '<div class="contact-fields">';
    if (active === "other") {
      fields +=
        field("f-other-label", "Как называется", "") +
        field("f-other-value", "Контакт / ссылка", "") +
        '<p class="hint">Можно добавить несколько «Ещё».</p>';
    } else if (active === "max") {
      fields +=
        field("f-contact-value", "MAX (ник или номер)", state.contacts.max) +
        '<p class="hint">Можно пропустить экран целиком.</p>';
    } else {
      const labels = {
        telegram: "Telegram (@username или номер)",
        vk: "ВКонтакте (ссылка или id)",
        ok: "Одноклассники",
        facebook: "Facebook",
      };
      fields +=
        field("f-contact-value", labels[active] || "Контакт", state.contacts[active] || "") +
        '<p class="hint">Можно пропустить экран целиком.</p>';
    }
    fields += "</div>";

    return (
      icons +
      fields +
      btn("Сохранить контакт", { act: "contact-save", soft: true, noarrow: true }) +
      btn("Далее", { act: "contacts-next" }) +
      '<button type="button" class="tim-link" data-act="contacts-skip">Пропустить</button>'
    );
  }

  function basketCount() {
    return state.dreamBasket.length;
  }

  /** 1 мечту, 2 мечты, 5 мечт */
  function dreamWordAccusative(n) {
    const abs = Math.abs(n) % 100;
    const d = abs % 10;
    if (abs > 10 && abs < 20) return "мечт";
    if (d === 1) return "мечту";
    if (d >= 2 && d <= 4) return "мечты";
    return "мечт";
  }

  function dreamWordNominative(n) {
    const abs = Math.abs(n) % 100;
    const d = abs % 10;
    if (abs > 10 && abs < 20) return "мечт";
    if (d === 1) return "мечта";
    if (d >= 2 && d <= 4) return "мечты";
    return "мечт";
  }

  function addDreamsLabel(n) {
    return "Добавить " + n + " " + dreamWordAccusative(n);
  }

  function iconEdit() {
    const src = (A.ICONS && A.ICONS.editDream) || "assets/v2/icon_edit_dream_128.png";
    return '<img class="tim-ico" src="' + src + '" alt="" width="36" height="36" decoding="async">';
  }

  function iconDelete() {
    const src = (A.ICONS && A.ICONS.deleteDream) || "assets/v2/icon_delete_dream_128.png";
    return '<img class="tim-ico" src="' + src + '" alt="" width="36" height="36" decoding="async">';
  }

  function renderBasketBadge() {
    const n = basketCount();
    if (!n) return "";
    return (
      '<button type="button" class="tim-basket" data-act="basket-open" aria-label="Корзина мечт, ' +
      n +
      '">' +
      '<span class="tim-basket__bag" aria-hidden="true"></span>' +
      '<span class="tim-basket__badge">' +
      escapeHtml(String(n)) +
      "</span></button>"
    );
  }

  function renderBasketItemsOnly() {
    const list = state.dreamBasket;
    if (!list.length) return "";
    let rows = "";
    list.forEach(function (text, i) {
      rows +=
        '<li class="tim-basket-item">' +
        '<span class="tim-basket-item__num">' +
        escapeHtml(String(i + 1)) +
        "</span>" +
        '<p class="tim-basket-item__text">' +
        escapeHtml(text) +
        "</p>" +
        '<div class="tim-basket-item__acts">' +
        '<button type="button" class="tim-ico-btn tim-ico-btn--edit" data-act="basket-edit" data-i="' +
        i +
        '" aria-label="Изменить мечту ' +
        (i + 1) +
        '">' +
        iconEdit() +
        "</button>" +
        '<button type="button" class="tim-ico-btn tim-ico-btn--del" data-act="basket-del" data-i="' +
        i +
        '" aria-label="Удалить мечту ' +
        (i + 1) +
        '">' +
        iconDelete() +
        "</button>" +
        "</div></li>";
    });
    return '<ul class="tim-basket-list">' + rows + "</ul>";
  }

  function renderDreamCompose() {
    const editing = state.editingIndex != null;
    const combined = isBasketCombined();
    const ph = editing
      ? "Поправь текст этой мечты"
      : A.DREAM_PLACEHOLDER || "Одна мечта — своими словами.";
    const n = editing ? 1 : basketCount() + 1;
    const primary = editing ? "Сохранить мечту" : addDreamsLabel(n);
    const count = basketCount();
    const listHtml = combined && count ? renderBasketItemsOnly() : "";

    return (
      '<div class="tim-dream-compose' +
      (combined ? " tim-dream-compose--combined" : "") +
      (count ? " has-basket" : "") +
      '">' +
      (!combined && count
        ? '<div class="tim-dream-compose__top">' + renderBasketBadge() + "</div>"
        : "") +
      (editing
        ? '<p class="tim-dream-edit-label">Правка мечты ' +
          escapeHtml(String(state.editingIndex + 1)) +
          "</p>"
        : "") +
      '<div class="tim-field tim-field--dream">' +
      '<label class="tim-sr-only" for="f-dream">Мечта</label>' +
      '<textarea id="f-dream" rows="6" placeholder="' +
      escapeHtml(String(ph).replace(/\n/g, " ")) +
      '">' +
      escapeHtml(state.dreamText) +
      "</textarea></div>" +
      btn(primary, { act: "dream-add", noarrow: true }) +
      (editing
        ? '<button type="button" class="tim-link tim-link--confirm" data-act="dream-edit-cancel">Отмена</button>'
        : "") +
      (listHtml
        ? '<div class="tim-basket-inline">' +
          '<p class="tim-basket-inline__title">В корзине · ' +
          escapeHtml(String(count)) +
          " " +
          dreamWordNominative(count) +
          "</p>" +
          listHtml +
          btn(state.busy ? "Сохраняю…" : "Сохранить на Остров", {
            act: "dream-save",
            noarrow: true,
            disabled: state.busy,
          }) +
          "</div>"
        : "") +
      "</div>"
    );
  }

  function renderBasketList() {
    const list = state.dreamBasket;
    let rows = "";
    if (!list.length) {
      rows =
        '<p class="tim-basket-empty">Корзина пуста. Добавь хотя бы одну мечту.</p>';
    } else {
      rows = renderBasketItemsOnly();
    }

    return (
      '<div class="tim-confirm-panel tim-basket-panel">' +
      '<p class="tim-confirm-tech">Корзина мечт</p>' +
      '<p class="tim-confirm-count">' +
      (list.length
        ? escapeHtml(String(list.length)) + " " + dreamWordNominative(list.length)
        : "Пока пусто") +
      "</p>" +
      rows +
      btn("+ Добавить мечту", { act: "basket-add", soft: true, noarrow: true }) +
      btn(state.busy ? "Сохраняю…" : "Сохранить на Остров", {
        act: "dream-save",
        noarrow: true,
        disabled: state.busy || !list.length,
      }) +
      '<button type="button" class="tim-link tim-link--confirm" data-act="basket-back">К полю ввода</button>' +
      "</div>"
    );
  }

  function refreshDreamScreen() {
    if (state.screen === 3 || state.screen === "3") {
      applyScene(3);
      renderCard();
      return;
    }
    renderCard();
  }

  function focusDreamField() {
    const ta = document.getElementById("f-dream");
    if (!ta) return;
    try {
      ta.focus();
      const len = ta.value.length;
      ta.setSelectionRange(len, len);
    } catch (_) {}
  }

  function bindCard() {
    els.body.querySelectorAll("[data-act]").forEach(function (el) {
      el.addEventListener("click", function () {
        const act = el.getAttribute("data-act");
        const iAttr = el.getAttribute("data-i");
        onAct(act, iAttr != null ? Number(iAttr) : null);
      });
    });
    if (state.screen === 1) bindCitySuggest();
    if (state.screen === 2) bindVideoScreen();
  }

  function markVideoWatched() {
    if (state.videoWatched) return;
    state.videoWatched = true;
    renderCard();
  }

  function bindVideoScreen() {
    const video = document.getElementById("about-video");
    if (video) {
      video.addEventListener("ended", markVideoWatched);
    }
  }

  function bindCitySuggest() {
    const input = document.getElementById("f-city");
    const list = document.getElementById("f-city-suggest");
    const api = window.TIM_CITIES;
    if (!input || !list || !api || typeof api.suggest !== "function") return;

    function hide() {
      list.hidden = true;
      list.innerHTML = "";
    }

    function pick(city) {
      input.value = city;
      state.city = city;
      hide();
      input.focus();
    }

    function renderSuggest() {
      const items = api.suggest(input.value, 6);
      if (!items.length) {
        hide();
        return;
      }
      list.innerHTML = items
        .map(function (city) {
          return (
            '<li role="option"><button type="button" class="tim-city-suggest__item" data-city="' +
            escapeHtml(city) +
            '">' +
            escapeHtml(city) +
            "</button></li>"
          );
        })
        .join("");
      list.hidden = false;
      list.querySelectorAll("[data-city]").forEach(function (btn) {
        btn.addEventListener("mousedown", function (e) {
          e.preventDefault();
          pick(btn.getAttribute("data-city"));
        });
      });
    }

    input.addEventListener("input", renderSuggest);
    input.addEventListener("focus", renderSuggest);
    input.addEventListener("blur", function () {
      setTimeout(hide, 120);
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape") hide();
    });
  }

  function readHelloFields() {
    const n = document.getElementById("f-name");
    const c = document.getElementById("f-city");
    if (n) state.name = n.value.trim();
    if (c) state.city = c.value.trim();
  }

  function readRegFields() {
    readHelloFields();
    const s = document.getElementById("f-surname");
    const p = document.getElementById("f-phone");
    const pw = document.getElementById("f-password");
    if (s) state.surname = s.value.trim();
    if (p) state.phone = fullPhone(p.value);
    if (pw) state.password = pw.value;
  }

  async function onAct(act, index) {
    if (act === "hello-next") {
      readHelloFields();
      if (!state.name || !state.city) {
        setError("Напиши имя и город.");
        return;
      }
      go(2);
      return;
    }
    if (act === "invite-next") {
      // кнопка всегда кликабельна (серая и цветная); цвет — после тапа по заглушке
      go(3);
      return;
    }
    if (act === "video-stub") {
      markVideoWatched();
      return;
    }
    if (act === "about-next" || act === "about-skip") {
      go(4);
      return;
    }
    if (act === "register") {
      await doRegister();
      return;
    }
    if (act.indexOf("ch-") === 0) {
      persistContactField();
      state.activeChannel = act.slice(3);
      renderCard();
      return;
    }
    if (act === "contact-save") {
      persistContactField(true);
      renderCard();
      return;
    }
    if (act === "contacts-next" || act === "contacts-skip") {
      persistContactField();
      await saveContactsToServer();
      afterContacts();
      return;
    }
    if (act === "pwa-install") {
      await doPwaInstall();
      return;
    }
    if (act === "pwa-browser" || act === "pwa-later") {
      markPwaDone();
      go(3);
      return;
    }
    if (act === "dream-add") {
      const ta = document.getElementById("f-dream");
      const text = ta ? ta.value.trim() : "";
      if (!text) {
        setError("Напиши одну мечту — хотя бы пару слов.");
        return;
      }
      if (state.editingIndex != null) {
        state.dreamBasket[state.editingIndex] = text;
        state.editingIndex = null;
      } else {
        if (state.dreamBasket.length >= 20) {
          setError("Пока максимум 20 мечт за раз.");
          return;
        }
        state.dreamBasket.push(text);
      }
      state.dreamText = "";
      setError("");
      if (isBasketCombined()) {
        refreshDreamScreen();
        return;
      }
      go(8);
      return;
    }
    if (act === "dream-edit-cancel") {
      state.editingIndex = null;
      state.dreamText = "";
      setError("");
      refreshDreamScreen();
      return;
    }
    if (act === "basket-open") {
      if (isBasketCombined()) {
        refreshDreamScreen();
        return;
      }
      go(8);
      return;
    }
    if (act === "basket-back") {
      state.editingIndex = null;
      state.dreamText = "";
      go(3);
      return;
    }
    if (act === "basket-add") {
      state.editingIndex = null;
      state.dreamText = "";
      go(3);
      return;
    }
    if (act === "basket-edit") {
      const i = index;
      if (i == null || !state.dreamBasket[i]) return;
      state.editingIndex = i;
      state.dreamText = state.dreamBasket[i];
      if (isBasketCombined()) {
        if (state.screen !== 3 && state.screen !== "3") go(3);
        else refreshDreamScreen();
        setTimeout(focusDreamField, 0);
        return;
      }
      go(3);
      return;
    }
    if (act === "basket-del") {
      const i = index;
      if (i == null || i < 0 || i >= state.dreamBasket.length) return;
      state.dreamBasket.splice(i, 1);
      if (state.editingIndex != null) {
        if (state.editingIndex === i) {
          state.editingIndex = null;
          state.dreamText = "";
        } else if (state.editingIndex > i) {
          state.editingIndex -= 1;
        }
      }
      setError("");
      if (isBasketCombined()) {
        if (state.screen !== 3 && state.screen !== "3") go(3);
        else refreshDreamScreen();
        return;
      }
      if (!state.dreamBasket.length) {
        go(3);
        return;
      }
      applyScene(8);
      renderCard();
      return;
    }
    if (act === "dream-save") {
      if (!state.dreamBasket.length) {
        setError("Сначала добавь хотя бы одну мечту в корзину.");
        return;
      }
      state.pendingDreams = state.dreamBasket.slice();
      await saveDreams();
      return;
    }
    if (act === "again-dream") {
      state.dreamText = "";
      state.dreamBasket = [];
      state.editingIndex = null;
      state.pendingDreams = null;
      go(3);
      return;
    }
    if (act === "video-soon") {
      setError("Видеоинструкции появятся позже.");
      return;
    }
    if (act === "login") {
      await doLogin();
      return;
    }
    if (act === "back-hello") {
      go(1);
    }
  }

  function persistContactField(addOther) {
    const active = state.activeChannel;
    if (active === "other") {
      const labelEl = document.getElementById("f-other-label");
      const valEl = document.getElementById("f-other-value");
      const label = labelEl ? labelEl.value.trim() : "";
      const value = valEl ? valEl.value.trim() : "";
      if (addOther && label && value) {
        state.contacts.other.push({ label: label, value: value });
        if (labelEl) labelEl.value = "";
        if (valEl) valEl.value = "";
      }
      return;
    }
    const el = document.getElementById("f-contact-value");
    if (el) state.contacts[active] = el.value.trim();
  }

  function saveContactsDraft() {
    try {
      localStorage.setItem(CONTACTS_DRAFT_KEY, JSON.stringify(state.contacts));
    } catch (_) {}
  }

  async function saveContactsToServer() {
    saveContactsDraft();
    const user = state.user || readSavedUser();
    if (!user || !user.id) return;
    const body = { user_id: user.id };
    if (state.contacts.telegram) body.telegram = state.contacts.telegram;
    if (state.contacts.vk) body.vk = state.contacts.vk;
    if (!body.telegram && !body.vk) return;
    try {
      await fetch(apiBase() + "/users/me?user_id=" + encodeURIComponent(user.id), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch (_) {}
  }

  function pwaAlreadyStandalone() {
    try {
      if (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) return true;
      if (navigator.standalone) return true;
    } catch (_) {}
    return false;
  }

  function pwaOfferDone() {
    try {
      return localStorage.getItem(PWA_KEY) === "1";
    } catch (_) {
      return false;
    }
  }

  function markPwaDone() {
    try {
      localStorage.setItem(PWA_KEY, "1");
    } catch (_) {}
  }

  function afterContacts() {
    if (pwaAlreadyStandalone() || pwaOfferDone()) {
      go(3);
    } else {
      go(6);
    }
  }

  async function doPwaInstall() {
    markPwaDone();
    if (state.deferredInstall) {
      try {
        state.deferredInstall.prompt();
        await state.deferredInstall.userChoice;
      } catch (_) {}
      state.deferredInstall = null;
      go(3);
      return;
    }
    setError("На iPhone: «Поделиться» → «На экран „Домой“». На Android установка может быть в меню браузера.");
    go(3);
  }

  async function doRegister() {
    readRegFields();
    if (!state.name || !state.surname || !state.city || !state.password) {
      setError("Заполни имя, фамилию, город и пароль.");
      return;
    }
    if (digitsOnly(state.phone).length < 11) {
      setError("Проверь телефон: нужны 10 цифр после +7.");
      return;
    }
    state.busy = true;
    renderCard();
    try {
      const res = await fetch(apiBase() + "/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: state.name,
          surname: state.surname,
          phone: state.phone,
          city: state.city,
          password: state.password,
          telegram: null,
          vk: null,
        }),
      });
      const data = await res.json().catch(function () {
        return {};
      });
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Ошибка регистрации");

      const loginRes = await fetch(apiBase() + "/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: state.phone, password: state.password }),
      });
      const user = await loginRes.json().catch(function () {
        return {};
      });
      if (!loginRes.ok) throw new Error(user.detail || "Аккаунт создан, войди вручную");
      saveUser(user);
      state.busy = false;
      if (state.pendingDreamSave) {
        await saveDreams();
        return;
      }
      go(5);
    } catch (e) {
      state.busy = false;
      setError(e.message || "Сеть недоступна");
      renderCard();
    }
  }

  async function doLogin() {
    const p = document.getElementById("f-phone");
    const pw = document.getElementById("f-password");
    state.phone = fullPhone(p ? p.value : "");
    state.password = pw ? pw.value : "";
    if (digitsOnly(state.phone).length < 11 || !state.password) {
      setError("Введи телефон и пароль.");
      return;
    }
    state.busy = true;
    renderCard();
    try {
      const res = await fetch(apiBase() + "/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: state.phone, password: state.password }),
      });
      const user = await res.json().catch(function () {
        return {};
      });
      if (!res.ok) throw new Error(typeof user.detail === "string" ? user.detail : "Не удалось войти");
      saveUser(user);
      state.name = user.name || state.name;
      state.city = user.city || state.city;
      state.busy = false;
      // После входа — в продукт (ЛК), не через весь онбординг
      window.location.href = lkUrl();
    } catch (e) {
      state.busy = false;
      setError(e.message || "Сеть недоступна");
      renderCard();
    }
  }

  function collectEditedDreams() {
    if (state.pendingDreams && state.pendingDreams.length) {
      return state.pendingDreams.slice();
    }
    if (state.dreamBasket && state.dreamBasket.length) {
      return state.dreamBasket.slice();
    }
    const t = String(state.dreamText || "").trim();
    return t ? [t] : [];
  }

  async function saveDreams() {
    const user = state.user || readSavedUser();
    if (!user || !user.id) {
      state.pendingDreamSave = true;
      state.pendingDreams = collectEditedDreams();
      setError("");
      go(4);
      return;
    }
    const dreams =
      state.pendingDreams && state.pendingDreams.length
        ? state.pendingDreams
        : collectEditedDreams();
    state.busy = true;
    renderCard();
    try {
      for (let i = 0; i < dreams.length; i++) {
        const res = await fetch(apiBase() + "/dreams", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: user.id, dream: dreams[i] }),
        });
        if (!res.ok) {
          const err = await res.json().catch(function () {
            return {};
          });
          throw new Error(err.detail || "Не удалось сохранить мечту");
        }
      }
      state.busy = false;
      state.pendingDreamSave = false;
      state.pendingDreams = null;
      state.dreamBasket = [];
      state.dreamText = "";
      state.editingIndex = null;
      go(9);
    } catch (e) {
      state.busy = false;
      setError(e.message || "Ошибка сохранения");
      renderCard();
    }
  }

  function boot() {
    window.addEventListener("beforeinstallprompt", function (e) {
      e.preventDefault();
      state.deferredInstall = e;
    });
    window.addEventListener("resize", fitTimCanvas);
    if (window.visualViewport) {
      window.visualViewport.addEventListener("resize", fitTimCanvas);
    }

    els.headerLogin.addEventListener("click", function () {
      go("login");
    });

    const saved = readSavedUser();
    if (saved && !/force=1/.test(location.search || "")) {
      // Возвращающийся: Tim не встаёт между человеком и ЛК
      window.location.replace(lkUrl());
      return;
    }
    if (saved) {
      state.user = saved;
      state.name = saved.name || "";
      state.city = saved.city || "";
    }
    fitTimCanvas();
    const screenParam = (location.search || "").match(/[?&]screen=(\d+|login)/);
    if (screenParam) {
      const raw = screenParam[1];
      go(raw === "login" ? "login" : parseInt(raw, 10));
      return;
    }
    go(1);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
