/**
 * Tim assets.
 * Экран 1–2: baked 1080×2400 + HTML-controls.
 * Экраны 3–9: пакет fin/ (941×1672) пока без изменений.
 */
(function (global) {
  const FIN = "assets/fin/";
  const V2 = "assets/v2/";

  /** Старый пакет fin/ */
  const DESIGN_LEGACY = { w: 941, h: 1672 };
  /** Канон production-сцен: 1080×2400 */
  const DESIGN_CANON = { w: 1080, h: 2400 };

  const S1 = DESIGN_CANON.w / DESIGN_LEGACY.w;

  const SCENE = {
    1: V2 + "scene_01_welcome_1080x2400.png",
    2: V2 + "scene_02_video_1080x2400.png",
    3: FIN + "3.png",
    4: FIN + "13.png",
    5: FIN + "14.png",
    6: FIN + "15.png",
    7: FIN + "16.png",
    8: FIN + "17.png",
    9: FIN + "18.png",
    login: FIN + "13.png",
  };

  const BAKED_SCENE = {
    1: true,
    2: true,
  };

  const BUBBLE = {
    1: null,
    2: null,
    3: FIN + "6.png",
    4: FIN + "19.png",
    5: FIN + "7.png",
    6: FIN + "20.png",
    7: FIN + "8.png",
    8: FIN + "9.png",
    9: FIN + "21.png",
    login: FIN + "19.png",
  };

  const DECOR = {
    tagline: FIN + "10.png",
    plaque: FIN + "22.png",
  };

  const CARD_LAYOUT = {
    1: {
      left: Math.round(61 * S1),
      top: 1160,
      width: Math.round(819 * S1),
    },
    // видео + «к Мечтам!» между водой/жестом и слоганом на песке
    2: {
      left: 90,
      top: 1080,
      width: 900,
    },
    3: { left: 66, top: 836, width: 809 },
    4: { left: 61, top: 719, width: 819 },
    5: { left: 71, top: 640, width: 800 },
    6: { left: 61, top: 736, width: 819 },
    7: { left: 61, top: 736, width: 819 },
    8: { left: 61, top: 819, width: 819 },
    9: { left: 61, top: 869, width: 819 },
    login: { left: 61, top: 719, width: 819 },
  };

  const ABOUT_VIDEO = {
    src: "",
    poster: "",
    placeholderLabel: "Видео скоро появится\nНажми, чтобы продолжить",
  };

  function designFor(screen) {
    const s = String(screen);
    if (s === "1" || s === "2") return DESIGN_CANON;
    return DESIGN_LEGACY;
  }

  global.TIM_ASSETS = {
    DESIGN_WIDTH: DESIGN_LEGACY.w,
    DESIGN_HEIGHT: DESIGN_LEGACY.h,
    DESIGN_LEGACY: DESIGN_LEGACY,
    DESIGN_SCREEN_1: DESIGN_CANON,
    DESIGN_CANON: DESIGN_CANON,
    S1: S1,
    designFor: designFor,
    FIN: FIN,
    V2: V2,
    SCENE: SCENE,
    BAKED_SCENE: BAKED_SCENE,
    BUBBLE: BUBBLE,
    DECOR: DECOR,
    CARD_LAYOUT: CARD_LAYOUT,
    ABOUT_VIDEO: ABOUT_VIDEO,
  };
})(window);
