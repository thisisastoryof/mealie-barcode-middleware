// Minimal service worker for push notifications on mobile browsers
self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    var url = event.notification.data && event.notification.data.url;
    if (url) {
        event.waitUntil(clients.openWindow(url));
    }
});
