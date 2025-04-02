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