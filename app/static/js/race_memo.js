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
            
            // フォームデータを取得
            const formData = new FormData(this);
            const csrfToken = document.querySelector('input[name="csrf_token"]').value;
            
            // XMLHttpRequestを使用
            const xhr = new XMLHttpRequest();
            xhr.open('POST', this.action, true);
            xhr.setRequestHeader('X-CSRFToken', csrfToken);
            
            xhr.onload = function() {
                if (xhr.status >= 200 && xhr.status < 400) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        if (data.status === 'success') {
                            // フォームをリセット
                            memoForm.reset();
                            
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
                            if (memoList.children.length > 1) {
                                memoList.insertBefore(newMemo, memoList.children[1]);
                            } else {
                                memoList.appendChild(newMemo);
                            }
                        } else {
                            console.error('Error:', data.message);
                            alert('メモの保存に失敗しました: ' + data.message);
                        }
                    } catch (e) {
                        console.error('JSON parse error:', e);
                        alert('メモの保存に失敗しました: レスポンスの解析エラー');
                    }
                } else {
                    console.error('Server error:', xhr.status);
                    alert('メモの保存に失敗しました: サーバーエラー');
                }
            };
            
            xhr.onerror = function() {
                console.error('Request failed');
                alert('メモの保存に失敗しました: 通信エラー');
            };
            
            xhr.send(formData);
        });
    }

    // メモ削除機能
    window.deleteRaceMemo = function(raceId, memoId) {
        if (confirm('このメモを削除してもよろしいですか？')) {
            const csrfToken = document.querySelector('input[name="csrf_token"]').value;
            
            // XMLHttpRequestを使用
            const xhr = new XMLHttpRequest();
            xhr.open('DELETE', `/races/${raceId}/memos/${memoId}`, true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.setRequestHeader('X-CSRFToken', csrfToken);
            
            xhr.onload = function() {
                if (xhr.status >= 200 && xhr.status < 400) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        if (data.status === 'success') {
                            const memoElement = document.getElementById(`memo-${memoId}`);
                            if (memoElement) {
                                memoElement.remove();
                            }
                        } else {
                            console.error('Error:', data.message);
                            alert('メモの削除に失敗しました: ' + data.message);
                        }
                    } catch (e) {
                        console.error('JSON parse error:', e);
                        alert('メモの削除に失敗しました: レスポンスの解析エラー');
                    }
                } else {
                    console.error('Server error:', xhr.status);
                    alert('メモの削除に失敗しました: サーバーエラー');
                }
            };
            
            xhr.onerror = function() {
                console.error('Request failed');
                alert('メモの削除に失敗しました: 通信エラー');
            };
            
            xhr.send();
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