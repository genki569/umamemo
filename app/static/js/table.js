document.addEventListener('DOMContentLoaded', function() {
    const tableWrappers = document.querySelectorAll('.table-responsive-wrapper');
    
    tableWrappers.forEach(wrapper => {
        const checkScroll = () => {
            if (wrapper.scrollWidth > wrapper.clientWidth) {
                wrapper.classList.add('has-scroll');
            } else {
                wrapper.classList.remove('has-scroll');
            }
        };
        
        // 初期チェック
        checkScroll();
        
        // リサイズ時にチェック
        window.addEventListener('resize', checkScroll);
        
        // スクロール位置による影の表示制御
        wrapper.addEventListener('scroll', () => {
            if (wrapper.scrollLeft + wrapper.clientWidth >= wrapper.scrollWidth) {
                wrapper.classList.remove('has-scroll');
            } else {
                wrapper.classList.add('has-scroll');
            }
        });
    });
}); 