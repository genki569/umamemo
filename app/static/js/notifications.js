document.addEventListener('DOMContentLoaded', function() {
    const notificationList = document.getElementById('notification-list');
    const notificationBadge = document.getElementById('notification-badge');
    
    // 通知を取得する関数
    async function fetchNotifications() {
        try {
            // APIエンドポイントを修正
            const response = await fetch('/mypage/api/notifications');
            if (!response.ok) {
                console.warn('通知の取得に失敗しました:', response.status);
                return { notifications: [], unread_count: 0 };
            }
            const data = await response.json();
            updateNotificationBadge(data.unread_count);
            updateNotificationList(data.notifications);
            return data;
        } catch (error) {
            console.error('通知の取得中にエラーが発生しました:', error);
            return { notifications: [], unread_count: 0 };
        }
    }
    
    // 通知バッジを更新
    function updateNotificationBadge(count) {
        if (!notificationBadge) return;
        
        if (count > 0) {
            notificationBadge.textContent = count;
            notificationBadge.style.display = 'block';
        } else {
            notificationBadge.style.display = 'none';
        }
    }
    
    // 通知リストを更新
    function updateNotificationList(notifications) {
        if (!notificationList) return;
        
        notificationList.innerHTML = '';
        if (notifications && notifications.length > 0) {
            notifications.forEach(notification => {
                const item = createNotificationItem(notification);
                notificationList.appendChild(item);
            });
        } else {
            notificationList.innerHTML = '<div class="empty-notification">新しい通知はありません</div>';
        }
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
    
    // 通知カウントを取得して表示する
    function updateNotificationCount() {
        const badge = document.getElementById('notification-badge');
        if (!badge) return;
        
        fetch('/api/notifications/count')
            .then(response => response.json())
            .then(data => {
                const count = data.count;
                
                if (count > 0) {
                    badge.textContent = count;
                    badge.classList.remove('d-none');
                } else {
                    badge.classList.add('d-none');
                }
            })
            .catch(error => console.error('Error fetching notification count:', error));
    }
    
    // 要素が存在する場合のみ通知更新を設定
    if (notificationList || notificationBadge) {
        // 初回読み込み
        fetchNotifications();
        
        // 定期的に通知を更新（エラーが発生しても続行）
        setInterval(() => {
            try {
                fetchNotifications();
            } catch (e) {
                console.warn('通知の更新中にエラーが発生しました:', e);
            }
        }, 60000); // 1分ごとに更新
    }
    
    // ページ読み込み時と定期的に通知カウントを更新
    if (document.getElementById('notification-badge')) {
        updateNotificationCount();
        // 1分ごとに更新
        setInterval(updateNotificationCount, 60000);
    }
}); 