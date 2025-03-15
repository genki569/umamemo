document.addEventListener('DOMContentLoaded', function() {
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
        button.addEventListener('click', async (e) => {
            e.preventDefault();
            
            if (!confirm('このレビューを購入しますか？')) {
                return;
            }
            
            const reviewId = e.target.dataset.reviewId;
            const reviewPrice = parseInt(e.target.dataset.reviewPrice);
            const currentPoints = parseInt(e.target.dataset.userPoints || 0);
            
            // ポイント不足チェック
            if (currentPoints < reviewPrice) {
                const requiredPoints = reviewPrice - currentPoints;
                const chargeUrl = `/mypage/charge-points?required_points=${requiredPoints}&return_to=${encodeURIComponent(window.location.pathname)}`;
                if (confirm('ポイントが不足しています。チャージページに移動しますか？')) {
                    window.location.href = chargeUrl;
                    return;
                }
                return;
            }
            
            try {
                const response = await fetch(`/reviews/${reviewId}/purchase`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                    }
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('レビューを購入しました。');
                    window.location.href = data.redirect_url;
                } else {
                    alert(data.message || '購入処理中にエラーが発生しました。');
                }
                
            } catch (error) {
                console.error('Error:', error);
                alert('購入処理中にエラーが発生しました。');
            }
        });
    });

    // フォーム送信のイベントリスナーを削除（通常のフォーム送信を使用）
    // 代わりに、価格セクションの表示制御のみを残す
    const saleStatus = document.getElementById('saleStatus');
    if (saleStatus) {
        saleStatus.addEventListener('change', function() {
            const priceSection = document.getElementById('priceSection');
            priceSection.style.display = this.value === 'paid' ? 'block' : 'none';
        });
    }

    // モバイルデバイスかどうかを確認
    const isMobile = window.innerWidth <= 768;
    AOS.init({
        duration: isMobile ? 0 : 800,
        once: true,
        disable: isMobile
    });

    // 統計カードのカウントアップアニメーション
    const statsNumbers = document.querySelectorAll('.stats-number');
    statsNumbers.forEach(number => {
        const finalValue = parseInt(number.textContent);
        animateValue(number, 0, finalValue, 2000);
    });

    // ホバーエフェクト
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-10px)';
        });
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });

    // ポイントチャージフォームの処理
    const paymentForm = document.getElementById('payment-form');
    if (paymentForm) {
        const stripe = Stripe(paymentForm.dataset.stripeKey);
        const elements = stripe.elements();
        const card = elements.create('card', {
            style: {
                base: {
                    fontSize: '16px',
                    color: '#32325d',
                }
            }
        });

        // カード入力フォームをマウント
        card.mount('#card-element');

        // エラーハンドリング
        card.addEventListener('change', function(event) {
            const displayError = document.getElementById('card-errors');
            if (event.error) {
                displayError.textContent = event.error.message;
            } else {
                displayError.textContent = '';
            }
        });

        // フォーム送信処理
        paymentForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            
            const submitButton = document.getElementById('submit-button');
            submitButton.disabled = true;
            submitButton.textContent = '処理中...';

            try {
                const {token, error} = await stripe.createToken(card);

                if (error) {
                    const errorElement = document.getElementById('card-errors');
                    errorElement.textContent = error.message;
                    submitButton.disabled = false;
                    submitButton.textContent = 'チャージする';
                    return;
                }

                // トークンをサーバーに送信
                const response = await fetch('/mypage/charge-points', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                    },
                    body: JSON.stringify({
                        stripeToken: token.id,
                        amount: document.getElementById('amount').value
                    })
                });

                const result = await response.json();

                if (result.success) {
                    window.location.href = result.redirect_url || '/mypage';
                } else {
                    throw new Error(result.message || '決済処理に失敗しました');
                }

            } catch (error) {
                console.error('Error:', error);
                const errorElement = document.getElementById('card-errors');
                errorElement.textContent = error.message || '決済処理中にエラーが発生しました';
                submitButton.disabled = false;
                submitButton.textContent = 'チャージする';
            }
        });
    }

    // レース一覧ページの日付ナビゲーション
    const dateButtons = document.querySelectorAll('.date-btn');
    const scrollContainer = document.querySelector('.date-buttons');
    
    if (scrollContainer && dateButtons.length > 0) {
        // アクティブな日付を中央に表示
        const activeButton = document.querySelector('.date-btn.active');
        if (activeButton) {
            setTimeout(() => {
                activeButton.scrollIntoView({
                    behavior: 'smooth',
                    block: 'nearest',
                    inline: 'center'
                });
            }, 100);
        }
    }

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
    const observer = new IntersectionObserver((entries) => {
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

    // CSRFトークンを取得（複数のソースから試行）
    const csrfToken = 
        document.querySelector('meta[name="csrf-token"]')?.content ||
        document.querySelector('#csrf-form input[name="csrf_token"]')?.value ||
        document.querySelector('input[name="csrf_token"]')?.value;

    if (!csrfToken) {
        console.error('CSRF token not found');
        return;
    }

    // フォームにCSRFトークンを追加
    document.querySelectorAll('form').forEach(function(form) {
        if (!form.querySelector('input[name="csrf_token"]')) {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'csrf_token';
            input.value = csrfToken;
            form.appendChild(input);
        }
    });

    // 動的に追加されるフォームのための監視
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
                if (node.nodeName === 'FORM' && !node.querySelector('input[name="csrf_token"]')) {
                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = 'csrf_token';
                    input.value = csrfToken;
                    node.appendChild(input);
                }
            });
        });
    });

    // body全体を監視
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    // Ajaxリクエスト用のCSRFトークンヘッダー設定
    const token = document.querySelector('meta[name="csrf-token"]')?.content || csrfToken;
    if (token) {
        document.querySelectorAll('form').forEach(form => {
            form.addEventListener('submit', function(e) {
                if (this.method.toLowerCase() === 'post') {
                    const csrfInput = this.querySelector('input[name="csrf_token"]');
                    if (!csrfInput) {
                        e.preventDefault();
                        const input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = 'csrf_token';
                        input.value = token;
                        this.appendChild(input);
                        this.submit();
                    }
                }
            });
        });
    }
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

// タッチイベント処理
const dateButtons = document.querySelector('.date-buttons');
if (dateButtons) {
    let touchStartX = 0;

    dateButtons.addEventListener('touchstart', e => {
        touchStartX = e.touches[0].clientX;
    }, { passive: true });

    dateButtons.addEventListener('touchend', e => {
        const touchEndX = e.changedTouches[0].clientX;
        const diff = touchStartX - touchEndX;
        
        if (Math.abs(diff) > 50) {
            if (diff > 0) {
                navigateDate('next');
            } else {
                navigateDate('prev');
            }
        }
    }, { passive: true });
}

// 予想を実行する関数
function performPrediction() {
    const raceId = this.dataset.raceId;
    fetch(`/predict/${raceId}`, {
        method: 'POST',
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

    if (usernameInput.value.trim() === '' || passwordInput.value.trim() === '') {
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
