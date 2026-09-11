/**
 * Tim assets.
 * Экран 1 (v2): одна готовая сцена + HTML overlay.
 * Экраны 2–9: пока старый пакет fin/ (до нового design package).
 */
(function (global) {
  const FIN = "assets/fin/";
  const V2 = "assets/v2/";

  /** Базовый artboard старого пакета */
  const DESIGN_LEGACY = { w: 941, h: 1672 };
  /** Artboard сцены экрана 1 (Тим2) */
  const DESIGN_V2 = { w: 967, h: 1626 };

  const SCENE = {
    1: V2 + "screen-01.png", // baked: фон+Тим+реплика+табличка+лого
    2: FIN + "2.png",
    3: FIN + "3.png",
    4: FIN + "13.png",
    5: FIN + "14.png",
    6: FIN + "15.png",
    7: FIN + "16.png",
    8: FIN + "17.png",
    9: FIN + "18.png",
    login: FIN + "13.png",
  };

  /** Экраны, где художественные слои уже в scene (не дублируем PNG-overlays) */
  const BAKED_SCENE = {
    1: true,
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
    // песок под Тимом на 967×1626
    1: { left: 70, top: 1120, width: 827 },
    2: { left: 66, top: 1087, width: 809 },
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
    placeholderLabel: "Видео скоро появится",
  };

  function designFor(screen) {
    return BAKED_SCENE[screen] ? DESIGN_V2 : DESIGN_LEGACY;
  }

  global.TIM_ASSETS = {
    DESIGN_WIDTH: DESIGN_LEGACY.w,
    DESIGN_HEIGHT: DESIGN_LEGACY.h,
    DESIGN_LEGACY: DESIGN_LEGACY,
    DESIGN_V2: DESIGN_V2,
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
