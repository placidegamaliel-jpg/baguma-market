const CACHE_NAME = 'baguma-v2.1';
const STATIC_ASSETS = [
  '/',
  '/login',
  '/dashboard',
  '/ventes',
  '/produits',
  '/stock',
  '/clients',
  '/dettes',
  '/recus',
  '/rapports',
  '/notifications',
  '/settings',
  '/static/icon-192.png',
  '/static/icon-512.png'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  
  e.respondWith(
    fetch(e.request).then(res => {
      if (res.ok) {
        const clone = res.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
      }
      return res;
    }).catch(() => caches.match(e.request).then(cached => cached || caches.match('/')))
  );
});

self.addEventListener('sync', e => {
  if (e.tag === 'sync-sales') {
    e.waitUntil(syncSales());
  }
});

async function syncSales() {
  const db = await openDB();
  const tx = db.transaction('pending-sales', 'readonly');
  const sales = await tx.objectStore('pending-sales').getAll();
  
  for (const sale of sales) {
    try {
      await fetch('/ventes/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(sale)
      });
      const delTx = db.transaction('pending-sales', 'readwrite');
      await delTx.objectStore('pending-sales').delete(sale.id);
    } catch (err) {
      console.log('Sync failed:', err);
    }
  }
}

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('baguma-offline', 1);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('pending-sales')) {
        db.createObjectStore('pending-sales', { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = e => reject(e);
  });
}