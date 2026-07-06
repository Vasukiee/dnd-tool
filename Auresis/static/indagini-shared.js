(function () {
    function scenaNodo(nodo) {
        return Math.floor(nodo.numero_nodo / 10);
    }

    function nodiById(nodi) {
        const byId = {};
        nodi.forEach(n => { byId[n.id] = n; });
        return byId;
    }

    function tutteLeScene(nodi) {
        return [...new Set(nodi.map(n => Math.floor(n.numero_nodo / 10)))].sort((a, b) => a - b);
    }

    function escapeHtml(value) {
        return String(value || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
    }

    function stellaPunti(cx, cy, R, r, punte) {
        const irr = [1.0, 0.85, 1.12, 0.9, 1.06, 0.82, 1.15, 0.93, 1.02, 0.88, 1.08, 0.91];
        const pts = [];
        for (let i = 0; i < punte * 2; i++) {
            const f = i % 2 === 0 ? R * irr[i % irr.length] : r;
            const a = (Math.PI / punte) * i - Math.PI / 2;
            pts.push(`${cx + f * Math.cos(a)},${cy + f * Math.sin(a)}`);
        }
        return pts.join(" ");
    }

    function statiDaPayload(stati) {
        const normalizzati = {};
        Object.entries(stati || {}).forEach(([k, v]) => { normalizzati[parseInt(k)] = v; });
        return normalizzati;
    }

    function statiDiversi(a, b) {
        const keys = new Set(Object.keys(a).concat(Object.keys(b)));
        for (const key of keys) {
            if (a[key] !== b[key]) return true;
        }
        return false;
    }

    function nodoHaFigliScoperti(nodoId, collegamenti, stati, nodiById, scenaCorrente) {
        return collegamenti.some(c => {
            if (c.nodo_genitore_id !== nodoId || stati[c.nodo_figlio_id] !== "SCOPERTO") return false;
            if (!nodiById || scenaCorrente === undefined || scenaCorrente === null) return true;
            const figlio = nodiById[c.nodo_figlio_id];
            if (!figlio) return false;
            const scenaFiglio = scenaNodo(figlio);
            return scenaFiglio === scenaCorrente || scenaFiglio === scenaCorrente - 1;
        });
    }

    function nodoRichiamato(nodo, scenaCorrente, collegamenti, stati, nodiById) {
        return scenaNodo(nodo) <= scenaCorrente - 2 && nodoHaFigliScoperti(nodo.id, collegamenti, stati, nodiById, scenaCorrente);
    }

    window.IndaginiShared = {
        scenaNodo,
        nodiById,
        tutteLeScene,
        escapeHtml,
        stellaPunti,
        statiDaPayload,
        statiDiversi,
        nodoHaFigliScoperti,
        nodoRichiamato,
    };
})();
