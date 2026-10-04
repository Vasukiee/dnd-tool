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

    // ----------------------------------------------------------------
    // Layout del grafo (bacheca giocatrice e live view)
    // ----------------------------------------------------------------
    // dim: { nodeW, nodeH, pad, rivR, ghostGap, ghostR, boxPad, boxTitleH }
    // Restituisce il grafo dagre con, per ogni nodo, pos.x/pos.y (centro della
    // carta o della stella) e pos.ext = ingombro reale {l, r, t, b} dal centro.
    // Garanzie: carte e stelle non si sovrappongono, i riquadri di scena
    // nemmeno, gli archi spostati vengono ritracciati senza attraversare carte.
    const STELLA_IRR_MAX = 1.15;  // punta più lunga di stellaPunti
    const LAYOUT_GAP_Y = 28;      // spazio verticale tra carte della stessa colonna
    const LAYOUT_BOX_GAP = 16;    // spazio minimo tra riquadri di scena
    const LAYOUT_EDGE_M = 8;      // distanza minima di un arco da una carta
    const LAYOUT_LABEL_H = 14;    // etichetta "da S.x" sopra le carte richiamate

    function ingombroNodo(nodo, dim) {
        if (nodo.tipo_speciale !== "rivelazione") {
            return { l: dim.nodeW / 2, r: dim.nodeW / 2, t: dim.nodeH / 2, b: dim.nodeH / 2 };
        }
        // Stella più il "?" fantasma alla sua destra
        const raggio = Math.ceil(dim.rivR * STELLA_IRR_MAX);
        const destra = Math.max(raggio, dim.rivR + dim.ghostGap + dim.ghostR) + 6;
        return { l: raggio, r: destra, t: raggio, b: raggio };
    }

    function rettNodo(pos) {
        return { x1: pos.x - pos.ext.l, y1: pos.y - pos.ext.t, x2: pos.x + pos.ext.r, y2: pos.y + pos.ext.b };
    }

    // Riquadro di scena attorno a un insieme di posizioni (stessa formula del disegno)
    function riquadroScena(posizioni, dim) {
        let x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
        posizioni.forEach(pos => {
            const r = rettNodo(pos);
            x1 = Math.min(x1, r.x1); y1 = Math.min(y1, r.y1);
            x2 = Math.max(x2, r.x2); y2 = Math.max(y2, r.y2);
        });
        if (x1 === Infinity) return null;
        return {
            x: x1 - dim.boxPad,
            y: y1 - dim.boxPad - dim.boxTitleH,
            w: x2 - x1 + dim.boxPad * 2,
            h: y2 - y1 + dim.boxPad * 2 + dim.boxTitleH,
        };
    }

    function rettIntersecano(a, b, m) {
        return a.x1 < b.x2 + m && b.x1 < a.x2 + m && a.y1 < b.y2 + m && b.y1 < a.y2 + m;
    }

    // Segmento p-q contro rettangolo (Liang–Barsky)
    function segmentoTagliaRett(p, q, r) {
        let t0 = 0, t1 = 1;
        const dx = q.x - p.x, dy = q.y - p.y;
        const prove = [[-dx, p.x - r.x1], [dx, r.x2 - p.x], [-dy, p.y - r.y1], [dy, r.y2 - p.y]];
        for (const [pp, qq] of prove) {
            if (pp === 0) { if (qq < 0) return false; continue; }
            const t = qq / pp;
            if (pp < 0) { if (t > t1) return false; if (t > t0) t0 = t; }
            else { if (t < t0) return false; if (t < t1) t1 = t; }
        }
        return t0 < t1;
    }

    function calcolaLayoutGrafo(nodi, collegamenti, dim) {
        const byId = nodiById(nodi);
        const coll = collegamenti.filter(c => byId[c.nodo_genitore_id] && byId[c.nodo_figlio_id]);
        // Un arco verso una scena precedente tirerebbe il figlio fuori dalla sua
        // scena: dagre non lo vede, viene solo tracciato alla fine.
        const avanti = coll.filter(c => scenaNodo(byId[c.nodo_genitore_id]) <= scenaNodo(byId[c.nodo_figlio_id]));
        const scene = [...new Set(nodi.map(scenaNodo))].sort((a, b) => a - b);

        const ghostExt = (n) => { const e = ingombroNodo(n, dim); return e.r - e.l; };
        const gl = new dagre.graphlib.Graph();
        gl.setGraph({ rankdir: "LR", nodesep: 28, ranksep: 160, marginx: dim.pad, marginy: dim.pad });
        gl.setDefaultEdgeLabel(() => ({}));
        nodi.forEach(n => {
            const e = ingombroNodo(n, dim);
            gl.setNode(String(n.id), { width: e.l + e.r, height: e.t + e.b });
        });
        avanti.forEach(c => gl.setEdge(String(c.nodo_genitore_id), String(c.nodo_figlio_id)));

        // Radici virtuali per scena in catena: forzano rank crescenti da sinistra a destra.
        // Una scena senza radici (solo figli di altre scene) si aggancia ai nodi
        // d'ingresso; i suoi nodi terminali alla scena successiva.
        const figliIds = new Set(avanti.map(c => c.nodo_figlio_id));
        const radiciPerScena = {};
        nodi.forEach(n => {
            if (!figliIds.has(n.id)) (radiciPerScena[scenaNodo(n)] = radiciPerScena[scenaNodo(n)] || []).push(n.id);
        });
        const genitoriDiId = {};
        avanti.forEach(c => {
            (genitoriDiId[c.nodo_figlio_id] = genitoriDiId[c.nodo_figlio_id] || []).push(c.nodo_genitore_id);
        });
        let prevScenaVId = null;
        scene.forEach(scena => {
            const vId = `__scena_${scena}__`;
            gl.setNode(vId, { width: 0, height: 0 });
            if (prevScenaVId) gl.setEdge(prevScenaVId, vId);
            if (radiciPerScena[scena]) {
                radiciPerScena[scena].forEach(id => gl.setEdge(vId, String(id)));
            } else {
                nodi.forEach(n => {
                    if (scenaNodo(n) !== scena) return;
                    const parents = genitoriDiId[n.id] || [];
                    if (parents.some(pid => scenaNodo(byId[pid]) !== scena)) gl.setEdge(vId, String(n.id));
                });
            }
            prevScenaVId = vId;
        });
        scene.forEach((scena, i) => {
            if (radiciPerScena[scena] || i === scene.length - 1) return;
            const nextVId = `__scena_${scene[i + 1]}__`;
            nodi.forEach(n => {
                if (scenaNodo(n) !== scena) return;
                const figlioStessaScena = avanti.some(c =>
                    c.nodo_genitore_id === n.id && scenaNodo(byId[c.nodo_figlio_id]) === scena);
                if (!figlioStessaScena) gl.setEdge(String(n.id), nextVId);
            });
        });

        dagre.layout(gl);

        // Ingombri; la stella sta a sinistra del suo spazio, il fantasma a destra
        const posDi = {};
        nodi.forEach(n => {
            const pos = gl.node(String(n.id));
            pos.ext = ingombroNodo(n, dim);
            pos.col = Math.round(pos.x);
            pos.yDagre = pos.y;
            pos.x -= ghostExt(n) / 2;
            posDi[n.id] = pos;
        });

        // Compatta ogni colonna di ogni scena: dagre lascia buchi verticali
        // perché tira i nodi verso i figli delle scene successive.
        scene.forEach(scena => {
            const perColonna = {};
            nodi.forEach(n => {
                if (scenaNodo(n) !== scena) return;
                (perColonna[posDi[n.id].col] = perColonna[posDi[n.id].col] || []).push(n);
            });
            Object.values(perColonna).forEach(gruppo => {
                if (gruppo.length < 2) return;
                gruppo.sort((a, b) => posDi[a.id].y - posDi[b.id].y);
                let y = posDi[gruppo[0].id].y - posDi[gruppo[0].id].ext.t;
                gruppo.forEach(n => {
                    const pos = posDi[n.id];
                    pos.y = y + pos.ext.t;
                    y = pos.y + pos.ext.b + LAYOUT_GAP_Y;
                });
            });
        });

        // Dentro una scena, le fasce orizzontali vuote più alte di una carta
        // (un nodo tirato giù da un figlio lontano) si chiudono al passo normale.
        scene.forEach(scena => {
            const membri = nodi.filter(n => scenaNodo(n) === scena)
                .sort((a, b) => (posDi[a.id].y - posDi[a.id].ext.t) - (posDi[b.id].y - posDi[b.id].ext.t));
            let fondo = Infinity, su = 0;
            membri.forEach(n => {
                const pos = posDi[n.id];
                let top = pos.y - pos.ext.t - su;
                if (fondo !== Infinity && top > fondo + dim.nodeH) {
                    su += top - (fondo + LAYOUT_GAP_Y);
                    top = fondo + LAYOUT_GAP_Y;
                }
                pos.y = top + pos.ext.t;
                fondo = fondo === Infinity ? pos.y + pos.ext.b : Math.max(fondo, pos.y + pos.ext.b);
            });
        });

        // Riquadri di scena separati: in ordine di scena, chi tocca un riquadro
        // già piazzato scende quanto basta. Le scene che non si toccano restano ferme.
        const piazzati = [];
        scene.forEach(scena => {
            const membri = nodi.filter(n => scenaNodo(n) === scena).map(n => posDi[n.id]);
            const b = riquadroScena(membri, dim);
            if (!b) return;
            const r = { x1: b.x, y1: b.y, x2: b.x + b.w, y2: b.y + b.h };
            let dy = 0;
            for (let giri = 0; giri < piazzati.length + 1; giri++) {
                const urto = piazzati.find(p => rettIntersecano(r, p, LAYOUT_BOX_GAP));
                if (!urto) break;
                const d = urto.y2 + LAYOUT_BOX_GAP - r.y1;
                r.y1 += d; r.y2 += d; dy += d;
            }
            if (dy) membri.forEach(pos => { pos.y += dy; });
            piazzati.push(r);
        });

        // Archi
        const ostacoli = nodi.map(n => ({ id: n.id, r: rettNodo(posDi[n.id]) }));
        const colonne = {};
        nodi.forEach(n => {
            const pos = posDi[n.id], r = rettNodo(pos);
            const c = colonne[pos.col] = colonne[pos.col] || { x1: Infinity, x2: -Infinity, rett: [] };
            c.x1 = Math.min(c.x1, r.x1); c.x2 = Math.max(c.x2, r.x2);
            c.rett.push(r);
        });
        const listaColonne = Object.values(colonne).sort((a, b) => a.x1 - b.x1);
        const colonnaDi = (pos) => colonne[pos.col];
        const ostacolato = (punti, escludi) => {
            for (let i = 0; i < punti.length - 1; i++) {
                for (const o of ostacoli) {
                    if (escludi.has(o.id)) continue;
                    const r = { x1: o.r.x1 - 2, y1: o.r.y1 - LAYOUT_LABEL_H, x2: o.r.x2 + 2, y2: o.r.y2 + 2 };
                    if (segmentoTagliaRett(punti[i], punti[i + 1], r)) return true;
                }
            }
            return false;
        };
        // y libera in una colonna, la più vicina a quella desiderata
        const yLibera = (col, yDes) => {
            const m = LAYOUT_EDGE_M;
            const occ = col.rett.map(r => [r.y1 - LAYOUT_LABEL_H - m, r.y2 + m]).sort((a, b) => a[0] - b[0]);
            const fusi = [];
            occ.forEach(iv => {
                const ult = fusi[fusi.length - 1];
                if (ult && iv[0] <= ult[1]) ult[1] = Math.max(ult[1], iv[1]); else fusi.push(iv.slice());
            });
            const dentro = fusi.find(iv => yDes > iv[0] && yDes < iv[1]);
            if (!dentro) return yDes;
            return (yDes - dentro[0] <= dentro[1] - yDes) ? dentro[0] : dentro[1];
        };
        // Da p0 (lato destro di una carta) a p1 (lato sinistro di un'altra), passando
        // le colonne intermedie in orizzontale su una y libera; tra colonne non c'è nulla.
        const traccia = (p0, colDa, p1, colA) => {
            const punti = [p0, { x: colDa.x2, y: p0.y }];
            let prec = punti[1];
            listaColonne.forEach(col => {
                if (col === colDa || col === colA || col.x1 < colDa.x2 || col.x2 > colA.x1) return;
                const cx = (col.x1 + col.x2) / 2;
                const yDes = prec.y + (p1.y - prec.y) * (cx - prec.x) / Math.max(1, p1.x - prec.x);
                const y = yLibera(col, yDes);
                punti.push({ x: col.x1, y }, { x: col.x2, y });
                prec = punti[punti.length - 1];
            });
            punti.push({ x: colA.x1, y: p1.y }, p1);
            return punti.filter((p, i) => i === 0 || Math.abs(p.x - punti[i - 1].x) > 0.5 || Math.abs(p.y - punti[i - 1].y) > 0.5);
        };
        const latoD = (pos) => ({ x: pos.x + pos.ext.r, y: pos.y });
        const latoS = (pos) => ({ x: pos.x - pos.ext.l, y: pos.y });
        // Lato destro della carta (per la stella, il bordo della stella, non del fantasma)
        const uscita = (n, pos) => n.tipo_speciale === "rivelazione"
            ? { x: pos.x + Math.ceil(dim.rivR * STELLA_IRR_MAX), y: pos.y } : latoD(pos);

        // Nodo che non sta più dove l'ha messo dagre: i punti intermedi dei suoi
        // archi non valgono più
        const spostato = (pos) => Math.abs(pos.y - pos.yDagre) > 0.5;
        coll.forEach(c => {
            const u = byId[c.nodo_genitore_id], v = byId[c.nodo_figlio_id];
            const pu = posDi[u.id], pv = posDi[v.id];
            const vId = String(u.id), wId = String(v.id);
            const escludi = new Set([u.id, v.id]);
            const edge = gl.edge(vId, wId);
            if (edge && edge.points && edge.points.length >= 2 && !spostato(pu) && !spostato(pv)) {
                // Arco di dagre intatto: si aggiustano solo gli estremi
                const pts = edge.points.map(p => ({ x: p.x, y: p.y }));
                pts[0] = uscita(u, pu);
                pts[pts.length - 1] = latoS(pv);
                if (!ostacolato(pts, escludi)) { edge.points = pts; return; }
            }
            const cu = colonnaDi(pu), cv = colonnaDi(pv);
            let punti;
            if (cu.x2 <= cv.x1) {
                punti = traccia(uscita(u, pu), cu, latoS(pv), cv);
            } else if (cv.x2 <= cu.x1) {
                // Arco all'indietro: esce a sinistra del genitore, entra a destra del figlio
                punti = traccia(uscita(v, pv), cv, latoS(pu), cu).reverse();
            } else if (cu === cv) {
                // Stessa colonna: gira nel corridoio libero alla sua destra
                const xc = cu.x2 + LAYOUT_GAP_Y;
                const a = uscita(u, pu), z = uscita(v, pv);
                punti = [a, { x: xc, y: a.y }, { x: xc, y: z.y }, z];
            } else {
                punti = [uscita(u, pu), latoS(pv)];
            }
            gl.setEdge(vId, wId, Object.assign(edge || {}, { points: punti }));
        });

        return gl;
    }

    window.IndaginiShared = {
        calcolaLayoutGrafo,
        riquadroScena,
        rettNodo,
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
