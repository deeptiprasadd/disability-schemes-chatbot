/* =========================================================================
 * Service worker: makes the app installable ("Add to Home screen") and lets
 * it open without a connection.
 *
 * Network first for the app's own files, so an update is visible on the next
 * visit, with the cached copy as the offline fallback. /api/* is never cached:
 * answers must be live, and the app already shows a clear "you seem to be
 * offline" message when a question cannot be sent.
 * ========================================================================= */

const CACHE = "dsa-shell-v1";
const SHELL = ["/", "/style.css", "/app.js", "/icons.svg", "/manifest.json", "/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) {
    return; // let the browser handle it normally
  }
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((c) => c.put(event.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(event.request).then((hit) => hit || caches.match("/")))
  );
});
