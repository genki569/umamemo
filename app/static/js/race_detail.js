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

// メモの削除機能 - 無効化
// function deleteRaceMemo(raceId, memoId) {
//     // 関数の内容をコメントアウト
// }

// テーブルの表示を最適化
function optimizeTableDisplay() {
    const entryTable = document.querySelector('.entry-table');
    if (!entryTable) return;
    
    // 馬名のセルにクラスを追加
    const horseNameCells = entryTable.querySelectorAll('td:nth-child(4)');
    horseNameCells.forEach(cell => {
        cell.classList.add('horse-name');
    });
    
    // 各セルの幅を調整
    const headerCells = entryTable.querySelectorAll('th');
    headerCells.forEach((cell, index) => {
        // 必要最小限の幅を設定
        if (index === 0 || index === 1 || index === 2) { // 着順、枠番、馬番
            cell.style.width = '40px';
            cell.style.minWidth = '40px';
            cell.style.maxWidth = '40px';
        } else if (index === 3) { // 馬名
            cell.style.width = '120px';
            cell.style.minWidth = '120px';
            cell.style.maxWidth = '120px';
        } else if (index === 5) { // 騎手
            cell.style.width = '80px';
            cell.style.minWidth = '80px';
            cell.style.maxWidth = '80px';
        } else { // その他
            cell.style.width = '70px';
            cell.style.minWidth = '70px';
        }
    });
    
    // テーブルを強制的に再描画
    entryTable.style.display = 'none';
    setTimeout(() => {
        entryTable.style.display = 'table';
        
        // 表示後に再度幅を調整
        setTimeout(() => {
            const tableWidth = entryTable.offsetWidth;
            const containerWidth = entryTable.closest('.table-responsive').offsetWidth;
            
            // テーブルが表示領域より広い場合、固定列の背景色を確実に設定
            if (tableWidth > containerWidth) {
                const fixedCells = entryTable.querySelectorAll('td:nth-child(-n+4)');
                fixedCells.forEach(cell => {
                    const row = cell.closest('tr');
                    const isEven = [...row.parentNode.children].indexOf(row) % 2 === 1;
                    
                    if (isEven) {
                        cell.style.backgroundColor = '#f8f9fa';
                    } else {
                        cell.style.backgroundColor = '#fff';
                    }
                });
            }
        }, 100);
    }, 10);
}

// DOMContentLoaded時に実行
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

        // テーブルの行をタップしたときの処理
        const tableRows = table.querySelectorAll('tbody tr');
        tableRows.forEach(row => {
            row.addEventListener('click', function(e) {
                // ボタンをクリックした場合は何もしない
                if (e.target.tagName === 'BUTTON' || e.target.tagName === 'A' || e.target.tagName === 'I') {
                    return;
                }
                
                // 他の行の選択を解除
                tableRows.forEach(r => {
                    if (r !== this) {
                        r.classList.remove('selected-row');
                        r.style.backgroundColor = '';
                    }
                });
                
                // この行の選択状態をトグル
                this.classList.toggle('selected-row');
                
                // 選択された行のスタイルを設定
                if (this.classList.contains('selected-row')) {
                    this.style.backgroundColor = 'rgba(79, 70, 229, 0.2)';
                } else {
                    this.style.backgroundColor = '';
                }
            });
        });
        
        // ダブルタップで馬詳細ページに移動
        const horseCells = table.querySelectorAll('td:nth-child(4)');
        horseCells.forEach(cell => {
            let lastTap = 0;
            
            cell.addEventListener('click', function(e) {
                const currentTime = new Date().getTime();
                const tapLength = currentTime - lastTap;
                
                if (tapLength < 300 && tapLength > 0) {
                    // ダブルタップ検出
                    const link = this.querySelector('a');
                    if (link) {
                        window.location.href = link.href;
                    }
                    e.preventDefault();
                }
                
                lastTap = currentTime;
            });
        });
    }
    
    // スクロールインジケーターの制御
    const tableResponsive = document.querySelector('.table-responsive');
    if (tableResponsive) {
        // スクロール時にインジケーターを非表示
        tableResponsive.addEventListener('scroll', function() {
            if (this.scrollLeft > 50) {
                this.classList.add('scrolled');
            } else {
                this.classList.remove('scrolled');
            }
        });
        
        // 初期状態でスクロール可能かチェック
        setTimeout(function() {
            if (tableResponsive.scrollWidth <= tableResponsive.clientWidth) {
                tableResponsive.classList.add('scrolled');
            }
        }, 500);
    }
    
    // テーブルの表示を最適化
    optimizeTableDisplay();
    
    // ウィンドウのリサイズ時にも最適化
    window.addEventListener('resize', optimizeTableDisplay);
    
    // 向きが変わった時にも最適化
    window.addEventListener('orientationchange', function() {
        setTimeout(optimizeTableDisplay, 100);
    });
}); 