(function () {
    function normalize(text) {
        return (text || '').toString().toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
    }

    function matchesFilter(item, filter) {
        if (!filter || filter === 'all') return true;
        var parts = filter.split(':');
        return item.dataset[parts[0]] === parts[1];
    }

    document.querySelectorAll('[data-list-tools]').forEach(function (tools) {
        var list = tools.nextElementSibling;
        if (!list || !list.matches('[data-list]')) return;
        var input = tools.querySelector('[data-list-search]');
        var filters = Array.prototype.slice.call(tools.querySelectorAll('[data-list-filter]'));
        var empty = list.parentElement.querySelector('[data-list-empty]');
        var activeFilter = 'all';

        function apply() {
            var query = normalize(input ? input.value : '');
            var visibleCount = 0;
            Array.prototype.slice.call(list.querySelectorAll('[data-list-item]')).forEach(function (item) {
                var textMatch = !query || normalize(item.textContent).indexOf(query) !== -1;
                var filterMatch = matchesFilter(item, activeFilter);
                var visible = textMatch && filterMatch;
                item.hidden = !visible;
                if (visible) visibleCount += 1;
            });
            if (empty) empty.hidden = visibleCount !== 0;
        }

        if (input) input.addEventListener('input', apply);
        filters.forEach(function (button) {
            button.addEventListener('click', function () {
                activeFilter = button.dataset.listFilter || 'all';
                filters.forEach(function (b) { b.classList.toggle('is-active', b === button); });
                apply();
            });
        });
        apply();
    });
})();
