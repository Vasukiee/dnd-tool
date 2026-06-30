(function () {
    var SVG_PLAY  = '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><polygon points="2,1 13,7 2,13" fill="currentColor"/></svg>';
    var SVG_PAUSE = '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><rect x="2" y="1" width="4" height="12" fill="currentColor"/><rect x="8" y="1" width="4" height="12" fill="currentColor"/></svg>';
    var SVG_VOL_HIGH = '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><polygon points="1,4 5,4 9,1 9,13 5,10 1,10" fill="currentColor"/><path d="M11 3.5 Q14 7 11 10.5" stroke="currentColor" stroke-width="1.4" fill="none" stroke-linecap="round"/><path d="M11.5 5.5 Q13 7 11.5 8.5" stroke="currentColor" stroke-width="1.2" fill="none" stroke-linecap="round"/></svg>';
    var SVG_VOL_LOW  = '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><polygon points="1,4 5,4 9,1 9,13 5,10 1,10" fill="currentColor"/><path d="M11 5 Q12.8 7 11 9" stroke="currentColor" stroke-width="1.4" fill="none" stroke-linecap="round"/></svg>';
    var SVG_VOL_MUTE = '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><polygon points="1,4 5,4 9,1 9,13 5,10 1,10" fill="currentColor"/><line x1="11" y1="5" x2="13.5" y2="9.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/><line x1="13.5" y1="5" x2="11" y2="9.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>';

    var activeAudio = null;

    function formatTime(seconds) {
        if (!isFinite(seconds) || isNaN(seconds)) return '--:--';
        var m = Math.floor(seconds / 60);
        var s = Math.floor(seconds % 60);
        return m + ':' + (s < 10 ? '0' : '') + s;
    }

    function initPlayer(container) {
        var audio     = container.querySelector('.audio-player__audio');
        var btnPlay   = container.querySelector('.audio-player__play');
        var timeEl    = container.querySelector('.audio-player__time');
        var progress  = container.querySelector('.audio-player__progress');
        var bar       = container.querySelector('.audio-player__bar');
        var fill      = container.querySelector('.audio-player__fill');
        var thumb     = container.querySelector('.audio-player__thumb');
        var btnVol    = container.querySelector('.audio-player__vol');
        var volSlider = container.querySelector('.audio-player__vol-slider');

        var isDragging = false;

        btnPlay.innerHTML = SVG_PLAY;

        // ---- Volume helpers ----

        function updateVolIcon() {
            if (audio.muted || audio.volume === 0) {
                btnVol.innerHTML = SVG_VOL_MUTE;
            } else if (audio.volume < 0.4) {
                btnVol.innerHTML = SVG_VOL_LOW;
            } else {
                btnVol.innerHTML = SVG_VOL_HIGH;
            }
        }

        function updateSliderFill(vol) {
            // CSS variable read by the ::webkit-slider-runnable-track gradient.
            volSlider.style.setProperty('--vol-pct', Math.round(vol * 100) + '%');
        }

        // Init at full volume
        updateVolIcon();
        updateSliderFill(1);

        // ---- Progress helpers ----

        function updateTime() {
            var cur = audio.currentTime;
            var dur = audio.duration;
            timeEl.textContent = formatTime(cur) + ' / ' + (isFinite(dur) ? formatTime(dur) : '--:--');
        }

        function updateBar() {
            var dur = audio.duration;
            var pct = (isFinite(dur) && dur > 0) ? (audio.currentTime / dur) * 100 : 0;
            fill.style.width = pct + '%';
            thumb.style.left = pct + '%';
        }

        // ---- Audio events ----

        audio.addEventListener('loadedmetadata', updateTime);

        audio.addEventListener('timeupdate', function () {
            if (!isDragging) { updateBar(); updateTime(); }
        });

        audio.addEventListener('ended', function () {
            btnPlay.innerHTML = SVG_PLAY;
            fill.style.width  = '0%';
            thumb.style.left  = '0%';
            updateTime();
            if (activeAudio === audio) activeAudio = null;
        });

        // ---- Play / Pause ----

        btnPlay.addEventListener('click', function () {
            if (audio.paused) {
                if (activeAudio && activeAudio !== audio) {
                    activeAudio.pause();
                    var prev = activeAudio.closest('.audio-player');
                    if (prev) prev.querySelector('.audio-player__play').innerHTML = SVG_PLAY;
                }
                activeAudio = audio;
                audio.play();
                btnPlay.innerHTML = SVG_PAUSE;
            } else {
                audio.pause();
                if (activeAudio === audio) activeAudio = null;
                btnPlay.innerHTML = SVG_PLAY;
            }
        });

        // ---- Progress bar seek ----

        function seekFromEvent(e) {
            var rect = bar.getBoundingClientRect();
            var pct  = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            var dur  = audio.duration;
            if (isFinite(dur) && dur > 0) audio.currentTime = pct * dur;
            fill.style.width = (pct * 100) + '%';
            thumb.style.left = (pct * 100) + '%';
            updateTime();
        }

        progress.addEventListener('mousedown', function (e) {
            isDragging = true;
            container.classList.add('dragging');
            seekFromEvent(e);
        });

        window.addEventListener('mousemove', function (e) {
            if (isDragging) seekFromEvent(e);
        });

        window.addEventListener('mouseup', function () {
            if (!isDragging) return;
            isDragging = false;
            container.classList.remove('dragging');
        });

        // ---- Volume slider ----

        volSlider.addEventListener('input', function () {
            var vol = parseFloat(volSlider.value);
            audio.volume = vol;
            audio.muted  = (vol === 0);
            updateVolIcon();
            updateSliderFill(vol);
        });

        // Speaker button: toggle mute, keep slider position
        btnVol.addEventListener('click', function () {
            audio.muted = !audio.muted;
            // When unmuting via button, if slider is at 0 restore to a sensible level
            if (!audio.muted && audio.volume === 0) {
                audio.volume = 0.7;
                volSlider.value = '0.7';
            }
            updateVolIcon();
            updateSliderFill(audio.muted ? 0 : audio.volume);
        });

        updateTime();
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.audio-player').forEach(initPlayer);
    });

    window.AudioPlayer = { init: initPlayer };
})();
