/**
 * Tim assets.
 * Экраны 1–3 + 8 (сверка): baked 1080×2400.
 * Остальные: fin/ пока без изменений.
 */
(function (global) {
  const FIN = "assets/fin/";
  const V2 = "assets/v2/";

  const DESIGN_LEGACY = { w: 941, h: 1672 };
  const DESIGN_CANON = { w: 1080, h: 2400 };
  const S1 = DESIGN_CANON.w / DESIGN_LEGACY.w;

  const SCENE = {
    1: V2 + "scene_01_welcome_1080x2400.png",
    2: V2 + "scene_02_video_1080x2400.png",
    3: V2 + "scene_03_dream_1080x2400.png",
    4: FIN + "13.png",
    5: FIN + "14.png",
    6: FIN + "15.png",
    7: FIN + "16.png",
    8: V2 + "scene_04_confirm_many_1080x2400.png",
    9: FIN + "18.png",
    login: FIN + "13.png",
    confirmOne: V2 + "scene_04_confirm_one_1080x2400.png",
    confirmMany: V2 + "scene_04_confirm_many_1080x2400.png",
  };

  const BAKED_SCENE = {
    1: true,
    2: true,
    3: true,
    8: true,
  };

  const BUBBLE = {
    1: null,
    2: null,
    3: null,
    4: FIN + "19.png",
    5: FIN + "7.png",
    6: FIN + "20.png",
    7: FIN + "8.png",
    8: null,
    9: FIN + "21.png",
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
  };

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
    4: { left: 61, top: 719, width: 819 },
    5: { left: 71, top: 640, width: 800 },
    6: { left: 61, top: 736, width: 819 },
    7: { left: 61, top: 736, width: 819 },
    // сверка на песке под кромкой (~¾ экрана)
    8: {
      left: 70,
      top: 880,
      width: 940,
    },
    9: { left: 61, top: 869, width: 819 },
    login: { left: 61, top: 719, width: 819 },
  };

  const ABOUT_VIDEO = {
    src: "",
    poster: "",
    placeholderLabel: "Видео скоро появится\nНажми, чтобы продолжить",
  };

  const DREAM_PLACEHOLDER = "Напиши мечту своими словами";

  function designFor(screen) {
    const s = String(screen);
    if (s === "1" || s === "2" || s === "3" || s === "8") return DESIGN_CANON;
    return DESIGN_LEGACY;
  }

  function confirmSceneForCount(n) {
    return n <= 1 ? SCENE.confirmOne : SCENE.confirmMany;
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
  };
})(window);
