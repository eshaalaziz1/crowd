self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open("app-cache").then((cache) => {
            return cache.addAll([
                "/",
                "/static/styles.css",
                "/static/heatmap.html",
                "/static/icons/icon-192x192.png",
                "/static/icons/icon-512x512.png",
                "/static/manifest.json"
            ]);
        })
    );
});

self.addEventListener("fetch", (event) => {
    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request);
        })
    );
});
