/* Offline copy of the autocorrect page: the page, its glue, the engine and the counts, cached on first visit.
   Bump VERSION when any of them changes. */
var VERSION = 't2b-autocorrect-v2';
var FILES = ['./', 'index.html', 'glue.js', 't2b.wasm', 'model.bin', '../../site.css'];
self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) { return c.addAll(FILES); }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (ks) {
    return Promise.all(ks.filter(function (k) { return k.indexOf('t2b-autocorrect-') === 0 && k !== VERSION; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});
self.addEventListener('fetch', function (e) {
  var u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return;
  e.respondWith(caches.match(e.request, { ignoreSearch: true }).then(function (hit) {
    return hit || fetch(e.request).then(function (resp) {
      if (resp.ok) { var copy = resp.clone(); caches.open(VERSION).then(function (c) { c.put(e.request, copy); }); }
      return resp;
    });
  }));
});
