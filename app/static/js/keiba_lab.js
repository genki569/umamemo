/**
 * keiba_lab.js
 * @description 競馬ラボページで使用するJavaScript機能
 * @overview 記事リストの表示制御やフィルタリング、エフェクトなどの機能を提供
 */

/**
 * ドキュメントの読み込み完了時に実行する初期化処理
 * @returns {void}
 */
document.addEventListener('DOMContentLoaded', function() {
  // 目次の自動生成
  generateTableOfContents();
  
  // スクロールスパイの初期化
  initScrollSpy();
  
  // 検索機能の初期化
  initSearch();
  
  // レベル別フィルタリングの初期化
  initLevelFilter();
  
  // 記事カードのホバーエフェクト
  initCardHoverEffects();
  
  // 記事詳細ページでのコードブロックのハイライト
  highlightCodeBlocks();
  
  // ページトップへ戻るボタンの表示制御
  initBackToTopButton();
});

/**
 * 目次を自動生成する関数
 * @returns {void}
 */
function generateTableOfContents() {
  const tocContainer = document.querySelector('.keiba-lab-toc-content');
  if (!tocContainer) return;
  
  const headings = document.querySelectorAll('.keiba-lab-article h2, .keiba-lab-article h3');
  if (headings.length === 0) return;
  
  const tocList = document.createElement('ul');
  
  headings.forEach((heading, index) => {
    // ID設定（なければ生成）
    if (!heading.id) {
      heading.id = `heading-${index}`;
    }
    
    const listItem = document.createElement('li');
    const link = document.createElement('a');
    link.href = `#${heading.id}`;
    link.textContent = heading.textContent;
    
    // h3要素の場合はインデント
    if (heading.tagName.toLowerCase() === 'h3') {
      listItem.style.paddingLeft = '1rem';
    }
    
    listItem.appendChild(link);
    tocList.appendChild(listItem);
    
    // クリックイベント
    link.addEventListener('click', function(e) {
      e.preventDefault();
      const targetHeading = document.querySelector(this.getAttribute('href'));
      window.scrollTo({
        top: targetHeading.offsetTop - 100,
        behavior: 'smooth'
      });
    });
  });
  
  tocContainer.appendChild(tocList);
}

/**
 * スクロールスパイを初期化する関数
 * スクロール位置に応じて目次のアクティブ項目を変更
 * @returns {void}
 */
function initScrollSpy() {
  const tocLinks = document.querySelectorAll('.keiba-lab-toc-content a');
  if (tocLinks.length === 0) return;
  
  const headingElements = Array.from(document.querySelectorAll('.keiba-lab-article h2, .keiba-lab-article h3'));
  if (headingElements.length === 0) return;
  
  window.addEventListener('scroll', function() {
    const scrollPosition = window.scrollY + 150;
    
    // 現在表示されている見出しを特定
    let currentHeading = null;
    
    for (let i = 0; i < headingElements.length; i++) {
      if (headingElements[i].offsetTop <= scrollPosition) {
        currentHeading = headingElements[i];
      } else {
        break;
      }
    }
    
    // 目次の項目をハイライト
    if (currentHeading) {
      tocLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === `#${currentHeading.id}`) {
          link.classList.add('active');
        }
      });
    }
  });
}

/**
 * 記事検索機能を初期化する関数
 * @returns {void}
 */
function initSearch() {
  const searchInput = document.querySelector('.keiba-lab-search-input');
  if (!searchInput) return;
  
  const articleCards = document.querySelectorAll('.keiba-lab-card');
  if (articleCards.length === 0) return;
  
  searchInput.addEventListener('input', function() {
    const searchTerm = this.value.toLowerCase().trim();
    
    // 検索語がなければすべて表示
    if (searchTerm === '') {
      articleCards.forEach(card => {
        card.closest('.col').style.display = 'block';
      });
      return;
    }
    
    // 記事カードをフィルタリング
    articleCards.forEach(card => {
      const cardTitle = card.querySelector('.card-title').textContent.toLowerCase();
      const cardText = card.querySelector('.card-text')?.textContent.toLowerCase() || '';
      
      if (cardTitle.includes(searchTerm) || cardText.includes(searchTerm)) {
        card.closest('.col').style.display = 'block';
      } else {
        card.closest('.col').style.display = 'none';
      }
    });
  });
}

/**
 * レベル別フィルタリング機能を初期化する関数
 * @returns {void}
 */
