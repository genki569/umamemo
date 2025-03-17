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
    // モバイル表示でもテーブル表示を維持する（カード表示を無効化）
    if (window.innerWidth < 768) {
        // テーブルのスタイルを調整して見やすくする
        const table = document.querySelector('.entry-table');
        if (!table) return;
        
        // テーブルのスタイルを調整
        table.style.fontSize = '0.85rem';
        
        // テーブルの横スクロールを有効にする
        const tableContainer = table.closest('.table-responsive');
        if (tableContainer) {
            tableContainer.style.overflowX = 'auto';
        }
        
        // 各セルの幅を調整
        const headerCells = table.querySelectorAll('th');
        headerCells.forEach(cell => {
            // 必要最小限の幅を設定
            if (cell.textContent.includes('馬番') || cell.textContent.includes('枠')) {
                cell.style.width = '40px';
                cell.style.minWidth = '40px';
            } else if (cell.textContent.includes('騎手') || cell.textContent.includes('タイム') || 
                       cell.textContent.includes('着差') || cell.textContent.includes('上り') || 
                       cell.textContent.includes('人気') || cell.textContent.includes('オッズ')) {
                cell.style.width = '60px';
                cell.style.minWidth = '60px';
            } else if (cell.textContent.includes('馬名')) {
                cell.style.width = '120px';
                cell.style.minWidth = '120px';
            }
        });
        
        // 行の高さを調整
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            row.style.height = 'auto';
        });
        
        // 馬名のセルを強調
        const horseNameCells = table.querySelectorAll('td:nth-child(4)');
        horseNameCells.forEach(cell => {
            cell.style.fontWeight = 'bold';
            cell.style.textAlign = 'left';
        });
    }
}); 