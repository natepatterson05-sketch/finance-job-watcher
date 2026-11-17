const SHELL_CACHE = 'finance-watcher-shell-v4';
const ROOT = new URL('./', self.location.href);
const SHELL = ['./', './index.html', './browse.html', './market.html', './assets/style.css?v=editorial-4', './assets/app.mjs?v=editorial-4', './assets/metrics.mjs', './manifest.webmanifest', './assets/icon.svg', './assets/icon-192.png', './assets/icon-512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(SHELL_CACHE).then(cache => cache.addAll(SHELL.map(path => new URL(path, ROOT).href))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('finance-watcher-shell-') && key !== SHELL_CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== ROOT.origin || !url.pathname.startsWith(ROOT.pathname)) return;
  const relative = url.pathname.slice(ROOT.pathname.length);
  // app.mjs stores a validated history/status pair, so never mix cached data files.
  if (relative.startsWith('data/') || relative === '__last_data_pair') return;
  const path = new URL(relative || 'index.html', ROOT).href;
  const asset = SHELL.find(item => new URL(item, ROOT).pathname === url.pathname || (relative === '' && item === './index.html'));
  const allowed = Boolean(asset);
  if (!allowed) return;
  event.respondWith((async () => {
    const cache = await caches.open(SHELL_CACHE);
    try {
      const response = await fetch(event.request);
      if (!response.ok) throw new Error('Page unavailable');
      await cache.put(path, response.clone());
      return response;
    } catch (error) {
      const saved = await cache.match(path) || await cache.match(new URL(asset, ROOT).href);
      if (saved) return saved;
      throw error;
    }
  })());
});
