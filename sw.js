/* IslandDream minimal SW — нужен для installability (PWA). */
const CACHE = "island-pwa-v1";

self.addEventListener("install", function (event) {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE).then(function (cache) {
    return cache.addAll(["/index.html", "/manifest.webmanifest"]);
  }).catch(function () {}));
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) {
        return caches.delete(k);
      }));
    }).then(function () {
      return self.clients.claim();
    })
  );
});

self.addEventListener("fetch", function (event) {
  const req = event.request;
  if (req.method !== "GET") return;
  event.respondWith(
    fetch(req).catch(function () {
      return caches.match(req).then(function (hit) {
        return hit || caches.match("/index.html");
      });
    })
  );
});
