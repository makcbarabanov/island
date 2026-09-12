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
    interpreted: null, // { dreams: [{title}], understood, ambiguous }
    busy: false,
    deferredInstall: null,
    videoWatched: false,
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
    els.scene.src = A.SCENE[key] || A.SCENE[1];
    els.scene.setAttribute("width", String(designW));
    els.scene.setAttribute("height", String(designH));

    const layout = (A.CARD_LAYOUT && A.CARD_LAYOUT[key]) || { left: 61, top: 850, width: 819 };
    els.card.style.left = layout.left + "px";
    els.card.style.top = layout.top + "px";
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
      (o.disabled || o.locked ? " disabled" : "") +
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
      const cfg = A.ABOUT_VIDEO || {};
      const hasVideo = !!(cfg.src && cfg.src.trim());
      html =
        '<div class="tim-video">' +
        (hasVideo
          ? '<video id="about-video" controls playsinline preload="metadata" src="' +
            escapeHtml(cfg.src) +
            '"' +
            (cfg.poster ? ' poster="' + escapeHtml(cfg.poster) + '"' : "") +
            "></video>"
          : '<div class="tim-video__ph">' + escapeHtml(cfg.placeholderLabel || "Видео скоро появится") + "</div>") +
        "</div>" +
        btn("Продолжить", { act: "about-next" }) +
        '<button type="button" class="tim-link" data-act="about-skip">Пропустить и перейти дальше</button>';
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
      html =
        '<div class="tim-field"><label for="f-dream">Твоя мечта</label><textarea id="f-dream" placeholder="Хочу свозить маму на море и чтобы она больше путешествовала…">' +
        escapeHtml(state.dreamText) +
        "</textarea></div>" +
        '<div class="tim-modes">' +
        '<button type="button" class="tim-mode is-on" disabled>Текст</button>' +
        '<button type="button" class="tim-mode" disabled>Голосом · скоро</button>' +
        '<button type="button" class="tim-mode" disabled>Файлом · скоро</button>' +
        "</div>" +
        btn(state.busy ? "Думаю…" : "Далее", { act: "dream-next", disabled: state.busy });
    } else if (s === 8) {
      html = renderInterpret();
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

  function renderInterpret() {
    const data = state.interpreted || { dreams: [{ title: state.dreamText }], understood: state.dreamText };
    const list = (data.dreams || []).map(function (d, i) {
      const title = typeof d === "string" ? d : d.title || "";
      return (
        '<div class="dream-item"><input data-dream-i="' +
        i +
        '" value="' +
        escapeHtml(title) +
        '"><div class="meta">✏ можно поправить</div></div>'
      );
    });
    return (
      (data.understood
        ? '<p class="lead">' + escapeHtml(data.understood) + "</p>"
        : "") +
      '<div class="dream-list">' +
      list.join("") +
      "</div>" +
      btn("Исправить", { act: "dream-fix", soft: true, noarrow: true }) +
      btn(state.busy ? "Сохраняю…" : "Да, сохранить", { act: "dream-save", disabled: state.busy })
    );
  }

  function bindCard() {
    els.body.querySelectorAll("[data-act]").forEach(function (el) {
      el.addEventListener("click", function () {
        onAct(el.getAttribute("data-act"));
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

  async function onAct(act) {
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
      if (!state.videoWatched) {
        setError("Сначала посмотри видео (пока можно нажать на заглушку).");
        return;
      }
      // этап 2 = видео; старый экран 3 пропускаем → регистрация (пока каркас 1–9)
      go(4);
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
      go(7);
      return;
    }
    if (act === "dream-next") {
      const ta = document.getElementById("f-dream");
      state.dreamText = ta ? ta.value.trim() : "";
      if (!state.dreamText) {
        setError("Напиши мечту — хотя бы пару слов.");
        return;
      }
      await interpretDream();
      return;
    }
    if (act === "dream-fix") {
      go(7);
      return;
    }
    if (act === "dream-save") {
      await saveDreams();
      return;
    }
    if (act === "again-dream") {
      state.dreamText = "";
      state.interpreted = null;
      go(7);
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
      go(7);
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
      go(7);
      return;
    }
    setError("На iPhone: «Поделиться» → «На экран „Домой“». На Android установка может быть в меню браузера.");
    // всё равно пускаем дальше по кнопке «Открыть в браузере» — здесь не блокируем
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

  async function interpretDream() {
    state.busy = true;
    renderCard();
    try {
      const res = await fetch(apiBase() + "/api/v1/dream-interpret", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: state.dreamText }),
      });
      const data = await res.json().catch(function () {
        return {};
      });
      if (!res.ok) throw new Error("ai");
      const dreams = Array.isArray(data.dreams) && data.dreams.length ? data.dreams : [state.dreamText];
      state.interpreted = {
        understood: data.understood || "Я так понял твою мечту:",
        dreams: dreams.map(function (d) {
          return typeof d === "string" ? { title: d } : { title: d.title || String(d) };
        }),
        ambiguous: !!data.ambiguous,
      };
      state.busy = false;
      go(8);
    } catch (_) {
      // fallback: исходный текст
      state.interpreted = {
        understood: "Пока не удалось уточнить у модели — сохрани, как написала/написал, или поправь.",
        dreams: [{ title: state.dreamText }],
        ambiguous: true,
      };
      state.busy = false;
      go(8);
    }
  }

  function collectEditedDreams() {
    const inputs = els.body.querySelectorAll("input[data-dream-i]");
    const out = [];
    inputs.forEach(function (inp) {
      const t = inp.value.trim();
      if (t) out.push(t);
    });
    return out.length ? out : [state.dreamText];
  }

  async function saveDreams() {
    const user = state.user || readSavedUser();
    if (!user || !user.id) {
      setError("Нет сессии. Войди снова.");
      return;
    }
    const dreams = collectEditedDreams();
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
