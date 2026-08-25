self.addEventListener('install', function() {
  self.skipWaiting();
});

self.addEventListener('activate', function(event) {
  event.waitUntil((async function() {
    var keys = await caches.keys();
    await Promise.all(keys.map(function(key) {
      return caches.delete(key);
    }));
    await self.registration.unregister();
    var clients = await self.clients.matchAll({type: 'window'});
    clients.forEach(function(client) {
      client.navigate(client.url);
    });
  })());
});
