/**
 * Gojo Trip Planner — Service Worker
 * Handles offline caching and push notifications
 */

const CACHE_NAME = 'gojo-v2';
const STATIC_ASSETS = [
    '/static/css/design-system.css',
    '/static/css/components.css',
    '/static/css/main.css',
    '/static/js/main.js',
    '/static/manifest.json',
    '/static/images/icon-192.png',
    '/static/images/icon-512.png',
];

// ===== Install: cache static assets =====
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS).catch(err => {
                console.warn('[SW] Some assets failed to cache:', err);
            });
        })
    );
    self.skipWaiting();
});

// ===== Activate: clean up old caches =====
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
            )
        )
    );
    self.clients.claim();
});

// ===== Fetch: network-first for API, cache-first for static =====
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET, cross-origin, WebSocket
    if (request.method !== 'GET' || url.origin !== location.origin) return;
    if (url.pathname.startsWith('/ws/')) return;

    // API requests: network only
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/auth/')) return;

    // Static assets: cache first, then network
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(request).then(cached => {
                if (cached) return cached;
                return fetch(request).then(response => {
                    if (response && response.status === 200) {
                        const clone = response.clone();
                        caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
                    }
                    return response;
                }).catch(() => cached);
            })
        );
        return;
    }

    // HTML pages: network first, fallback to cache
    event.respondWith(
        fetch(request).catch(() => caches.match(request))
    );
});

// ===== Push: handle incoming push notifications =====
self.addEventListener('push', (event) => {
    if (!event.data) return;

    let data;
    try {
        data = event.data.json();
    } catch (e) {
        data = { title: 'Gojo Trip Planner', body: event.data.text() };
    }

    const options = {
        body: data.body || '',
        icon: data.icon || '/static/images/icon-192.png',
        badge: data.badge || '/static/images/icon-192.png',
        data: data.data || {},
        vibrate: [100, 50, 100],
        requireInteraction: false,
        tag: 'gojo-message',
        renotify: true,
        actions: [
            { action: 'open', title: '💬 Open Chat' },
        ]
    };

    event.waitUntil(
        self.registration.showNotification(data.title || 'Gojo Trip Planner', options)
    );
});

// ===== Notification Click: navigate to chat =====
self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    const data = event.notification.data || {};
    const url = data.url || '/dashboard';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
            for (const client of clientList) {
                if (client.url.includes(location.origin) && 'focus' in client) {
                    client.navigate(url);
                    return client.focus();
                }
            }
            if (clients.openWindow) return clients.openWindow(url);
        })
    );
});
