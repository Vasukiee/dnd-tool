// Heartbeat: keeps the Render free-tier instance warm while the tab is visible.
// Sends a lightweight GET /ping every 5 minutes; pauses when the tab goes to
// background so the server is not woken up during long idle periods.

(function () {
    var INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

    // --- Pulse dot ---
    var dot = document.createElement('div');
    dot.id = 'heartbeat-dot';
    document.body.appendChild(dot);

    function showDot() { dot.classList.add('heartbeat-dot--active'); }
    function hideDot() { dot.classList.remove('heartbeat-dot--active'); }

    // --- Ping ---
    function ping() {
        fetch('/ping', { method: 'GET', credentials: 'same-origin' })
            .catch(function () { /* ignore network errors silently */ });
    }

    // --- Interval management ---
    var timer = null;
    var firstPingTimer = null;

    function start() {
        if (timer !== null) return;
        if (firstPingTimer === null) {
            firstPingTimer = setTimeout(function () {
                firstPingTimer = null;
                if (timer !== null && document.visibilityState === 'visible') {
                    ping();
                }
            }, 10000);
        }
        timer = setInterval(ping, INTERVAL_MS);
        showDot();
    }

    function stop() {
        if (timer === null) return;
        clearInterval(timer);
        timer = null;
        if (firstPingTimer !== null) {
            clearTimeout(firstPingTimer);
            firstPingTimer = null;
        }
        hideDot();
    }

    // --- Page Visibility API ---
    function onVisibilityChange() {
        if (document.visibilityState === 'visible') {
            start();
        } else {
            stop();
        }
    }

    document.addEventListener('visibilitychange', onVisibilityChange);

    // Kick off immediately if the tab is already visible on load
    if (document.visibilityState === 'visible') {
        start();
    }
})();
