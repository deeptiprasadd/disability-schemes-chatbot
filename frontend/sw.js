/* =========================================================================
 * Service worker: makes the app installable ("Add to Home screen") and lets
 * it open without a connection.
 *
 * Network first for the app's own files, so an update is visible on the next
 * visit, with the cached copy as the offline fallback. /api/* is never cached:
 * answers must be live, and the app already shows a clear "you seem to be
 * offline" message when a question cannot be sent.
 *
 * "Network" means the server, not the browser's own HTTP cache: scripts and
 * styles are fetched with cache "no-cache" (a small 304 when unchanged), because
 * browsers that saved them before the server sent Cache-Control would otherwise
 * keep serving the old app for a day or more after an update.
 * ========================================================================= */

const CACHE = "sneh-saathi-v4";
const SHELL = ["/", "/style.css", "/fonts/fonts.css", "/i18n.js", "/app.js", "/icons.svg",
               "/manifest.json", "/icon-192.png"];

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
  if (event.request.method !== "GET" || url.origin !== self.location.origin
      || url.pathname.startsWith("/api/") || url.pathname.startsWith("/download/")) {
    return; // let the browser handle it normally (and don't store the APK offline)
  }
  // A page navigation can't be copied with new options (and the page's text
  // comes from the scripts anyway); fonts and icons may come from the browser cache.
  const rarelyChanges = url.pathname.startsWith("/fonts/") || url.pathname.endsWith(".png");
  const request = event.request.mode === "navigate" || rarelyChanges
    ? event.request
    : new Request(event.request, { cache: "no-cache" });
  event.respondWith(
    fetch(request)
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
