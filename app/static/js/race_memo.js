document.addEventListener('DOMContentLoaded', function() {
    const memoSection = document.querySelector('.race-memo-section');
    const toggleButton = document.querySelector('.memo-toggle');

    if (toggleButton && memoSection) {
        toggleButton.addEventListener('click', function(e) {
            e.preventDefault();
            memoSection.classList.toggle('minimized');
            const icon = this.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-chevron-left');
                icon.classList.toggle('fa-chevron-right');
            }
        });
    }

    const memoForm = document.querySelector('form');
    if (memoForm) {
        memoForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            
            fetch(this.action, {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
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
                    const form = document.querySelector('form.sticky-note');
                    form.parentNode.insertBefore(newMemo, form.nextSibling);
                } else {
                    throw new Error(data.message || 'メモの保存に失敗しました');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('メモの保存に失敗しました');
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
});

function deleteRaceMemo(raceId, memoId) {
    if (!confirm('このメモを削除してもよろしいですか？')) {
        return;
    }

    fetch(`/race/${raceId}/memo/${memoId}/delete`, {
        method: 'POST'
    })
    .then(response => response.json())
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
        alert('メモの削除に失敗しました');
    });
}

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