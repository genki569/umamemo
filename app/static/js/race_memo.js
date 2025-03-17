document.addEventListener('DOMContentLoaded', function() {
    console.log('race_memo.js loaded');
    
    const memoSection = document.querySelector('.race-memo-section');
    const memoToggle = document.querySelector('.memo-toggle');
    
    if (memoToggle && memoSection) {
        console.log('Memo elements found');
        
        // 初期状態を設定
        memoSection.classList.add('minimized');
        
        memoToggle.addEventListener('click', function() {
            console.log('Memo toggle clicked');
            memoSection.classList.toggle('minimized');
            
            // アイコンを切り替え
            const icon = this.querySelector('i');
            if (memoSection.classList.contains('minimized')) {
                icon.className = 'fas fa-bookmark';
            } else {
                icon.className = 'fas fa-times';
            }
        });
    } else {
        console.log('Memo elements not found');
    }

    // メモフォームの送信処理
    const memoForm = document.querySelector('.race-memo-section form');
    if (memoForm) {
        memoForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // FormDataオブジェクトを作成
            const formData = new FormData(this);
            
            // CSRFトークンを確認
            const csrfToken = document.querySelector('input[name="csrf_token"]').value;
            
            fetch(this.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRF-Token': csrfToken
                },
                credentials: 'same-origin'
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('サーバーエラー: ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    // フォームをリセット
                    this.reset();
                    
                    // 新しいメモを追加
                    const memoList = document.querySelector('.memo-content');
                    const newMemo = document.createElement('div');
                    newMemo.className = 'sticky-note';
                    newMemo.id = `memo-${data.memo.id}`;
                    newMemo.innerHTML = `
                        <div class="sticky-note-content">${data.memo.content}</div>
                        <button type="button" class="btn btn-sm btn-danger sticky-note-delete" 
                                onclick="deleteRaceMemo(${data.memo.race_id}, ${data.memo.id})">
                            <i class="fas fa-trash"></i>
                        </button>
                    `;
                    
                    // フォームの後に新しいメモを挿入
                    memoList.insertBefore(newMemo, memoList.children[1]);
                } else {
                    throw new Error(data.message || 'メモの保存に失敗しました');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('メモの保存に失敗しました: ' + error.message);
            });
        });
    }

    // メモの保存処理
    document.querySelectorAll('.memo-input').forEach(textarea => {
        let timeoutId;
        
        textarea.addEventListener('input', function() {
            clearTimeout(timeoutId);
            
            timeoutId = setTimeout(() => {
                const horseId = this.dataset.horseId;
                const memoText = this.value;
                
                fetch(`/horses/${horseId}/memo`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: `memo=${encodeURIComponent(memoText)}`
                })
                .then(response => response.text())
                .then(content => {
                    // 返された内容をそのまま表示
                    this.value = content;
                })
                .catch(error => console.error('Error:', error));
            }, 500);
        });
    });

    // メモ削除機能
    window.deleteRaceMemo = function(raceId, memoId) {
        if (confirm('このメモを削除してもよろしいですか？')) {
            const csrfToken = document.querySelector('input[name="csrf_token"]').value;
            
            fetch(`/races/${raceId}/memos/${memoId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken
                },
                credentials: 'same-origin'
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('サーバーエラー: ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    const memoElement = document.getElementById(`memo-${memoId}`);
                    if (memoElement) {
                        memoElement.remove();
                    }
                } else {
                    throw new Error(data.message || 'メモの削除に失敗しました');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('メモの削除に失敗しました: ' + error.message);
            });
        }
    };
});

// メモの表示を整形する関数
function formatMemo(memos) {
    if (!memos || memos.length === 0) return '';
    
    // 最新のメモを取得
    const latestMemo = memos[memos.length - 1];
    return latestMemo.content;
}

// メモ保存後の処理
function updateMemoDisplay(response, memoArea) {
    if (typeof response === 'string') {
        try {
            response = JSON.parse(response);
        } catch (e) {
            console.error('JSON parse error:', e);
            return;
        }
    }
    
    // メモエリアに整形したテキストを表示
    memoArea.value = formatMemo(response);
}