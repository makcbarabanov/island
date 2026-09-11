/**
 * Карта ассетов «фин» + layout artboard 941×1672.
 * Координаты карточек — px относительно исходных PNG, не viewport.
 */
(function (global) {
  const FIN = "assets/fin/";
  const DESIGN_WIDTH = 941;
  const DESIGN_HEIGHT = 1672;

  const SCENE = {
    1: FIN + "1.png",
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

  /** 5.png не используем — динамическое HTML-облако */
  const BUBBLE = {
    1: FIN + "4.png",
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

  /**
   * Карточка в координатах artboard (из SSOT % × 941/1672).
   * Экран 5: top ≈ 39.5% — рука Тима на верхней кромке.
   */
  const CARD_LAYOUT = {
    1: { left: 61, top: 853, width: 819 },
    2: { left: 66, top: 1087, width: 809 },
    3: { left: 66, top: 836, width: 809 },
    4: { left: 61, top: 719, width: 819 },
    // рука на полке ~39.5%; чуть выше SSOT 660, если визуально рука «висит» над кромкой
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

  global.TIM_ASSETS = {
    DESIGN_WIDTH: DESIGN_WIDTH,
    DESIGN_HEIGHT: DESIGN_HEIGHT,
    FIN: FIN,
    SCENE: SCENE,
    BUBBLE: BUBBLE,
    DECOR: DECOR,
    CARD_LAYOUT: CARD_LAYOUT,
    ABOUT_VIDEO: ABOUT_VIDEO,
  };
})(window);
