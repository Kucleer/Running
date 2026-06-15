const pages = {};

function registerPage(hash, renderFn) {
    pages[hash] = renderFn;
}

function navigate() {
    const hash = location.hash || '#dashboard';
    const renderFn = pages[hash];
    const main = document.getElementById('app');
    
    // Toggle body class for full-height pages
    document.body.classList.toggle('page-heatmap', hash === '#heatmap');
    
    if (renderFn) {
        main.innerHTML = '';
        renderFn(main);
    } else {
        main.innerHTML = '<div class="empty-state">页面不存在</div>';
    }
    document.querySelectorAll('#nav a, .app-sidebar a').forEach(a => {
        a.classList.toggle('active', a.getAttribute('href') === hash);
    });
}

window.addEventListener('DOMContentLoaded', () => {
    const search = document.getElementById('global-search');
    if (search) {
        search.addEventListener('keydown', (event) => {
            if (event.key !== 'Enter') return;
            const value = search.value.trim();
            if (!value) return;
            sessionStorage.setItem('activitySearch', value);
            location.hash = '#activities';
        });
    }
});

window.addEventListener('hashchange', navigate);
window.addEventListener('DOMContentLoaded', navigate);
