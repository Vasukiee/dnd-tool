/* Visibilità di una scheda (personaggio, luogo, incarico) cambiata sul posto:
   la lista non si ricarica, quindi ricerca, filtro e scroll restano dove sono.
   Senza JavaScript il form funziona come prima (POST + ritorno alla lista). */
(function () {
    function aggiornaScheda(form, visibile) {
        var card = form.closest('[data-list-item]');
        var button = form.querySelector('button');
        var check = form.querySelector('.completata-toggle__check');

        if (button) {
            button.classList.toggle('completata-toggle--attivo', visibile);
            if (check) check.textContent = visibile ? '✓' : '';
            // l'etichetta è l'ultimo nodo di testo del bottone
            var label = button.lastChild;
            if (label && label.nodeType === Node.TEXT_NODE) {
                label.textContent = ' ' + (visibile ? 'Mostrabile alla giocatrice' : 'Nascosto');
            }
        }
        if (!card) return;
        card.dataset.visible = visibile ? 'true' : 'false';
        card.querySelectorAll('.visibility-chip, .secret-chip').forEach(function (chip) {
            chip.classList.toggle('visibility-chip', visibile);
            chip.classList.toggle('secret-chip', !visibile);
            chip.textContent = visibile ? 'visibile' : 'nascosto';
        });
    }

    document.addEventListener('submit', function (event) {
        var form = event.target;
        if (!form.matches || !form.matches('[data-visibility-toggle]')) return;
        event.preventDefault();

        var button = form.querySelector('button');
        if (button && button.getAttribute('aria-busy') === 'true') return;
        if (button) {
            button.setAttribute('aria-busy', 'true');
            button.classList.remove('is-errore');
        }

        fetch(form.action, {
            method: 'POST',
            headers: {'Accept': 'application/json'},
            credentials: 'same-origin'
        }).then(function (response) {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return response.json();
        }).then(function (data) {
            aggiornaScheda(form, !!data.visibile);
        }).catch(function () {
            // sessione scaduta o rete assente: lo si vede sul bottone, e un
            // secondo clic riprova
            if (button) button.classList.add('is-errore');
        }).then(function () {
            if (button) button.removeAttribute('aria-busy');
        });
    });
})();
