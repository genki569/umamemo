document.addEventListener('DOMContentLoaded', function() {
    // Enterキーでもリンクを実行できるように
    document.querySelectorAll('.race-item').forEach(item => {
        item.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.click();
            }
        });
    });

    // 日付選択時のスムーズスクロール
    const dateSelect = document.getElementById('dateSelect');
    if (dateSelect) {
        dateSelect.addEventListener('change', function() {
            setTimeout(() => {
                window.scrollTo({
                    top: 0,
                    behavior: 'smooth'
                });
            }, 100);
        });
    }

    // 日付選択時のページリセット
    const dateSelect = document.getElementById('dateSelect');
    if (dateSelect) {
        dateSelect.addEventListener('change', function() {
            const url = new URL(this.value, window.location.origin);
            url.searchParams.set('page', '1');
            window.location.href = url.toString();
        });
    }

    // レース結果の遅延読み込みを最適化
    function loadRaceResults(raceId) {
        const resultContainer = document.getElementById(`race-results-${raceId}`);
        
        if (!resultContainer || resultContainer.dataset.loaded === 'true') {
            return;
        }

        resultContainer.dataset.loaded = 'true';
        
        // キャッシュの確認
        const cachedResults = sessionStorage.getItem(`race-results-${raceId}`);
        if (cachedResults) {
            displayRaceResults(resultContainer, JSON.parse(cachedResults));
            return;
        }
        
        fetch(`/api/race_results/${raceId}`)
            .then(response => response.json())
            .then(data => {
                // キャッシュに保存
                sessionStorage.setItem(`race-results-${raceId}`, JSON.stringify(data.results));
                displayRaceResults(resultContainer, data.results);
            })
            .catch(error => {
                console.error('Error:', error);
                resultContainer.dataset.loaded = 'false';  // 再試行可能に
            });
    }

    // 遅延読み込みの最適化
    function initLazyLoading() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const raceId = entry.target.dataset.raceId;
                    requestIdleCallback(() => loadRaceResults(raceId));
                }
            });
        }, {
            rootMargin: '50px 0px',  // 事前読み込みの範囲を設定
            threshold: 0.1
        });

        document.querySelectorAll('.race-results-container').forEach(container => {
            observer.observe(container);
        });
    }
}); 