function initLevelFilter() {
  const levelFilters = document.querySelectorAll('.keiba-lab-level-filter');
  if (levelFilters.length === 0) return;
  
  const articleCards = document.querySelectorAll('.keiba-lab-card');
  if (articleCards.length === 0) return;
  
  // アクティブなフィルタを保持する変数
  let activeFilter = 'all';
  
  levelFilters.forEach(filter => {
    filter.addEventListener('click', function(e) {
      e.preventDefault();
      
      // アクティブクラスの切り替え
      levelFilters.forEach(btn => btn.classList.remove('active'));
      this.classList.add('active');
      
      // フィルタ値の取得
      const filterValue = this.getAttribute('data-filter');
      activeFilter = filterValue;
      
      // 記事カードのフィルタリング
      articleCards.forEach(card => {
        const cardLevel = card.getAttribute('data-level');
        
        if (filterValue === 'all' || cardLevel === filterValue) {
          card.closest('.col').style.display = 'block';
        } else {
          card.closest('.col').style.display = 'none';
        }
      });
    });
  });
}

/**
 * 記事カードのホバーエフェクトを初期化する関数
 * @returns {void}
 */
function initCardHoverEffects() {
  const articleCards = document.querySelectorAll('.keiba-lab-card');
  
  articleCards.forEach(card => {
    card.addEventListener('mouseenter', function() {
      this.classList.add('shadow-lg');
    });
    
    card.addEventListener('mouseleave', function() {
      this.classList.remove('shadow-lg');
    });
  });
}

/**
 * コードブロックのシンタックスハイライトを適用する関数
 * @returns {void}
 */
function highlightCodeBlocks() {
  // Prism.jsがロードされていることを確認
  if (typeof Prism !== 'undefined') {
    Prism.highlightAll();
  }
}

/**
 * ページトップへ戻るボタンの表示制御を初期化する関数
 * @returns {void}
 */
function initBackToTopButton() {
  const backToTopBtn = document.querySelector('.keiba-lab-back-to-top');
  if (!backToTopBtn) return;
  
  // スクロール量に応じて表示/非表示を切り替え
  window.addEventListener('scroll', function() {
    if (window.pageYOffset > 300) {
      backToTopBtn.classList.add('show');
    } else {
      backToTopBtn.classList.remove('show');
    }
  });
  
  // クリック時の挙動
  backToTopBtn.addEventListener('click', function(e) {
    e.preventDefault();
    window.scrollTo({
      top: 0,
      behavior: 'smooth'
    });
  });
}

/**
 * 関連記事をAPIから取得して表示する関数
 * @param {string} articleId - 現在の記事ID
 * @param {string} category - 記事のカテゴリ
 * @returns {Promise<void>}
 */
async function loadRelatedArticles(articleId, category) {
  try {
    const response = await fetch(`/api/related-articles?id=${articleId}&category=${category}`);
    if (!response.ok) {
      throw new Error('関連記事の取得に失敗しました');
    }
    
    const data = await response.json();
    const relatedContainer = document.querySelector('.keiba-lab-related-articles');
    
    if (!relatedContainer || !data.articles || data.articles.length === 0) {
      // 関連記事がない場合はセクションを非表示
      const relatedSection = document.querySelector('.keiba-lab-related-section');
      if (relatedSection) {
        relatedSection.style.display = 'none';
      }
      return;
    }
    
    // 関連記事の表示
    let html = '';
    
    data.articles.forEach(article => {
      html += `
        <div class="col-md-4 mb-4">
          <div class="keiba-lab-card card h-100">
            <img src="${article.image}" class="card-img-top" alt="${article.title}">
            <div class="card-body">
              <span class="keiba-lab-level keiba-lab-level-${article.level}">${getLevelText(article.level)}</span>
              <h5 class="card-title">${article.title}</h5>
              <p class="card-text">${article.excerpt}</p>
              <a href="${article.url}" class="btn btn-outline-primary btn-sm">続きを読む</a>
            </div>
          </div>
        </div>
      `;
    });
    
    relatedContainer.innerHTML = html;
    
    // ホバーエフェクトの適用
    initCardHoverEffects();
  } catch (error) {
    console.error('関連記事の取得エラー:', error);
  }
}

/**
 * レベル表示のテキストを取得する関数
 * @param {string} level - 記事レベル（beginner/intermediate/advanced）
 * @returns {string} レベル表示用テキスト
 */
function getLevelText(level) {
  switch(level) {
    case 'beginner':
      return '初心者向け';
    case 'intermediate':
      return '中級者向け';
    case 'advanced':
      return '上級者向け';
    default:
      return '全てのレベル';
  }
} 