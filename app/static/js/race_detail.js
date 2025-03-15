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
    // モバイル表示かどうかを確認
    const isMobile = window.innerWidth < 768;
    
    if (isMobile) {
        // テーブルをカード形式に変換
        const tableRows = document.querySelectorAll('.entry-table tbody tr');
        
        tableRows.forEach(row => {
            // 着順によってクラスを追加
            const resultCell = row.querySelector('td:first-child');
            if (resultCell && resultCell.textContent.trim()) {
                const result = resultCell.textContent.trim();
                if (result === '1') {
                    row.classList.add('first-place');
                } else if (result === '2') {
                    row.classList.add('second-place');
                } else if (result === '3') {
                    row.classList.add('third-place');
                }
            }
            
            // カードをタップしたときの処理
            row.addEventListener('click', function(e) {
                // ボタンをクリックした場合は何もしない
                if (e.target.tagName === 'BUTTON' || e.target.tagName === 'A' || e.target.tagName === 'I' || 
                    e.target.closest('button') || e.target.closest('a')) {
                    return;
                }
                
                // 馬名のセルを取得
                const horseNameCell = this.querySelector('td:nth-child(4)');
                if (horseNameCell) {
                    const link = horseNameCell.querySelector('a');
                    if (link) {
                        // 馬詳細ページに移動
                        window.location.href = link.href;
                    }
                }
            });
        });
        
        // 各カードに展開/折りたたみ機能を追加
        tableRows.forEach(row => {
            // 最初は詳細情報を折りたたむ
            const detailCells = Array.from(row.querySelectorAll('td')).slice(5, 13);
            detailCells.forEach(cell => {
                cell.style.display = 'none';
            });
            
            // 馬名セルに展開/折りたたみボタンを追加
            const horseNameCell = row.querySelector('td:nth-child(4)');
            if (horseNameCell) {
                const toggleButton = document.createElement('button');
                toggleButton.className = 'btn-toggle-details';
                toggleButton.innerHTML = '<i class="fas fa-chevron-down"></i>';
                
                toggleButton.addEventListener('click', function(e) {
                    e.stopPropagation();
                    
                    // 詳細情報の表示/非表示を切り替え
                    const isExpanded = detailCells[0].style.display !== 'none';
                    
                    detailCells.forEach(cell => {
                        cell.style.display = isExpanded ? 'none' : 'block';
                    });
                    
                    // カードの展開状態を切り替え
                    row.classList.toggle('expanded', !isExpanded);
                    
                    // ボタンのアイコンを切り替え
                    this.innerHTML = isExpanded ? 
                        '<i class="fas fa-chevron-down"></i>' : 
                        '<i class="fas fa-chevron-up"></i>';
                });
                
                horseNameCell.appendChild(toggleButton);
            }
        });
        
        // 表示の最適化
        document.querySelector('.race-entries h3').textContent = '出走馬一覧';
        
        // スクロール位置をリセット
        window.scrollTo(0, 0);
    }
}); 