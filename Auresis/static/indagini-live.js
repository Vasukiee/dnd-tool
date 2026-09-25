(function () {
    const SVG_NS = "http://www.w3.org/2000/svg";
    const RAW = JSON.parse(document.getElementById("indagini-live-data").textContent);
    const INDAGINE_ID = window.INDAGINI_LIVE_CONFIG.indagineId;
    const {
        scenaNodo,
        nodiById,
        tutteLeScene: listaTutteLeScene,
        escapeHtml: escHtml,
        stellaPunti,
        statiDaPayload,
        statiDiversi,
        nodoHaFigliScoperti: sharedNodoHaFigliScoperti,
        nodoRichiamato: sharedNodoRichiamato
    } = window.IndaginiShared;
    const NODE_W = 170;
    const NODE_H = 80;
    const PAD = 40;
    const GHOST_GAP = 90;
    const GHOST_R = 28;
    const ARROW_AMB_LEN = 80;
    const RIV_R = Math.round(NODE_H * 1.8);
    const RIV_r = Math.round(RIV_R * 0.42);

    let statiCorrente = {};
    Object.entries(RAW.stati).forEach(([k, v]) => { statiCorrente[parseInt(k)] = v; });

    // ----------------------------------------------------------------
    // Pannello dettaglio nodo
    // ----------------------------------------------------------------
    let nodoDetailId = null;
    const detailPanel  = document.getElementById("liveDetail");
    const detailInner  = document.getElementById("liveDetailInner");
    const detailClose  = document.getElementById("liveDetailClose");

    function apriDettaglio(n) {
        nodoDetailId = n.id;
        const scena = Math.floor(n.numero_nodo / 10);
        const manuale = n.sbloccato_manualmente;
        const isRiv   = n.tipo_speciale === "rivelazione";

        let html = `
            <p class="live-detail__scena">Scena ${scena}</p>
            <p class="live-detail__num">#${n.numero_nodo}</p>
            <h2 class="live-detail__titolo">${escHtml(n.titolo)}</h2>`;

        if (n.immagine_url) {
            html += `<img class="live-detail__img" src="${escHtml(n.immagine_url)}"
                          alt="${escHtml(n.titolo)}" loading="lazy">`;
        }

        if (n.descrizione) {
            html += `<hr class="live-detail__divider">
                     <p class="live-detail__desc">${escHtml(n.descrizione)}</p>`;
        }

        if (isRiv) {
            html += `<span class="live-detail__badge live-detail__badge--riv">★ Rivelazione</span>`;
        } else if (manuale) {
            html += `<span class="live-detail__badge live-detail__badge--manuale">● Sblocco manuale</span>`;
        } else {
            html += `<span class="live-detail__badge live-detail__badge--auto">● Sblocco automatico</span>`;
        }

        detailInner.innerHTML = html;
        detailPanel.classList.add("aperto");
    }

    function chiudiDettaglio() {
        nodoDetailId = null;
        detailPanel.classList.remove("aperto");
    }

    detailClose.addEventListener("click", chiudiDettaglio);

    let cronologiaId = RAW.cronologia_id;
    let scenaCorrente = RAW.scena_corrente ?? 1;
    let siparioAperto = !!RAW.sipario_aperto;
    const POLL_MS = window.INDAGINI_LIVE_CONFIG.pollMs;

    const NODI = RAW.nodi;
    const COLL = RAW.collegamenti;
    const nodoById = nodiById(NODI);

    // Tutte le scene presenti (da TUTTI i nodi, non solo radici) — usata da disegnaScene
    // e da aggiornaBottoneAvanza/avanzaScena per rilevare scene con soli nodi-figli.
    const tutteLeScene = listaTutteLeScene(NODI);

    // --- Dagre layout ---
    const g = new dagre.graphlib.Graph();
    g.setGraph({ rankdir: "LR", nodesep: 28, ranksep: 160, marginx: PAD, marginy: PAD });
    g.setDefaultEdgeLabel(() => ({}));
    NODI.forEach(n => g.setNode(String(n.id), { width: NODE_W, height: NODE_H }));
    COLL.forEach(c => g.setEdge(String(c.nodo_genitore_id), String(c.nodo_figlio_id)));

    // Virtual roots per scena in catena: forza rank crescenti da sinistra a destra.
    // La catena percorre TUTTE le scene (tutteLeScene), incluse quelle senza nodi radice
    // (es. scena 3: tutti i nodi sono figli di nodi di un'altra scena).
    // Per quelle scene, il nodo virtuale si collega ai nodi d'ingresso cross-scena;
    // i nodi terminali della scena (nessun figlio nella stessa scena) vengono poi collegati
    // al nodo virtuale della scena successiva, garantendo il rank corretto oltre tutti i nodi.
    const figliIds = new Set(COLL.map(c => c.nodo_figlio_id));
    const radiciPerScena = {};
    NODI.forEach(n => {
        if (!figliIds.has(n.id)) {
            const scena = scenaNodo(n);
            (radiciPerScena[scena] = radiciPerScena[scena] || []).push(n.id);
        }
    });
    const genitoriDiId = {};
    COLL.forEach(c => {
        genitoriDiId[c.nodo_figlio_id] = genitoriDiId[c.nodo_figlio_id] || [];
        genitoriDiId[c.nodo_figlio_id].push(c.nodo_genitore_id);
    });
    let prevScenaVId = null;
    tutteLeScene.forEach(scena => {
        const vId = `__scena_${scena}__`;
        g.setNode(vId, { width: 0, height: 0 });
        if (prevScenaVId) g.setEdge(prevScenaVId, vId);
        if (radiciPerScena[scena]) {
            radiciPerScena[scena].forEach(id => g.setEdge(vId, String(id)));
        } else {
            NODI.forEach(n => {
                if (scenaNodo(n) !== scena) return;
                const parents = genitoriDiId[n.id] || [];
                if (parents.some(pid => nodoById[pid] && scenaNodo(nodoById[pid]) !== scena))
                    g.setEdge(vId, String(n.id));
            });
        }
        prevScenaVId = vId;
    });
    tutteLeScene.forEach((scena, i) => {
        if (radiciPerScena[scena] || i === tutteLeScene.length - 1) return;
        const nextVId = `__scena_${tutteLeScene[i + 1]}__`;
        NODI.forEach(n => {
            if (scenaNodo(n) !== scena) return;
            const hasChildInSameScene = COLL.some(c =>
                c.nodo_genitore_id === n.id &&
                nodoById[c.nodo_figlio_id] &&
                scenaNodo(nodoById[c.nodo_figlio_id]) === scena
            );
            if (!hasChildInSameScene) g.setEdge(String(n.id), nextVId);
        });
    });

    dagre.layout(g);

    // Post-processing: redistribuisce i nodi di ogni scena per eliminare i gap verticali
    // causati dalla forza attrattiva di dagre verso i nodi-figli in scene successive.
    {
        const STEP_Y = NODE_H + 28; // 80 + nodesep
        tutteLeScene.forEach(scena => {
            const byRank = {};
            NODI.forEach(n => {
                if (Math.floor(n.numero_nodo / 10) !== scena) return;
                const pos = g.node(String(n.id));
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
                    (g.nodeEdges(item.id) || []).forEach(e => {
                        const edge = g.edge(e);
                        if (!edge || !edge.points || !edge.points.length) return;
                        if (e.v === item.id) edge.points[0].y += dy;
                        else edge.points[edge.points.length - 1].y += dy;
                    });
                });
            });
        });
    }

    const svg = document.getElementById("liveSvg");
    const root = document.getElementById("liveG");

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
    // Pan e zoom (libero, nessun troncamento del canvas)
    // ----------------------------------------------------------------
    const PZ_MIN = 0.15, PZ_MAX = 4;
    let pz = { tx: 0, ty: 0, s: 1 };
    let pzInit = false;

    function applyPZ() {
        root.setAttribute("transform", `translate(${pz.tx},${pz.ty}) scale(${pz.s})`);
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
        if (!pzDragMoved && (Math.abs(nx - pz.tx) > 3 || Math.abs(ny - pz.ty) > 3))
            pzDragMoved = true;
        pz.tx = nx; pz.ty = ny;
        applyPZ();
    });
    window.addEventListener("mouseup", () => {
        pzDrag = false;
        svg.style.cursor = "";
    });
    // Sopprime il click sui nodi se il gesto era un drag
    svg.addEventListener("click", e => {
        if (pzDragMoved) { e.stopPropagation(); pzDragMoved = false; }
    }, true);

    // ----------------------------------------------------------------
    // Helper stato nodo
    // ----------------------------------------------------------------
    function nodoHaFigliScoperti(nodoId) {
        return sharedNodoHaFigliScoperti(nodoId, COLL, statiCorrente, nodoById, scenaCorrente);
    }

    // Concetto 3: scene future invisibili; Concetto 4: sparizione dopo 2 scene senza freccia agganciata
    function nodoDovrebbeEssereVisibile(n) {
        const stato = statiCorrente[n.id];
        if (stato === "ASSENTE") return false;
        const scena = scenaNodo(n);
        // Scena futura: resta visibile solo ciò che era già stato scoperto (scene fuori ordine)
        if (scena > scenaCorrente) return stato === "SCOPERTO";
        if (scena <= scenaCorrente - 2) {
            // Concetto 5: visibile solo se ha almeno un figlio scoperto (richiamo retroattivo)
            return nodoHaFigliScoperti(n.id);
        }
        return true;
    }

    // Nodo che torna visibile da sparizione: scena vecchia + ha un figlio scoperto
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
                    // (il canvas è free-roaming: nessun resize dell'SVG necessario)
                }, 320);
            }, 520);
        }, 370);
    }

    // ----------------------------------------------------------------
    // Crea elemento SVG nodo
    // ----------------------------------------------------------------
    function creaElementoNodo(n, stato, animClass) {
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

        if (stato === "BLOCCATO_VISIBILE") {
            const rect = document.createElementNS(SVG_NS, "rect");
            rect.setAttribute("x", x); rect.setAttribute("y", y);
            rect.setAttribute("width", NODE_W); rect.setAttribute("height", NODE_H);
            rect.setAttribute("rx", 4);
            rect.setAttribute("fill", "#0F0D0B"); rect.setAttribute("stroke", "#2A241C");
            rect.setAttribute("stroke-width", "1");
            if (isRiv) rect.classList.add("riv-locked-rect");
            gEl.appendChild(rect);

            const tNum = document.createElementNS(SVG_NS, "text");
            tNum.setAttribute("x", pos.x); tNum.setAttribute("y", pos.y + 5);
            tNum.setAttribute("text-anchor", "middle"); tNum.setAttribute("dominant-baseline", "middle");
            tNum.setAttribute("font-family", "JetBrains Mono, monospace");
            tNum.setAttribute("font-size", "18"); tNum.setAttribute("fill", "#2A241C");
            tNum.setAttribute("font-weight", "500");
            tNum.textContent = `#${n.numero_nodo}`;
            gEl.appendChild(tNum);

            // Cosa si esamina per trovarlo: la stessa etichetta che vedono i giocatori
            const punto = (n.punto_interesse || "").trim();
            if (punto) {
                const tPunto = document.createElementNS(SVG_NS, "text");
                tPunto.setAttribute("x", pos.x); tPunto.setAttribute("y", y + 15);
                tPunto.setAttribute("text-anchor", "middle");
                tPunto.setAttribute("font-family", "IBM Plex Sans, sans-serif");
                tPunto.setAttribute("font-size", "10"); tPunto.setAttribute("fill", "#6B5E48");
                tPunto.textContent = punto.length > 26 ? punto.slice(0, 24) + "…" : punto;
                gEl.appendChild(tPunto);
            }

            const fo = document.createElementNS(SVG_NS, "foreignObject");
            fo.setAttribute("x", x + NODE_W / 2 - 36); fo.setAttribute("y", y + NODE_H - 22);
            fo.setAttribute("width", 72); fo.setAttribute("height", 20);
            const btn = document.createElement("button");
            btn.className = "btn";
            btn.style.cssText = "font-size:0.65rem;padding:2px 8px;width:100%;cursor:pointer;";
            btn.textContent = "Sblocca";
            btn.addEventListener("click", () => sbloccaNodo(n.id));
            fo.appendChild(btn);
            gEl.appendChild(fo);

        } else if (stato === "SCOPERTO") {
            // Click su nodo scoperto → pannello dettaglio
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

                const tNum = document.createElementNS(SVG_NS, "text");
                tNum.setAttribute("x", x + 8); tNum.setAttribute("y", y + 14);
                tNum.setAttribute("font-family", "JetBrains Mono, monospace");
                tNum.setAttribute("font-size", "10"); tNum.setAttribute("fill", "#9C7A3C");
                tNum.textContent = `#${n.numero_nodo}`;
                gEl.appendChild(tNum);

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
                badge.setAttribute("fill", n.sbloccato_manualmente ? "#9C7A3C" : "#5C8A71");
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
        }
        return gEl;
    }

    // ----------------------------------------------------------------
    // Frecce: ambigue per nodi senza figli scoperti, reali altrimenti
    // ----------------------------------------------------------------
    function disegnaFrecce(animEdgeSet) {
        edgesGroup.innerHTML = "";

        NODI.forEach(n => {
            if (statiCorrente[n.id] !== "SCOPERTO") return;
            if (!nodoDovrebbeEssereVisibile(n)) return;
            if (n.tipo_speciale === "rivelazione") return; // ghost query gestita nel nodo

            const pos = g.node(String(n.id));
            if (!pos) return;

            if (!nodoHaFigliScoperti(n.id)) {
                // Freccia ambigua: linea dritta orizzontale identica per tutti
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
                // Archi reali verso tutti i figli scoperti
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
                // Contabilizza la freccia ambigua
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

    function aggiornaSVG() {
        if (pzInit) return; // Non resettare la vista dopo il primo rendering
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
        applyPZ();
        pzInit = true;
    }

    // ----------------------------------------------------------------
    // Render completo
    // ----------------------------------------------------------------
    function renderTutti(animNew, animRevealed, skipIds, animEdgeSet, recallIds) {
        nodesGroup.innerHTML = "";
        const ghostsDaAggiungere = [];

        NODI.forEach(n => {
            if (!nodoDovrebbeEssereVisibile(n)) return;
            if (skipIds && skipIds.has(n.id)) return;
            const stato = statiCorrente[n.id];
            let animClass = null;
            if (animNew && animNew.has(n.id)) animClass = "g-node-new";
            else if (animRevealed && animRevealed.has(n.id)) animClass = "g-node-revealed";
            else if (recallIds && recallIds.has(n.id)) animClass = "g-node-richiamato";
            const el = creaElementoNodo(n, stato, animClass);
            if (!el) return;
            nodesGroup.appendChild(el);
            if (el._ghostDaAggiungere) ghostsDaAggiungere.push(el._ghostDaAggiungere);
        });

        ghostsDaAggiungere.forEach(gh => nodesGroup.appendChild(gh));
        disegnaScene();
        disegnaFrecce(animEdgeSet);
        aggiornaSVG();
    }

    // ----------------------------------------------------------------
    // Macroriquadri di scena (solo scene ≤ scenaCorrente)
    // ----------------------------------------------------------------
    const BOX_PAD = 22;
    const BOX_TITLE_H = 18;

    function disegnaScene() {
        scenesGroup.innerHTML = "";
        tutteLeScene.forEach(scena => {
            // Concetto 3: le scene future non hanno riquadro, salvo nodi già scoperti
            // (il riquadro nasce solo dai nodi visibili, vedi il controllo su minX).
            // Bbox da TUTTI i nodi della scena visibili (radici + figli), non solo le radici.
            // Questo garantisce che nodi come #33/#34 (figli di nodi della stessa scena)
            // siano contenuti nel riquadro della loro scena di appartenenza.
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
            if (minX === Infinity) return;

            const isCorrente = scena === scenaCorrente;
            const isChiusa   = scena < scenaCorrente;

            const bx = minX - BOX_PAD;
            const by = minY - BOX_PAD - BOX_TITLE_H;
            const bw = maxX - minX + BOX_PAD * 2;
            const bh = maxY - minY + BOX_PAD * 2 + BOX_TITLE_H;

            const rect = document.createElementNS(SVG_NS, "rect");
            rect.setAttribute("x", bx); rect.setAttribute("y", by);
            rect.setAttribute("width", bw); rect.setAttribute("height", bh);
            rect.setAttribute("rx", 6);
            rect.setAttribute("fill", isChiusa ? "#08070A" : "none");
            rect.setAttribute("stroke", isCorrente ? "#5C5040" : "#221E18");
            rect.setAttribute("stroke-width", isCorrente ? "1.5" : "1");
            rect.setAttribute("stroke-dasharray", isChiusa ? "none" : "4 3");
            if (isChiusa) rect.setAttribute("opacity", "0.7");
            scenesGroup.appendChild(rect);

            const label = document.createElementNS(SVG_NS, "text");
            label.setAttribute("x", bx + 8);
            label.setAttribute("y", by + 13);
            label.setAttribute("font-family", "JetBrains Mono, monospace");
            label.setAttribute("font-size", "9");
            label.setAttribute("letter-spacing", "0.08em");
            label.setAttribute("fill", isCorrente ? "#9C7A3C" : "#3A322A");
            label.textContent = `SCENA ${scena}`;
            scenesGroup.appendChild(label);
        });
    }

    // ----------------------------------------------------------------
    // Avanzamento scena
    // ----------------------------------------------------------------

    function aggiornaBottoneAvanza() {
        const ultimaScena = tutteLeScene[tutteLeScene.length - 1];
        const btn = document.getElementById("avanzaBtn");
        if (btn) btn.hidden = !(tutteLeScene.length > 1 && scenaCorrente < ultimaScena);
    }

    function aggiornaBottoneSipario(aperto) {
        siparioAperto = !!aperto;
        const btn = document.getElementById("siparioBtn");
        if (!btn) return;
        btn.classList.toggle("is-open", siparioAperto);
        btn.textContent = siparioAperto ? "🎭 Sipario Aperto" : "🎭 Sipario";
    }

    function applicaStatoRemoto(data, opts) {
        opts = opts || {};
        const nuovaScena = data.scena_corrente ?? 0;
        const nuoviStati = statiDaPayload(data.stati);
        const scenaCambiata = nuovaScena !== scenaCorrente;
        const statiCambiati = statiDiversi(statiCorrente, nuoviStati);
        const siparioCambiato = typeof data.sipario_aperto === "boolean" && data.sipario_aperto !== siparioAperto;
        if (data.cronologia_id) cronologiaId = data.cronologia_id;
        if (siparioCambiato || opts.forceSipario) aggiornaBottoneSipario(data.sipario_aperto);
        aggiornaPuntiInteresse(data.punti_interesse);
        aggiornaListaMostrata(data.lista_mostrata);
        if (!scenaCambiata && !statiCambiati) return;

        const statiPrecedenti = Object.assign({}, statiCorrente);
        scenaCorrente = nuovaScena;
        statiCorrente = nuoviStati;

        const animNew = new Set();
        const animRevealed = new Set();
        Object.entries(statiCorrente).forEach(([idStr, nuovo]) => {
            const id = parseInt(idStr);
            const vecchio = statiPrecedenti[id];
            if (vecchio === "ASSENTE" && nuovo !== "ASSENTE") animNew.add(id);
            if (vecchio === "BLOCCATO_VISIBILE" && nuovo === "SCOPERTO") animRevealed.add(id);
        });

        renderTutti(animNew, animRevealed, null, null, null);
        aggiornaBottoneAvanza();
        if (scenaCambiata) scrollToScena(scenaCorrente);
    }

    function scrollToScena(scena) {
        let minX = Infinity, maxX = -Infinity;
        NODI.forEach(n => {
            if (scenaNodo(n) !== scena || !nodoDovrebbeEssereVisibile(n)) return;
            const pos = g.node(String(n.id));
            if (!pos) return;
            minX = Math.min(minX, pos.x - NODE_W / 2);
            maxX = Math.max(maxX, pos.x + NODE_W / 2);
        });
        if (minX === Infinity) return;
        const svgRect = svg.getBoundingClientRect();
        const sceneCenterX = (minX + maxX) / 2;
        // Porta il centro della scena al centro del viewport, mantenendo la scala attuale
        pz.tx = svgRect.width / 2 - sceneCenterX * pz.s;
        applyPZ();
    }

    async function avanzaScena() {
        const idx = tutteLeScene.indexOf(scenaCorrente);
        if (idx === -1 || idx === tutteLeScene.length - 1) return;
        const nuovaScena = tutteLeScene[idx + 1];
        const statiPrecedenti = Object.assign({}, statiCorrente);

        try {
            const resp = await fetch(window.INDAGINI_LIVE_CONFIG.endpoints.avanzaScena, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ scena_corrente: nuovaScena }),
            });
            if (!resp.ok) { console.error("Errore avanzamento scena"); return; }
            const data = await resp.json();

            // Traccia nodi che appaiono per la prima volta (nuova scena)
            const animNew = new Set();
            Object.entries(data.stati).forEach(([k, v]) => {
                const id = parseInt(k);
                if (statiPrecedenti[id] === "ASSENTE" && v !== "ASSENTE") animNew.add(id);
            });
            scenaCorrente = data.scena_corrente;
            aggiornaBottoneSipario(data.sipario_aperto);
            aggiornaPuntiInteresse(data.punti_interesse);
            aggiornaListaMostrata(data.lista_mostrata);
            statiCorrente = {};
            Object.entries(data.stati).forEach(([k, v]) => { statiCorrente[parseInt(k)] = v; });

            renderTutti(animNew, null, null, null, null);
            aggiornaBottoneAvanza();
            scrollToScena(scenaCorrente);

            if (data.cronologia_nuova) {
                cronologiaId = data.cronologia_nuova.id;
                aggiornaCronologieDopoCreazione(data.cronologia_nuova);
            }
        } catch (e) {
            console.error("Errore fetch avanza scena:", e);
        }
    }

    // ----------------------------------------------------------------
    // SFX helper + Mute Toggle
    // ----------------------------------------------------------------
    let sfxMuted = localStorage.getItem("indaginiSfxMuted") === "true";

    function updateMuteBtnUI() {
        const btn = document.getElementById("muteSfxBtn");
        if (!btn) return;
        btn.textContent = sfxMuted ? "🔇 SFX Muted" : "🔊 SFX On";
        btn.style.opacity = sfxMuted ? "0.6" : "1";
    }

    // ----------------------------------------------------------------
    // Lista "Da esaminare": la stessa dei giocatori, più le esche da barrare a mano
    // ----------------------------------------------------------------
    const esploraBox = document.getElementById("liveEsplora");
    const esploraLista = document.getElementById("liveEsploraLista");
    const esploraMostra = document.getElementById("liveEsploraMostra");
    let listaMostrata = !!RAW.lista_mostrata;

    function aggiornaListaMostrata(mostrata) {
        if (typeof mostrata !== "boolean" || !esploraBox) return;
        listaMostrata = mostrata;
        esploraBox.classList.toggle("player-esplora--nascosta", !mostrata);
        esploraMostra.textContent = mostrata ? "Visibile · nascondi" : "Nascosta · mostra";
    }

    esploraMostra.addEventListener("click", async () => {
        try {
            const resp = await fetch(window.INDAGINI_LIVE_CONFIG.endpoints.listaEsamina, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mostra: !listaMostrata }),
            });
            if (!resp.ok) { console.error("Errore lista da esaminare"); return; }
            const data = await resp.json();
            aggiornaListaMostrata(data.lista_mostrata);
            aggiornaPuntiInteresse(data.punti_interesse);
        } catch (e) {
            console.error("Errore fetch lista da esaminare:", e);
        }
    });

    function aggiornaPuntiInteresse(voci) {
        if (!voci || !esploraBox) return;
        esploraLista.innerHTML = "";
        voci.forEach(v => {
            const li = document.createElement("li");
            li.className = "player-esplora__voce";
            li.textContent = v.etichetta;
            if (v.esaminato) li.classList.add("player-esplora__voce--esaminata");
            if (v.esca) {
                li.classList.add("player-esplora__voce--esca");
                const tag = document.createElement("span");
                tag.className = "player-esplora__tag";
                tag.textContent = "esca";
                li.appendChild(tag);
                li.title = v.esaminato ? "Esca: clic per rimetterla da esaminare" : "Esca: clic quando l'hanno guardata";
                li.addEventListener("click", () => togglePuntoExtra(v.etichetta));
            } else {
                li.title = "Si barra sbloccando l'indizio";
            }
            esploraLista.appendChild(li);
        });
        esploraBox.hidden = voci.length === 0;
    }

    async function togglePuntoExtra(etichetta) {
        try {
            const resp = await fetch(window.INDAGINI_LIVE_CONFIG.endpoints.puntoExtraEsaminato, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ etichetta }),
            });
            if (!resp.ok) { console.error("Errore esca"); return; }
            aggiornaPuntiInteresse((await resp.json()).punti_interesse);
        } catch (e) {
            console.error("Errore fetch esca:", e);
        }
    }

    // Render iniziale
    aggiornaPuntiInteresse(RAW.punti_interesse);
    aggiornaListaMostrata(listaMostrata);
    renderTutti(null, null, null, null, null);
    aggiornaBottoneAvanza();
    updateMuteBtnUI();

    window.toggleSfxMute = function() {
        sfxMuted = !sfxMuted;
        localStorage.setItem("indaginiSfxMuted", sfxMuted);
        updateMuteBtnUI();
    };

    function riproduciSfx(path) {
        if (sfxMuted) return;
        try {
            const audio = new Audio(path);
            audio.volume = 0.5; // Dimezza il volume di default
            audio.play().catch(e => console.warn("SFX non riproducibile:", e));
        } catch (e) {
            console.warn("SFX non riproducibile:", e);
        }
    }

    // ----------------------------------------------------------------
    // Sipario
    // ----------------------------------------------------------------
    window.toggleSipario = async function() {
        try {
            const resp = await fetch(window.INDAGINI_LIVE_CONFIG.endpoints.sipario, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ azione: "toggle" }),
            });
            if (resp.ok) {
                const data = await resp.json();
                aggiornaBottoneSipario(data.sipario_aperto);
            } else {
                let detail = "";
                try {
                    const data = await resp.json();
                    detail = data.error ? `: ${data.error}` : "";
                } catch (_) {}
                alert("Errore nel toggle del sipario" + detail);
            }
        } catch (e) {
            console.error("Errore fetch sipario:", e);
        }
    };

    let livePollingAttivo = true;
    async function pollLiveState() {
        if (!livePollingAttivo) return;
        try {
            const resp = await fetch(window.INDAGINI_LIVE_CONFIG.endpoints.statoLive);
            if (!resp.ok) return;
            applicaStatoRemoto(await resp.json());
        } catch (e) {
            console.warn("Polling live non riuscito:", e);
        }
    }
    setInterval(pollLiveState, POLL_MS);
    window.addEventListener("beforeunload", function () { livePollingAttivo = false; });
    aggiornaBottoneSipario(siparioAperto);

    // ----------------------------------------------------------------
    // Sblocco AJAX
    // ----------------------------------------------------------------
    async function sbloccaNodo(nodoId) {
        // Feedback visivo immediato: il nodo si attenua prima che la fetch risponda
        const nodoElPre = nodesGroup.querySelector(`[data-id="${nodoId}"]`);
        if (nodoElPre) nodoElPre.style.opacity = '0.35';

        const statiPrecedenti = Object.assign({}, statiCorrente);
        try {
            const resp = await fetch(window.INDAGINI_LIVE_CONFIG.endpoints.sbloccaNodo.replace("__NODO_ID__", nodoId), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ manuale: true }),
            });
            if (!resp.ok) { console.error("Errore sblocco"); return; }
            const data = await resp.json();

            data.nodi.forEach(n => { nodoById[n.id] = n; });
            aggiornaPuntiInteresse(data.punti_interesse);
            const nuoviStati = data.stati;

            const animNew = new Set();
            const animRevealed = new Set();
            const animEdgeSet = new Set();
            const recallIds = new Set();
            let idRivelazioneAnimata = null;

            Object.keys(nuoviStati).forEach(idStr => {
                const id = parseInt(idStr);
                const vecchio = statiPrecedenti[id];
                const nuovo = nuoviStati[id];

                if (vecchio === "ASSENTE" && nuovo !== "ASSENTE") {
                    animNew.add(id);
                } else if (vecchio === "BLOCCATO_VISIBILE" && nuovo === "SCOPERTO") {
                    const nodoSfx = nodoById[id];
                    if (nodoSfx && nodoSfx.tipo_speciale === "rivelazione") {
                        idRivelazioneAnimata = id;
                        riproduciSfx(window.INDAGINI_LIVE_CONFIG.sfx.rivelazione);
                    } else {
                        animRevealed.add(id);
                        if (nodoSfx && nodoSfx.livello_sfx) {
                            riproduciSfx(window.INDAGINI_LIVE_CONFIG.sfx.livelloBase.replace("__LIVELLO__", nodoSfx.livello_sfx));
                        }
                    }
                }

                // Detecta archi che diventano "reali" e nodi richiamati (Add9: entrambe le direzioni)
                if (nuovo === "SCOPERTO" && vecchio !== "SCOPERTO") {
                    COLL.forEach(c => {
                        // Caso A: id è il FIGLIO — il genitore era già SCOPERTO → arco genitore→id
                        if (c.nodo_figlio_id === id) {
                            const parentId = c.nodo_genitore_id;
                            if (statiPrecedenti[parentId] !== "SCOPERTO") return;
                            // Anima solo se il genitore non aveva ancora figli SCOPERTO
                            // (trasformazione freccia ambigua → arco reale)
                            const parenteAvevaScopert = COLL.some(c2 =>
                                c2.nodo_genitore_id === parentId &&
                                statiPrecedenti[c2.nodo_figlio_id] === "SCOPERTO"
                            );
                            if (!parenteAvevaScopert) {
                                animEdgeSet.add(`${parentId}-${id}`);
                                // Nodo richiamato: era sparito (scena vecchia), ora torna
                                const parentNodo = nodoById[parentId];
                                if (parentNodo && scenaNodo(parentNodo) <= scenaCorrente - 2) {
                                    recallIds.add(parentId);
                                }
                            }
                        }
                        // Caso B: id è il GENITORE — il figlio era già SCOPERTO → arco id→figlio
                        // (il figlio era stato scoperto prima del genitore)
                        if (c.nodo_genitore_id === id) {
                            const figlioId = c.nodo_figlio_id;
                            if (statiPrecedenti[figlioId] === "SCOPERTO") {
                                animEdgeSet.add(`${id}-${figlioId}`);
                            }
                        }
                    });
                }
            });

            statiCorrente = {};
            Object.entries(nuoviStati).forEach(([k, v]) => { statiCorrente[parseInt(k)] = v; });

            if (idRivelazioneAnimata !== null) {
                const rivGEl = nodesGroup.querySelector(`[data-id="${idRivelazioneAnimata}"]`);
                const rivPos = g.node(String(idRivelazioneAnimata));
                renderTutti(animNew, animRevealed, new Set([idRivelazioneAnimata]), animEdgeSet, recallIds);
                if (rivGEl && rivPos) {
                    nodesGroup.appendChild(rivGEl);
                    animaRivelazione(rivGEl, rivPos, nodoById[idRivelazioneAnimata]);
                }
            } else {
                renderTutti(animNew, animRevealed, null, animEdgeSet, recallIds);
            }

            if (data.cronologia_nuova) {
                cronologiaId = data.cronologia_nuova.id;
                aggiornaCronologieDopoCreazione(data.cronologia_nuova);
            }
        } catch (e) {
            console.error("Errore fetch sblocco:", e);
        }
    }

    // ----------------------------------------------------------------
    // Aggiorna lista cronologie quando ne viene creata una
    // ----------------------------------------------------------------
    function aggiornaCronologieDopoCreazione(cron) {
        const lista = document.getElementById("cronologieList");
        const vuoto = document.getElementById("cronologieVuote");
        if (vuoto) vuoto.remove();

        const riga = document.createElement("div");
        riga.className = "cronologia-row";
        riga.dataset.id = cron.id;
        riga.innerHTML = `
            <span class="cronologia-nome" title="Clicca per rinominare"
                  onclick="iniziaRinomina(this, ${cron.id})">${escHtml(cron.nome)}</span>
            <span class="tag-attuale">ATTUALE</span>
            <span class="cronologia-data">${cron.creata_il.slice(0, 16).replace('T', ' ')}</span>
            <form method="POST" action="${window.INDAGINI_LIVE_CONFIG.endpoints.cronologiaElimina.replace('__CRONOLOGIA_ID__', cron.id)}"
                  onsubmit="return confirm('Eliminare questa cronologia?');" class="stage-inline-form">
                <button type="submit" class="btn btn--danger btn--micro">✕</button>
            </form>`;
        lista.prepend(riga);
    }

    window.avanzaScena = avanzaScena;

    // ----------------------------------------------------------------
    // Rinomina inline (AJAX)
    // ----------------------------------------------------------------
    window.iniziaRinomina = function(el, cronId) {
        const nomeCorrente = el.textContent.trim();
        const input = document.createElement("input");
        input.type = "text";
        input.className = "cronologia-nome-input";
        input.value = nomeCorrente;
        el.replaceWith(input);
        input.focus();
        input.select();

        async function salva() {
            const nuovoNome = input.value.trim();
            if (!nuovoNome || nuovoNome === nomeCorrente) {
                const span = document.createElement("span");
                span.className = "cronologia-nome";
                span.title = "Clicca per rinominare";
                span.textContent = nomeCorrente;
                span.onclick = () => iniziaRinomina(span, cronId);
                input.replaceWith(span);
                return;
            }
            try {
                const resp = await fetch(window.INDAGINI_LIVE_CONFIG.endpoints.cronologiaRinomina.replace("__CRONOLOGIA_ID__", cronId), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ nome: nuovoNome }),
                });
                const data = await resp.json();
                const span = document.createElement("span");
                span.className = "cronologia-nome";
                span.title = "Clicca per rinominare";
                span.textContent = data.nome || nuovoNome;
                span.onclick = () => iniziaRinomina(span, cronId);
                input.replaceWith(span);
            } catch (e) {
                console.error("Errore rinomina:", e);
                const span = document.createElement("span");
                span.className = "cronologia-nome";
                span.title = "Clicca per rinominare";
                span.textContent = nomeCorrente;
                span.onclick = () => iniziaRinomina(span, cronId);
                input.replaceWith(span);
            }
        }

        input.addEventListener("blur", salva);
        input.addEventListener("keydown", e => {
            if (e.key === "Enter") { e.preventDefault(); input.blur(); }
            if (e.key === "Escape") { input.value = nomeCorrente; input.blur(); }
        });
    };
})();
