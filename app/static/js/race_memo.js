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
            console.log('Form submit intercepted');
            
            // 通常のフォーム送信を使用
            const form = this;
            const formAction = form.action;
            const formMethod = form.method;
            
            console.log('Submitting form to:', formAction, 'with method:', formMethod);
            
            // フォームを直接送信
            form.submit();
            
            // 送信後にページをリロード
            setTimeout(function() {
                window.location.reload();
            }, 500);
        });
    }

    // メモ削除機能
    window.deleteRaceMemo = function(raceId, memoId) {
        if (confirm('このメモを削除してもよろしいですか？')) {
            console.log('Deleting memo:', memoId, 'for race:', raceId);
            
            // 削除用のフォームを動的に作成
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = `/races/${raceId}/memos/${memoId}/delete`;
            form.style.display = 'none';
            
            // CSRFトークンを追加
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrf_token';
            csrfInput.value = document.querySelector('input[name="csrf_token"]').value;
            form.appendChild(csrfInput);
            
            // フォームをドキュメントに追加して送信
            document.body.appendChild(form);
            form.submit();
            
            // 送信後にページをリロード
            setTimeout(function() {
                window.location.reload();
            }, 500);
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