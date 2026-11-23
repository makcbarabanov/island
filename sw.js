/* IslandDream PWA service worker.
 * Версия CACHE подставляется при отдаче /sw.js из .app-version в index.html.
 * После деплоя с новым номером версии байты sw.js меняются → браузер ставит новый SW.
 */
const CACHE = "island-pwa-v__ISLAND_APP_VERSION__";

self.addEventListener("install", function (event) {
  self.skipWaiting();
  // Не кладём index.html в кэш на install — иначе залипает старая вёрстка до смены CACHE.
  event.waitUntil(
    caches.open(CACHE).then(function (cache) {
      return cache.addAll(["/manifest.webmanifest"]).catch(function () {});
    })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys
          .filter(function (k) {
            return k !== CACHE;
          })
          .map(function (k) {
            return caches.delete(k);
          })
      );
    }).then(function () {
      return self.clients.claim();
    })
  );
});

function isHtmlNavigation(req) {
  if (req.mode === "navigate") return true;
  var accept = req.headers.get("accept") || "";
  return accept.indexOf("text/html") !== -1;
}

self.addEventListener("fetch", function (event) {
  var req = event.request;
  if (req.method !== "GET") return;

  // HTML / навигация: только сеть; в кэш — свежая копия для офлайна; при ошибке — запасной кэш.
  if (isHtmlNavigation(req)) {
    event.respondWith(
      fetch(req)
        .then(function (res) {
          if (res && res.ok) {
            var copy = res.clone();
            caches.open(CACHE).then(function (cache) {
              cache.put("/index.html", copy).catch(function () {});
            });
          }
          return res;
        })
        .catch(function () {
          return caches.match("/index.html").then(function (hit) {
            return hit || caches.match(req);
          });
        })
    );
    return;
  }

  // Остальное: сеть → при сбое кэш (офлайн).
  event.respondWith(
    fetch(req).catch(function () {
      return caches.match(req);
    })
  );
});
