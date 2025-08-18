// static/pwa/sw.js
const CACHE_NAME = 'app-v1';
const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/js/app.js'
];

// Install service worker
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

// Fetch from cache
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});
