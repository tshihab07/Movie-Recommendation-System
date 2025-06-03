// Carousel functionality with navigation
document.addEventListener('DOMContentLoaded', function() {
    // Initialize carousels
    initCarousels();
    
    // Search autocomplete
    initSearchAutocomplete();
});

// Initialize carousels on the page
// This function sets up the carousels with navigation buttons
function initCarousels() {
    const carousels = document.querySelectorAll('.carousel-container');
    
    carousels.forEach(container => {
        const carousel = container.querySelector('.carousel');
        const prevBtn = container.querySelector('.carousel-prev');
        const nextBtn = container.querySelector('.carousel-next');
        
        let scrollAmount = 0;
        const itemWidth = 220;
        
        // Button event listeners
        nextBtn.addEventListener('click', () => {
            scrollAmount += itemWidth * 3;
            if (scrollAmount > carousel.scrollWidth - carousel.clientWidth) {
                scrollAmount = carousel.scrollWidth - carousel.clientWidth;
            }
            smoothScroll(carousel, scrollAmount);
        });
        
        prevBtn.addEventListener('click', () => {
            scrollAmount -= itemWidth * 3;
            if (scrollAmount < 0) scrollAmount = 0;
            smoothScroll(carousel, scrollAmount);
        });
    });
}

// Smooth scrolling function for carousels
// This function scrolls the carousel smoothly to the target position
function smoothScroll(element, target) {
    element.scrollTo({
        left: target,
        behavior: 'smooth'
    });
}

// Search autocomplete functionality
// This function initializes the search autocomplete feature
function initSearchAutocomplete() {
    const searchInput = document.querySelector('input[name="q"]');
    if (!searchInput) return;

    const searchForm = searchInput.closest('form');
    const resultsContainer = document.createElement('div');
    resultsContainer.className = 'autocomplete-results';
    searchForm.appendChild(resultsContainer);

    // Debounce implementation
    let debounceTimer;
    const debounceDelay = 300;
    
    searchInput.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        const query = this.value.trim();
        
        if (query.length < 2) {
            resultsContainer.innerHTML = '';
            return;
        }
        
        debounceTimer = setTimeout(async () => {
            try {
                const response = await fetch(`/search_suggestions?q=${encodeURIComponent(query)}`);
                const results = await response.json();
                
                resultsContainer.innerHTML = '';
                
                results.forEach(movie => {
                    const item = document.createElement('div');
                    item.className = 'autocomplete-item';
                    item.innerHTML = `
                        ${movie.poster ? `<img src="${movie.poster}" class="suggestion-poster">` : ''}
                        <span>${movie.title}</span>
                    `;
                    
                    item.addEventListener('click', () => {
                        searchInput.value = movie.title;
                        resultsContainer.innerHTML = '';
                        window.location.href = `/movie/${movie.id}`;
                    });
                    
                    resultsContainer.appendChild(item);
                });
            } catch (error) {
                console.error('Autocomplete error:', error);
            }
        }, debounceDelay);
    });

    // Hide results when clicking outside the search form
    document.addEventListener('click', (e) => {
        if (!searchForm.contains(e.target)) {
            resultsContainer.innerHTML = '';
        }
    });

    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Tab' && resultsContainer.innerHTML !== '') {
            e.preventDefault();
        }
    });
}

// Search form validation to prevent empty queries
document.addEventListener('DOMContentLoaded', function() {
    const searchForm = document.querySelector('.search-container form');
    const searchInput = document.querySelector('.search-container input[name="q"]');
    
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            // Ensure empty queries don't submit
            if (searchInput.value.trim() === '') {
                e.preventDefault();
            }
        });
    }
    
    initSearchAutocomplete();
});