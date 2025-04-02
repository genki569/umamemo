// グローバル変数として一度だけ宣言
var observer;
var csrfToken;

document.addEventListener('DOMContentLoaded', function() {
    console.log('main.js loaded');
    
    // CSRFトークンを一度だけ取得
    if (!csrfToken) {
        csrfToken = document.querySelector('meta[name="csrf-token"]')?.content ||
                   document.querySelector('#csrf-form input[name="csrf_token"]')?.value ||
                   document.querySelector('input[name="csrf_token"]')?.value;
        console.log('CSRF Token initialized:', csrfToken ? 'Yes' : 'No');
    }
    
    // モバイルデバイスの検出
    const isMobile = window.innerWidth <= 768;
    console.log('Mobile device detected:', isMobile);
    
    // モバイル向けの最適化
    if (isMobile) {
        // 画像の遅延読み込み
        const lazyImages = document.querySelectorAll('img[data-src]');
        lazyImages.forEach(img => {
            img.src = img.dataset.src;
            img.removeAttribute('data-src');
        });
        
        // フォントサイズの最適化
        document.body.style.fontSize = '16px';
        
        // ヘッダーの最適化
        const header = document.querySelector('header');
        if (header) {
            header.style.padding = '10px 15px';
        }
        
        // コンテンツの最適化
        const containers = document.querySelectorAll('.container');
        containers.forEach(container => {
            container.style.padding = '0 15px';
        });
    }
    
    // ページの表示を確認
    setTimeout(() => {
        const body = document.body;
        if (body.offsetHeight === 0 || body.innerHTML.trim() === '') {
            console.error('Page content is empty or not visible');
            // 強制的にページを再描画
            body.style.display = 'none';
            setTimeout(() => {
                body.style.display = 'block';
            }, 10);
        } else {
            console.log('Page content is visible');
        }
        
        // ヒーローセクションの表示を確認
        const heroSection = document.querySelector('.hero-section');
        if (heroSection) {
            console.log('Hero section found');
            heroSection.style.display = 'block';
            heroSection.style.visibility = 'visible';
            heroSection.style.opacity = '1';
            
            const heroContent = document.querySelector('.hero-content');
            if (heroContent) {
                console.log('Hero content found');
                heroContent.style.display = 'flex';
                heroContent.style.visibility = 'visible';
                heroContent.style.opacity = '1';
            }
        }
    }, 500);

    // フラッシュメッセージの自動非表示
    const flashes = document.querySelector('.flashes');
    if (flashes) {
        setTimeout(() => {
            flashes.style.display = 'none';
        }, 5000); // 5秒後に非表示
    }

    // 予想ボタンのイベントリスナー
    const predictButton = document.getElementById('predict-button');
    if (predictButton) {
        predictButton.addEventListener('click', performPrediction);
    }

    // フォームのバリデーション
    const loginForm = document.querySelector('form');
    if (loginForm) {
        loginForm.addEventListener('submit', validateForm);
    }

    // レビュー購入処理
    document.querySelectorAll('.purchase-review').forEach(button => {
        button.addEventListener('click', purchaseReview);
    });

    // 新しいアニメーション機能の追加
    // AOSの初期化
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 800,
            easing: 'ease-out',
            once: true,
            offset: 100,
            delay: 100
        });
    }

    // Intersection Observerの設定
    if (!observer) {
        observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    
                    // 数値のカウントアップアニメーション
                    if (entry.target.classList.contains('stats-number')) {
                        const finalValue = parseInt(entry.target.dataset.value);
                        animateValue(entry.target, 0, finalValue, 2000);
                    }
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        });
    }

    // アニメーション対象の要素を監視
    document.querySelectorAll('.fade-in, .scale-in, .stats-number').forEach(el => {
        observer.observe(el);
    });

    // ホバーエフェクトの強化
    document.querySelectorAll('.shadow-hover').forEach(element => {
        element.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
            this.style.transition = 'all 0.3s ease';
        });

        element.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });

    // スクロールアニメーションの強化
    let lastScrollTop = 0;
    window.addEventListener('scroll', () => {
        const currentScrollTop = window.pageYOffset || document.documentElement.scrollTop;
        
        // 要素の存在確認を追加
        const elements = document.querySelectorAll('.feature-card, .feature-item, .benefit-item, .step-item, .plan-card');
        if (elements.length > 0) {
            elements.forEach(el => {
                const rect = el.getBoundingClientRect();
                const isVisible = rect.top < window.innerHeight && rect.bottom >= 0;
                
                if (isVisible) {
                    el.style.opacity = '1';
                    el.style.transform = 'translateY(0)';
                }
            });
        }

        lastScrollTop = currentScrollTop;
    });

    // セクションタイトルのアニメーション
    document.querySelectorAll('.section-title').forEach(title => {
        title.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.05)';
            this.style.transition = 'transform 0.3s ease';
        });

        title.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
        });
    });

    // ボタンのホバーエフェクト強化
    document.querySelectorAll('.btn-start, .btn-market, .btn-plan').forEach(button => {
        button.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-3px)';
            this.style.boxShadow = '0 5px 15px rgba(0, 0, 0, 0.1)';
        });

        button.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '0 2px 5px rgba(0, 0, 0, 0.05)';
        });
    });

    // スクロール検知でナビバーの見た目を変更
    window.addEventListener('scroll', () => {
        const navbar = document.querySelector('.navbar');
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });

    const skeleton = document.querySelector('.skeleton-loading');
    
    // skeletonが存在する場合のみ処理を実行
    if (skeleton) {
        window.addEventListener('load', () => {
            skeleton.style.opacity = '0';
            setTimeout(() => {
                skeleton.style.display = 'none';
            }, 300);
        });

        // 3秒後のフォールバック
        setTimeout(() => {
            if (skeleton.style.display !== 'none') {
                skeleton.style.opacity = '0';
                setTimeout(() => {
                    skeleton.style.display = 'none';
                }, 300);
            }
        }, 3000);
    }

    // レース詳細ページのアコーディオン機能
    const accordionItems = document.querySelectorAll('.accordion-item');
    if (accordionItems.length > 0) {
        // アコーディオンが存在する場合、最初の項目を展開（オプション）
        // document.querySelector('.accordion-button').click();
        
        // 着順に応じてバッジの色を変更
        document.querySelectorAll('.mobile-entries .badge:not(.bg-primary)').forEach(badge => {
            const text = badge.textContent.trim();
            if (text === '1着') {
                badge.className = 'badge bg-success';
            } else if (text === '2着') {
                badge.className = 'badge bg-info';
            } else if (text === '3着') {
                badge.className = 'badge bg-warning';
            } else {
                badge.className = 'badge bg-secondary';
            }
        });
    }
    
    // 馬メモボタンのイベントリスナー
    document.querySelectorAll('.horse-memo-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.stopPropagation(); // アコーディオンの開閉を防止
            const horseId = this.dataset.horseId;
            const raceId = this.dataset.raceId;
            // メモ機能の実装（モーダルを表示するなど）
            console.log(`馬ID: ${horseId}, レースID: ${raceId} のメモを編集`);
        });
    });
    
    // お気に入りボタンのイベントリスナー
    document.querySelectorAll('.horse-favorite-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.stopPropagation(); // アコーディオンの開閉を防止
            const horseId = this.dataset.horseId;
            // お気に入り機能の実装
            console.log(`馬ID: ${horseId} をお気に入りに追加/削除`);
        });
    });

    // レース詳細ページのモバイル表示改善
    if (isMobile) {
        // テーブルの横スクロールを改善
        const tableResponsive = document.querySelector('.race-results-wrapper .table-responsive');
        if (tableResponsive) {
            // スクロール位置を記憶する変数
            let lastScrollLeft = 0;
            
            // スクロール位置を保存
            tableResponsive.addEventListener('scroll', function() {
                lastScrollLeft = this.scrollLeft;
                
                // スクロール中はヒントを非表示
                this.classList.add('scrolling');
                
                // スクロールが止まったらヒントを再表示
                clearTimeout(this.scrollTimer);
                this.scrollTimer = setTimeout(() => {
                    this.classList.remove('scrolling');
                }, 500);
            });
            
            // 画面回転時にスクロール位置を復元
            window.addEventListener('orientationchange', function() {
                setTimeout(() => {
                    if (tableResponsive) {
                        tableResponsive.scrollLeft = lastScrollLeft;
                    }
                }, 100);
            });
            
            // テーブルの行をタップしたときの処理
            const tableRows = document.querySelectorAll('.entry-table tbody tr');
            tableRows.forEach(row => {
                row.addEventListener('click', function(e) {
                    // ボタンをクリックした場合は何もしない
                    if (e.target.tagName === 'BUTTON' || e.target.tagName === 'A' || e.target.tagName === 'I') {
                        return;
                    }
                    
                    // 行の選択状態をトグル
                    this.classList.toggle('selected-row');
                    
                    // 選択された行のスタイルを設定
                    if (this.classList.contains('selected-row')) {
                        this.style.backgroundColor = 'rgba(79, 70, 229, 0.1)';
                        this.style.fontWeight = 'bold';
                    } else {
                        this.style.backgroundColor = '';
                        this.style.fontWeight = '';
                    }
                });
            });
            
            // 馬名のセルをダブルタップしたときに馬詳細ページに移動
            const horseNameCells = document.querySelectorAll('.entry-table td:nth-child(4)');
            horseNameCells.forEach(cell => {
                let tapCount = 0;
                let tapTimer;
                
                cell.addEventListener('click', function(e) {
                    tapCount++;
                    
                    if (tapCount === 1) {
                        tapTimer = setTimeout(() => {
                            tapCount = 0;
                        }, 300);
                    } else if (tapCount === 2) {
                        clearTimeout(tapTimer);
                        tapCount = 0;
                        
                        // リンクがあればそのリンク先に移動
                        const link = this.querySelector('a');
                        if (link) {
                            window.location.href = link.href;
                        }
                    }
                });
            });
        }
    }

    // スクロール位置の記憶と復元
    const saveScrollPosition = () => {
        sessionStorage.setItem('scrollPosition', window.scrollY);
    };
    
    // ページ遷移時にスクロール位置を保存
    document.querySelectorAll('a').forEach(link => {
        if (link.hostname === window.location.hostname) {
            link.addEventListener('click', saveScrollPosition);
        }
    });
    
    // ページ読み込み時にスクロール位置を復元
    const savedPosition = sessionStorage.getItem('scrollPosition');
    if (savedPosition) {
        window.scrollTo(0, parseInt(savedPosition));
        sessionStorage.removeItem('scrollPosition');
    }

    // 遅延読み込みの実装
    const lazyLoadElements = () => {
        const lazyImages = document.querySelectorAll('img[data-src]');
        lazyImages.forEach(img => {
            if (isElementInViewport(img)) {
                img.src = img.dataset.src;
                img.removeAttribute('data-src');
            }
        });
    };
    
    // 要素が表示領域内にあるか確認
    const isElementInViewport = (el) => {
        const rect = el.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    };
    
    // スクロール時に遅延読み込みを実行
    window.addEventListener('scroll', lazyLoadElements);
    lazyLoadElements(); // 初回実行

    // モバイルナビゲーションの修正
    if (window.innerWidth <= 768) {
        // ナビゲーションの開閉
        const navbarToggler = document.querySelector('.navbar-toggler');
        const navbarCollapse = document.querySelector('.navbar-collapse');
        
        if (navbarToggler && navbarCollapse) {
            navbarToggler.addEventListener('click', function() {
                navbarCollapse.classList.toggle('show');
            });
            
            // 画面外をクリックしたときにメニューを閉じる
            document.addEventListener('click', function(e) {
                if (!navbarToggler.contains(e.target) && !navbarCollapse.contains(e.target)) {
                    navbarCollapse.classList.remove('show');
                }
            });
            
            // ナビゲーションリンクをクリックしたときにメニューを閉じる
            const navLinks = navbarCollapse.querySelectorAll('.nav-link');
            navLinks.forEach(link => {
                link.addEventListener('click', function() {
                    navbarCollapse.classList.remove('show');
                });
            });
        }
        
        // ドロップダウンメニューの動作修正
        const dropdownToggles = document.querySelectorAll('.dropdown-toggle');
        dropdownToggles.forEach(toggle => {
            toggle.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
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
                }
            });
        });
    }

    // CSRFトークンをすべてのAJAXリクエストに追加
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    
    // Fetchリクエストのデフォルトヘッダーを設定
    const originalFetch = window.fetch;
    window.fetch = function(url, options = {}) {
        // ヘッダーがない場合は作成
        if (!options.headers) {
            options.headers = {};
        }
        
        // CSRFトークンを追加
        if (typeof options.headers === 'object') {
            options.headers['X-CSRF-Token'] = csrfToken;
        }
        
        return originalFetch(url, options);
    };
});

