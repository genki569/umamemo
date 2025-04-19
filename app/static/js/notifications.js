document.addEventListener('DOMContentLoaded', function() {
    const notificationList = document.getElementById('notification-list');
    const notificationBadge = document.getElementById('notification-badge');
    
    // 通知を取得する関数
    async function fetchNotifications() {
        try {
            // APIエンドポイントを呼び出し
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
        item.dataset.id = notification.id;
        
        // 通知タイプに基づくアイコンクラスの設定
        let iconClass = 'fa-bell';
        if (notification.type === 'favorite_horse_entry') {
            iconClass = 'fa-horse text-success';
        } else if (notification.type === 'memo_comment') {
            iconClass = 'fa-comment text-info';
        }
        
        item.innerHTML = `
            <div class="notification-content">
                <div class="notification-header">
                    <i class="fas ${iconClass} me-2"></i>
                    <p>${notification.message}</p>
                </div>
                <small>${new Date(notification.created_at).toLocaleString()}</small>
            </div>
            ${!notification.is_read ? '<button class="mark-read-btn" data-id="' + notification.id + '">既読</button>' : ''}
        `;
        
        // リンクがある場合はクリック時の挙動を追加
        if (notification.link) {
            item.addEventListener('click', (e) => {
                if (e.target.classList.contains('mark-read-btn')) return; // 既読ボタンの場合は除外
                window.location.href = notification.link;
            });
        }
        
        // 既読ボタンのイベント追加
        const readBtn = item.querySelector('.mark-read-btn');
        if (readBtn) {
            readBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // クリックイベントの伝播を停止
                markNotificationAsRead(notification.id, item);
            });
        }
        
        return item;
    }
    
    // 通知を既読にする関数
    async function markNotificationAsRead(notificationId, itemElement) {
        try {
            const response = await fetch(`/mypage/api/notifications/${notificationId}/read`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                console.error('通知の既読処理に失敗しました:', response.status);
                return;
            }
            
            // UI更新
            if (itemElement) {
                itemElement.classList.remove('unread');
                itemElement.classList.add('read');
                const readBtn = itemElement.querySelector('.mark-read-btn');
                if (readBtn) readBtn.remove();
            }
            
            // 通知カウント更新
            updateNotificationCount();
        } catch (error) {
            console.error('通知の既読処理中にエラーが発生しました:', error);
        }
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