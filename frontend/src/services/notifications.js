
export const registerServiceWorker = async () => {
    if ('serviceWorker' in navigator) {
        try {
            const registration = await navigator.serviceWorker.register('/sw.js');
            console.log('Service Worker registered with scope:', registration.scope);
            return registration;
        } catch (error) {
            console.error('Service Worker registration failed:', error);
            return null;
        }
    }
    return null;
};

export const requestNotificationPermission = async () => {
    if (!('Notification' in window)) {
        console.log('This browser does not support notifications.');
        return false;
    }

    if (Notification.permission === 'granted') {
        return true;
    }

    const permission = await Notification.requestPermission();
    return permission === 'granted';
};

export const showNotification = async (title, options = {}) => {
    if (Notification.permission === 'granted') {
        try {
            // Try to use Service Worker for notification if available (better for Mobile/PWA)
            const registration = await navigator.serviceWorker.ready;
            if (registration && registration.showNotification) {
                await registration.showNotification(title, options);
            } else {
                // Fallback to standard Notification API
                const notification = new Notification(title, options);
                notification.onclick = () => {
                    window.focus();
                    notification.close();
                };
            }
        } catch (e) {
            console.error('Notification error:', e);
            // Last resort fallback
            new Notification(title, options);
        }
    }
};
