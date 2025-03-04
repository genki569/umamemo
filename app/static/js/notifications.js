document.addEventListener('DOMContentLoaded', function() {
    const notificationList = document.getElementById('notification-list');
    const notificationBadge = document.getElementById('notification-badge');
    
    // 通知を取得する関数
    function fetchNotifications() {
        fetch('/api/notifications')
            .then(response => response.json())
            .then(data => {
                updateNotificationBadge(data.unread_count);
                updateNotificationList(data.notifications);
            });
    }
    
    // 通知バッジを更新
    function updateNotificationBadge(count) {
        if (count > 0) {
            notificationBadge.textContent = count;
            notificationBadge.style.display = 'block';
        } else {
            notificationBadge.style.display = 'none';
        }
    }
    
    // 通知リストを更新
    function updateNotificationList(notifications) {
        notificationList.innerHTML = '';
        notifications.forEach(notification => {
            const item = createNotificationItem(notification);
            notificationList.appendChild(item);
        });
    }
    
    // 通知アイテムを作成
    function createNotificationItem(notification) {
        const item = document.createElement('div');
        item.className = `notification-item ${notification.is_read ? 'read' : 'unread'}`;
        
        item.innerHTML = `
            <div class="notification-content">
                <p>${notification.content}</p>
                <small>${new Date(notification.created_at).toLocaleString()}</small>
            </div>
            ${!notification.is_read ? '<button class="mark-read-btn" data-id="' + notification.id + '">既読</button>' : ''}
        `;
        
        return item;
    }
    
    // 定期的に通知を更新
    setInterval(fetchNotifications, 60000); // 1分ごとに更新
    fetchNotifications(); // 初回読み込み
}); 