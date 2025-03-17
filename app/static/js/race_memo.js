document.addEventListener('DOMContentLoaded', function() {
    console.log('race_memo.js loaded');
    
    // メモセクションの表示/非表示切り替え
    const memoSection = document.querySelector('.race-memo-section');
    const memoToggle = document.querySelector('.memo-toggle');
    
    if (memoToggle && memoSection) {
        console.log('Memo elements found');
        
        // 初期状態を設定
        if (!memoSection.classList.contains('minimized')) {
            memoSection.classList.add('minimized');
        }
        
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

    // メモフォームの送信処理は行わない（通常のフォーム送信を使用）
    
    // メモ削除ボタンのイベントリスナーを削除（フォーム送信を使用）
    // document.querySelectorAll('.sticky-note-delete').forEach(button => {
    //     button.addEventListener('click', function(e) {
    //         // イベントリスナーの内容をコメントアウト
    //     });
    // });
});

// メモの表示を整形する関数（必要に応じて）
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