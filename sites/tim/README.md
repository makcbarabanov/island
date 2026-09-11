# `/tim/` — онбординг «Островёнок Тим»

## URL

`/tim/` (редирект `/tim` → `/tim/`)

## Ассеты

Канон: `assets/fin/` из `Images/фин.zip` + SSOT `Images/Файл Что это Где используется.txt` (копия ориентира: `ASSETS-MAP.txt`).

Не используются: 11, 12, `16без ног` (удалены из папки).

Экран 2: **не** показываем `5.png` (там «Макс») — HTML-облако с `{имя}`.

Видео about: `js/assets.js` → `ABOUT_VIDEO.src`.

## Экраны 1–9

1 Знакомство (имя+город) → 2 Приглашение → 3 About → 4 Регистрация → 5 Контакты (skip) → 6 PWA (один раз) → 7 Мечта → 8 AI confirm → 9 Успех → ЛК `/index.html`

API: `POST /register`, `POST /login`, `PATCH /users/me` (telegram/vk), `POST /api/v1/dream-interpret`, `POST /dreams`.

Контакты max/ok/fb/other пока в `localStorage` (`tim_contact_channels`); telegram/vk — в legacy-поля users. Таблица `user_contact_channels` — отдельным шагом.

## Layout

Artboard **941×1672** (`.tim-canvas`), scale только по ширине `.tim-stage` (`fitTimCanvas`).
Координаты карточек: `CARD_LAYOUT` в `js/assets.js` (px artboard).
Smoke-превью экрана: `?force=1&screen=5` (и 1–9 / `login`).
