/*
 * Lavagna indizi della player view.
 *
 * Quando la scena corrente è marcata "lavagna" (editor → Scene), al centro
 * della player view si srotola una bacheca in cuoio con gli indizi scoperti.
 * Master e giocatrice li spostano e li collegano con un filo rosso
 * (trascinando dallo spillo di una carta a un'altra); solo il master può
 * metterli da parte o rimetterli. Ogni modifica è un'operazione singola che
 * il server applica sullo stato corrente, così due persone possono lavorare
 * insieme; mentre la lavagna è aperta lo stato si rilegge ogni secondo.
 *
 * Stato salvato per cronologia: {posizioni: {id: [x, y]}, rimossi: [id], fili: [[a, b]]}
 * con x, y frazioni 0..1 del centro della carta. Solo le carte spostate a mano
 * hanno una posizione: le altre seguono un layout a griglia deterministico,
 * così master e spettatori vedono la stessa disposizione senza salvataggi.
 */
(function () {
    const SVG_NS = "http://www.w3.org/2000/svg";
    const DURATA_APERTURA = 1500;   // arrivo del rotolo + srotolamento (vedi CSS)
    const DURATA_CHIUSURA = 1350;
    const RITARDO_CARTE = 1250;     // le carte si appuntano a bacheca già aperta
    const PASSO_CARTE = 70;
    const SOGLIA_TRASCINAMENTO = 4;
    const COLONNE = 6;
    const POLL_LAVAGNA_MS = 1000;

    let cfg = null;
    let el = {};
    let fase = "chiusa";            // chiusa | apertura | aperta | chiusura
    let gettone = 0;                // invalida i timer di un'animazione interrotta
    let indizi = [];                // nodi scoperti, ordinati per numero_nodo
    let stato = { posizioni: {}, rimossi: [], fili: [] };
    let versione = 0;
    let cronologia = null;
    const carte = new Map();        // id → elemento carta
    let zTop = 10;

    let trascinamento = null;       // {id, carta, pointerId, dx, dy, mosso}
    let collegamento = null;        // {da, pointerId, linea}
    const coda = [];                // operazioni in attesa di invio
    let opInVolo = false;
    let pollTimer = null;
    let avvisoTimer = null;

    // ------------------------------------------------------------------
    // Utility
    // ------------------------------------------------------------------
    function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }

    function hash(id, mod) { return ((id * 2654435761) >>> 0) % mod; }

    function rotazione(id) { return (hash(id, 9) - 4) * 0.9; }

    function chiaveFilo(a, b) { return a < b ? `${a}-${b}` : `${b}-${a}`; }

    function visibili() {
        const rimossi = new Set(stato.rimossi);
        return indizi.filter(n => !rimossi.has(n.id));
    }

    function statoPulito(lav) {
        return {
            posizioni: Object.assign({}, lav.posizioni || {}),
            rimossi: (lav.rimossi || []).slice(),
            fili: (lav.fili || []).map(f => [f[0], f[1]]),
        };
    }

    // ------------------------------------------------------------------
    // Layout predefinito: griglia a slot, saltando quelli già occupati
    // da carte posizionate a mano. Deterministico per id.
    // ------------------------------------------------------------------
    function layoutPredefinito(elenco) {
        const out = {};
        const occupati = [];
        const liberi = [];
        elenco.forEach(n => {
            const p = stato.posizioni[String(n.id)];
            if (p) occupati.push(p); else liberi.push(n);
        });
        if (!liberi.length) return out;

        // Griglia che occupa tutta la bacheca: poche carte → poche colonne, centrate
        const colonne = Math.min(COLONNE, elenco.length);
        const righe = Math.ceil(elenco.length / colonne);
        const passoX = 1 / colonne;
        const passoY = 0.84 / righe;
        const slot = [];
        for (let r = 0; r < righe; r++) {
            for (let c = 0; c < colonne; c++) {
                slot.push([(c + 0.5) * passoX, 0.08 + (r + 0.5) * passoY]);
            }
        }
        const liberoDa = s => !occupati.some(p =>
            Math.abs(p[0] - s[0]) < passoX * 0.6 && Math.abs(p[1] - s[1]) < passoY * 0.6);

        let i = 0;
        slot.filter(liberoDa).concat(slot).forEach(s => {
            if (i >= liberi.length) return;
            const n = liberi[i++];
            const jx = (hash(n.id, 11) - 5) / 5 * passoX * 0.12;
            const jy = (hash(n.id * 7, 11) - 5) / 5 * passoY * 0.12;
            out[n.id] = [s[0] + jx, s[1] + jy];
        });
        // Più carte che slot: si impilano al centro, sfalsate
        for (; i < liberi.length; i++) {
            out[liberi[i].id] = [0.5 + (i % 5) * 0.02, 0.5 + (i % 5) * 0.02];
        }
        return out;
    }

    // ------------------------------------------------------------------
    // Carte
    // ------------------------------------------------------------------
    function creaCarta(n) {
        const carta = document.createElement("div");
        carta.className = "lavagna-carta";
        carta.dataset.id = n.id;
        carta.style.setProperty("--rot", `${rotazione(n.id)}deg`);

        const spillo = document.createElement("span");
        spillo.className = "lavagna-carta__spillo";
        carta.appendChild(spillo);

        riempiCarta(carta, n);

        spillo.title = "Trascina su un altro indizio per collegarli";
        spillo.addEventListener("pointerdown", e => iniziaCollegamento(e, n.id));

        if (cfg.gestione) {
            const togli = document.createElement("button");
            togli.type = "button";
            togli.className = "lavagna-carta__togli";
            togli.title = "Togli dalla lavagna";
            togli.textContent = "×";
            togli.addEventListener("pointerdown", e => e.stopPropagation());
            togli.addEventListener("click", e => {
                e.stopPropagation();
                togliCarta(n.id);
            });
            carta.appendChild(togli);
        }
        carta.addEventListener("pointerdown", e => iniziaTrascinamento(e, n.id));
        return carta;
    }

    function riempiCarta(carta, n) {
        carta.querySelectorAll(".lavagna-carta__corpo").forEach(x => x.remove());
        const corpo = document.createElement("div");
        corpo.className = "lavagna-carta__corpo";

        const conFoto = !!n.immagine_url;
        carta.classList.toggle("lavagna-carta--foto", conFoto);
        carta.classList.toggle("lavagna-carta--nota", !conFoto);
        carta.classList.toggle("lavagna-carta--rivelazione", n.tipo_speciale === "rivelazione");

        if (conFoto) {
            const img = document.createElement("img");
            img.src = n.immagine_url;
            img.alt = n.titolo || "";
            img.draggable = false;
            img.loading = "lazy";
            img.addEventListener("load", () => disegnaFili());
            corpo.appendChild(img);
        } else {
            const num = document.createElement("p");
            num.className = "lavagna-carta__num";
            num.textContent = `#${n.numero_nodo}`;
            corpo.appendChild(num);
        }
        const titolo = document.createElement("p");
        titolo.className = "lavagna-carta__titolo";
        titolo.textContent = n.titolo || "";
        corpo.appendChild(titolo);
        if (!conFoto && n.descrizione) {
            const desc = document.createElement("p");
            desc.className = "lavagna-carta__desc";
            desc.textContent = n.descrizione;
            corpo.appendChild(desc);
        }
        carta.insertBefore(corpo, carta.firstChild.nextSibling);
        carta.dataset.firma = firmaNodo(n);
    }

    function firmaNodo(n) {
        return JSON.stringify([n.titolo, n.descrizione, n.immagine_url, n.numero_nodo, n.tipo_speciale]);
    }

    function posizionaCarta(carta, p) {
        carta.style.left = `${p[0] * 100}%`;
        carta.style.top = `${p[1] * 100}%`;
    }

    function render(inApertura) {
        const elenco = visibili();
        const predef = layoutPredefinito(elenco);
        const presenti = new Set();
        let nuove = 0;

        elenco.forEach(n => {
            presenti.add(n.id);
            let carta = carte.get(n.id);
            if (!carta) {
                carta = creaCarta(n);
                carte.set(n.id, carta);
                el.carte.appendChild(carta);
                const ritardo = (inApertura ? RITARDO_CARTE : 0) + Math.min(nuove, 20) * PASSO_CARTE;
                carta.style.setProperty("--ritardo", `${ritardo}ms`);
                carta.classList.add("is-entrata");
                carta.addEventListener("animationend", () => carta.classList.remove("is-entrata"), { once: true });
                nuove++;
            } else if (carta.dataset.firma !== firmaNodo(n)) {
                riempiCarta(carta, n);
            }
            if (!trascinamento || trascinamento.id !== n.id) {
                posizionaCarta(carta, stato.posizioni[String(n.id)] || predef[n.id]);
            }
        });
        carte.forEach((carta, id) => {
            if (presenti.has(id)) return;
            carta.remove();
            carte.delete(id);
        });

        el.vuota.hidden = indizi.length > 0;
        renderVassoio();
        disegnaFili();
    }

    // ------------------------------------------------------------------
    // Fili rossi
    // ------------------------------------------------------------------
    function centroSpillo(id) {
        const carta = carte.get(id);
        if (!carta) return null;
        const spillo = carta.querySelector(".lavagna-carta__spillo");
        const r = spillo.getBoundingClientRect();
        const base = el.telo.getBoundingClientRect();
        if (!base.width) return null;
        return [r.left + r.width / 2 - base.left, r.top + r.height / 2 - base.top];
    }

    function tracciato(p1, p2) {
        const dist = Math.hypot(p2[0] - p1[0], p2[1] - p1[1]);
        const cedimento = Math.min(70, dist * 0.14);
        const mx = (p1[0] + p2[0]) / 2;
        const my = (p1[1] + p2[1]) / 2 + cedimento;
        return `M ${p1[0]} ${p1[1]} Q ${mx} ${my} ${p2[0]} ${p2[1]}`;
    }

    let filiDaAnimare = new Set();

    function disegnaFili() {
        if (fase === "chiusa") return;
        const svg = el.fili;
        svg.querySelectorAll(".lavagna-filo").forEach(x => x.remove());
        stato.fili.forEach(([a, b]) => {
            if (!carte.has(a) || !carte.has(b)) return;
            const p1 = centroSpillo(a), p2 = centroSpillo(b);
            if (!p1 || !p2) return;
            const d = tracciato(p1, p2);
            const chiave = chiaveFilo(a, b);

            const g = document.createElementNS(SVG_NS, "g");
            g.classList.add("lavagna-filo");
            if (filiDaAnimare.has(chiave)) g.classList.add("is-nuovo");

            const ombra = document.createElementNS(SVG_NS, "path");
            ombra.setAttribute("d", d);
            ombra.setAttribute("class", "lavagna-filo__ombra");
            ombra.setAttribute("pathLength", "1");
            g.appendChild(ombra);

            const filo = document.createElementNS(SVG_NS, "path");
            filo.setAttribute("d", d);
            filo.setAttribute("class", "lavagna-filo__linea");
            filo.setAttribute("pathLength", "1");
            g.appendChild(filo);

            {
                const presa = document.createElementNS(SVG_NS, "path");
                presa.setAttribute("d", d);
                presa.setAttribute("class", "lavagna-filo__presa");
                const titolo = document.createElementNS(SVG_NS, "title");
                titolo.textContent = "Clicca per tagliare il filo";
                presa.appendChild(titolo);
                presa.addEventListener("click", () => tagliaFilo(a, b));
                g.appendChild(presa);
            }
            svg.insertBefore(g, el.filoTemporaneo);
        });
        filiDaAnimare = new Set();
    }

    // ------------------------------------------------------------------
    // Vassoio: indizi messi da parte (solo master)
    // ------------------------------------------------------------------
    function renderVassoio() {
        if (!el.vassoio) return;
        const byId = new Map(indizi.map(n => [n.id, n]));
        const daParte = stato.rimossi.map(id => byId.get(id)).filter(Boolean);
        el.vassoio.hidden = daParte.length === 0;
        el.vassoioConta.textContent = String(daParte.length);
        el.vassoioLista.innerHTML = "";
        daParte.forEach(n => {
            const b = document.createElement("button");
            b.type = "button";
            b.className = "lavagna-vassoio__indizio";
            b.title = "Rimetti sulla lavagna";
            b.textContent = n.titolo || `#${n.numero_nodo}`;
            b.addEventListener("click", () => rimettiCarta(n.id));
            el.vassoioLista.appendChild(b);
        });
        if (!daParte.length) el.vassoio.classList.remove("is-aperto");
    }

    // ------------------------------------------------------------------
    // Modifiche: applicate subito in locale, poi mandate al server una alla
    // volta. Quando la coda si svuota si adotta lo stato del server, che
    // contiene anche le modifiche fatte nel frattempo dall'altro schermo.
    // ------------------------------------------------------------------
    function mostraAvviso(testo) {
        el.avviso.textContent = testo;
        el.avviso.hidden = false;
        clearTimeout(avvisoTimer);
        avvisoTimer = setTimeout(() => { el.avviso.hidden = true; }, 4000);
    }

    function invia(op) {
        coda.push(op);
        prossimaOp();
    }

    async function prossimaOp() {
        if (opInVolo || !coda.length) return;
        opInVolo = true;
        const op = coda.shift();
        try {
            const resp = await fetch(cfg.endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(op),
            });
            if (resp.status === 403) {
                mostraAvviso("Serve la sessione master per questa modifica");
                versione = -1;
            } else if (resp.status === 409) {
                versione = -1;  // lavagna chiusa nel frattempo: vale lo stato del server
            } else if (!resp.ok) {
                throw new Error(`HTTP ${resp.status}`);
            } else {
                const data = await resp.json();
                if (!coda.length && !trascinamento && !collegamento) {
                    adotta(data);
                    render(false);
                }
            }
        } catch (e) {
            console.warn("Modifica alla lavagna non salvata:", e);
            mostraAvviso("Modifica non salvata");
            versione = -1;  // al prossimo giro si riallinea al server
        } finally {
            opInVolo = false;
            prossimaOp();
        }
    }

    function inattiva() {
        return !trascinamento && !collegamento && !opInVolo && !coda.length;
    }

    function arrotonda(p) { return p.map(v => Math.round(v * 10000) / 10000); }

    // La griglia predefinita dipende da quante carte ci sono: prima di ogni
    // modifica si fissano le posizioni correnti, così togliere o rimettere
    // una carta non fa saltare tutte le altre. Ritorna quelle appena fissate,
    // da mandare al server insieme all'operazione.
    function fissaPosizioni() {
        const fisse = {};
        Object.entries(layoutPredefinito(visibili())).forEach(([id, p]) => {
            fisse[id] = stato.posizioni[id] = arrotonda(p);
        });
        return fisse;
    }

    function togliCarta(id) {
        const posizioni = fissaPosizioni();
        if (!stato.rimossi.includes(id)) stato.rimossi.push(id);
        delete stato.posizioni[String(id)];
        render(false);
        invia({ op: "togli", id, posizioni });
    }

    function rimettiCarta(id) {
        const posizioni = fissaPosizioni();
        stato.rimossi = stato.rimossi.filter(x => x !== id);
        delete stato.posizioni[String(id)];
        render(false);
        invia({ op: "rimetti", id, posizioni });
    }

    function tagliaFilo(a, b) {
        const posizioni = fissaPosizioni();
        const k = chiaveFilo(a, b);
        stato.fili = stato.fili.filter(f => chiaveFilo(f[0], f[1]) !== k);
        disegnaFili();
        invia({ op: "taglia", a, b, posizioni });
    }

    function aggiungiFilo(a, b) {
        if (a === b) return;
        const k = chiaveFilo(a, b);
        if (stato.fili.some(f => chiaveFilo(f[0], f[1]) === k)) return;
        const posizioni = fissaPosizioni();
        stato.fili.push([Math.min(a, b), Math.max(a, b)]);
        filiDaAnimare.add(k);
        disegnaFili();
        invia({ op: "collega", a, b, posizioni });
    }

    // Stato arrivato dal server: i fili nuovi si tendono con l'animazione,
    // le carte spostate altrove scivolano al loro posto (transizione CSS).
    function adotta(lav) {
        const prima = new Set(stato.fili.map(f => chiaveFilo(f[0], f[1])));
        stato = statoPulito(lav);
        versione = lav.versione || 0;
        stato.fili.forEach(f => {
            const k = chiaveFilo(f[0], f[1]);
            if (!prima.has(k)) filiDaAnimare.add(k);
        });
    }

    // Stato letto dal polling: si adotta solo se più nuovo di quello locale e
    // se qui non c'è niente in corso. Ritorna true se va ridisegnato.
    function applicaRemoto(lav) {
        let cambiato = false;
        // Cronologia cambiata (nuova run o un'altra riattivata): le versioni
        // non sono confrontabili, si riparte da quella del server.
        if ((lav.cronologia ?? null) !== cronologia) {
            cronologia = lav.cronologia ?? null;
            versione = -1;
            stato = { posizioni: {}, rimossi: [], fili: [] };
            coda.length = 0;
            cambiato = true;
        }
        if ((lav.versione || 0) > versione && inattiva()) {
            adotta(lav);
            cambiato = true;
        }
        return cambiato;
    }

    let pollInCorso = false;
    async function pollLavagna() {
        if (pollInCorso || fase === "chiusa" || fase === "chiusura") return;
        pollInCorso = true;
        try {
            const resp = await fetch(cfg.endpoint);
            if (!resp.ok) return;
            const lav = await resp.json();
            // La chiusura la decide il polling principale, insieme al cambio scena
            if (lav.attiva && fase !== "chiusa" && applicaRemoto(lav)) render(false);
        } catch (e) {
            console.warn("Polling lavagna:", e);
        } finally {
            pollInCorso = false;
        }
    }

    // --- Trascinamento carta (o click → dettaglio) ---
    function iniziaTrascinamento(e, id) {
        if (e.button !== 0 || fase !== "aperta" || collegamento) return;
        const carta = carte.get(id);
        const r = carta.getBoundingClientRect();
        trascinamento = {
            id, carta, pointerId: e.pointerId, mosso: false,
            x0: e.clientX, y0: e.clientY,
            dx: e.clientX - (r.left + r.width / 2),
            dy: e.clientY - (r.top + r.height / 2),
        };
        carta.setPointerCapture(e.pointerId);
        carta.addEventListener("pointermove", muoviTrascinamento);
        carta.addEventListener("pointerup", fineTrascinamento);
        carta.addEventListener("pointercancel", fineTrascinamento);
        e.preventDefault();
    }

    function muoviTrascinamento(e) {
        const t = trascinamento;
        if (!t || e.pointerId !== t.pointerId) return;
        if (!t.mosso) {
            if (Math.hypot(e.clientX - t.x0, e.clientY - t.y0) < SOGLIA_TRASCINAMENTO) return;
            t.mosso = true;
            t.carta.classList.add("is-trascinata");
            t.carta.style.zIndex = String(++zTop);
        }
        const base = el.carte.getBoundingClientRect();
        const mezzaW = t.carta.offsetWidth / 2, mezzaH = t.carta.offsetHeight / 2;
        const cx = clamp(e.clientX - t.dx - base.left, mezzaW, base.width - mezzaW);
        const cy = clamp(e.clientY - t.dy - base.top, mezzaH, base.height - mezzaH);
        t.pos = [cx / base.width, cy / base.height];
        posizionaCarta(t.carta, t.pos);
        disegnaFili();
    }

    function fineTrascinamento(e) {
        const t = trascinamento;
        if (!t || (e && e.pointerId !== t.pointerId)) return;
        trascinamento = null;
        t.carta.removeEventListener("pointermove", muoviTrascinamento);
        t.carta.removeEventListener("pointerup", fineTrascinamento);
        t.carta.removeEventListener("pointercancel", fineTrascinamento);
        try { t.carta.releasePointerCapture(t.pointerId); } catch (_) { /* già rilasciato */ }
        t.carta.classList.remove("is-trascinata");
        if (t.mosso && t.pos) {
            const posizioni = fissaPosizioni();
            posizioni[String(t.id)] = stato.posizioni[String(t.id)] = arrotonda(t.pos);
            invia({ op: "sposta", posizioni });
        } else if (!t.mosso && e && e.type === "pointerup") {
            const n = indizi.find(x => x.id === t.id);
            if (n && cfg.onApriDettaglio) cfg.onApriDettaglio(n);
        }
    }

    // --- Collegamento: dallo spillo a un'altra carta ---
    function iniziaCollegamento(e, id) {
        if (e.button !== 0 || fase !== "aperta" || trascinamento) return;
        e.stopPropagation();
        e.preventDefault();
        const spillo = e.currentTarget;
        collegamento = { da: id, pointerId: e.pointerId, spillo };
        spillo.setPointerCapture(e.pointerId);
        spillo.addEventListener("pointermove", muoviCollegamento);
        spillo.addEventListener("pointerup", fineCollegamento);
        spillo.addEventListener("pointercancel", fineCollegamento);
        el.telo.classList.add("is-collegamento");
        muoviCollegamento(e);
    }

    function cartaSotto(x, y) {
        const sotto = document.elementFromPoint(x, y);
        const carta = sotto && sotto.closest(".lavagna-carta");
        return carta && el.carte.contains(carta) ? parseInt(carta.dataset.id, 10) : null;
    }

    function muoviCollegamento(e) {
        const c = collegamento;
        if (!c || e.pointerId !== c.pointerId) return;
        const p1 = centroSpillo(c.da);
        const base = el.telo.getBoundingClientRect();
        if (!p1) return;
        const p2 = [e.clientX - base.left, e.clientY - base.top];
        el.filoTemporaneo.setAttribute("d", tracciato(p1, p2));
        el.filoTemporaneo.style.display = "";
        const bersaglio = cartaSotto(e.clientX, e.clientY);
        carte.forEach((carta, id) => carta.classList.toggle("is-bersaglio", id === bersaglio && id !== c.da));
    }

    function fineCollegamento(e) {
        const c = collegamento;
        if (!c || (e && e.pointerId !== c.pointerId)) return;
        collegamento = null;
        c.spillo.removeEventListener("pointermove", muoviCollegamento);
        c.spillo.removeEventListener("pointerup", fineCollegamento);
        c.spillo.removeEventListener("pointercancel", fineCollegamento);
        try { c.spillo.releasePointerCapture(c.pointerId); } catch (_) { /* già rilasciato */ }
        el.filoTemporaneo.style.display = "none";
        el.telo.classList.remove("is-collegamento");
        carte.forEach(carta => carta.classList.remove("is-bersaglio"));
        if (e && e.type === "pointerup") {
            const bersaglio = cartaSotto(e.clientX, e.clientY);
            if (bersaglio !== null) aggiungiFilo(c.da, bersaglio);
        }
    }

    function annullaInterazioni() {
        if (trascinamento) fineTrascinamento(null);
        if (collegamento) fineCollegamento(null);
    }

    // ------------------------------------------------------------------
    // Apertura / chiusura
    // ------------------------------------------------------------------
    function apri() {
        if (fase === "aperta" || fase === "apertura") return false;
        const mio = ++gettone;
        const riapertura = fase === "chiusura";
        fase = "apertura";
        el.radice.hidden = false;
        el.grafo.classList.add("lavagna-aperta");
        if (!riapertura) {
            carte.forEach(carta => carta.remove());
            carte.clear();
        }
        void el.radice.offsetWidth; // forza il reflow: la transizione parte dallo stato chiuso
        el.radice.classList.add("is-visibile", "is-aperta");
        el.radice.setAttribute("aria-hidden", "false");
        setTimeout(() => {
            if (gettone !== mio) return;
            fase = "aperta";
            disegnaFili();
        }, DURATA_APERTURA);
        return !riapertura;
    }

    function chiudi() {
        if (fase === "chiusa" || fase === "chiusura") return;
        annullaInterazioni();
        const mio = ++gettone;
        fase = "chiusura";
        el.radice.classList.remove("is-visibile", "is-aperta");
        el.radice.setAttribute("aria-hidden", "true");
        el.grafo.classList.remove("lavagna-aperta");
        if (el.vassoio) el.vassoio.classList.remove("is-aperto");
        setTimeout(() => {
            if (gettone !== mio) return;
            fase = "chiusa";
            el.radice.hidden = true;
            carte.forEach(carta => carta.remove());
            carte.clear();
            el.fili.querySelectorAll(".lavagna-filo").forEach(x => x.remove());
        }, DURATA_CHIUSURA);
    }

    // ------------------------------------------------------------------
    // API per indagini-player.js
    // ------------------------------------------------------------------
    function aggiorna(lavagna, nodiScoperti) {
        if (!cfg) return;
        if (!lavagna || !lavagna.attiva) {
            chiudi();
            return;
        }
        const nuoviIndizi = nodiScoperti.slice().sort((a, b) => a.numero_nodo - b.numero_nodo);
        // Il polling ricrea gli oggetti nodo a ogni giro: si confronta il contenuto
        let cambiato = nuoviIndizi.length !== indizi.length ||
            nuoviIndizi.some((n, i) => n.id !== indizi[i].id || firmaNodo(n) !== firmaNodo(indizi[i]));
        indizi = nuoviIndizi;

        if (applicaRemoto(lavagna)) cambiato = true;

        const primaApertura = apri();
        if (cambiato || primaApertura) render(primaApertura);
    }

    function init(config) {
        cfg = config;
        el.grafo = document.querySelector(".player-graph");
        el.radice = document.getElementById("lavagna");
        el.telo = document.getElementById("lavagnaTelo");
        el.carte = document.getElementById("lavagnaCarte");
        el.fili = document.getElementById("lavagnaFili");
        el.filoTemporaneo = document.getElementById("lavagnaFiloTemp");
        el.vuota = document.getElementById("lavagnaVuota");
        el.avviso = document.getElementById("lavagnaAvviso");
        el.vassoio = document.getElementById("lavagnaVassoio");
        if (el.vassoio) {
            el.vassoioConta = document.getElementById("lavagnaVassoioConta");
            el.vassoioLista = document.getElementById("lavagnaVassoioLista");
            document.getElementById("lavagnaVassoioApri").addEventListener("click", () => {
                el.vassoio.classList.toggle("is-aperto");
            });
        }
        if (window.ResizeObserver) new ResizeObserver(() => disegnaFili()).observe(el.telo);
        window.addEventListener("keydown", e => {
            if (e.key === "Escape") annullaInterazioni();
        });
        pollTimer = setInterval(pollLavagna, POLL_LAVAGNA_MS);
    }

    window.IndaginiLavagna = { init, aggiorna };
})();
