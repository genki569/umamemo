// インクリメンタルサーチ
const searchInput = document.querySelector('.search-input');
searchInput.addEventListener('input', debounce(function(e) {
    const searchTerm = e.target.value;
    if (searchTerm.length > 2) {
        fetch(`/api/search?q=${searchTerm}`)
            .then(response => response.json())
            .then(data => updateSearchResults(data));
    }
}, 300));

function updateSearchResults(results) {
    const resultsContainer = document.querySelector('.search-results');
    resultsContainer.innerHTML = results.map(result => `
        <div class="search-result-item">
            <a href="${result.url}">
                <h6>${result.title}</h6>
                <p class="mb-0 text-muted small">${result.description}</p>
            </a>
        </div>
    `).join('');
} 