var observer; // グローバル変数として一度だけ宣言

// 使用時に初期化されていない場合のみ初期化
if (!observer) {
    observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });
}

// エラーハンドリングの改善
window.onerror = function(message, source, lineno, colno, error) {
    console.log('JavaScript Error Details');
    console.log('Message: ' + message);
    console.log('URL: ' + source);
    console.log('Line: ' + lineno);
    console.log('Column: ' + colno);
    console.log('Error object: ' + error);
    return false;
};

// DOMContentLoadedイベントリスナー
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded');
    
    // 要素を取得
    const fadeElements = document.querySelectorAll('.fade-in');
    const scaleElements = document.querySelectorAll('.scale-in');
    
    // フェードイン要素にIntersectionObserverを適用
    fadeElements.forEach(function(element) {
        observer.observe(element);
    });
    
    // スケールイン要素にIntersectionObserverを適用
    scaleElements.forEach(function(element) {
        observer.observe(element);
    });
    
    // 可視性チェック
    console.log('Checking visibility...');
    
    // カード要素のカウント
    const cards = document.querySelectorAll('.card');
    console.log('Cards count: ' + cards.length);
    
    // モバイルナビゲーションの初期化
    console.log('Initializing mobile navigation');
    
    // スクロールスタイルの修正
    console.log('Fixing scroll styles');
}); 