// 日付ナビゲーション関数
function navigateDate(direction) {
    const buttons = Array.from(document.querySelectorAll('.date-btn'));
    const activeButton = document.querySelector('.date-btn.active');
    
    if (!buttons.length || !activeButton) return;
    
    const currentIndex = buttons.indexOf(activeButton);
    let newIndex;
    
    if (direction === 'next' && currentIndex < buttons.length - 1) {
        newIndex = currentIndex + 1;
    } else if (direction === 'prev' && currentIndex > 0) {
        newIndex = currentIndex - 1;
    }
    
    if (newIndex !== undefined && buttons[newIndex]) {
        window.location.href = buttons[newIndex].href;
    }
}

// キーボードイベントリスナー
document.addEventListener('keydown', function(e) {
    if (e.key === 'ArrowLeft') {
        navigateDate('prev');
    } else if (e.key === 'ArrowRight') {
        navigateDate('next');
    }
});

// 予想を実行する関数
function performPrediction() {
    const raceId = this.dataset.raceId;
    fetch(`/predict/${raceId}`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken
        }
    })
    .then(response => response.json())
    .then(data => {
        displayPredictionResults(data);
    })
    .catch(error => {
        console.error('Error:', error);
        alert('予想の実行中にエラーが発生しました。');
    });
}

// 予想結果を表示する関数
function displayPredictionResults(predictions) {
    const predictionList = document.getElementById('prediction-list');
    predictionList.innerHTML = '';
    predictions.forEach((prediction, index) => {
        const li = document.createElement('li');
        li.textContent = `${index + 1}位: ${prediction.horse_name} (予想スコア: ${prediction.predicted_position.toFixed(2)})`;
        predictionList.appendChild(li);
    });
    document.getElementById('prediction-results').style.display = 'block';
}

// フォームのバリデーション関数
function validateForm(event) {
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');

    if (usernameInput && passwordInput && (usernameInput.value.trim() === '' || passwordInput.value.trim() === '')) {
        event.preventDefault();
        alert('ユーザー名とパスワードを入力してください。');
    }
}

// カウントアップアニメーション関数
function animateValue(obj, start, end, duration) {
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        obj.innerHTML = Math.floor(progress * (end - start) + start);
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
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
