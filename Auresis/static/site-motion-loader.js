(function () {
    var hasMotionRoot = document.getElementById('react-motion-root');
    var hasRelationOverlay = document.querySelector('[data-relation-react-overlay]');
    var decorativeMotionEnabled = !document.documentElement.classList.contains('motion-disabled') && localStorage.getItem('dnd_motion_enabled') === '1';
    var shouldLoadDecorativeMotion = hasMotionRoot && decorativeMotionEnabled;
    if (!shouldLoadDecorativeMotion && !hasRelationOverlay) return;

    function loadScript(src) {
        return new Promise(function (resolve, reject) {
            var script = document.createElement('script');
            script.src = src;
            script.defer = true;
            script.crossOrigin = 'anonymous';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    function startReactLayers() {
        loadScript('https://unpkg.com/react@18/umd/react.production.min.js')
            .then(function () { return loadScript('https://unpkg.com/react-dom@18/umd/react-dom.production.min.js'); })
            .then(function () { return shouldLoadDecorativeMotion ? loadScript('/static/site-motion-react.js') : null; })
            .then(function () { return hasRelationOverlay ? loadScript('/static/relation-map-react.js') : null; })
            .catch(function () {
                document.documentElement.classList.add('react-motion-deferred');
            });
    }

    if (document.readyState === 'complete') {
        window.setTimeout(startReactLayers, 120);
    } else {
        window.addEventListener('load', function () {
            window.setTimeout(startReactLayers, 120);
        }, { once: true });
    }
})();
