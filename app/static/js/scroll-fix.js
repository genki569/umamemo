// スクロール問題を修正するスクリプト
document.addEventListener('DOMContentLoaded', function() {
    console.log('Scroll fix script loaded');
    
    // スクロール関連の問題を修正
    function fixScrollIssues() {
        // body要素のスタイルを修正
        document.body.style.height = 'auto';
        document.body.style.overflow = 'auto';
        document.body.style.position = 'static';
        
        // html要素のスタイルも修正
        document.documentElement.style.height = 'auto';
        document.documentElement.style.overflow = 'auto';
        document.documentElement.style.position = 'static';
        
        // 固定位置の要素を除いて、すべての要素のpositionプロパティをチェック
        document.querySelectorAll('*:not(.navbar):not(.fixed-bottom):not(.fixed-top)').forEach(el => {
            const position = window.getComputedStyle(el).position;
            if (position === 'fixed' && !el.classList.contains('navbar') && 
                !el.classList.contains('fixed-bottom') && !el.classList.contains('fixed-top') &&
                !el.classList.contains('race-memo-section') && !el.classList.contains('memo-toggle-btn')) {
                console.log('Fixed element found and modified:', el);
                el.style.position = 'absolute';
            }
        });
        
        // スクロールイベントを監視して、スクロールが止まったら強制的に再開
        let lastScrollTop = 0;
        let scrollStuckCounter = 0;
        
        window.addEventListener('scroll', function() {
            const st = window.pageYOffset || document.documentElement.scrollTop;
            
            // スクロール位置が変わらない場合
            if (st === lastScrollTop) {
                scrollStuckCounter++;
                
                // 10回連続で同じ位置にいる場合、スクロールが止まっていると判断
                if (scrollStuckCounter > 10) {
                    console.log('Scroll appears to be stuck, forcing refresh');
                    // 強制的にスクロール位置を少し動かす
                    window.scrollBy(0, 1);
                    window.scrollBy(0, -1);
                    scrollStuckCounter = 0;
                }
            } else {
                // スクロール位置が変わった場合はカウンターをリセット
                scrollStuckCounter = 0;
                lastScrollTop = st;
            }
        }, { passive: true });
    }
    
    // 初回実行
    fixScrollIssues();
    
    // 読み込み完了時にも実行
    window.addEventListener('load', fixScrollIssues);
    
    // 1秒後にも実行（遅延読み込みの問題対策）
    setTimeout(fixScrollIssues, 1000);
    
    // 3秒後にも実行（最終チェック）
    setTimeout(fixScrollIssues, 3000);
}); 