// モバイルナビゲーション専用のスクリプト
document.addEventListener('DOMContentLoaded', function() {
    console.log('Mobile navigation script loaded');
    
    // モバイルデバイスの場合のみ実行
    if (window.innerWidth <= 768) {
        // ナビゲーションの要素を取得
        const navbarToggler = document.querySelector('.navbar-toggler');
        const navbarCollapse = document.querySelector('.navbar-collapse');
        
        console.log('Navbar toggler:', navbarToggler);
        console.log('Navbar collapse:', navbarCollapse);
        
        // トグルボタンのクリックイベント
        if (navbarToggler && navbarCollapse) {
            navbarToggler.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                console.log('Toggler clicked');
                
                // クラスをトグル
                if (navbarCollapse.classList.contains('show')) {
                    navbarCollapse.classList.remove('show');
                    console.log('Navbar collapsed');
                } else {
                    navbarCollapse.classList.add('show');
                    console.log('Navbar expanded');
                }
            });
            
            // ドキュメント全体のクリックイベント（メニュー外をクリックしたら閉じる）
            document.addEventListener('click', function(e) {
                if (navbarCollapse.classList.contains('show') && 
                    !navbarToggler.contains(e.target) && 
                    !navbarCollapse.contains(e.target)) {
                    navbarCollapse.classList.remove('show');
                    console.log('Navbar closed by outside click');
                }
            });
            
            // ナビゲーションリンクのクリックイベント
            const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
            navLinks.forEach(link => {
                link.addEventListener('click', function() {
                    navbarCollapse.classList.remove('show');
                    console.log('Navbar closed by link click');
                });
            });
        }
        
        // ドロップダウンメニューの処理
        const dropdownToggles = document.querySelectorAll('.dropdown-toggle');
        dropdownToggles.forEach(toggle => {
            toggle.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                console.log('Dropdown toggle clicked');
                
                const dropdownMenu = this.nextElementSibling;
                if (dropdownMenu) {
                    // 他のドロップダウンを閉じる
                    document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
                        if (menu !== dropdownMenu) {
                            menu.classList.remove('show');
                        }
                    });
                    
                    // このドロップダウンをトグル
                    dropdownMenu.classList.toggle('show');
                    console.log('Dropdown toggled');
                }
            });
        });
        
        // ドロップダウンアイテムのクリックイベント
        const dropdownItems = document.querySelectorAll('.dropdown-item');
        dropdownItems.forEach(item => {
            item.addEventListener('click', function() {
                // メニューを閉じる
                navbarCollapse.classList.remove('show');
                console.log('Navbar closed by dropdown item click');
            });
        });
    }
}); 