(function () {
    function storageKey(ta) {
        var field = ta.id || ta.name;
        if (!field) return null;
        return 'textarea-h:' + location.pathname + ':' + field;
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('textarea').forEach(function (ta) {
            // Wrap textarea in a div so ::after can overlay the resize corner
            var wrapper = document.createElement('div');
            wrapper.className = 'textarea-wrapper';
            ta.parentNode.insertBefore(wrapper, ta);
            wrapper.appendChild(ta);

            var key = storageKey(ta);
            if (!key) return;

            // Restore persisted height before first paint
            var saved = localStorage.getItem(key);
            if (saved) ta.style.height = saved;

            // ResizeObserver: skip the initial layout fire, then save on every
            // subsequent resize (which can only be user-triggered drag)
            if (!window.ResizeObserver) return;

            var firstFire = true;
            var ro = new ResizeObserver(function () {
                if (firstFire) {
                    firstFire = false;
                    return;
                }
                var h = ta.offsetHeight;
                if (h > 0) localStorage.setItem(key, h + 'px');
            });
            ro.observe(ta);
        });
    });
})();
