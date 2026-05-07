const pages = {};

function registerPage(hash, renderFn) {
    pages[hash] = renderFn;
}

function navigate() {
    const hash = location.hash || '#dashboard';
    const renderFn = pages[hash];
    const main = document.getElementById('app');
    if (renderFn) {
        main.innerHTML = '';
        renderFn(main);
    } else {
        main.innerHTML = '<p>页面不存在</p>';
    }
    document.querySelectorAll('#nav a').forEach(a => {
        a.classList.toggle('active', a.getAttribute('href') === hash);
    });
}

window.addEventListener('hashchange', navigate);
window.addEventListener('DOMContentLoaded', navigate);
