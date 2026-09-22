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
    patronymic: "",
    phone: "",
    dialCode: "+7",
    dialPickerOpen: false,
    password: "",
    password2: "",
    showRegPassword: false,
    pwaInstalledUi: false,
    user: null,
    contacts: {
      max: { user: "", phone: "" },
      telegram: { user: "", phone: "" },
      vk: { value: "" },
      whatsapp: { value: "" },
      email: { value: "" },
      ok: { value: "" },
      facebook: { value: "" },
      other: [],
    },
    /** Канал подтверждён галочкой → иконка цветная */
    channelConfirmed: {
      max: false,
      telegram: false,
      vk: false,
      whatsapp: false,
      email: false,
    },
    /** Поля, подтверждённые галочкой (ключ: max_user, telegram_phone, vk_value…) */
    fieldConfirmed: {},
    activeChannel: null, // null = ни одна соцсеть не раскрыта
    dreamText: "",
    /** Витрина мечт: строго по одной, без парсера */
    dreamBasket: [],
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

  /** Отмена устаревшего апгрейда lite→full при быстрой смене экрана */
  let sceneLoadToken = 0;

  let designW = (A && A.DESIGN_WIDTH) || 941;
  let designH = (A && A.DESIGN_HEIGHT) || 1672;

  /** Масштаб только по ширине (max 430). Лёгкий вертикальный скролл — ок; без песочных полей по бокам. */
  function fitTimCanvas() {
    if (!els.stage || !els.canvas) return;
    const stageW = Math.min(window.innerWidth || 430, 430);
    const scale = stageW / designW;
    els.canvas.style.width = designW + "px";
    els.canvas.style.height = designH + "px";
    els.canvas.style.transform = "scale(" + scale + ")";
    els.stage.style.width = stageW + "px";
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
    const code = state.dialCode || "+7";
    const codeDigits = digitsOnly(code);
    // если вставили номер с кодом страны — не дублируем
    if (codeDigits && d.indexOf(codeDigits) === 0 && d.length > codeDigits.length) {
      d = d.slice(codeDigits.length);
    }
    if (code === "+7" && d.charAt(0) === "8") d = d.slice(1);
    if (code === "+7" && d.charAt(0) === "7" && d.length >= 11) d = d.slice(1);
    return code + d;
  }

  function nationalPhoneDigits() {
    const full = digitsOnly(state.phone);
    const codeDigits = digitsOnly(state.dialCode || "+7");
    if (codeDigits && full.indexOf(codeDigits) === 0) return full.slice(codeDigits.length);
    return full;
  }

  function phoneLooksOk() {
    const national = nationalPhoneDigits();
    const code = state.dialCode || "+7";
    if (code === "+7") return national.length === 10;
    return national.length >= 6 && national.length <= 14;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /** Сначала lite JPEG, затем WebP (если другой URL и экран ещё тот же). */
  function setSceneProgressive(entry) {
    const urls = A.sceneUrls ? A.sceneUrls(entry) : { lite: entry, full: entry };
    const lite = urls.lite || "";
    const full = urls.full || lite;
    const token = ++sceneLoadToken;
    if (lite) els.scene.src = lite;
    if (!full || full === lite) return;
    const img = new Image();
    img.decoding = "async";
    img.onload = function () {
      if (token !== sceneLoadToken) return;
      els.scene.src = full;
    };
    img.src = full;
  }

  function applyScene(screen) {
    const key = screen;
    const baked = !!(A.BAKED_SCENE && A.BAKED_SCENE[key]);
    const design = A.designFor ? A.designFor(key) : { w: A.DESIGN_WIDTH, h: A.DESIGN_HEIGHT };
    designW = design.w || 941;
    designH = design.h || 1672;

    els.screen.dataset.screen = String(screen === "login" ? "login" : screen);
    els.screen.dataset.baked = baked ? "1" : "0";

    // Экран 3 (витрина): 0 мечт — «запиши»; ≥1 — «Вау, какая мечта!»
    let sceneEntry;
    if (key === 3 || key === "3") {
      if (state.dreamBasket && state.dreamBasket.length && A.confirmSceneForCount) {
        sceneEntry = A.confirmSceneForCount(state.dreamBasket.length);
      } else {
        sceneEntry = A.SCENE[3] || A.SCENE[1];
      }
    } else if ((key === 8 || key === "8") && A.confirmSceneForCount) {
      sceneEntry = A.confirmSceneForCount(state.dreamBasket.length || 1);
    } else {
      sceneEntry = A.SCENE[key] || A.SCENE[1];
    }
    setSceneProgressive(sceneEntry);
    els.scene.setAttribute("width", String(designW));
    els.scene.setAttribute("height", String(designH));

    const layout = (A.CARD_LAYOUT && A.CARD_LAYOUT[key]) || { left: 61, top: 850, width: 819 };
    let top = layout.top;
    // витрина с мечтами: ниже на песок, не под табличку на скале
    if ((key === 3 || key === "3") && state.dreamBasket && state.dreamBasket.length) {
      top = Math.max(top, 1040); // ближе к вывеске «Витрина мечт»
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
    } else if (key === 6 || key === "6" || key === "pwa") {
      // Резюме: только сцена с телефоном + HTML-кнопки (без «привет»-пузыря и табличек)
      els.bubbleImg.hidden = true;
      els.bubbleHtml.hidden = true;
      els.plaque.hidden = true;
      els.tagline.hidden = true;
      if (els.logo) els.logo.hidden = true;
      // жёстко сцена 15 — не оставлять обои аккаунта
      els.scene.src = (A.SCENE && (A.SCENE[6] || A.SCENE.pwa)) || "assets/fin/15.png";
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
      els.headerLogin.hidden = !(key === 1 || key === "1" || key === 4 || key === "4" || key === "login");
    }
    fitTimCanvas();
  }

  function clearAuthPasswords() {
    state.password = "";
    state.password2 = "";
  }

  function phoneNationalMaxLen() {
    return (state.dialCode || "+7") === "+7" ? 10 : 14;
  }

  function go(screen) {
    const prev = state.screen;
    // Пароль общий в state: при переключении «Войти» ↔ регистрация не тащим значение между формами
    if ((prev === "login") !== (screen === "login")) {
      clearAuthPasswords();
    }
    state.screen = screen;
    state.dialPickerOpen = false;
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
      // Без файла ролика кнопка сразу активна; с видео — цвет после открытия/просмотра
      const ctaLocked = hasVideo ? !watched : false;
      html =
        '<div class="tim-video" id="tim-video-wrap">' +
        (hasVideo
          ? '<button type="button" class="tim-video__open" id="btn-video-open" data-act="video-open" aria-label="Смотреть видео об Острове">' +
            '<video class="tim-video__thumb" muted playsinline preload="metadata" src="' +
            escapeHtml(cfg.src) +
            '"' +
            (cfg.poster ? ' poster="' + escapeHtml(cfg.poster) + '"' : "") +
            "></video>" +
            '<span class="tim-video__play" aria-hidden="true">▶</span>' +
            '<span class="tim-video__open-label">Видео об Острове</span>' +
            "</button>"
          : '<button type="button" class="tim-video__ph" id="btn-video-stub" data-act="video-stub">' +
            escapeHtml(cfg.placeholderLabel || "Ролик скоро будет здесь") +
            "</button>") +
        "</div>" +
        '<p class="tim-video-cta-hint">Дальше — большая кнопка «к Мечтам!»</p>' +
        btn("к Мечтам!", {
          act: "invite-next",
          noarrow: true,
          locked: ctaLocked,
        });
    } else if (s === 3) {
      html = renderDreamVitrine();
    } else if (s === 4) {
      html = renderAccountScreen();
    } else if (s === 5) {
      html = renderSocialsScreen();
    } else if (s === "fio") {
      html = renderFioScreen();
    } else if (s === 6 || s === "pwa") {
      html = renderResumeScreen();
    } else if (s === 7) {
      html = renderDreamVitrine();
    } else if (s === 8) {
      // витрина живёт на экране 3
      state.screen = 3;
      applyScene(3);
      html = renderDreamVitrine();
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
        '<div class="tim-field"><label for="f-phone">Телефон</label><div class="tim-phone-row"><button type="button" class="tim-phone-code" id="btn-dial-code" data-act="dial-open">' +
        escapeHtml(state.dialCode || "+7") +
        '</button><input id="f-phone" inputmode="numeric" maxlength="' +
        phoneNationalMaxLen() +
        '" value="' +
        escapeHtml(nationalPhoneDigits()) +
        '"></div></div>' +
        (state.dialPickerOpen ? renderDialPicker() : "") +
        '<div class="tim-field"><label for="f-password">Пароль</label><input id="f-password" type="password" minlength="4" autocomplete="current-password" value=""></div>' +
        btn(state.busy ? "Вход…" : "Войти", { act: "login", disabled: state.busy }) +
        '<button type="button" class="tim-link" data-act="back-hello">К знакомству</button>';
    }

    els.body.innerHTML = html;
    bindCard();
  }

  function renderDialPicker() {
    const codes = A.DIAL_CODES && A.DIAL_CODES.length ? A.DIAL_CODES : [{ code: "+7", label: "Россия" }];
    let list = '<div class="tim-dial-picker" role="listbox" aria-label="Код страны">';
    codes.forEach(function (row) {
      const on = row.code === (state.dialCode || "+7");
      list +=
        '<button type="button" class="tim-dial-picker__item' +
        (on ? " is-on" : "") +
        '" data-act="dial-pick" data-code="' +
        escapeHtml(row.code) +
        '" role="option" aria-selected="' +
        (on ? "true" : "false") +
        '"><span class="tim-dial-picker__code">' +
        escapeHtml(row.code) +
        '</span><span class="tim-dial-picker__label">' +
        escapeHtml(row.label) +
        "</span></button>";
    });
    list += "</div>";
    return list;
  }

  function renderAccountScreen() {
    const nameOk = !!String(state.name || "").trim();
    const cityOk = !!String(state.city || "").trim();
    const cta = state.busy
      ? state.pendingDreamSave
        ? "Отправляю…"
        : "Регистрация…"
      : "Зарегистрироваться";

    return (
      '<div class="tim-reg tim-reg--account">' +
      '<div class="tim-field tim-field--check' +
      (nameOk ? " is-ok" : "") +
      '">' +
      '<label class="tim-sr-only" for="f-name">Имя</label>' +
      '<div class="tim-input-check-row">' +
      '<input id="f-name" type="text" placeholder="Имя" value="' +
      escapeHtml(state.name || "") +
      '" autocomplete="given-name">' +
      '<span class="tim-field-check" aria-hidden="true">✓</span>' +
      "</div></div>" +
      '<div class="tim-field tim-field--check' +
      (cityOk ? " is-ok" : "") +
      '">' +
      '<label class="tim-sr-only" for="f-city">Город</label>' +
      '<div class="tim-input-check-row">' +
      '<input id="f-city" type="text" placeholder="Город" value="' +
      escapeHtml(state.city || "") +
      '" autocomplete="address-level2">' +
      '<span class="tim-field-check" aria-hidden="true">✓</span>' +
      "</div></div>" +
      '<div class="tim-field-row">' +
      '<div class="tim-field">' +
      '<label class="tim-sr-only" for="f-surname">Фамилия</label>' +
      '<div class="tim-input-check-row">' +
      '<input id="f-surname" type="text" placeholder="Фамилия" value="' +
      escapeHtml(state.surname || "") +
      '" autocomplete="family-name">' +
      "</div></div>" +
      '<div class="tim-field">' +
      '<label class="tim-sr-only" for="f-patronymic">Отчество</label>' +
      '<div class="tim-input-check-row">' +
      '<input id="f-patronymic" type="text" placeholder="Отчество" value="' +
      escapeHtml(state.patronymic || "") +
      '" autocomplete="additional-name">' +
      "</div></div>" +
      "</div>" +
      '<div class="tim-field">' +
      '<label class="tim-sr-only" for="f-phone">Номер телефона</label>' +
      '<div class="tim-phone-row">' +
      '<button type="button" class="tim-phone-code" id="btn-dial-code" data-act="dial-open" aria-label="Код страны">' +
      escapeHtml(state.dialCode || "+7") +
      "</button>" +
      '<div class="tim-input-check-row tim-input-check-row--phone">' +
      '<input id="f-phone" inputmode="numeric" maxlength="' +
      phoneNationalMaxLen() +
      '" placeholder="9001234567" value="' +
      escapeHtml(nationalPhoneDigits()) +
      '" autocomplete="tel-national">' +
      "</div></div></div>" +
      (state.dialPickerOpen ? renderDialPicker() : "") +
      '<div class="tim-field">' +
      '<label class="tim-sr-only" for="f-password">Пароль</label>' +
      '<div class="tim-input-check-row tim-input-check-row--pw">' +
      '<input id="f-password" type="' +
      (state.showRegPassword ? "text" : "password") +
      '" placeholder="Пароль * (мин. 4)" minlength="4" value="' +
      escapeHtml(state.password || "") +
      '" autocomplete="new-password">' +
      '<button type="button" class="tim-pw-toggle" data-act="pw-toggle" aria-pressed="' +
      (state.showRegPassword ? "true" : "false") +
      '" aria-label="' +
      (state.showRegPassword ? "Скрыть пароль" : "Показать пароль") +
      '">' +
      (state.showRegPassword ? "Скрыть" : "Показать") +
      "</button>" +
      "</div></div>" +
      '<div class="tim-field">' +
      '<label class="tim-sr-only" for="f-password2">Повтор пароля</label>' +
      '<div class="tim-input-check-row tim-input-check-row--pw">' +
      '<input id="f-password2" type="' +
      (state.showRegPassword ? "text" : "password") +
      '" placeholder="Повтор пароля *" minlength="4" value="' +
      escapeHtml(state.password2 || "") +
      '" autocomplete="new-password">' +
      "</div></div>" +
      btn(cta, { act: "register", disabled: state.busy }) +
      '<p class="tim-reg-legal">Регистрируясь, ты принимаешь условия сервиса</p>' +
      "</div>"
    );
  }

  function channelIsFilled(id) {
    return !!(state.channelConfirmed && state.channelConfirmed[id]);
  }

  function fieldIsConfirmed(key) {
    return !!(state.fieldConfirmed && state.fieldConfirmed[key]);
  }

  function normalizeContactEntry(raw, dual) {
    if (raw && typeof raw === "object" && !Array.isArray(raw)) {
      if (dual) {
        return { user: String(raw.user || "").trim(), phone: String(raw.phone || "").trim() };
      }
      return { value: String(raw.value || raw.user || raw.phone || "").trim() };
    }
    const s = String(raw || "").trim();
    if (dual) {
      if (s.charAt(0) === "@" || (s && !/^\+?\d[\d\s()-]{5,}$/.test(s))) {
        return { user: s, phone: "" };
      }
      return { user: "", phone: s };
    }
    return { value: s };
  }

  function contactValueForApi(id) {
    const c = state.contacts[id];
    if (!c) return "";
    if (typeof c === "string") return c.trim();
    if (id === "max" || id === "telegram") {
      return String(c.user || c.phone || "").trim();
    }
    return String(c.value || "").trim();
  }

  function iconConfirmBtn(fieldKey, on) {
    const src = A.ICONS && A.ICONS.confirmCheck;
    const inner = src
      ? '<img src="' + src + '" alt="" width="44" height="44" decoding="async">'
      : '<span class="tim-confirm-check__mark" aria-hidden="true">✓</span>';
    return (
      '<button type="button" class="tim-confirm-check' +
      (on ? " is-on" : "") +
      '" data-act="social-confirm" data-field="' +
      escapeHtml(fieldKey) +
      '" aria-label="Подтвердить" title="Подтвердить">' +
      inner +
      "</button>"
    );
  }

  function renderSocialFieldRow(inputId, placeholder, value, fieldKey) {
    const on = fieldIsConfirmed(fieldKey);
    return (
      '<div class="tim-field tim-field--social tim-field--check' +
      (on ? " is-ok" : "") +
      '">' +
      '<div class="tim-input-check-row">' +
      '<input id="' +
      escapeHtml(inputId) +
      '" type="text" placeholder="' +
      escapeHtml(placeholder) +
      '" value="' +
      escapeHtml(value || "") +
      '" autocomplete="off" data-social-field="' +
      escapeHtml(fieldKey) +
      '">' +
      iconConfirmBtn(fieldKey, on) +
      "</div></div>"
    );
  }

  function renderSocialsScreen() {
    const socials = [
      ["max", "MAX"],
      ["telegram", "TG"],
      ["vk", "VK"],
      ["whatsapp", "WA"],
      ["email", "Mail"],
    ];
    let icons =
      '<p class="tim-reg-optional">По желанию — ещё один канал</p>' +
      '<div class="tim-channels tim-channels--reg">';
    socials.forEach(function (c) {
      const id = c[0];
      const filled = channelIsFilled(id);
      const cls =
        "tim-ch" +
        (state.activeChannel === id ? " is-active" : "") +
        (filled ? " is-filled" : "");
      icons +=
        '<button type="button" class="' +
        cls +
        '" data-act="ch-' +
        id +
        '" aria-label="' +
        escapeHtml(c[1]) +
        '">' +
        escapeHtml(c[1]) +
        "</button>";
    });
    icons += "</div>";

    // Два слота всегда: поля появляются/исчезают на месте, «Далее» не прыгает
    let slot1 = "";
    let slot2 = "";
    const active = state.activeChannel;
    if (active === "max" || active === "telegram") {
      const entry = normalizeContactEntry(state.contacts[active], true);
      state.contacts[active] = entry;
      slot1 = renderSocialFieldRow("f-social-user", "Юзернейм (@nick)", entry.user, active + "_user");
      slot2 = renderSocialFieldRow("f-social-phone", "Телефон", entry.phone, active + "_phone");
    } else if (active === "vk") {
      const entry = normalizeContactEntry(state.contacts.vk, false);
      state.contacts.vk = entry;
      slot1 = renderSocialFieldRow(
        "f-social-value",
        "ВКонтакте — ссылка на профиль",
        entry.value,
        "vk_value"
      );
    } else if (active === "whatsapp") {
      const entry = normalizeContactEntry(state.contacts.whatsapp, false);
      state.contacts.whatsapp = entry;
      slot1 = renderSocialFieldRow("f-social-value", "WhatsApp — номер", entry.value, "whatsapp_value");
    } else if (active === "email") {
      const entry = normalizeContactEntry(state.contacts.email, false);
      state.contacts.email = entry;
      slot1 = renderSocialFieldRow("f-social-value", "Почта", entry.value, "email_value");
    } else {
      slot1 =
        '<p class="tim-socials__placeholder">Выбери канал — поля появятся здесь</p>';
    }

    return (
      '<div class="tim-reg tim-reg--socials">' +
      icons +
      '<div class="tim-socials__panel" id="tim-socials-panel">' +
      '<div class="tim-socials__slot">' +
      slot1 +
      "</div>" +
      '<div class="tim-socials__slot">' +
      slot2 +
      "</div>" +
      "</div>" +
      '<div class="tim-socials__dock">' +
      btn("Далее", { act: "socials-next", noarrow: true }) +
      "</div></div>"
    );
  }

  function renderFioScreen() {
    const cta = state.pendingDreamSave
      ? state.busy
        ? "Отправляю…"
        : "Отправить на остров"
      : state.busy
        ? "Регистрация…"
        : "Далее";
    return (
      '<div class="tim-reg tim-reg--fio">' +
      field("f-surname", "Фамилия*", state.surname) +
      field("f-patronymic", "Отчество", state.patronymic) +
      btn(cta, { act: "fio-next", disabled: state.busy, noarrow: true }) +
      "</div>"
    );
  }

  /** Экран 6 — резюме: PWA / ВК / браузер → ЛК */
  function renderResumeScreen() {
    const installed = !!(state.pwaInstalledUi || pwaAlreadyStandalone());
    const installBlock = installed
      ? '<div class="tim-pwa-installed" role="status">' +
        '<img class="tim-pwa-installed__ico" src="/assets/icons/icon-192.png" alt="" width="64" height="64">' +
        '<p class="tim-pwa-installed__text">Ваше приложение установлено — ищи иконку «Остров» на экране телефона</p>' +
        "</div>"
      : btn("Установить приложение", { act: "pwa-install", noarrow: true });

    return (
      '<div class="tim-reg tim-reg--resume">' +
      '<p class="tim-resume-lead">Добро пожаловать на Остров.<br>Мечты сохранены — выбери, как продолжить.</p>' +
      installBlock +
      '<a class="tim-btn tim-btn--soft tim-btn--noarrow" href="https://vk.ru/islanddreams" target="_blank" rel="noopener noreferrer">Группа ВКонтакте</a>' +
      btn("Перейти в личный кабинет", { act: "pwa-browser", soft: true, noarrow: true }) +
      "</div>"
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

  function hasWholeWord(text) {
    return /\S+/.test(String(text || "").trim());
  }

  function iconDelete() {
    const src = (A.ICONS && A.ICONS.deleteDream) || "assets/v2/icon_delete_dream_128.png";
    return '<img class="tim-ico" src="' + src + '" alt="" width="36" height="36" decoding="async">';
  }

  function iconSendPlane() {
    const src = A.ICONS && A.ICONS.sendDream;
    if (src) {
      return '<img class="tim-send-ico" src="' + src + '" alt="" width="40" height="40" decoding="async">';
    }
    return (
      '<svg class="tim-send-ico" viewBox="0 0 24 24" aria-hidden="true">' +
      '<path fill="currentColor" d="M3.4 20.6 21 12 3.4 3.4l-.1 6.7L15 12 3.3 13.9l.1 6.7z"/>' +
      "</svg>"
    );
  }

  function sendDreamsLabel(n) {
    return "Отправить " + n + " " + dreamWordAccusative(n) + " Тиму";
  }

  function renderSendCta(n) {
    return (
      '<button type="button" class="tim-btn tim-btn--noarrow tim-btn--send" data-act="dream-save"' +
      (state.busy ? " disabled" : "") +
      ">" +
      iconSendPlane() +
      "<span>" +
      escapeHtml(state.busy ? "Отправляю…" : sendDreamsLabel(n)) +
      "</span></button>"
    );
  }

  function renderDoneCta() {
    return btn("Готово!", { act: "dream-done", noarrow: true });
  }

  function isComposeFocused() {
    const el = document.getElementById("f-dream-new");
    return !!(el && document.activeElement === el);
  }

  function readDraftDream() {
    const el = document.getElementById("f-dream-new");
    return el ? el.value.trim() : String(state.dreamText || "").trim();
  }

  /** Сколько мечт уйдёт Тиму: корзина + недописанный черновик (считаем дописанным). */
  function effectiveSendCount() {
    const n = basketCount();
    return hasWholeWord(readDraftDream()) ? n + 1 : n;
  }

  function commitDraftDreamIfAny() {
    const draft = readDraftDream();
    if (!hasWholeWord(draft)) return false;
    if (state.dreamBasket.length >= 20) return false;
    state.dreamBasket.push(draft);
    state.dreamText = "";
    const el = document.getElementById("f-dream-new");
    if (el) el.value = "";
    return true;
  }

  function updateVitrineCta() {
    const dock = els.body.querySelector(".tim-vitrine__dock");
    let ctaWrap = document.getElementById("tim-vitrine-cta");
    let html = "";
    // Клавиатура открыта → «Готово!» (= «+» для черновика + снять фокус)
    if (isComposeFocused()) {
      html = renderDoneCta();
    } else {
      const sendN = effectiveSendCount();
      if (sendN >= 1) html = renderSendCta(sendN);
    }
    if (!html) {
      if (ctaWrap) ctaWrap.remove();
      return;
    }
    if (!ctaWrap && dock) {
      ctaWrap = document.createElement("div");
      ctaWrap.className = "tim-vitrine__cta";
      ctaWrap.id = "tim-vitrine-cta";
      dock.appendChild(ctaWrap);
    }
    if (!ctaWrap) return;
    ctaWrap.innerHTML = html;
    ctaWrap.querySelectorAll("[data-act]").forEach(function (el) {
      el.addEventListener("click", function () {
        onAct(el.getAttribute("data-act"), null);
      });
    });
  }

  /** Сброс «уезда» страницы после клавиатуры (синее небо под сценой). */
  function resetPageScroll() {
    try {
      window.scrollTo(0, 0);
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
    } catch (_) {}
  }

  /** Пока клавиатура открыта — поднять карточку; список — только внутри stage, без scrollIntoView. */
  function syncVitrineKeyboardLayout() {
    if (!(state.screen === 3 || state.screen === "3" || state.screen === 7)) return;
    const focused = isComposeFocused();
    const vv = window.visualViewport;
    const fullH = window.innerHeight || 0;
    const kbOpen = !!(focused || (vv && fullH - vv.height > 100));
    const wasKb = els.screen && els.screen.classList.contains("is-kb");
    if (els.screen) els.screen.classList.toggle("is-kb", kbOpen);

    const layout = (A.CARD_LAYOUT && A.CARD_LAYOUT[3]) || { top: 880 };
    let top = layout.top;
    if (state.dreamBasket && state.dreamBasket.length) {
      top = Math.max(top, 1040);
    }
    if (kbOpen) {
      // временно выше: первая мечта остаётся в видимой зоне над клавиатурой
      top = Math.min(top, 620);
    }
    els.card.style.top = top + "px";

    const listStage = els.body.querySelector(".tim-vitrine__stage");
    if (listStage && kbOpen) listStage.scrollTop = 0;

    // После закрытия клавиатуры — вернуть страницу наверх (иначе синяя полоса body)
    if (wasKb && !kbOpen) {
      resetPageScroll();
      fitTimCanvas();
    }
  }

  function renderDreamVitrine() {
    const list = state.dreamBasket;
    const draft = state.dreamText || "";
    const canPlus = hasWholeWord(draft);
    const n = list.length;

    let rows = "";
    if (list.length) {
      list.forEach(function (text, i) {
        rows +=
          '<li class="tim-vitrine-item">' +
          '<span class="tim-vitrine-item__num">' +
          escapeHtml(String(i + 1)) +
          "</span>" +
          '<input type="text" class="tim-vitrine-item__text" data-dream-edit="' +
          i +
          '" value="' +
          escapeHtml(text) +
          '" aria-label="Мечта ' +
          (i + 1) +
          '">' +
          '<button type="button" class="tim-ico-btn tim-ico-btn--del" data-act="basket-del" data-i="' +
          i +
          '" aria-label="Удалить мечту ' +
          (i + 1) +
          '">' +
          iconDelete() +
          "</button></li>";
      });
      rows = '<ul class="tim-vitrine-list">' + rows + "</ul>";
    } else {
      rows = '<p class="tim-vitrine-empty" aria-hidden="true"></p>';
    }

    const sendN = n + (hasWholeWord(draft) ? 1 : 0);
    const cta = !isComposeFocused() && sendN >= 1 ? renderSendCta(sendN) : "";

    const ph =
      n >= 1
        ? A.DREAM_PLACEHOLDER_MORE || "Добавь ещё одну мечту"
        : A.DREAM_PLACEHOLDER || "Напиши мечту своими словами";

    return (
      '<div class="tim-vitrine' +
      (n ? " has-items" : "") +
      '">' +
      '<div class="tim-vitrine__stage">' +
      rows +
      "</div>" +
      '<div class="tim-vitrine__dock">' +
      '<div class="tim-vitrine__compose">' +
      '<label class="tim-sr-only" for="f-dream-new">Новая мечта</label>' +
      '<input id="f-dream-new" class="tim-vitrine__input" type="text" autocomplete="off" placeholder="' +
      escapeHtml(ph) +
      '" value="' +
      escapeHtml(draft) +
      '">' +
      '<button type="button" class="tim-vitrine__plus' +
      (canPlus ? "" : " is-disabled") +
      '" data-act="dream-plus" aria-label="Добавить мечту в витрину"' +
      (canPlus ? "" : " disabled") +
      ">+</button></div>" +
      (cta ? '<div class="tim-vitrine__cta" id="tim-vitrine-cta">' + cta + "</div>" : "") +
      "</div></div>"
    );
  }

  function refreshDreamScreen(opts) {
    const o = opts || {};
    if (o.clearDraft) {
      state.dreamText = "";
    } else {
      const draftEl = document.getElementById("f-dream-new");
      if (draftEl) state.dreamText = draftEl.value;
    }
    if (state.screen === 3 || state.screen === "3" || state.screen === 7) {
      applyScene(3);
      state.screen = 3;
      renderCard();
      resetPageScroll();
      // После «+» не возвращаем фокус — иначе снова клавиатура и «уезд» экрана
      if (!o.clearDraft) {
        const again = document.getElementById("f-dream-new");
        if (again) {
          try {
            again.focus({ preventScroll: true });
            const len = again.value.length;
            again.setSelectionRange(len, len);
          } catch (_) {
            try {
              again.focus();
            } catch (__) {}
          }
        }
      }
      return;
    }
    renderCard();
  }

  function syncVitrineDock() {
    const draft = readDraftDream();
    state.dreamText = draft;
    const plus = els.body.querySelector(".tim-vitrine__plus");
    const canPlus = hasWholeWord(draft);
    if (plus) {
      plus.disabled = !canPlus;
      plus.classList.toggle("is-disabled", !canPlus);
    }
    updateVitrineCta();
    syncVitrineKeyboardLayout();
  }

  function commitDreamEditsFromDom() {
    els.body.querySelectorAll("[data-dream-edit]").forEach(function (inp) {
      const i = Number(inp.getAttribute("data-dream-edit"));
      if (Number.isNaN(i) || i < 0 || i >= state.dreamBasket.length) return;
      const t = inp.value.trim();
      if (t) state.dreamBasket[i] = t;
    });
  }

  function bindVitrine() {
    const input = document.getElementById("f-dream-new");
    if (input) {
      input.addEventListener("input", syncVitrineDock);
      input.addEventListener("focus", function () {
        syncVitrineDock();
        setTimeout(syncVitrineKeyboardLayout, 50);
        setTimeout(syncVitrineKeyboardLayout, 280);
      });
      input.addEventListener("blur", function () {
        setTimeout(function () {
          syncVitrineDock();
          syncVitrineKeyboardLayout();
        }, 120);
      });
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          onAct("dream-plus");
        }
      });
    }
    els.body.querySelectorAll("[data-dream-edit]").forEach(function (inp) {
      inp.addEventListener("blur", function () {
        const i = Number(inp.getAttribute("data-dream-edit"));
        const t = inp.value.trim();
        if (Number.isNaN(i) || i < 0) return;
        if (!t) {
          setError("Пустую мечту лучше удалить крестиком.");
          inp.value = state.dreamBasket[i] || "";
          return;
        }
        state.dreamBasket[i] = t;
        setError("");
      });
      inp.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          inp.blur();
        }
      });
      inp.addEventListener("focus", function () {
        setTimeout(syncVitrineKeyboardLayout, 50);
      });
    });
    syncVitrineKeyboardLayout();
  }

  function bindCard() {
    els.body.querySelectorAll("[data-act]").forEach(function (el) {
      el.addEventListener("click", function () {
        const act = el.getAttribute("data-act");
        if (act === "dial-pick") {
          const code = el.getAttribute("data-code") || "+7";
          readRegFields();
          state.dialCode = code;
          const p = document.getElementById("f-phone");
          if (p) state.phone = fullPhone(p.value);
          state.dialPickerOpen = false;
          renderCard();
          return;
        }
        if (act === "social-confirm") {
          onSocialConfirm(el.getAttribute("data-field") || "");
          return;
        }
        const iAttr = el.getAttribute("data-i");
        onAct(act, iAttr != null ? Number(iAttr) : null);
      });
    });
    if (state.screen === 1) bindCitySuggest();
    if (state.screen === 2) bindVideoScreen();
    if (state.screen === 3 || state.screen === 7) bindVitrine();
    if (state.screen === 4 || state.screen === "login") bindAccountChecks();
    if (state.screen === 5) bindSocialInputs();
  }

  function bindAccountChecks() {
    ["f-name", "f-city"].forEach(function (id) {
      const input = document.getElementById(id);
      if (!input) return;
      const wrap = input.closest(".tim-field--check");
      input.addEventListener("input", function () {
        if (wrap) wrap.classList.toggle("is-ok", !!input.value.trim());
      });
    });
  }

  function syncSocialChips() {
    els.body.querySelectorAll(".tim-ch[data-act]").forEach(function (btn) {
      const act = btn.getAttribute("data-act") || "";
      if (act.indexOf("ch-") !== 0) return;
      const id = act.slice(3);
      btn.classList.toggle("is-filled", channelIsFilled(id));
      btn.classList.toggle("is-active", state.activeChannel === id);
    });
  }

  function readSocialPanelIntoState() {
    const active = state.activeChannel;
    if (!active || active === "other") return;
    if (active === "max" || active === "telegram") {
      const u = document.getElementById("f-social-user");
      const p = document.getElementById("f-social-phone");
      state.contacts[active] = {
        user: u ? u.value.trim() : "",
        phone: p ? p.value.trim() : "",
      };
      return;
    }
    const v = document.getElementById("f-social-value");
    state.contacts[active] = { value: v ? v.value.trim() : "" };
  }

  function onSocialConfirm(fieldKey) {
    if (!fieldKey) return;
    readSocialPanelIntoState();
    const parts = fieldKey.split("_");
    const channel = parts[0];
    const kind = parts.slice(1).join("_") || "value";
    let val = "";
    if (channel === "max" || channel === "telegram") {
      const entry = normalizeContactEntry(state.contacts[channel], true);
      state.contacts[channel] = entry;
      val = kind === "phone" ? entry.phone : entry.user;
    } else {
      const entry = normalizeContactEntry(state.contacts[channel], false);
      state.contacts[channel] = entry;
      val = entry.value;
    }
    if (!val) {
      setError("Сначала заполни поле, потом галочку.");
      return;
    }
    setError("");
    if (!state.fieldConfirmed) state.fieldConfirmed = {};
    state.fieldConfirmed[fieldKey] = true;
    if (!state.channelConfirmed) state.channelConfirmed = {};
    state.channelConfirmed[channel] = true;
    saveContactsDraft();
    renderCard();
  }

  function bindSocialInputs() {
    els.body.querySelectorAll("[data-social-field]").forEach(function (input) {
      input.addEventListener("input", function () {
        readSocialPanelIntoState();
        const key = input.getAttribute("data-social-field");
        if (key && state.fieldConfirmed && state.fieldConfirmed[key]) {
          state.fieldConfirmed[key] = false;
          const wrap = input.closest(".tim-field--check");
          if (wrap) wrap.classList.remove("is-ok");
          const btn = wrap && wrap.querySelector(".tim-confirm-check");
          if (btn) btn.classList.remove("is-on");
        }
      });
    });
  }

  function markVideoWatched() {
    if (state.videoWatched) return;
    state.videoWatched = true;
    renderCard();
  }

  function closeAboutVideoFs() {
    const root = document.getElementById("tim-video-fs");
    if (!root) return;
    const video = root.querySelector("video");
    if (video) {
      try {
        video.pause();
      } catch (e) {}
    }
    root.hidden = true;
    document.body.classList.remove("tim-video-fs-open");
  }

  function openAboutVideoFs() {
    const cfg = A.ABOUT_VIDEO || {};
    const src = (cfg.src || "").trim();
    if (!src) return;

    let root = document.getElementById("tim-video-fs");
    if (!root) {
      root = document.createElement("div");
      root.id = "tim-video-fs";
      root.className = "tim-video-fs";
      root.setAttribute("role", "dialog");
      root.setAttribute("aria-modal", "true");
      root.setAttribute("aria-label", "Видео об Острове");
      root.innerHTML =
        '<button type="button" class="tim-video-fs__close" id="tim-video-fs-close" aria-label="Закрыть">×</button>' +
        '<div class="tim-video-fs__frame">' +
        '<video id="about-video-fs" controls playsinline webkit-playsinline preload="metadata"></video>' +
        "</div>";
      document.body.appendChild(root);
      root.addEventListener("click", function (e) {
        if (e.target === root) closeAboutVideoFs();
      });
      const closeBtn = document.getElementById("tim-video-fs-close");
      if (closeBtn) {
        closeBtn.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopPropagation();
          closeAboutVideoFs();
        });
      }
      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") closeAboutVideoFs();
      });
    }

    const video = root.querySelector("video");
    if (video) {
      if (video.getAttribute("src") !== src) {
        video.setAttribute("src", src);
        video.load();
      }
      video.onended = function () {
        markVideoWatched();
      };
      video.onplay = function () {
        markVideoWatched();
      };
    }

    root.hidden = false;
    document.body.classList.add("tim-video-fs-open");
    markVideoWatched();
    if (video) {
      const playPromise = video.play();
      if (playPromise && typeof playPromise.catch === "function") {
        playPromise.catch(function () {});
      }
    }
  }

  function bindVideoScreen() {
    /* полноэкран открывается по data-act=video-open */
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
    const pat = document.getElementById("f-patronymic");
    const p = document.getElementById("f-phone");
    const pw = document.getElementById("f-password");
    const pw2 = document.getElementById("f-password2");
    if (s) state.surname = s.value.trim();
    if (pat) state.patronymic = pat.value.trim();
    if (p) state.phone = fullPhone(p.value);
    if (pw) state.password = pw.value;
    if (pw2) state.password2 = pw2.value;
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
    if (act === "video-open") {
      openAboutVideoFs();
      return;
    }
    if (act === "about-next" || act === "about-skip") {
      go(4);
      return;
    }
    if (act === "dial-open") {
      readRegFields();
      state.dialPickerOpen = !state.dialPickerOpen;
      renderCard();
      return;
    }
    if (act === "pw-toggle") {
      readRegFields();
      state.showRegPassword = !state.showRegPassword;
      renderCard();
      return;
    }
    if (act === "auth-next") {
      // совместимость: сразу форма аккаунта
      go(4);
      return;
    }
    if (act === "socials-next") {
      readSocialPanelIntoState();
      saveContactsDraft();
      state.activeChannel = null;
      state.busy = true;
      renderCard();
      try {
        await saveContactsToServer();
      } catch (_) {}
      state.busy = false;
      if (state.pendingDreamSave) {
        await saveDreams();
        return;
      }
      afterContacts();
      return;
    }
    if (act === "fio-next" || act === "register") {
      await doRegister();
      return;
    }
    if (act.indexOf("ch-") === 0) {
      readSocialPanelIntoState();
      const next = act.slice(3);
      state.activeChannel = state.activeChannel === next ? null : next;
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
      window.location.href = lkUrl();
      return;
    }
    if (act === "dream-hint") {
      setError("Напиши мечту в поле внизу, потом нажми «+».");
      const el = document.getElementById("f-dream-new");
      if (el) el.focus();
      return;
    }
    if (act === "dream-done") {
      // Как «+»: недописанный черновик → в витрину; затем обычный экран (отправка)
      commitDreamEditsFromDom();
      const text = readDraftDream();
      if (hasWholeWord(text)) {
        if (state.dreamBasket.length >= 20) {
          setError("Пока максимум 20 мечт за раз.");
          return;
        }
        state.dreamBasket.push(text);
        setError("");
        refreshDreamScreen({ clearDraft: true });
        resetPageScroll();
        setTimeout(function () {
          syncVitrineDock();
          syncVitrineKeyboardLayout();
        }, 80);
        return;
      }
      const el = document.getElementById("f-dream-new");
      if (el) el.blur();
      setError("");
      setTimeout(function () {
        syncVitrineDock();
        syncVitrineKeyboardLayout();
      }, 80);
      return;
    }
    if (act === "dream-plus") {
      commitDreamEditsFromDom();
      const text = readDraftDream();
      if (!hasWholeWord(text)) {
        setError("Напиши хотя бы одно слово.");
        return;
      }
      if (state.dreamBasket.length >= 20) {
        setError("Пока максимум 20 мечт за раз.");
        return;
      }
      state.dreamBasket.push(text);
      setError("");
      refreshDreamScreen({ clearDraft: true });
      return;
    }
    if (act === "basket-del") {
      commitDreamEditsFromDom();
      const i = index;
      if (i == null || i < 0 || i >= state.dreamBasket.length) return;
      state.dreamBasket.splice(i, 1);
      setError("");
      refreshDreamScreen();
      return;
    }
    if (act === "dream-save") {
      commitDreamEditsFromDom();
      // Черновик в поле = дописанная мечта (без обязательного «+»)
      commitDraftDreamIfAny();
      if (!state.dreamBasket.length) {
        setError("Сначала напиши хотя бы одну мечту.");
        return;
      }
      // Happy-path: 3 → 4 → 5 (не прыгать на соцсети, даже если есть savedUser)
      state.pendingDreamSave = true;
      state.pendingDreams = state.dreamBasket.slice();
      resetPageScroll();
      go(4);
      return;
    }
    if (act === "again-dream") {
      state.dreamText = "";
      state.dreamBasket = [];
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
    if (!active) return;
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
    readSocialPanelIntoState();
  }

  function saveContactsDraft() {
    try {
      localStorage.setItem(
        CONTACTS_DRAFT_KEY,
        JSON.stringify({
          contacts: state.contacts,
          channelConfirmed: state.channelConfirmed,
          fieldConfirmed: state.fieldConfirmed,
        })
      );
    } catch (_) {}
  }

  function loadContactsDraft() {
    try {
      const raw = localStorage.getItem(CONTACTS_DRAFT_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      const src = data && data.contacts ? data.contacts : data;
      if (!src || typeof src !== "object") return;
      ["max", "telegram"].forEach(function (id) {
        if (src[id] != null) state.contacts[id] = normalizeContactEntry(src[id], true);
      });
      ["vk", "whatsapp", "email", "ok", "facebook"].forEach(function (id) {
        if (src[id] != null) state.contacts[id] = normalizeContactEntry(src[id], false);
      });
      if (Array.isArray(src.other)) state.contacts.other = src.other;
      if (data.channelConfirmed) state.channelConfirmed = data.channelConfirmed;
      if (data.fieldConfirmed) state.fieldConfirmed = data.fieldConfirmed;
    } catch (_) {}
  }

  async function saveContactsToServer() {
    saveContactsDraft();
    const user = state.user || readSavedUser();
    if (!user || !user.id) return;
    const body = { user_id: user.id };
    const tg = contactValueForApi("telegram");
    const vk = contactValueForApi("vk");
    if (tg) body.telegram = tg;
    if (vk) body.vk = vk;
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
    // Резюме: PWA / ВК / браузер → ЛК
    go(6);
  }

  async function doPwaInstall() {
    markPwaDone();
    if (state.deferredInstall) {
      try {
        state.deferredInstall.prompt();
        await state.deferredInstall.userChoice;
      } catch (_) {}
      state.deferredInstall = null;
    } else if (!pwaAlreadyStandalone()) {
      const isIos = /iPad|iPhone|iPod/.test(navigator.userAgent || "");
      if (isIos) {
        setError("iPhone: «Поделиться» → «На экран „Домой“», потом ищи иконку «Остров».");
      } else {
        setError(
          "Если диалог не появился: меню ⋮ → «Установить приложение» / «Добавить на главный экран»."
        );
      }
    }
    // Остаёмся на экране 6: кнопка → «установлено»
    state.pwaInstalledUi = true;
    renderCard();
  }

  async function doRegister() {
    persistContactField();
    readRegFields();
    if (!state.name || !state.city) {
      setError("Нужны имя и город.");
      return;
    }
    if (!state.password) {
      setError("Придумай пароль для входа.");
      return;
    }
    if (state.password.length < 4) {
      setError("Пароль — минимум 4 символа.");
      return;
    }
    if (!state.password2) {
      setError("Повтори пароль.");
      return;
    }
    if (state.password !== state.password2) {
      setError("Пароли не совпадают.");
      return;
    }
    if (!phoneLooksOk()) {
      setError(
        (state.dialCode || "+7") === "+7"
          ? "Проверь телефон: 10 цифр после кода страны."
          : "Проверь номер телефона."
      );
      return;
    }
    try {
      localStorage.setItem(
        "tim_patronymic",
        JSON.stringify({ patronymic: state.patronymic || "", at: Date.now() })
      );
    } catch (_) {}
    state.busy = true;
    renderCard();
    try {
      const res = await fetch(apiBase() + "/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: state.name,
          surname: state.surname || "",
          phone: state.phone,
          city: state.city,
          password: state.password,
          telegram: contactValueForApi("telegram") || null,
          vk: contactValueForApi("vk") || null,
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
      // Соцсети — следующий экран на той же обложке
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
    if (!phoneLooksOk() || !state.password) {
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
          body: JSON.stringify({
            user_id: user.id,
            dream: dreams[i],
            // status_id 2 = «Сейчас» в ЛК (дефолтный фильтр); 1 = «План» — мечты «пропадали»
            status_id: 2,
            is_public: true,
          }),
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
      // Резюме: установка / ВК / браузер → ЛК
      go(6);
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
    window.addEventListener("resize", function () {
      fitTimCanvas();
      syncVitrineKeyboardLayout();
    });
    if (window.visualViewport) {
      window.visualViewport.addEventListener("resize", function () {
        fitTimCanvas();
        syncVitrineKeyboardLayout();
      });
      window.visualViewport.addEventListener("scroll", syncVitrineKeyboardLayout);
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
    loadContactsDraft();
    fitTimCanvas();
    const screenParam = (location.search || "").match(/[?&]screen=(\d+|login|fio|pwa)/);
    if (screenParam) {
      const raw = screenParam[1];
      if (raw === "login" || raw === "fio" || raw === "pwa") go(raw);
      else go(parseInt(raw, 10));
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
