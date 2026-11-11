/* Form di modifica delle schede:
   - avviso prima di lasciare la pagina con modifiche non salvate;
   - Ctrl/Cmd+S salva il form in cui si sta scrivendo;
   - un solo invio per clic (niente doppioni da doppio clic). */
(function () {
    var forms = Array.prototype.slice.call(
        document.querySelectorAll('form.form-grid:not([data-no-guard])')
    ).filter(function (form) {
        return (form.getAttribute('method') || '').toLowerCase() === 'post';
    });
    if (!forms.length) return;

    var modificato = false;
    var inInvio = false;

    forms.forEach(function (form) {
        form.addEventListener('input', function () { modificato = true; });
        form.addEventListener('change', function () { modificato = true; });
        form.addEventListener('submit', function (event) {
            if (inInvio) {
                event.preventDefault();
                return;
            }
            inInvio = true;
            modificato = false;
            // se l'invio non parte (es. annullato da un altro script), si sblocca da solo
            setTimeout(function () { inInvio = false; }, 4000);
        });
    });

    window.addEventListener('beforeunload', function (event) {
        if (!modificato) return;
        event.preventDefault();
        event.returnValue = '';
    });

    document.addEventListener('keydown', function (event) {
        if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 's') return;
        var attivo = document.activeElement && document.activeElement.closest
            ? document.activeElement.closest('form') : null;
        var form = forms.indexOf(attivo) !== -1 ? attivo : (forms.length === 1 ? forms[0] : null);
        if (!form) return;
        event.preventDefault();
        if (form.requestSubmit) form.requestSubmit(); else form.submit();
    });
})();
