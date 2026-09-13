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
      whatsapp: "",
      email: "",
      ok: "",
      facebook: "",
      other: [],
    },
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

    // Экран 3 (витрина): 0 мечт — «запиши»; ≥1 — «Вау, какая мечта!»
    if (key === 3 || key === "3") {
      if (state.dreamBasket && state.dreamBasket.length && A.confirmSceneForCount) {
        els.scene.src = A.confirmSceneForCount(state.dreamBasket.length);
      } else {
        els.scene.src = A.SCENE[3] || A.SCENE[1];
      }
    } else if ((key === 8 || key === "8") && A.confirmSceneForCount) {
      els.scene.src = A.confirmSceneForCount(state.dreamBasket.length || 1);
    } else {
      els.scene.src = A.SCENE[key] || A.SCENE[1];
    }
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
      html = renderDreamVitrine();
    } else if (s === 4) {
      html = renderRegisterScreen();
    } else if (s === 5) {
      html = renderContacts();
    } else if (s === 6) {
      html =
        '<h2>Установить как приложение?</h2><p class="lead">Так Остров будет всегда под рукой. Предложение один раз — потом можно найти установку в профиле.</p>' +
        btn("Установить", { act: "pwa-install", noarrow: true }) +
        btn("Открыть в браузере", { act: "pwa-browser", soft: true, noarrow: true }) +
        '<button type="button" class="tim-link" data-act="pwa-later">Позже</button>';
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

  function renderRegisterScreen() {
    const n = basketCount() || (state.pendingDreams && state.pendingDreams.length) || 0;
    const lead =
      n > 0
        ? "Супер, я вижу твои " +
          n +
          " " +
          dreamWordAccusative(n) +
          "! Чтобы отправить их на остров, оставь хотя бы один контакт для связи с тобой."
        : "Чтобы попасть на остров, оставь хотя бы один контакт для связи с тобой.";

    const socials = [
      ["max", "MAX"],
      ["telegram", "TG"],
      ["vk", "VK"],
      ["whatsapp", "WA"],
      ["email", "Mail"],
    ];
    let icons = '<p class="tim-reg-optional">По желанию — ещё один канал</p><div class="tim-channels tim-channels--reg">';
    socials.forEach(function (c) {
      const id = c[0];
      const filled = !!(state.contacts[id] && String(state.contacts[id]).trim());
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

    let socialField = "";
    const active = state.activeChannel;
    if (active) {
      const meta = {
        max: { label: "MAX — ник или номер", ph: "@nick или +7…" },
        telegram: { label: "Telegram — @username или номер", ph: "@username или +7…" },
        vk: { label: "ВКонтакте — ссылка на профиль", ph: "https://vk.com/…" },
        whatsapp: { label: "WhatsApp — номер (этот или другой)", ph: "9001234567" },
        email: { label: "Почта", ph: "you@example.com" },
      };
      const m = meta[active] || { label: "Контакт", ph: "" };
      socialField =
        '<div class="tim-field tim-field--social">' +
        '<label for="f-contact-value">' +
        escapeHtml(m.label) +
        "</label>" +
        '<input id="f-contact-value" type="text" placeholder="' +
        escapeHtml(m.ph) +
        '" value="' +
        escapeHtml(state.contacts[active] || "") +
        '"></div>';
    }

    const ctaLabel = state.pendingDreamSave
      ? state.busy
        ? "Отправляю…"
        : "Отправить на остров"
      : state.busy
        ? "Регистрация…"
        : "Далее";

    return (
      '<div class="tim-reg">' +
      '<p class="tim-reg-lead">' +
      escapeHtml(lead) +
      "</p>" +
      '<div class="tim-field"><label for="f-phone">Телефон*</label><div class="tim-phone-row"><span class="tim-phone-code">+7</span><input id="f-phone" inputmode="numeric" value="' +
      escapeHtml(digitsOnly(state.phone).replace(/^8/, "").replace(/^\+?7/, "")) +
      '" placeholder="9001234567"></div></div>' +
      field("f-password", "Пароль для входа в личный кабинет*", state.password, "password") +
      field("f-surname", "Фамилия (чтобы не спутать с другим Максом)*", state.surname) +
      icons +
      socialField +
      btn(ctaLabel, { act: "register", disabled: state.busy, noarrow: true }) +
      "</div>"
    );
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

  function updateVitrineCta() {
    const n = basketCount();
    const dock = els.body.querySelector(".tim-vitrine__dock");
    let ctaWrap = document.getElementById("tim-vitrine-cta");
    let html = "";
    if (isComposeFocused()) {
      html = renderDoneCta();
    } else if (n >= 1 && !hasWholeWord(readDraftDream())) {
      html = renderSendCta(n);
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

    // При фокусе — «Готово!»; без клавы и пустом поле — «Отправить»
    const cta =
      n >= 1 && !hasWholeWord(draft) ? renderSendCta(n) : "";

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
      const again = document.getElementById("f-dream-new");
      if (again) {
        try {
          again.focus();
          const len = again.value.length;
          again.setSelectionRange(len, len);
        } catch (_) {}
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
      input.addEventListener("focus", syncVitrineDock);
      input.addEventListener("blur", function () {
        setTimeout(syncVitrineDock, 120);
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
    });
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
    if (state.screen === 3 || state.screen === 7) bindVitrine();
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
      go(3);
      return;
    }
    if (act === "dream-hint") {
      setError("Напиши мечту в поле внизу, потом нажми «+».");
      const el = document.getElementById("f-dream-new");
      if (el) el.focus();
      return;
    }
    if (act === "dream-done") {
      const el = document.getElementById("f-dream-new");
      if (el) el.blur();
      setError("");
      setTimeout(syncVitrineDock, 80);
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
      if (!state.dreamBasket.length) {
        setError("Сначала добавь хотя бы одну мечту кнопкой «+».");
        return;
      }
      state.pendingDreams = state.dreamBasket.slice();
      await saveDreams();
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
    persistContactField();
    readRegFields();
    if (!state.name || !state.city) {
      setError("Вернись к знакомству: нужны имя и город.");
      return;
    }
    if (!state.surname || !state.password) {
      setError("Нужны фамилия и пароль.");
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
          telegram: state.contacts.telegram || null,
          vk: state.contacts.vk || null,
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
      await saveContactsToServer();
      state.busy = false;
      if (state.pendingDreamSave) {
        await saveDreams();
        return;
      }
      afterContacts();
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
