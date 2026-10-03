/* Versioni alternative di una scena nei copioni (blocchi @varianti).
   Il click su una scheda mostra la sua versione e nasconde le altre.
   Il listener è delegato su document perché la "Lettura a Scene" clona
   i nodi del copione e l'anteprima dell'editor li ricrea a ogni tasto.
   La scelta è ricordata per pagina (sessionStorage) e riapplicata con
   copioniVarianti.ripristina(radice). */
(function () {
    'use strict';

    const CHIAVE = 'copioni_varianti:' + location.pathname;

    function leggi() {
        try { return JSON.parse(sessionStorage.getItem(CHIAVE) || '{}') || {}; }
        catch (e) { return {}; }
    }

    function scrivi(scelte) {
        try { sessionStorage.setItem(CHIAVE, JSON.stringify(scelte)); } catch (e) { /* niente memoria */ }
    }

    function seleziona(blocco, versione) {
        const schede = blocco.querySelectorAll(':scope > .copione-varianti__schede > .copione-varianti__scheda');
        if (!Array.from(schede).some(s => s.dataset.versione === versione)) return;
        schede.forEach(s => s.setAttribute('aria-selected', String(s.dataset.versione === versione)));
        blocco.querySelectorAll(':scope > .copione-varianti__pannello').forEach(p => {
            p.hidden = p.dataset.versione !== versione;
        });
    }

    function ripristina(radice) {
        const scelte = leggi();
        (radice || document).querySelectorAll('.copione-varianti').forEach(blocco => {
            const versione = scelte[blocco.dataset.varianti];
            if (versione !== undefined) seleziona(blocco, versione);
        });
    }

    document.addEventListener('click', e => {
        const scheda = e.target.closest('.copione-varianti__scheda');
        if (!scheda) return;
        const blocco = scheda.closest('.copione-varianti');
        seleziona(blocco, scheda.dataset.versione);
        const scelte = leggi();
        scelte[blocco.dataset.varianti] = scheda.dataset.versione;
        scrivi(scelte);
    });

    document.addEventListener('DOMContentLoaded', () => ripristina(document));

    window.copioniVarianti = { ripristina };
})();
