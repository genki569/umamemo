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

// レース詳細ページのカード表示
document.addEventListener('DOMContentLoaded', function() {
    // モバイル表示の場合、テーブルをカード表示に変換
    if (window.innerWidth < 768) {
        const table = document.querySelector('.entry-table');
        if (!table) return;
        
        // テーブルの行を取得
        const tableRows = Array.from(table.querySelectorAll('tbody tr'));
        if (tableRows.length === 0) return;
        
        // テーブルを非表示にする
        table.style.display = 'none';
        
        // カードコンテナを作成
        const cardContainer = document.createElement('div');
        cardContainer.className = 'mobile-entries';
        table.parentNode.insertBefore(cardContainer, table.nextSibling);
        
        // 各行をカードに変換
        tableRows.forEach(row => {
            // カードを作成
            const card = document.createElement('div');
            card.className = 'entry-card';
            
            // 必要なデータを抽出
            const cells = Array.from(row.querySelectorAll('td'));
            if (cells.length < 4) return;
            
            // カードの内容を構築
            const horseName = cells[3].textContent.trim();
            const horseLink = cells[3].querySelector('a') ? cells[3].querySelector('a').href : null;
            const jockey = cells[4].textContent.trim();
            const weight = cells[5].textContent.trim();
            const odds = cells[8].textContent.trim();
            const popularity = cells[9].textContent.trim();
            
            // カードのHTMLを構築
            card.innerHTML = `
                <div class="card-header">
                    <span class="gate">${cells[0].textContent.trim()}</span>
                    <span class="horse-number">${cells[1].textContent.trim()}</span>
                    <h4 class="horse-name">${horseName}</h4>
                </div>
                <div class="card-body">
                    <div class="info-row">
                        <span class="label">騎手:</span>
                        <span class="value">${jockey}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">斤量:</span>
                        <span class="value">${weight}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">オッズ:</span>
                        <span class="value">${odds}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">人気:</span>
                        <span class="value">${popularity}</span>
                    </div>
                </div>
            `;
            
            // カードをクリックしたときの処理
            card.addEventListener('click', function() {
                if (horseLink) {
                    window.location.href = horseLink;
                }
            });
            
            // カードをコンテナに追加
            cardContainer.appendChild(card);
        });
    }
}); 