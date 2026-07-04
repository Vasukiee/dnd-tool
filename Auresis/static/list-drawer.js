(function () {
    var list = document.querySelector('[data-list]');
    if (!list) return;

    var drawer = document.createElement('aside');
    drawer.className = 'detail-drawer';
    drawer.hidden = true;
    drawer.innerHTML = '' +
        '<button type="button" class="detail-drawer__close" aria-label="Chiudi anteprima">×</button>' +
        '<p class="detail-drawer__eyebrow">Anteprima rapida</p>' +
        '<h2 class="detail-drawer__title"></h2>' +
        '<p class="detail-drawer__subtitle"></p>' +
        '<div class="detail-drawer__tags"></div>' +
        '<p class="detail-drawer__desc"></p>' +
        '<a class="detail-drawer__link" href="#">Apri scheda completa</a>';
    document.body.appendChild(drawer);

    var closeButton = drawer.querySelector('.detail-drawer__close');
    var title = drawer.querySelector('.detail-drawer__title');
    var subtitle = drawer.querySelector('.detail-drawer__subtitle');
    var tags = drawer.querySelector('.detail-drawer__tags');
    var desc = drawer.querySelector('.detail-drawer__desc');
    var link = drawer.querySelector('.detail-drawer__link');

    function closeDrawer() {
        drawer.hidden = true;
        document.body.classList.remove('has-detail-drawer');
    }

    function openDrawer(card) {
        var titleLink = card.querySelector('.card__title a');
        if (!titleLink) return;
        title.textContent = titleLink.textContent.trim();
        subtitle.textContent = (card.querySelector('.card__subtitle') || {}).textContent || '';
        desc.textContent = (card.querySelector('.card__desc') || {}).textContent || 'Nessuna nota breve registrata.';
        link.href = titleLink.href;
        tags.innerHTML = '';
        card.querySelectorAll('.card__footer .tag').forEach(function (tag) {
            tags.appendChild(tag.cloneNode(true));
        });
        drawer.hidden = false;
        document.body.classList.add('has-detail-drawer');
    }

    list.querySelectorAll('[data-list-item]').forEach(function (card) {
        if (card.querySelector('.card-preview-btn')) return;
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'card-preview-btn';
        button.textContent = 'Anteprima';
        button.addEventListener('click', function (event) {
            event.preventDefault();
            event.stopPropagation();
            openDrawer(card);
        });
        card.appendChild(button);
    });

    closeButton.addEventListener('click', closeDrawer);
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && !drawer.hidden) closeDrawer();
    });
})();
