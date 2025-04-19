// 通知を取得する関数
async function fetchNotifications() {
    try {
        // APIエンドポイントを修正
        const response = await fetch('/mypage/api/notifications');
        if (!response.ok) {
            throw new Error('通知の取得に失敗しました');
        }
        const data = await response.json();
        return data.notifications || []; // レスポンスから通知配列を取得
    } catch (error) {
        console.error('通知の取得中にエラーが発生しました:', error);
        return [];
    }
}

// 通知を表示する関数
function displayNotifications(notifications, containerId = 'dashboard-notifications') {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (notifications.length === 0) {
        container.innerHTML = '<p class="no-content">新しい通知はありません</p>';
        return;
    }

    container.innerHTML = '';
    notifications.forEach(notification => {
        const notificationItem = document.createElement('div');
        notificationItem.className = `notification-item ${notification.is_read ? '' : 'unread'}`; // readをis_readに修正
        notificationItem.dataset.id = notification.id;
        
        // 通知タイプに基づくアイコンクラスの設定
        let iconClass = 'fa-bell';
        if (notification.type === 'favorite_horse_entry') {
            iconClass = 'fa-horse';
        } else if (notification.type === 'memo_comment') {
            iconClass = 'fa-comment';
        }
        
        notificationItem.innerHTML = `
            <div class="notification-icon">
                <i class="fas ${notification.icon_class || iconClass}"></i>
            </div>
            <div class="notification-content">
                <p class="notification-text">${notification.message}</p>
                <span class="notification-time">${formatDate(notification.created_at)}</span>
            </div>
        `;
        
        // リンクがある場合はクリック時の挙動を変更
        if (notification.link) {
            notificationItem.addEventListener('click', () => {
                markAsRead(notification.id);
                window.location.href = notification.link;
            });
        } else {
            // リンクがない場合は既読のみにする
            notificationItem.addEventListener('click', () => markAsRead(notification.id));
        }
        
        container.appendChild(notificationItem);
    });
}

// 日付をフォーマットする関数
function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffDay > 0) {
        return `${diffDay}日前`;
    } else if (diffHour > 0) {
        return `${diffHour}時間前`;
    } else if (diffMin > 0) {
        return `${diffMin}分前`;
    } else {
        return '今すぐ';
    }
}

// 通知を既読にする関数
async function markAsRead(notificationId) {
    try {
        const response = await fetch(`/mypage/api/notifications/${notificationId}/read`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
            }
        });
        
        if (!response.ok) {
            throw new Error('通知の既読処理に失敗しました');
        }
        
        // UIを更新
        const notificationItem = document.querySelector(`.notification-item[data-id="${notificationId}"]`);
        if (notificationItem) {
            notificationItem.classList.remove('unread');
        }
        
        return await response.json();
    } catch (error) {
        console.error('通知の既読処理中にエラーが発生しました:', error);
    }
}

// ページ読み込み時に通知を取得して表示
document.addEventListener('DOMContentLoaded', async () => {
    const notificationsContainer = document.getElementById('dashboard-notifications');
    if (notificationsContainer) {
        const data = await fetchNotifications();
        displayNotifications(data);
    }
}); 