/**
 * Tim assets.
 * Экран 1: baked scene_01_welcome.png + HTML (имя/город/кнопка/Войти).
 * Экраны 2–9: пакет fin/ без изменений.
 */
(function (global) {
  const FIN = "assets/fin/";
  const V2 = "assets/v2/";

  /** Artboard fin/ и scene_01_welcome — 941×1672 */
  const DESIGN_LEGACY = { w: 941, h: 1672 };
  const DESIGN_SCREEN_1 = { w: 941, h: 1672 };

  const SCENE = {
    1: V2 + "scene_01_welcome.png",
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

  /** Художественные слои уже в scene — не дублируем PNG-overlays */
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
    // экран 1: форма на песке над «Мечты реальнее вместе!»
    1: { left: 61, top: 980, width: 819 },
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
    return screen === 1 || screen === "1" ? DESIGN_SCREEN_1 : DESIGN_LEGACY;
  }

  global.TIM_ASSETS = {
    DESIGN_WIDTH: DESIGN_LEGACY.w,
    DESIGN_HEIGHT: DESIGN_LEGACY.h,
    DESIGN_LEGACY: DESIGN_LEGACY,
    DESIGN_SCREEN_1: DESIGN_SCREEN_1,
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
