(function () {
    const SVG_NS = "http://www.w3.org/2000/svg";
    const RAW = JSON.parse(document.getElementById("indagini-player-data").textContent);
    const INDAGINE_ID = window.INDAGINI_PLAYER_CONFIG.indagineId;
    const POLL_MS = window.INDAGINI_PLAYER_CONFIG.pollMs;
    const {
        scenaNodo,
        nodiById,
        tutteLeScene: listaTutteLeScene,
        escapeHtml: escHtml,
        stellaPunti,
        nodoHaFigliScoperti: sharedNodoHaFigliScoperti,
        nodoRichiamato: sharedNodoRichiamato
    } = window.IndaginiShared;
    let SCENE_GIFS = RAW.scene_gifs || {};

    const siparioOverlay = document.getElementById("siparioOverlay");
    if (RAW.sipario_aperto) {
        siparioOverlay.classList.remove("attivo");
    } else {
        siparioOverlay.classList.add("attivo");
    }

    // --- Gestione sfondo scena ---
    const graphSceneBg = document.getElementById("graphSceneBg");
    const graphSceneOverlay = document.getElementById("graphSceneOverlay");

    let currentBgImg = null;
    let bgTimeout = null;

    function aggiornaSfondoScena(nuovaScena) {
        const img = SCENE_GIFS[String(nuovaScena)];
        const targetUrl = img ? `url(${JSON.stringify(img)})` : `url(${JSON.stringify(window.INDAGINI_PLAYER_CONFIG.defaultBackgroundUrl)})`;
        
        if (targetUrl === currentBgImg) return;
        currentBgImg = targetUrl;
        
        clearTimeout(bgTimeout);

        if (graphSceneBg.classList.contains("attivo")) {
            // Svanisce a nero (durata 0.6s) prima di caricare la nuova
            graphSceneBg.classList.remove("attivo");
            bgTimeout = setTimeout(() => {
                if (currentBgImg === targetUrl) {
                    graphSceneBg.style.backgroundImage = targetUrl;
                    graphSceneBg.classList.add("attivo");
                    graphSceneOverlay.classList.add("attivo");
                }
            }, 600);
        } else {
            graphSceneBg.style.backgroundImage = targetUrl;
            graphSceneBg.classList.add("attivo");
            graphSceneOverlay.classList.add("attivo");
        }
    }
    // --- Lista "Da esaminare" ---
    // Il server manda solo le etichette player-safe della scena corrente
    // (mai titoli o descrizioni), già raggruppate e con lo stato esaminato.
    const esploraBox = document.getElementById("playerEsplora");
    const esploraLista = document.getElementById("playerEsploraLista");
    let puntiPrecedenti = null; // {etichetta: esaminato} dell'ultimo render

    function aggiornaPuntiInteresse(voci) {
        voci = voci || [];
        const attuali = {};
        voci.forEach(v => { attuali[v.etichetta] = v.esaminato; });
        const etichette = Object.keys(attuali);
        if (puntiPrecedenti) {
            const vecchie = Object.keys(puntiPrecedenti);
            const identiche = vecchie.length === etichette.length &&
                etichette.every(e => puntiPrecedenti[e] === attuali[e]);
            if (identiche) return;
        }
        // Lista nuova (primo caricamento o cambio scena): le voci entrano in
        // sequenza. Stessa lista: si anima solo il tratto su quelle appena esaminate.
        const listaNuova = !puntiPrecedenti ||
            etichette.some(e => !(e in puntiPrecedenti)) ||
            Object.keys(puntiPrecedenti).some(e => !(e in attuali));

        esploraLista.innerHTML = "";
        voci.forEach((v, i) => {
            const li = document.createElement("li");
            li.className = "player-esplora__voce";
            li.textContent = v.etichetta;
            if (v.esaminato) {
                li.classList.add("player-esplora__voce--esaminata");
                if (!listaNuova && puntiPrecedenti[v.etichetta] === false) {
                    li.classList.add("player-esplora__voce--appena");
                }
            }
            if (listaNuova) {
                li.classList.add("player-esplora__voce--entra");
                li.style.animationDelay = `${120 + i * 70}ms`;
            }
            esploraLista.appendChild(li);
        });
        esploraBox.hidden = voci.length === 0;
        esploraBox.classList.toggle("player-esplora--completa", voci.length > 0 && voci.every(v => v.esaminato));
        puntiPrecedenti = attuali;
    }

    aggiornaPuntiInteresse(RAW.punti_interesse);

    const NODE_W = 170;
    const NODE_H = 80;
    const PAD = 40;
    const GHOST_GAP = 90;
    const GHOST_R = 28;
    const ARROW_AMB_LEN = 80;
    const RIV_R = Math.round(NODE_H * 1.8);
    const RIV_r = Math.round(RIV_R * 0.42);

    // --- Stato corrente (ricostruito dal server) ---
    let scopertiIds = new Set(RAW.scoperti_ids.map(Number));
    let scenaCorrente = RAW.scena_corrente ?? 1;

    // Costruisci statiCorrente dai dati iniziali
    let statiCorrente = {};
    const NODI = RAW.nodi;
    const COLL = RAW.collegamenti;
    const nodoById = nodiById(NODI);

    function ricalcolaStati(scopertiSet, scena) {
        const stati = {};
        NODI.forEach(n => {
            const nid = n.id;
            // Uno scoperto resta tale anche tornando a una scena precedente
            if (scopertiSet.has(nid)) {
                stati[nid] = "SCOPERTO";
            } else if (scena !== null && scenaNodo(n) > scena) {
                stati[nid] = "ASSENTE";
            } else {
                stati[nid] = "BLOCCATO_VISIBILE";
            }
        });
        return stati;
    }

    statiCorrente = ricalcolaStati(scopertiIds, scenaCorrente);

    // --- Tutte le scene ---
    const tutteLeScene = listaTutteLeScene(NODI);

    // ----------------------------------------------------------------
    // Pannello dettaglio nodo (versione player, senza badge sblocco)
    // ----------------------------------------------------------------
    let nodoDetailId = null;
    const detailPanel = document.getElementById("playerDetail");
    const detailInner = document.getElementById("playerDetailInner");
    const detailClose = document.getElementById("playerDetailClose");

    function apriDettaglio(n) {
        nodoDetailId = n.id;
        const scena = Math.floor(n.numero_nodo / 10);

        let html = `
            <p class="player-detail__scena">Scena ${scena}</p>
            <h2 class="player-detail__titolo">${escHtml(n.titolo)}</h2>`;

        if (n.immagine_url) {
            html += `<img class="player-detail__img" src="${escHtml(n.immagine_url)}"
                          alt="${escHtml(n.titolo)}" loading="lazy">`;
        }

        if (n.descrizione) {
            html += `<hr class="player-detail__divider">
                     <p class="player-detail__desc">${escHtml(n.descrizione)}</p>`;
        }

        detailInner.innerHTML = html;
        detailPanel.classList.add("aperto");
    }

    function chiudiDettaglio() {
        nodoDetailId = null;
        detailPanel.classList.remove("aperto");
    }

    detailClose.addEventListener("click", chiudiDettaglio);

    // ----------------------------------------------------------------
    // Dagre layout — SOLO sui nodi visibili, ricalcolato a ogni render.
    // Se i nodi non ancora scoperti tenessero il loro posto, il grafo
    // mostrerebbe i buchi (e quindi quanti indizi mancano): qui la scena
    // resta sempre compatta e i nodi già presenti scivolano nelle nuove
    // posizioni quando ne arriva uno.
    // ----------------------------------------------------------------
    let g = null;

    function calcolaLayout() {
        const visibili = NODI.filter(nodoDovrebbeEssereVisibile);
        const visIds = new Set(visibili.map(n => n.id));
        const coll = COLL.filter(c => visIds.has(c.nodo_genitore_id) && visIds.has(c.nodo_figlio_id));
        const scene = [...new Set(visibili.map(scenaNodo))].sort((a, b) => a - b);

        const gl = new dagre.graphlib.Graph();
        gl.setGraph({ rankdir: "LR", nodesep: 28, ranksep: 160, marginx: PAD, marginy: PAD });
        gl.setDefaultEdgeLabel(() => ({}));
        visibili.forEach(n => gl.setNode(String(n.id), { width: NODE_W, height: NODE_H }));
        coll.forEach(c => gl.setEdge(String(c.nodo_genitore_id), String(c.nodo_figlio_id)));

        // Virtual roots per scena: tengono le scene in colonna da sinistra a destra
        const figliIds = new Set(coll.map(c => c.nodo_figlio_id));
        const radiciPerScena = {};
        visibili.forEach(n => {
            if (!figliIds.has(n.id)) {
                (radiciPerScena[scenaNodo(n)] = radiciPerScena[scenaNodo(n)] || []).push(n.id);
            }
        });
        const genitoriDiId = {};
        coll.forEach(c => {
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
                visibili.forEach(n => {
                    if (scenaNodo(n) !== scena) return;
                    const parents = genitoriDiId[n.id] || [];
                    if (parents.some(pid => nodoById[pid] && scenaNodo(nodoById[pid]) !== scena))
                        gl.setEdge(vId, String(n.id));
                });
            }
            prevScenaVId = vId;
        });
        scene.forEach((scena, i) => {
            if (radiciPerScena[scena] || i === scene.length - 1) return;
            const nextVId = `__scena_${scene[i + 1]}__`;
            visibili.forEach(n => {
                if (scenaNodo(n) !== scena) return;
                const hasChildInSameScene = coll.some(c =>
                    c.nodo_genitore_id === n.id &&
                    nodoById[c.nodo_figlio_id] &&
                    scenaNodo(nodoById[c.nodo_figlio_id]) === scena
                );
                if (!hasChildInSameScene) gl.setEdge(String(n.id), nextVId);
            });
        });

        dagre.layout(gl);

        // Post-processing: redistribuzione nodi per eliminare gap verticali
        const STEP_Y = NODE_H + 28;
        scene.forEach(scena => {
            const byRank = {};
            visibili.forEach(n => {
                if (scenaNodo(n) !== scena) return;
                const pos = gl.node(String(n.id));
                if (!pos) return;
                const rk = Math.round(pos.x);
                (byRank[rk] = byRank[rk] || []).push({ id: String(n.id), pos });
            });
            Object.values(byRank).forEach(group => {
                if (group.length < 2) return;
                group.sort((a, b) => a.pos.y - b.pos.y);
                const baseY = group[0].pos.y;
                group.forEach((item, i) => {
                    const newY = baseY + i * STEP_Y;
                    const dy = newY - item.pos.y;
                    if (Math.abs(dy) < 0.5) return;
                    item.pos.y = newY;
                    (gl.nodeEdges(item.id) || []).forEach(e => {
                        const edge = gl.edge(e);
                        if (!edge || !edge.points || !edge.points.length) return;
                        if (e.v === item.id) edge.points[0].y += dy;
                        else edge.points[edge.points.length - 1].y += dy;
                    });
                });
            });
        });
        return gl;
    }

    // ----------------------------------------------------------------
    // SVG e gruppi
    // ----------------------------------------------------------------
    const svg = document.getElementById("playerSvg");
    const root = document.getElementById("playerG");

    const scenesGroup = document.createElementNS(SVG_NS, "g");
    scenesGroup.id = "scenesGroup";
    root.appendChild(scenesGroup);

    const edgesGroup = document.createElementNS(SVG_NS, "g");
    edgesGroup.id = "edgesGroup";
    root.appendChild(edgesGroup);

    const nodesGroup = document.createElementNS(SVG_NS, "g");
    nodesGroup.id = "nodesGroup";
    root.appendChild(nodesGroup);

    // ----------------------------------------------------------------
    // Pan e zoom
    // ----------------------------------------------------------------
    const PZ_MIN = 0.15, PZ_MAX = 4;
    let pz = { tx: 0, ty: 0, s: 1 };
    let pzInit = false;
    // Dopo un pan/zoom a mano la vista resta dove l'ha messa il master
    let pzManuale = false;

    function applyPZ(animato) {
        root.style.transition = animato ? "transform 0.8s cubic-bezier(0.4, 0, 0.2, 1)" : "none";
        root.style.transform = `translate(${pz.tx}px, ${pz.ty}px) scale(${pz.s})`;
    }

    svg.addEventListener("wheel", e => {
        e.preventDefault();
        const rect = svg.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
        const ns = Math.max(PZ_MIN, Math.min(PZ_MAX, pz.s * factor));
        pz.tx = mx - (mx - pz.tx) * (ns / pz.s);
        pz.ty = my - (my - pz.ty) * (ns / pz.s);
        pz.s = ns;
        pzManuale = true;
        applyPZ();
    }, { passive: false });

    let pzDrag = false, pzDragStart = null, pzDragMoved = false;
    svg.addEventListener("mousedown", e => {
        if (e.button !== 0) return;
        pzDrag = true; pzDragMoved = false;
        pzDragStart = { x: e.clientX - pz.tx, y: e.clientY - pz.ty };
        svg.style.cursor = "grabbing";
    });
    window.addEventListener("mousemove", e => {
        if (!pzDrag) return;
        const nx = e.clientX - pzDragStart.x;
        const ny = e.clientY - pzDragStart.y;
        if (!pzDragMoved && (Math.abs(nx - pz.tx) > 3 || Math.abs(ny - pz.ty) > 3)) {
            pzDragMoved = true;
            pzManuale = true;
        }
        pz.tx = nx; pz.ty = ny;
        applyPZ();
    });
    window.addEventListener("mouseup", () => {
        pzDrag = false;
        svg.style.cursor = "";
    });
    svg.addEventListener("click", e => {
        if (pzDragMoved) { e.stopPropagation(); pzDragMoved = false; }
    }, true);

    // ----------------------------------------------------------------
    // Helper stato nodo (PLAYER: mostra solo SCOPERTO)
    // ----------------------------------------------------------------
    function nodoHaFigliScoperti(nodoId) {
        return sharedNodoHaFigliScoperti(nodoId, COLL, statiCorrente, nodoById, scenaCorrente);
    }

    // Player: mostra SOLO nodi scoperti (nessun nodo bloccato visibile)
    function nodoDovrebbeEssereVisibile(n) {
        const stato = statiCorrente[n.id];
        if (stato !== "SCOPERTO") return false;
        const scena = scenaNodo(n);
        if (scena <= scenaCorrente - 2) {
            return nodoHaFigliScoperti(n.id);
        }
        return true;
    }

    function nodoRichiamato(n) {
        return sharedNodoRichiamato(n, scenaCorrente, COLL, statiCorrente, nodoById);
    }

    // ----------------------------------------------------------------
    // Helpers rivelazione
    // ----------------------------------------------------------------
    function renderStellaScoperta(gEl, pos, n, animClass) {
        const wrap = document.createElementNS(SVG_NS, "g");
        if (animClass) wrap.classList.add(animClass);

        const poly = document.createElementNS(SVG_NS, "polygon");
        poly.setAttribute("points", stellaPunti(pos.x, pos.y, RIV_R, RIV_r, 9));
        poly.setAttribute("fill", "#3D0F0F");
        poly.setAttribute("stroke", "#8A3A3A");
        poly.setAttribute("stroke-width", "2.5");
        wrap.appendChild(poly);

        const titolo = n.titolo.length > 16 ? n.titolo.slice(0, 14) + "…" : n.titolo;
        const tTit = document.createElementNS(SVG_NS, "text");
        tTit.setAttribute("x", pos.x); tTit.setAttribute("y", pos.y + 5);
        tTit.setAttribute("text-anchor", "middle"); tTit.setAttribute("dominant-baseline", "middle");
        tTit.setAttribute("font-family", "Fraunces, serif");
        tTit.setAttribute("font-size", "15"); tTit.setAttribute("font-weight", "700");
        tTit.setAttribute("fill", "#C87070");
        tTit.textContent = titolo;
        wrap.appendChild(tTit);

        gEl.appendChild(wrap);
    }

    function creaGhostQuery(pos, animato, startOffsetX) {
        const gGhost = document.createElementNS(SVG_NS, "g");
        const ox = startOffsetX !== undefined ? startOffsetX : NODE_W / 2;
        const x1 = pos.x + ox, y1 = pos.y;
        const x2 = pos.x + ox + GHOST_GAP, y2 = pos.y;

        const linea = document.createElementNS(SVG_NS, "line");
        linea.setAttribute("x1", x1); linea.setAttribute("y1", y1);
        linea.setAttribute("x2", x2 - GHOST_R); linea.setAttribute("y2", y2);
        linea.setAttribute("stroke", "#5A1F1F"); linea.setAttribute("stroke-width", "1.5");
        linea.setAttribute("stroke-dasharray", "6 4");
        linea.setAttribute("marker-end", "url(#arrowhead-ghost)");
        if (animato) {
            linea.classList.add("ghost-linea");
            const len = GHOST_GAP - GHOST_R;
            linea.setAttribute("stroke-dasharray", `${len} ${len}`);
            linea.setAttribute("stroke-dashoffset", len);
        } else {
            linea.setAttribute("opacity", "0.5");
        }
        gGhost.appendChild(linea);

        const cerchio = document.createElementNS(SVG_NS, "circle");
        cerchio.setAttribute("cx", x2); cerchio.setAttribute("cy", y2);
        cerchio.setAttribute("r", GHOST_R);
        cerchio.setAttribute("fill", "#0F0D0B"); cerchio.setAttribute("stroke", "#5A1F1F");
        cerchio.setAttribute("stroke-width", "1.5"); cerchio.setAttribute("stroke-dasharray", "4 3");
        if (animato) cerchio.classList.add("ghost-q"); else cerchio.setAttribute("opacity", "0.5");
        gGhost.appendChild(cerchio);

        const tQ = document.createElementNS(SVG_NS, "text");
        tQ.setAttribute("x", x2); tQ.setAttribute("y", y2 + 1);
        tQ.setAttribute("text-anchor", "middle"); tQ.setAttribute("dominant-baseline", "middle");
        tQ.setAttribute("font-family", "Fraunces, serif"); tQ.setAttribute("font-size", "24");
        tQ.setAttribute("font-weight", "600"); tQ.setAttribute("fill", "#5A1F1F");
        if (animato) tQ.classList.add("ghost-q"); else tQ.setAttribute("opacity", "0.5");
        tQ.textContent = "?";
        gGhost.appendChild(tQ);
        return gGhost;
    }

    function animaRivelazione(gEl, pos, n) {
        const lockedRect = gEl.querySelector(".riv-locked-rect");
        if (lockedRect) lockedRect.classList.add("esplodi");

        // Nella player view, il nodo era invisibile → facciamo partire dall'esplosione
        setTimeout(() => {
            while (gEl.firstChild) gEl.removeChild(gEl.firstChild);
            const tExcl = document.createElementNS(SVG_NS, "text");
            tExcl.setAttribute("x", pos.x); tExcl.setAttribute("y", pos.y + 2);
            tExcl.setAttribute("text-anchor", "middle"); tExcl.setAttribute("dominant-baseline", "middle");
            tExcl.setAttribute("font-family", "Fraunces, serif");
            tExcl.setAttribute("font-size", "68"); tExcl.setAttribute("font-weight", "600");
            tExcl.setAttribute("fill", "#8A3A3A");
            tExcl.classList.add("riv-excl");
            tExcl.textContent = "!";
            gEl.appendChild(tExcl);

            setTimeout(() => {
                while (gEl.firstChild) gEl.removeChild(gEl.firstChild);
                renderStellaScoperta(gEl, pos, n, "riv-contenuto");

                setTimeout(() => {
                    const ghost = creaGhostQuery(pos, true, RIV_R);
                    nodesGroup.appendChild(ghost);
                }, 320);
            }, 520);
        }, 150);
    }

    // ----------------------------------------------------------------
    // Crea elemento SVG nodo (PLAYER: solo stato SCOPERTO)
    // ----------------------------------------------------------------
    function creaElementoNodo(n, animClass) {
        const pos = g.node(String(n.id));
        if (!pos) return null;
        const x = pos.x - NODE_W / 2, y = pos.y - NODE_H / 2;
        const gEl = document.createElementNS(SVG_NS, "g");
        gEl.classList.add("g-node");
        if (animClass) gEl.classList.add(animClass);
        gEl.dataset.id = n.id;
        gEl.setAttribute("transform-origin", `${pos.x} ${pos.y}`);

        const isRiv = n.tipo_speciale === "rivelazione";
        const isRich = nodoRichiamato(n);

        // Click su nodo → pannello dettaglio
        gEl.style.cursor = "pointer";
        gEl.addEventListener("click", () => {
            if (nodoDetailId === n.id) { chiudiDettaglio(); return; }
            apriDettaglio(n);
        });

        if (isRiv) {
            renderStellaScoperta(gEl, pos, n, null);
            gEl._ghostDaAggiungere = creaGhostQuery(pos, false, RIV_R);
        } else {
            const rect = document.createElementNS(SVG_NS, "rect");
            rect.setAttribute("x", x); rect.setAttribute("y", y);
            rect.setAttribute("width", NODE_W); rect.setAttribute("height", NODE_H);
            rect.setAttribute("rx", 4);
            rect.setAttribute("fill", "#1E1A14"); rect.setAttribute("stroke", "#5C8A71");
            rect.setAttribute("stroke-width", "1");
            gEl.appendChild(rect);

            // Niente numero del nodo: i salti (#11, #16…) direbbero quanti indizi mancano

            const titolo = n.titolo.length > 22 ? n.titolo.slice(0, 20) + "…" : n.titolo;
            const tTit = document.createElementNS(SVG_NS, "text");
            tTit.setAttribute("x", pos.x); tTit.setAttribute("y", y + 34);
            tTit.setAttribute("text-anchor", "middle");
            tTit.setAttribute("font-family", "IBM Plex Sans, sans-serif");
            tTit.setAttribute("font-size", "13"); tTit.setAttribute("font-weight", "500");
            tTit.setAttribute("fill", "#E8E2D5");
            tTit.textContent = titolo;
            gEl.appendChild(tTit);

            if (n.descrizione) {
                const desc = n.descrizione.length > 28 ? n.descrizione.slice(0, 26) + "…" : n.descrizione;
                const tDesc = document.createElementNS(SVG_NS, "text");
                tDesc.setAttribute("x", pos.x); tDesc.setAttribute("y", y + 50);
                tDesc.setAttribute("text-anchor", "middle");
                tDesc.setAttribute("font-family", "IBM Plex Sans, sans-serif");
                tDesc.setAttribute("font-size", "10"); tDesc.setAttribute("fill", "#A89F8C");
                tDesc.textContent = desc;
                gEl.appendChild(tDesc);
            }

            if (n.immagine_url) {
                const img = document.createElementNS(SVG_NS, "text");
                img.setAttribute("x", x + NODE_W - 10); img.setAttribute("y", y + 16);
                img.setAttribute("text-anchor", "end"); img.setAttribute("font-size", "12");
                img.setAttribute("fill", "#9C7A3C"); img.textContent = "🖼";
                gEl.appendChild(img);
            }

            const badge = document.createElementNS(SVG_NS, "circle");
            badge.setAttribute("cx", x + NODE_W - 8); badge.setAttribute("cy", y + 8);
            badge.setAttribute("r", 4);
            badge.setAttribute("fill", "#5C8A71");
            gEl.appendChild(badge);

            // Etichetta scena di provenienza per nodi richiamati
            if (isRich) {
                const lbl = document.createElementNS(SVG_NS, "text");
                lbl.setAttribute("x", x + 4); lbl.setAttribute("y", y - 5);
                lbl.setAttribute("font-family", "JetBrains Mono, monospace");
                lbl.setAttribute("font-size", "8");
                lbl.setAttribute("fill", "#5C5040");
                lbl.setAttribute("letter-spacing", "0.04em");
                lbl.textContent = `da S.${scenaNodo(n)}`;
                gEl.appendChild(lbl);
            }
        }
        return gEl;
    }

    // ----------------------------------------------------------------
    // Frecce (solo tra nodi scoperti e visibili)
    // ----------------------------------------------------------------
    function disegnaFrecce(animEdgeSet) {
        edgesGroup.innerHTML = "";

        NODI.forEach(n => {
            if (statiCorrente[n.id] !== "SCOPERTO") return;
            if (!nodoDovrebbeEssereVisibile(n)) return;
            if (n.tipo_speciale === "rivelazione") return;

            const pos = g.node(String(n.id));
            if (!pos) return;

            if (!nodoHaFigliScoperti(n.id)) {
                // Freccia ambigua
                const x1 = pos.x + NODE_W / 2;
                const y1 = pos.y;
                const linea = document.createElementNS(SVG_NS, "line");
                linea.setAttribute("x1", x1); linea.setAttribute("y1", y1);
                linea.setAttribute("x2", x1 + ARROW_AMB_LEN); linea.setAttribute("y2", y1);
                linea.setAttribute("stroke", "#3A322A");
                linea.setAttribute("stroke-width", "1.5");
                linea.setAttribute("marker-end", "url(#arrowhead)");
                edgesGroup.appendChild(linea);
            } else {
                // Archi reali verso figli scoperti
                COLL.forEach(c => {
                    if (c.nodo_genitore_id !== n.id) return;
                    if (statiCorrente[c.nodo_figlio_id] !== "SCOPERTO") return;
                    const figlio = nodoById[c.nodo_figlio_id];
                    if (!figlio || !nodoDovrebbeEssereVisibile(figlio)) return;

                    const edge = g.edge(String(c.nodo_genitore_id), String(c.nodo_figlio_id));
                    if (!edge || !edge.points) return;
                    const pts = edge.points.map(p => `${p.x},${p.y}`).join(" L ");
                    const path = document.createElementNS(SVG_NS, "path");
                    path.setAttribute("d", `M ${pts}`);
                    path.setAttribute("fill", "none");
                    path.setAttribute("stroke", "#2A241C");
                    path.setAttribute("stroke-width", "1.5");
                    path.setAttribute("marker-end", "url(#arrowhead)");
                    const edgeKey = `${c.nodo_genitore_id}-${c.nodo_figlio_id}`;
                    if (animEdgeSet && animEdgeSet.has(edgeKey)) {
                        path.classList.add("edge-new");
                    }
                    edgesGroup.appendChild(path);
                });
            }
        });
    }

    // ----------------------------------------------------------------
    // Macroriquadri di scena
    // ----------------------------------------------------------------
    const BOX_PAD = 22;
    const BOX_TITLE_H = 18;

    const sceneEls = {}; // scena -> {rect, label}: riusati perché il riquadro si allarghi/stringa con transizione

    function disegnaScene() {
        const disegnate = new Set();
        tutteLeScene.forEach(scena => {
            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
            NODI.forEach(n => {
                if (scenaNodo(n) !== scena) return;
                if (!nodoDovrebbeEssereVisibile(n)) return;
                const pos = g.node(String(n.id));
                if (!pos) return;
                minX = Math.min(minX, pos.x - NODE_W / 2);
                minY = Math.min(minY, pos.y - NODE_H / 2);
                maxX = Math.max(maxX, pos.x + NODE_W / 2);
                maxY = Math.max(maxY, pos.y + NODE_H / 2);
            });
            // Player: mostra il riquadro scena SOLO se ci sono nodi scoperti dentro
            if (minX === Infinity) return;
            disegnate.add(scena);

            const isCorrente = scena === scenaCorrente;
            const isChiusa = scena < scenaCorrente;

            const bx = minX - BOX_PAD;
            const by = minY - BOX_PAD - BOX_TITLE_H;
            const bw = maxX - minX + BOX_PAD * 2;
            const bh = maxY - minY + BOX_PAD * 2 + BOX_TITLE_H;

            let els = sceneEls[scena];
            if (!els) {
                const rect = document.createElementNS(SVG_NS, "rect");
                rect.classList.add("scena-box");
                rect.setAttribute("rx", 6);
                const label = document.createElementNS(SVG_NS, "text");
                label.classList.add("scena-box__label");
                label.setAttribute("x", 0); label.setAttribute("y", 0);
                label.setAttribute("font-family", "JetBrains Mono, monospace");
                label.setAttribute("font-size", "9");
                label.setAttribute("letter-spacing", "0.08em");
                label.textContent = `SCENA ${scena}`;
                els = sceneEls[scena] = { rect, label };
                scenesGroup.appendChild(rect);
                scenesGroup.appendChild(label);
            }
            const { rect, label } = els;
            // Attributi per il layout, proprietà CSS per la transizione
            [["x", bx], ["y", by], ["width", bw], ["height", bh]].forEach(([k, v]) => {
                rect.setAttribute(k, v);
                rect.style[k] = `${v}px`;
            });
            rect.setAttribute("fill", isChiusa ? "#08070A" : "none");
            rect.setAttribute("stroke", isCorrente ? "#5C5040" : "#221E18");
            rect.setAttribute("stroke-width", isCorrente ? "1.5" : "1");
            rect.setAttribute("stroke-dasharray", isChiusa ? "none" : "4 3");
            rect.setAttribute("opacity", isChiusa ? "0.7" : "1");
            label.style.transform = `translate(${bx + 8}px, ${by + 13}px)`;
            label.setAttribute("fill", isCorrente ? "#9C7A3C" : "#3A322A");
        });
        Object.keys(sceneEls).forEach(k => {
            if (disegnate.has(Number(k))) return;
            sceneEls[k].rect.remove();
            sceneEls[k].label.remove();
            delete sceneEls[k];
        });
    }

    // ----------------------------------------------------------------
    // Dimensioni SVG
    // ----------------------------------------------------------------
    function calcolaWidthSVG() {
        let maxX = 0;
        let rivScoperta = false;
        NODI.forEach(n => {
            if (!nodoDovrebbeEssereVisibile(n)) return;
            const pos = g.node(String(n.id));
            if (!pos) return;
            if (n.tipo_speciale === "rivelazione" && statiCorrente[n.id] === "SCOPERTO") {
                rivScoperta = true;
                maxX = Math.max(maxX, pos.x + RIV_R);
            } else {
                maxX = Math.max(maxX, pos.x + NODE_W / 2);
                if (statiCorrente[n.id] === "SCOPERTO" && !nodoHaFigliScoperti(n.id)) {
                    maxX = Math.max(maxX, pos.x + NODE_W / 2 + ARROW_AMB_LEN);
                }
            }
        });
        const rivExt = rivScoperta ? GHOST_GAP + GHOST_R * 2 + 20 : 0;
        return Math.max(maxX, 200) + PAD + rivExt;
    }

    function calcolaAltezzaSVG() {
        let minY = Infinity, maxY = -Infinity;
        NODI.forEach(n => {
            if (!nodoDovrebbeEssereVisibile(n)) return;
            const pos = g.node(String(n.id));
            if (!pos) return;
            const ry = n.tipo_speciale === "rivelazione" && statiCorrente[n.id] === "SCOPERTO" ? RIV_R : NODE_H / 2;
            minY = Math.min(minY, pos.y - ry);
            maxY = Math.max(maxY, pos.y + ry);
        });
        if (minY === Infinity) return 300 + PAD * 2;
        return (maxY - minY) + PAD * 4;
    }

    function aggiornaSVG(forceRefit) {
        if (pzInit && (!forceRefit || pzManuale)) return;
        const animato = pzInit;
        const svgRect = svg.getBoundingClientRect();
        const cw = calcolaWidthSVG();
        const ch = calcolaAltezzaSVG();
        const scale = Math.min(
            svgRect.width  > 0 ? svgRect.width  / cw : 1,
            svgRect.height > 0 ? svgRect.height / ch : 1,
            1
        );
        pz.s  = scale;
        pz.tx = (svgRect.width  - cw * scale) / 2;
        pz.ty = Math.max(0, (svgRect.height - ch * scale) / 2);
        applyPZ(animato);
        pzInit = true;
    }

    // ----------------------------------------------------------------
    // Render completo
    // ----------------------------------------------------------------
    // Nodo già in scena spostato dal nuovo layout: parte dalla vecchia
    // posizione e scivola nella nuova (FLIP su un gruppo contenitore, così
    // non interferisce con le animazioni del nodo stesso).
    function avvolgiSpostamento(el, prima, ora) {
        const dx = prima.x - ora.x, dy = prima.y - ora.y;
        if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return el;
        const wrap = document.createElementNS(SVG_NS, "g");
        wrap.classList.add("g-node-sposta");
        wrap.style.transform = `translate(${dx}px, ${dy}px)`;
        wrap.appendChild(el);
        requestAnimationFrame(() => requestAnimationFrame(() => { wrap.style.transform = ""; }));
        return wrap;
    }

    let frecceTimer = null;

    function renderTutti(animNew, animRevealed, skipIds, animEdgeSet, recallIds) {
        const posPrecedenti = {};
        if (g) g.nodes().forEach(id => {
            const p = g.node(id);
            if (p && !id.startsWith("__")) posPrecedenti[id] = { x: p.x, y: p.y };
        });
        g = calcolaLayout();
        const spostati = Object.keys(posPrecedenti).some(id => {
            const p = g.node(id);
            return p && (Math.abs(p.x - posPrecedenti[id].x) > 0.5 || Math.abs(p.y - posPrecedenti[id].y) > 0.5);
        });

        nodesGroup.innerHTML = "";
        const ghostsDaAggiungere = [];

        NODI.forEach(n => {
            if (!nodoDovrebbeEssereVisibile(n)) return;
            if (skipIds && skipIds.has(n.id)) return;
            let animClass = null;
            if (animNew && animNew.has(n.id)) animClass = "g-node-new";
            else if (animRevealed && animRevealed.has(n.id)) animClass = "g-node-arriva";
            else if (recallIds && recallIds.has(n.id)) animClass = "g-node-richiamato";
            const el = creaElementoNodo(n, animClass);
            if (!el) return;
            // Chi arriva aspetta che gli altri gli abbiano fatto posto. Transizione
            // inline oltre all'animazione: funziona anche con le animazioni del sito spente.
            if (spostati && animClass) {
                el.style.animationDelay = "0.45s";
                el.style.opacity = "0";
                setTimeout(() => {
                    el.style.transition = "opacity 0.45s ease";
                    el.style.opacity = "";
                }, 450);
            }
            const prima = posPrecedenti[String(n.id)];
            const wrapped = prima ? avvolgiSpostamento(el, prima, g.node(String(n.id))) : el;
            nodesGroup.appendChild(wrapped);
            if (el._ghostDaAggiungere) {
                if (wrapped !== el) wrapped.appendChild(el._ghostDaAggiungere);
                else ghostsDaAggiungere.push(el._ghostDaAggiungere);
            }
        });

        ghostsDaAggiungere.forEach(gh => nodesGroup.appendChild(gh));
        disegnaScene();
        disegnaFrecce(animEdgeSet);
        // Le frecce sono già nelle posizioni nuove: compaiono a spostamento finito
        clearTimeout(frecceTimer);
        if (spostati) {
            edgesGroup.style.transition = "none";
            edgesGroup.style.opacity = "0";
            frecceTimer = setTimeout(() => {
                edgesGroup.style.transition = "opacity 0.4s ease";
                edgesGroup.style.opacity = "";
            }, 700);
        } else {
            edgesGroup.style.opacity = "";
        }
        aggiornaSVG(true);
    }

    // ----------------------------------------------------------------
    // SFX helper
    // ----------------------------------------------------------------
    function riproduciSfx(path) {
        try {
            const audio = new Audio(path);
            audio.volume = 0.5; // Dimezza il volume di default
            audio.play().catch(e => console.warn("SFX non riproducibile:", e));
        } catch (e) {
            console.warn("SFX non riproducibile:", e);
        }
    }

    // ----------------------------------------------------------------
    // Utility
    // ----------------------------------------------------------------
    // ----------------------------------------------------------------
    // Render iniziale
    // ----------------------------------------------------------------
    renderTutti(null, null, null, null, null);
    aggiornaSfondoScena(scenaCorrente);

    // ----------------------------------------------------------------
    // POLLING: aggiornamento automatico ogni 2 secondi
    // ----------------------------------------------------------------
    let pollingAttivo = true;

    async function poll() {
        if (!pollingAttivo) return;
        try {
            const resp = await fetch(window.INDAGINI_PLAYER_CONFIG.endpoints.statoPlayer);
            if (!resp.ok) return;
            const data = await resp.json();

            // Il caricamento iniziale contiene solo stub dei nodi non scoperti
            // (il server non manda titoli/descrizioni non rivelati): i dati
            // completi arrivano qui, insieme allo stato, quando vengono scoperti.
            if (data.nodi) {
                data.nodi.forEach(n => {
                    const idx = NODI.findIndex(x => x.id === n.id);
                    if (idx >= 0) NODI[idx] = n; else NODI.push(n);
                    nodoById[n.id] = n;
                });
            }
            if (data.scene_gifs) {
                SCENE_GIFS = data.scene_gifs;
            }
            aggiornaPuntiInteresse(data.punti_interesse);

            const nuoviScopertiIds = new Set(data.scoperti_ids.map(Number));
            const nuovaScena = data.scena_corrente;

            // Rileva cambiamenti
            let cambiato = false;

            // Nuovi nodi scoperti (prima non erano scoperti, ora sì)
            const appenaScoperti = new Set();
            nuoviScopertiIds.forEach(id => {
                if (!scopertiIds.has(id)) {
                    appenaScoperti.add(id);
                    cambiato = true;
                }
            });

            // Scena cambiata
            if (nuovaScena !== scenaCorrente) {
                cambiato = true;
                aggiornaSfondoScena(nuovaScena);
            }

            // Aggiorna stato sipario indipendentemente dal resto
            const siparioOverlay = document.getElementById("siparioOverlay");
            if (data.sipario_aperto) {
                if (siparioOverlay.classList.contains("attivo")) {
                    siparioOverlay.classList.remove("attivo");
                }
            } else {
                if (!siparioOverlay.classList.contains("attivo")) {
                    siparioOverlay.classList.add("attivo");
                }
            }

            if (!cambiato) return;

            // Salva stato precedente
            const statiPrecedenti = Object.assign({}, statiCorrente);

            // Aggiorna stato
            scopertiIds = nuoviScopertiIds;
            scenaCorrente = nuovaScena;
            statiCorrente = ricalcolaStati(scopertiIds, scenaCorrente);

            // Calcola animazioni
            const animNew = new Set();
            const animRevealed = new Set();
            const animEdgeSet = new Set();
            const recallIds = new Set();
            let idRivelazioneAnimata = null;

            NODI.forEach(n => {
                const id = n.id;
                const vecchio = statiPrecedenti[id];
                const nuovo = statiCorrente[id];

                // Nodi che appaiono per la prima volta (cambio scena)
                if (vecchio === "ASSENTE" && nuovo === "SCOPERTO") {
                    animNew.add(id);
                }
                // Nodi appena scoperti
                else if (vecchio !== "SCOPERTO" && nuovo === "SCOPERTO" && appenaScoperti.has(id)) {
                    const nodoSfx = nodoById[id];
                    if (nodoSfx && nodoSfx.tipo_speciale === "rivelazione") {
                        idRivelazioneAnimata = id;
                        riproduciSfx(window.INDAGINI_PLAYER_CONFIG.sfx.rivelazione);
                    } else {
                        animRevealed.add(id);
                        if (nodoSfx && nodoSfx.livello_sfx) {
                            riproduciSfx(window.INDAGINI_PLAYER_CONFIG.sfx.livelloBase.replace("__LIVELLO__", nodoSfx.livello_sfx));
                        }
                    }
                }

                // Detecta archi che diventano "reali" e nodi richiamati
                if (nuovo === "SCOPERTO" && vecchio !== "SCOPERTO") {
                    COLL.forEach(c => {
                        if (c.nodo_figlio_id === id) {
                            const parentId = c.nodo_genitore_id;
                            if (statiPrecedenti[parentId] !== "SCOPERTO") return;
                            const parenteAvevaScopert = COLL.some(c2 =>
                                c2.nodo_genitore_id === parentId &&
                                statiPrecedenti[c2.nodo_figlio_id] === "SCOPERTO"
                            );
                            if (!parenteAvevaScopert) {
                                animEdgeSet.add(`${parentId}-${id}`);
                                const parentNodo = nodoById[parentId];
                                if (parentNodo && scenaNodo(parentNodo) <= scenaCorrente - 2) {
                                    recallIds.add(parentId);
                                }
                            }
                        }
                        if (c.nodo_genitore_id === id) {
                            const figlioId = c.nodo_figlio_id;
                            if (statiPrecedenti[figlioId] === "SCOPERTO") {
                                animEdgeSet.add(`${id}-${figlioId}`);
                            }
                        }
                    });
                }
            });

            // Render con animazioni
            if (idRivelazioneAnimata !== null) {
                renderTutti(animNew, animRevealed, new Set([idRivelazioneAnimata]), animEdgeSet, recallIds);
                const rivPos = g.node(String(idRivelazioneAnimata));
                if (rivPos) {
                    const rivN = nodoById[idRivelazioneAnimata];
                    const gEl = document.createElementNS(SVG_NS, "g");
                    gEl.classList.add("g-node");
                    gEl.dataset.id = idRivelazioneAnimata;
                    // Crea un rettangolo iniziale da "esplodere"
                    const rx = rivPos.x - NODE_W / 2, ry = rivPos.y - NODE_H / 2;
                    const rectPh = document.createElementNS(SVG_NS, "rect");
                    rectPh.setAttribute("x", rx); rectPh.setAttribute("y", ry);
                    rectPh.setAttribute("width", NODE_W); rectPh.setAttribute("height", NODE_H);
                    rectPh.setAttribute("rx", 4);
                    rectPh.setAttribute("fill", "#3D0F0F"); rectPh.setAttribute("stroke", "#8A3A3A");
                    rectPh.setAttribute("stroke-width", "1.5");
                    rectPh.classList.add("riv-locked-rect");
                    gEl.appendChild(rectPh);
                    nodesGroup.appendChild(gEl);
                    animaRivelazione(gEl, rivPos, rivN);
                }
            } else {
                renderTutti(animNew, animRevealed, null, animEdgeSet, recallIds);
            }

        } catch (e) {
            console.warn("Polling error:", e);
        }
    }

    setInterval(poll, POLL_MS);

    // Cleanup al cambio pagina
    window.addEventListener("beforeunload", () => { pollingAttivo = false; });
})();
