/**
 * Gojo Trip Planner v2 — Main JavaScript
 * WebSocket chat, Push Notifications, PWA, Theme, Toasts
 */

const GojoApp = (function () {
    'use strict';

    // ===== Theme =====
    const theme = {
        init() {
            const saved = localStorage.getItem('gojo-theme') || 'light';
            this.apply(saved);
        },
        apply(mode) {
            document.documentElement.setAttribute('data-theme', mode);
            localStorage.setItem('gojo-theme', mode);
            // Update toggle button icons
            document.querySelectorAll('[data-theme-icon]').forEach(el => {
                el.textContent = mode === 'dark' ? '☀️' : '🌙';
            });
        },
        toggle() {
            const current = document.documentElement.getAttribute('data-theme');
            this.apply(current === 'dark' ? 'light' : 'dark');
        }
    };

    // ===== Toast =====
    const toast = {
        container: null,
        init() {
            this.container = document.createElement('div');
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        },
        show(message, type = 'info', duration = 4000) {
            if (!this.container) this.init();

            const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `
                <span class="toast-icon">${icons[type] || icons.info}</span>
                <div class="toast-content">
                    <div class="toast-message">${this._escape(message)}</div>
                </div>
                <button onclick="this.parentElement.remove()" style="background:none;border:none;cursor:pointer;color:var(--text-3);font-size:1rem;padding:0;line-height:1;">✕</button>
            `;
            this.container.appendChild(toast);

            if (duration > 0) {
                setTimeout(() => {
                    toast.style.animation = 'slideInRight 250ms reverse both';
                    setTimeout(() => toast.remove(), 250);
                }, duration);
            }
            return toast;
        },
        _escape(str) {
            return String(str).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[m]);
        }
    };

    // ===== Modal =====
    const modal = {
        open(id) {
            const el = document.getElementById(id);
            if (el) {
                el.classList.add('open');
                document.body.style.overflow = 'hidden';
            }
        },
        close(id) {
            const el = document.getElementById(id);
            if (el) {
                el.classList.remove('open');
                document.body.style.overflow = '';
            }
        },
        closeAll() {
            document.querySelectorAll('.modal-backdrop.open').forEach(el => {
                el.classList.remove('open');
            });
            document.body.style.overflow = '';
        }
    };

    // ===== Tabs =====
    const tabs = {
        init() {
            document.querySelectorAll('.tabs').forEach(tabGroup => {
                const tabId = tabGroup.dataset.tabs;
                const items = tabGroup.querySelectorAll('.tab-item');
                items.forEach(item => {
                    item.addEventListener('click', () => {
                        const panelId = item.dataset.panel;
                        this._activate(tabGroup, item, panelId);
                    });
                });
            });
        },
        _activate(tabGroup, activeItem, panelId) {
            tabGroup.querySelectorAll('.tab-item').forEach(i => i.classList.remove('active'));
            activeItem.classList.add('active');
            const groupId = tabGroup.dataset.tabs;
            document.querySelectorAll(`[data-tab-group="${groupId}"]`).forEach(p => p.classList.remove('active'));
            const panel = document.querySelector(`[data-panel-id="${panelId}"]`);
            if (panel) panel.classList.add('active');
        },
        activate(panelId) {
            const item = document.querySelector(`[data-panel="${panelId}"]`);
            if (item) {
                const tabGroup = item.closest('.tabs');
                this._activate(tabGroup, item, panelId);
            }
        }
    };

    // ===== WebSocket Chat =====
    const chat = {
        ws: null,
        tripId: null,
        userId: null,
        lastMessageId: 0,
        reconnectDelay: 2000,
        maxReconnectDelay: 30000,
        reconnecting: false,

        init(tripId, userId) {
            this.tripId = tripId;
            this.userId = userId;
            this.connect();
        },

        connect() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            const url = `${protocol}//${location.host}/ws/trip/${this.tripId}/chat`;

            try {
                this.ws = new WebSocket(url);

                this.ws.onopen = () => {
                    this.reconnectDelay = 2000;
                    this.reconnecting = false;
                    this._updateStatus('online');
                    console.log('[Gojo Chat] Connected');
                };

                this.ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        this._handleMessage(data);
                    } catch (e) {
                        console.error('[Gojo Chat] Parse error:', e);
                    }
                };

                this.ws.onclose = () => {
                    this._updateStatus('offline');
                    if (!this.reconnecting) {
                        this.reconnecting = true;
                        this._scheduleReconnect();
                    }
                };

                this.ws.onerror = () => {
                    this._updateStatus('offline');
                };
            } catch (e) {
                console.error('[Gojo Chat] Connection failed:', e);
                this._scheduleReconnect();
            }
        },

        _scheduleReconnect() {
            setTimeout(() => {
                if (document.visibilityState !== 'hidden') {
                    console.log(`[Gojo Chat] Reconnecting in ${this.reconnectDelay}ms...`);
                    this.connect();
                    this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
                }
            }, this.reconnectDelay);
        },

        send(content) {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ content }));
                return true;
            }
            return false;
        },

        _handleMessage(data) {
            switch (data.type) {
                case 'message':
                    this._appendMessage(data);
                    if (data.id > this.lastMessageId) this.lastMessageId = data.id;
                    this._scrollToBottom();
                    if (data.user_id !== this.userId) {
                        this._notifyMessage(data);
                    }
                    break;
                case 'user_joined':
                case 'user_left':
                    this._updateOnlineUsers(data.online_users);
                    const action = data.type === 'user_joined' ? 'joined' : 'left';
                    this._appendSystemMessage(`${data.user_name} ${action} the chat`);
                    break;
            }
        },

        _appendMessage(data) {
            const container = document.getElementById('chatMessages');
            if (!container) return;

            const isOwn = data.user_id === this.userId;
            const row = document.createElement('div');
            row.className = `chat-message-row ${isOwn ? 'own' : 'other'}`;
            row.id = `msg-${data.id}`;
            row.innerHTML = `
                ${!isOwn ? `<div class="avatar avatar-sm">${data.user_initial}</div>` : ''}
                <div style="display:flex;flex-direction:column;max-width:75%;">
                    ${!isOwn ? `<span style="font-size:11px;color:var(--text-3);margin-bottom:3px;font-weight:600;">${this._escape(data.user_name)}</span>` : ''}
                    <div class="chat-bubble ${isOwn ? 'own' : 'other'}">${this._escape(data.content)}</div>
                    <span class="chat-meta">${data.timestamp}</span>
                </div>
                ${isOwn ? `<div class="avatar avatar-sm">${data.user_initial}</div>` : ''}
            `;
            container.appendChild(row);
        },

        _appendSystemMessage(text) {
            const container = document.getElementById('chatMessages');
            if (!container) return;
            const el = document.createElement('div');
            el.style.cssText = 'text-align:center;font-size:11px;color:var(--text-4);padding:4px 0;';
            el.textContent = text;
            container.appendChild(el);
            this._scrollToBottom();
        },

        _scrollToBottom() {
            const container = document.getElementById('chatMessages');
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        },

        _updateStatus(status) {
            const el = document.getElementById('connectionStatus');
            if (el) {
                el.textContent = status === 'online' ? '🟢 Connected' : '🔴 Reconnecting...';
                el.className = status === 'online' ? 'badge badge-emerald' : 'badge badge-rose';
            }
        },

        _updateOnlineUsers(users) {
            const el = document.getElementById('onlineUsers');
            if (el) {
                el.innerHTML = users.map(u =>
                    `<span class="chip" title="${this._escape(u.name)}">${this._escape(u.name.split(' ')[0])}</span>`
                ).join('');
            }
        },

        _notifyMessage(data) {
            if (document.visibilityState === 'visible') return;
            if ('Notification' in window && Notification.permission === 'granted') {
                new Notification(`Gojo — ${data.user_name}`, {
                    body: data.content.substring(0, 100),
                    icon: '/static/images/icon-192.png',
                });
            }
        },

        _escape(str) {
            return String(str).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[m]);
        }
    };

    // ===== Push Notifications =====
    const push = {
        async init() {
            if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
            try {
                const reg = await navigator.serviceWorker.ready;
                const existingSub = await reg.pushManager.getSubscription();
                if (existingSub) return; // Already subscribed

                const keyResp = await fetch('/api/push/vapid-key');
                const { publicKey } = await keyResp.json();
                if (!publicKey) return;

                // Don't auto-prompt; wait for user interaction
            } catch (e) {
                console.debug('[Push] Init error:', e);
            }
        },

        async subscribe() {
            try {
                if (Notification.permission === 'default') {
                    const perm = await Notification.requestPermission();
                    if (perm !== 'granted') {
                        toast.show('Notifications blocked. Enable in browser settings.', 'warning');
                        return;
                    }
                }

                const reg = await navigator.serviceWorker.ready;
                const keyResp = await fetch('/api/push/vapid-key');
                const { publicKey } = await keyResp.json();
                if (!publicKey) {
                    toast.show('Push notifications not configured on this server.', 'info');
                    return;
                }

                const sub = await reg.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: this._urlBase64ToUint8Array(publicKey)
                });

                await fetch('/api/push/subscribe', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(sub)
                });

                toast.show('Push notifications enabled! 🔔', 'success');

                const btn = document.getElementById('notifToggle');
                if (btn) btn.textContent = '🔔 Notifications On';

            } catch (e) {
                console.error('[Push] Subscribe error:', e);
                toast.show('Could not enable notifications.', 'error');
            }
        },

        _urlBase64ToUint8Array(base64String) {
            const padding = '='.repeat((4 - base64String.length % 4) % 4);
            const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
            const rawData = window.atob(base64);
            return Uint8Array.from([...rawData].map(c => c.charCodeAt(0)));
        }
    };

    // ===== PWA / Service Worker =====
    const pwa = {
        deferredPrompt: null,

        async init() {
            if ('serviceWorker' in navigator) {
                try {
                    await navigator.serviceWorker.register('/static/sw.js');
                    console.log('[Gojo PWA] Service Worker registered');
                    await push.init();
                } catch (e) {
                    console.error('[Gojo PWA] SW registration failed:', e);
                }
            }

            window.addEventListener('beforeinstallprompt', (e) => {
                e.preventDefault();
                this.deferredPrompt = e;
                this._showInstallBanner();
            });

            window.addEventListener('appinstalled', () => {
                this._hideInstallBanner();
                toast.show('Gojo installed! Find it on your home screen. 🎉', 'success');
            });
        },

        async install() {
            if (!this.deferredPrompt) return;
            this.deferredPrompt.prompt();
            const { outcome } = await this.deferredPrompt.userChoice;
            this.deferredPrompt = null;
            if (outcome === 'accepted') this._hideInstallBanner();
        },

        _showInstallBanner() {
            const banner = document.getElementById('installBanner');
            if (banner) banner.classList.remove('install-banner-hidden');
        },

        _hideInstallBanner() {
            const banner = document.getElementById('installBanner');
            if (banner) banner.classList.add('install-banner-hidden');
        }
    };

    // ===== AI Recommendations =====
    const recommendations = {
        async load(tripId, container) {
            if (!container) return;
            container.innerHTML = `
                <div style="text-align:center;padding:var(--space-8);">
                    <div class="spinner" style="margin:0 auto var(--space-4);"></div>
                    <p style="color:var(--text-3);">Loading AI recommendations...</p>
                </div>
            `;
            try {
                const resp = await fetch(`/api/trip/${tripId}/recommendations`);
                if (!resp.ok) throw new Error('API error');
                const data = await resp.json();
                this._render(container, data);
            } catch (e) {
                container.innerHTML = `<p style="color:var(--text-3);text-align:center;">Could not load recommendations. Check your internet connection.</p>`;
            }
        },

        async loadItinerary(tripId, container) {
            if (!container) return;
            container.innerHTML = `
                <div style="text-align:center;padding:var(--space-8);">
                    <div class="spinner" style="margin:0 auto var(--space-4);"></div>
                    <p style="color:var(--text-3);">Generating personalized itinerary...</p>
                </div>
            `;
            try {
                const resp = await fetch(`/api/trip/${tripId}/ai-itinerary`);
                if (!resp.ok) throw new Error('API error');
                const days = await resp.json();
                this._renderItinerary(container, days);
            } catch (e) {
                container.innerHTML = `<p style="color:var(--text-3);text-align:center;">Could not generate itinerary suggestions.</p>`;
            }
        },

        _render(container, data) {
            const stars = (rating) => {
                const full = Math.floor(rating || 0);
                return '★'.repeat(full) + '☆'.repeat(5 - full);
            };

            container.innerHTML = `
                <div class="tabs" data-tabs="recs" style="margin-bottom:var(--space-4);">
                    <span class="tab-item active" data-panel="hotels">🏨 Hotels (${(data.hotels || []).length})</span>
                    <span class="tab-item" data-panel="restaurants">🍽️ Restaurants (${(data.restaurants || []).length})</span>
                    <span class="tab-item" data-panel="attractions">🏞️ Attractions (${(data.attractions || []).length})</span>
                    <span class="tab-item" data-panel="tips">💡 Tips (${(data.travel_tips || []).length})</span>
                </div>

                <div class="tab-panel active rec-grid" data-tab-group="recs" data-panel-id="hotels">
                    ${(data.hotels || []).map(h => `
                        <div class="rec-card">
                            <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:var(--space-2);">
                                <h5 style="margin:0;font-size:var(--text-sm);">${this._esc(h.name)}</h5>
                                <span class="rec-rating">${stars(h.rating)} ${h.rating || ''}</span>
                            </div>
                            <div style="display:flex;gap:var(--space-2);margin-bottom:var(--space-2);">
                                <span class="badge badge-amber">${this._esc(h.price || '')}</span>
                                ${h.area ? `<span class="badge badge-gray">📍 ${this._esc(h.area)}</span>` : ''}
                            </div>
                            <p style="font-size:var(--text-xs);color:var(--text-3);margin:0;">${this._esc(h.sentiment || '')}</p>
                        </div>
                    `).join('') || '<p class="text-muted">No hotels found.</p>'}
                </div>

                <div class="tab-panel rec-grid" data-tab-group="recs" data-panel-id="restaurants">
                    ${(data.restaurants || []).map(r => `
                        <div class="rec-card">
                            <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:var(--space-2);">
                                <h5 style="margin:0;font-size:var(--text-sm);">${this._esc(r.name)}</h5>
                                <span class="rec-rating">${stars(r.rating)} ${r.rating || ''}</span>
                            </div>
                            <div style="display:flex;gap:var(--space-2);margin-bottom:var(--space-2);">
                                <span class="badge badge-emerald">${this._esc(r.cuisine || '')}</span>
                                ${r.area ? `<span class="badge badge-gray">📍 ${this._esc(r.area)}</span>` : ''}
                            </div>
                            <p style="font-size:var(--text-xs);color:var(--text-3);margin:0;">${this._esc(r.sentiment || '')}</p>
                        </div>
                    `).join('') || '<p class="text-muted">No restaurants found.</p>'}
                </div>

                <div class="tab-panel rec-grid" data-tab-group="recs" data-panel-id="attractions">
                    ${(data.attractions || []).map(a => `
                        <div class="rec-card">
                            <h5 style="margin:0 0 var(--space-2);font-size:var(--text-sm);">${this._esc(a.name)}</h5>
                            <div style="display:flex;gap:var(--space-2);margin-bottom:var(--space-2);">
                                <span class="badge badge-primary">${this._esc(a.type || '')}</span>
                                ${a.area ? `<span class="badge badge-gray">📍 ${this._esc(a.area)}</span>` : ''}
                            </div>
                            <p style="font-size:var(--text-xs);color:var(--text-3);margin:0;">${this._esc(a.sentiment || '')}</p>
                        </div>
                    `).join('') || '<p class="text-muted">No attractions found.</p>'}
                </div>

                <div class="tab-panel" data-tab-group="recs" data-panel-id="tips">
                    ${(data.travel_tips || []).map(t => `
                        <div class="rec-card" style="grid-column:1/-1;">
                            <div style="display:flex;align-items:start;gap:var(--space-3);">
                                <span style="font-size:1.5rem;">💡</span>
                                <div>
                                    <h5 style="margin:0 0 4px;font-size:var(--text-sm);">${this._esc(t.tip || '')}</h5>
                                    <p style="font-size:var(--text-xs);color:var(--text-3);margin:0;">${this._esc(t.description || '')}</p>
                                </div>
                            </div>
                        </div>
                    `).join('') || '<p class="text-muted">No tips found.</p>'}
                </div>
            `;

            // Re-init tabs for dynamically rendered content
            tabs.init();
        },

        _renderItinerary(container, days) {
            if (!days || !days.length) {
                container.innerHTML = '<p style="color:var(--text-3);">Could not generate itinerary. Try again.</p>';
                return;
            }

            const categoryIcons = {
                Sightseeing: '🏛️', Food: '🍽️', Hotel: '🏨', Transport: '🚌',
                Activity: '🎯', Shopping: '🛍️', Nature: '🌿', Culture: '🎭'
            };

            container.innerHTML = days.map(day => `
                <div style="margin-bottom:var(--space-6);">
                    <h4 style="color:var(--primary);margin-bottom:var(--space-3);">Day ${day.day}</h4>
                    <div class="timeline">
                        ${(day.items || []).map(item => `
                            <div class="timeline-item">
                                <div class="timeline-dot"></div>
                                <div class="timeline-card">
                                    <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:var(--space-2);">
                                        <span class="timeline-time">${item.time || ''}</span>
                                        <span class="badge badge-primary">${categoryIcons[item.category] || '📍'} ${item.category || ''}</span>
                                    </div>
                                    <h5 style="margin:0 0 4px;">${this._esc(item.activity)}</h5>
                                    ${item.location ? `<p style="font-size:var(--text-xs);color:var(--cyan);margin:0 0 4px;">📍 ${this._esc(item.location)}</p>` : ''}
                                    ${item.description ? `<p style="font-size:var(--text-xs);color:var(--text-3);margin:0 0 4px;">${this._esc(item.description)}</p>` : ''}
                                    ${item.tips ? `<p style="font-size:var(--text-xs);color:var(--amber);margin:0;">💡 ${this._esc(item.tips)}</p>` : ''}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `).join('');
        },

        _esc(str) {
            return String(str || '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[m]);
        }
    };

    // ===== Map (Leaflet) =====
    const mapModule = {
        map: null,
        init(elementId, destCoords, startCoords, routePath, mapsApiKey) {
            if (!document.getElementById(elementId)) return;
            if (typeof L === 'undefined') { console.error('[Map] Leaflet not loaded'); return; }

            this.map = L.map(elementId, {
                center: destCoords,
                zoom: startCoords ? 7 : 11,
                zoomControl: true
            });

            // Use OSM tiles (free, no API key)
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                maxZoom: 19
            }).addTo(this.map);

            // Destination marker
            const destIcon = L.divIcon({
                html: '<div style="background:#4F46E5;width:16px;height:16px;border-radius:50%;border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.3);"></div>',
                className: '',
                iconSize: [16, 16],
                iconAnchor: [8, 8]
            });
            L.marker(destCoords, { icon: destIcon })
              .addTo(this.map)
              .bindPopup(`<b>📍 Destination</b>`)
              .openPopup();

            // Start marker
            if (startCoords) {
                const startIcon = L.divIcon({
                    html: '<div style="background:#10B981;width:14px;height:14px;border-radius:50%;border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.3);"></div>',
                    className: '',
                    iconSize: [14, 14],
                    iconAnchor: [7, 7]
                });
                L.marker(startCoords, { icon: startIcon })
                  .addTo(this.map)
                  .bindPopup('<b>🟢 Start Location</b>');
            }

            // Route
            if (routePath && routePath.length > 1) {
                L.polyline(routePath, {
                    color: '#4F46E5',
                    weight: 4,
                    opacity: 0.8,
                    dashArray: null
                }).addTo(this.map);

                const group = L.featureGroup();
                if (startCoords) group.addLayer(L.marker(startCoords));
                group.addLayer(L.marker(destCoords));
                this.map.fitBounds(group.getBounds().pad(0.2));
            }

            // Resize fix for hidden containers
            setTimeout(() => this.map.invalidateSize(), 300);
        }
    };

    // ===== Lightbox =====
    const lightbox = {
        init() {
            const lb = document.getElementById('lightbox');
            if (!lb) return;

            lb.addEventListener('click', (e) => {
                if (e.target === lb) this.close();
            });

            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') this.close();
            });
        },
        open(src, isVideo = false) {
            const lb = document.getElementById('lightbox');
            const content = document.getElementById('lightboxContent');
            if (!lb || !content) return;

            content.innerHTML = isVideo
                ? `<video src="${src}" controls autoplay style="max-width:90vw;max-height:90vh;border-radius:var(--radius-md);"></video>`
                : `<img src="${src}" style="max-width:90vw;max-height:90vh;object-fit:contain;border-radius:var(--radius-md);">`;

            lb.classList.add('open');
            document.body.style.overflow = 'hidden';
        },
        close() {
            const lb = document.getElementById('lightbox');
            if (lb) lb.classList.remove('open');
            document.body.style.overflow = '';
        }
    };

    // ===== Drag-Drop Upload =====
    const dragDrop = {
        init(zoneId, inputId) {
            const zone = document.getElementById(zoneId);
            const input = document.getElementById(inputId);
            if (!zone || !input) return;

            zone.addEventListener('click', () => input.click());

            zone.addEventListener('dragover', (e) => {
                e.preventDefault();
                zone.classList.add('drag-over');
            });

            zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));

            zone.addEventListener('drop', (e) => {
                e.preventDefault();
                zone.classList.remove('drag-over');
                if (e.dataTransfer.files.length > 0) {
                    input.files = e.dataTransfer.files;
                    this._showPreview(input.files[0], zone);
                }
            });

            input.addEventListener('change', () => {
                if (input.files.length > 0) {
                    this._showPreview(input.files[0], zone);
                }
            });
        },

        _showPreview(file, zone) {
            const preview = document.getElementById('uploadPreview');
            if (!preview) return;

            if (file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    preview.innerHTML = `<img src="${e.target.result}" style="max-width:200px;max-height:150px;border-radius:var(--radius-md);object-fit:cover;">`;
                };
                reader.readAsDataURL(file);
            } else {
                preview.innerHTML = `<span class="badge badge-gray">🎬 ${file.name}</span>`;
            }

            const label = zone.querySelector('.upload-label');
            if (label) label.textContent = file.name;
        }
    };

    // ===== Init =====
    function init() {
        // Prevent FOUC for theme
        theme.init();
        toast.init();
        tabs.init();
        lightbox.init();
        pwa.init();

        // Global click handlers
        document.addEventListener('click', (e) => {
            // Close user menu
            if (!e.target.closest('.user-menu-trigger') && !e.target.closest('.user-dropdown')) {
                document.querySelectorAll('.user-dropdown').forEach(d => d.style.display = 'none');
            }

            // Close modals on backdrop click
            if (e.target.classList.contains('modal-backdrop')) {
                modal.closeAll();
            }
        });

        // Handle URL error/success params
        const params = new URLSearchParams(location.search);
        if (params.get('error')) toast.show(decodeURIComponent(params.get('error')), 'error');
        if (params.get('msg')) toast.show(decodeURIComponent(params.get('msg')), 'info');
        if (params.get('success')) toast.show(decodeURIComponent(params.get('success')), 'success');
    }

    document.addEventListener('DOMContentLoaded', init);

    return { theme, toast, modal, tabs, chat, push, pwa, recommendations, mapModule, lightbox, dragDrop };
})();

// ===== Global helpers =====
function toggleTheme() { GojoApp.theme.toggle(); }
function toggleUserMenu() {
    const menu = document.querySelector('.user-dropdown');
    if (menu) menu.style.display = menu.style.display === 'none' || !menu.style.display ? 'block' : 'none';
}
function closeModal(id) { GojoApp.modal.close(id); }
function openModal(id) { GojoApp.modal.open(id); }
function enableNotifications() { GojoApp.push.subscribe(); }
function installApp() { GojoApp.pwa.install(); }
