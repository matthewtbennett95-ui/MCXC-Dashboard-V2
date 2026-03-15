/**
 * MCXC Service Worker
 * Handles incoming Web Push notifications and displays them.
 * Must live at the root of the site to have full scope.
 * For Streamlit Cloud this file won't be served directly, but
 * it is needed for the GitHub Pages hosted tools (timer, leaderboard).
 */

self.addEventListener('push', function(event) {
  if (!event.data) return;

  let data = {};
  try { data = event.data.json(); } catch(e) { data = { title: 'MCXC', body: event.data.text() }; }

  const title   = data.title   || 'MCXC Team';
  const options = {
    body:    data.body  || 'New update from your coaches.',
    icon:    data.icon  || '/mcxc_logo.png',
    badge:   '/mcxc_logo.png',
    tag:     data.type  || 'mcxc-notification',
    data:    { url: data.url || '/' },
    vibrate: [200, 100, 200],
    requireInteraction: false,
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
      // If app is already open, focus it
      for (const client of windowClients) {
        if (client.url.includes(url) && 'focus' in client) {
          return client.focus();
        }
      }
      // Otherwise open a new window
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
