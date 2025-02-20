function toggleRaceFavorite(raceId) {
    console.log('Toggling favorite for race:', raceId); // デバッグ用

    fetch(`/api/races/${raceId}/favorite`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const btn = document.querySelector('.btn-race-favorite');
            btn.classList.toggle('active');
            console.log('Favorite toggled successfully'); // デバッグ用
        } else {
            console.error('Failed to toggle favorite:', data.error); // デバッグ用
        }
    })
    .catch(error => console.error('Error:', error));
}

// メモの開閉状態を管理
let isMemoMinimized = false;

// メモの開閉トグル関数
function toggleMemo() {
    const memoContainer = document.querySelector('.race-memo-container');
    const toggleButton = document.querySelector('.memo-toggle-btn');
    
    if (isMemoMinimized) {
        memoContainer.style.transform = 'translateX(0)';
        toggleButton.innerHTML = '<i class="fas fa-chevron-right"></i>';
    } else {
        memoContainer.style.transform = 'translateX(calc(100% - 40px))';
        toggleButton.innerHTML = '<i class="fas fa-chevron-left"></i>';
    }
    
    isMemoMinimized = !isMemoMinimized;
}

// メモの削除機能
function deleteRaceMemo(raceId, memoId) {
    if (confirm('このメモを削除してもよろしいですか？')) {
        fetch(`/race/${raceId}/memo/${memoId}`, {
            method: 'DELETE',
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                document.getElementById(`memo-${memoId}`).remove();
            }
        });
    }
}

// ページ読み込み時に開閉ボタンを追加
document.addEventListener('DOMContentLoaded', function() {
    const memoContainer = document.querySelector('.race-memo-container');
    const toggleButton = document.createElement('button');
    toggleButton.className = 'memo-toggle-btn';
    toggleButton.innerHTML = '<i class="fas fa-chevron-right"></i>';
    toggleButton.onclick = toggleMemo;
    memoContainer.appendChild(toggleButton);
}); 