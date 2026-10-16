/**
 * The Flutter apps registered a service worker for their mount. Remove it, as the Flutter
 * index.html did, so it cannot serve old cached files. `public/flutter_service_worker.js`
 * covers a worker that still serves the old index.html: its update check gets a kill switch.
 */
export function removeLegacyServiceWorker(): void {
  if (!('serviceWorker' in navigator)) return
  const appScope = new URL('.', document.baseURI).href
  void navigator.serviceWorker.getRegistrations().then((registrations) => {
    for (const registration of registrations) {
      if (registration.scope === appScope) void registration.unregister()
    }
  })
}
