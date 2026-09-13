/**
 * Tim assets.
 * Экраны 1–3 + 8: baked 1080×2400.
 * 4–5 аккаунт/соцсети: scene_account (обложка без формы).
 * fio: запасной; основной ФИО на экране 4.
 */
(function (global) {
  const FIN = "assets/fin/";
  const V2 = "assets/v2/";

  const DESIGN_LEGACY = { w: 941, h: 1672 };
  const DESIGN_CANON = { w: 1080, h: 2400 };
  const S1 = DESIGN_CANON.w / DESIGN_LEGACY.w;

  /** Сцена: lite (быстрый JPEG) → full (WebP). Строка = один URL без апгрейда (fin/). */
  function scenePair(base) {
    return {
      lite: V2 + base + "_lite.jpg",
      full: V2 + base + ".webp",
    };
  }

  const ACCOUNT_SCENE = scenePair("scene_account_1080x2400");
  const FIO_SCENE = FIN + "15.png";

  const SCENE = {
    1: scenePair("scene_01_welcome_1080x2400"),
    2: scenePair("scene_02_video_1080x2400"),
    3: scenePair("scene_03_dream_1080x2400"),
    4: ACCOUNT_SCENE,
    5: ACCOUNT_SCENE,
    6: FIN + "15.png",
    7: FIN + "16.png",
    8: scenePair("scene_04_confirm_many_1080x2400"),
    9: FIN + "18.png",
    fio: FIO_SCENE,
    pwa: FIN + "16.png",
    login: ACCOUNT_SCENE,
    confirmOne: scenePair("scene_04_confirm_one_1080x2400"),
    confirmMany: scenePair("scene_04_confirm_many_1080x2400"),
  };

  function sceneUrls(entry) {
    if (!entry) return { lite: "", full: "" };
    if (typeof entry === "string") return { lite: entry, full: entry };
    return {
      lite: entry.lite || entry.full || "",
      full: entry.full || entry.lite || "",
    };
  }

  /** Без отдельного bubble/plaque — как песок на 1–3; пузырь не закрывает лицо. */
  const BAKED_SCENE = {
    1: true,
    2: true,
    3: true,
    4: true,
    5: true,
    8: true,
    fio: true,
    login: true,
  };

  const BUBBLE = {
    1: null,
    2: null,
    3: null,
    4: null,
    5: null,
    6: FIN + "20.png",
    7: FIN + "8.png",
    8: null,
    9: FIN + "21.png",
    fio: null,
    pwa: FIN + "20.png",
    login: FIN + "19.png",
  };

  const DECOR = {
    tagline: FIN + "10.png",
    plaque: FIN + "22.png",
  };

  const ICONS = {
    editDream: V2 + "icon_edit_dream_128.png",
    deleteDream: V2 + "icon_delete_dream_128.png",
    sendDream: V2 + "icon_send_dream_128.png",
    vitrinePlaque: V2 + "plaque_vitrine_dreams.png",
    /** Пока CSS-заглушка; после Компаса: icon_confirm_check_on_128.png */
    confirmCheck: "",
  };

  const ACCOUNT_LAYOUT = { left: 70, top: 980, width: 940 };

  const CARD_LAYOUT = {
    1: {
      left: Math.round(61 * S1),
      top: 1160,
      width: Math.round(819 * S1),
    },
    2: {
      left: 90,
      top: 960,
      width: 900,
    },
    3: {
      left: 70,
      top: 880,
      width: 940,
    },
    4: ACCOUNT_LAYOUT,
    5: ACCOUNT_LAYOUT,
    6: { left: 61, top: 736, width: 819 },
    7: { left: 61, top: 736, width: 819 },
    8: {
      left: 70,
      top: 880,
      width: 940,
    },
    9: { left: 61, top: 869, width: 819 },
    fio: { left: 70, top: 1100, width: 940 },
    pwa: { left: 61, top: 736, width: 819 },
    login: ACCOUNT_LAYOUT,
  };

  const ABOUT_VIDEO = {
    src: "",
    poster: "",
    placeholderLabel: "Видео скоро появится\nНажми, чтобы продолжить",
  };

  const DREAM_PLACEHOLDER = "Напиши мечту своими словами";
  const DREAM_PLACEHOLDER_MORE = "Добавь ещё одну мечту";

  /** Коды стран для выбора у телефона */
  const DIAL_CODES = [
    { code: "+7", label: "Россия / Казахстан" },
    { code: "+375", label: "Беларусь" },
    { code: "+380", label: "Украина" },
    { code: "+998", label: "Узбекистан" },
    { code: "+996", label: "Кыргызстан" },
    { code: "+992", label: "Таджикистан" },
    { code: "+993", label: "Туркменистан" },
    { code: "+994", label: "Азербайджан" },
    { code: "+374", label: "Армения" },
    { code: "+995", label: "Грузия" },
    { code: "+371", label: "Латвия" },
    { code: "+370", label: "Литва" },
    { code: "+372", label: "Эстония" },
    { code: "+48", label: "Польша" },
    { code: "+49", label: "Германия" },
    { code: "+33", label: "Франция" },
    { code: "+39", label: "Италия" },
    { code: "+34", label: "Испания" },
    { code: "+44", label: "Великобритания" },
    { code: "+1", label: "США / Канада" },
    { code: "+90", label: "Турция" },
    { code: "+971", label: "ОАЭ" },
    { code: "+972", label: "Израиль" },
    { code: "+86", label: "Китай" },
    { code: "+81", label: "Япония" },
    { code: "+82", label: "Корея" },
    { code: "+91", label: "Индия" },
    { code: "+66", label: "Таиланд" },
    { code: "+84", label: "Вьетнам" },
    { code: "+62", label: "Индонезия" },
  ];

  function designFor(screen) {
    const s = String(screen);
    if (s === "1" || s === "2" || s === "3" || s === "4" || s === "5" || s === "8" || s === "login") {
      return DESIGN_CANON;
    }
    return DESIGN_LEGACY;
  }

  function confirmSceneForCount(n) {
    return SCENE.confirmMany;
  }

  global.TIM_ASSETS = {
    DESIGN_WIDTH: DESIGN_LEGACY.w,
    DESIGN_HEIGHT: DESIGN_LEGACY.h,
    DESIGN_LEGACY: DESIGN_LEGACY,
    DESIGN_SCREEN_1: DESIGN_CANON,
    DESIGN_CANON: DESIGN_CANON,
    S1: S1,
    designFor: designFor,
    confirmSceneForCount: confirmSceneForCount,
    sceneUrls: sceneUrls,
    FIN: FIN,
    V2: V2,
    SCENE: SCENE,
    BAKED_SCENE: BAKED_SCENE,
    BUBBLE: BUBBLE,
    DECOR: DECOR,
    ICONS: ICONS,
    CARD_LAYOUT: CARD_LAYOUT,
    ABOUT_VIDEO: ABOUT_VIDEO,
    DREAM_PLACEHOLDER: DREAM_PLACEHOLDER,
    DREAM_PLACEHOLDER_MORE: DREAM_PLACEHOLDER_MORE,
    DIAL_CODES: DIAL_CODES,
  };
})(window);
