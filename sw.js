const CACHE='matchlab-v8';
const SHELL=['./','./index.html','./manifest.webmanifest','./icon.svg','./app.js','./research_ui.js','./tracker.js','./kalshi_ui.js','./icons/apple-touch-icon.png','./icons/icon-192.png','./icons/icon-512.png'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET'||new URL(e.request.url).origin!==self.location.origin)return;if(new URL(e.request.url).pathname.includes('/data/'))return;e.respondWith(fetch(e.request).then(r=>{if(!r.ok)return r;const copy=r.clone();caches.open(CACHE).then(c=>c.put(e.request,copy));return r}).catch(()=>caches.match(e.request)))});
