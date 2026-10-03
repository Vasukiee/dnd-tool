// Orologio di scena: il taschino da funzionario della Curia che compare nella
// player view solo nelle scene che lo prevedono. Una tacca per ogni cosa
// esaminata nella scena; la soglia è un segno di lacca sul quadrante.
// Volutamente muto: niente numeri, niente testo, niente title.
(function () {
    const SVG_NS = "http://www.w3.org/2000/svg";
    // Glifi alieni del quadrante, uno per divisione, in un box ~8x9 centrato.
    // Cinque, come le Forze. [tratti, punti]
    const GLIFI = [
        ["M-3 -3 Q0 -6 3 -3 M0 -3 V2.5 Q0 4.8 -2.6 4", [[2.6, 2.4]]],
        ["M-3 -4 Q3 -2.4 -0.6 0.6 Q-3 3 3 4.2", [[2.6, -3.4]]],
        ["M-3 -4 A3 3 0 0 0 3 -4 M-3 4 A3 3 0 0 1 3 4", [[0, 0]]],
        ["M0 -4.5 A2 2 0 1 0 0 -0.5 A2 2 0 1 1 0 3.5 V4.6", []],
        ["M-3.2 -1.6 Q0 -6 3.2 -1.6 Q0 2.2 -3.2 -1.6 M0 0.8 V4.6", []],
    ];
    const DIVISIONI = GLIFI.length;  // fisse: il quadrante non tradisce la soglia
    const GRADI_TACCA = 360 / DIVISIONI;
    const R_GLIFI = 30;
    const DURATA_SCATTO = 380;

    let seriale = 0;

    function el(tag, attrs, figli) {
        const e = document.createElementNS(SVG_NS, tag);
        Object.entries(attrs || {}).forEach(([k, v]) => e.setAttribute(k, v));
        (figli || []).forEach(f => e.appendChild(f));
        return e;
    }

    function polare(r, gradi) {
        const a = (gradi - 90) * Math.PI / 180;
        return [r * Math.cos(a), r * Math.sin(a)];
    }

    function arco(r, da, a) {
        const [x1, y1] = polare(r, da);
        const [x2, y2] = polare(r, a);
        const grande = (a - da) % 360 > 180 ? 1 : 0;
        return `M${x1.toFixed(2)} ${y1.toFixed(2)} A${r} ${r} 0 ${grande} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
    }

    function costruisciSvg() {
        const id = `orologio${++seriale}`;
        const svg = el("svg", {
            viewBox: "-60 -74 120 136",
            class: "orologio-scena__svg",
            "aria-hidden": "true",
            focusable: "false",
        });

        svg.appendChild(el("defs", {}, [
            el("radialGradient", { id: `${id}-ottone`, cx: "35%", cy: "30%", r: "80%" }, [
                el("stop", { offset: "0%", "stop-color": "#E9CD8A" }),
                el("stop", { offset: "45%", "stop-color": "#B08A45" }),
                el("stop", { offset: "85%", "stop-color": "#6B4F24" }),
                el("stop", { offset: "100%", "stop-color": "#3E2C12" }),
            ]),
            el("radialGradient", { id: `${id}-quadrante`, cx: "45%", cy: "40%", r: "70%" }, [
                el("stop", { offset: "0%", "stop-color": "#E6DCC1" }),
                el("stop", { offset: "70%", "stop-color": "#C9BA93" }),
                el("stop", { offset: "100%", "stop-color": "#8E7C55" }),
            ]),
            el("radialGradient", { id: `${id}-patina`, cx: "50%", cy: "50%", r: "50%" }, [
                el("stop", { offset: "0%", "stop-color": "#4F7A62", "stop-opacity": "0.55" }),
                el("stop", { offset: "100%", "stop-color": "#4F7A62", "stop-opacity": "0" }),
            ]),
            el("linearGradient", { id: `${id}-vetro`, x1: "0", y1: "0", x2: "1", y2: "1" }, [
                el("stop", { offset: "0%", "stop-color": "#FFFFFF", "stop-opacity": "0.32" }),
                el("stop", { offset: "38%", "stop-color": "#FFFFFF", "stop-opacity": "0.04" }),
                el("stop", { offset: "100%", "stop-color": "#FFFFFF", "stop-opacity": "0" }),
            ]),
            el("radialGradient", { id: `${id}-macchia`, cx: "50%", cy: "50%", r: "50%" }, [
                el("stop", { offset: "0%", "stop-color": "#6E5530", "stop-opacity": "0.22" }),
                el("stop", { offset: "100%", "stop-color": "#6E5530", "stop-opacity": "0" }),
            ]),
            el("clipPath", { id: `${id}-clip` }, [el("circle", { r: "44" })]),
        ]));

        // Anello di sospensione e corona zigrinata
        svg.appendChild(el("ellipse", {
            cx: "0", cy: "-65", rx: "9", ry: "7.5", fill: "none",
            stroke: `url(#${id}-ottone)`, "stroke-width": "3",
        }));
        svg.appendChild(el("rect", { x: "-5", y: "-60", width: "10", height: "8", rx: "1.5", fill: `url(#${id}-ottone)` }));
        const zigrino = [];
        for (let x = -3.5; x <= 3.6; x += 1.75) zigrino.push(`M${x} -59.5 V-52.5`);
        svg.appendChild(el("path", { d: zigrino.join(" "), stroke: "#4A3516", "stroke-width": "0.5", opacity: "0.7" }));
        svg.appendChild(el("rect", { x: "-3", y: "-53", width: "6", height: "3", fill: "#5C431D" }));

        // Cassa, con un po' di patina verderame e un'ammaccatura
        svg.appendChild(el("circle", { r: "52", fill: `url(#${id}-ottone)`, stroke: "#2E200C", "stroke-width": "0.8" }));
        svg.appendChild(el("circle", { cx: "-34", cy: "30", r: "11", fill: `url(#${id}-patina)` }));
        svg.appendChild(el("circle", { cx: "38", cy: "-24", r: "7", fill: `url(#${id}-patina)` }));
        svg.appendChild(el("path", { d: arco(50, 120, 136), stroke: "#2E200C", "stroke-width": "0.8", fill: "none", opacity: "0.55" }));
        svg.appendChild(el("circle", { r: "47.2", fill: "none", stroke: "#3E2C12", "stroke-width": "1.6" }));
        svg.appendChild(el("circle", { r: "46", fill: "none", stroke: "#D9BC78", "stroke-width": "0.5", opacity: "0.6" }));

        // Quadrante
        const quadrante = el("g", { "clip-path": `url(#${id}-clip)` });
        quadrante.appendChild(el("circle", { r: "44", fill: `url(#${id}-quadrante)` }));
        quadrante.appendChild(el("circle", { r: "44", fill: "#2A1E0E", class: "orologio-scena__ombra" }));
        quadrante.appendChild(el("ellipse", { cx: "15", cy: "19", rx: "12", ry: "8", fill: `url(#${id}-macchia)`, transform: "rotate(-30 15 19)" }));
        quadrante.appendChild(el("ellipse", { cx: "-24", cy: "-20", rx: "6", ry: "4", fill: `url(#${id}-macchia)` }));
        svg.appendChild(quadrante);

        // Pista esterna: divisioni e puntini intermedi
        const pista = [];
        for (let i = 0; i < DIVISIONI; i++) {
            const g = i * GRADI_TACCA;
            const [x1, y1] = polare(41.5, g);
            const [x2, y2] = polare(37.5, g);
            pista.push(`M${x1.toFixed(2)} ${y1.toFixed(2)} L${x2.toFixed(2)} ${y2.toFixed(2)}`);
        }
        svg.appendChild(el("circle", { r: "41.5", fill: "none", stroke: "#3A2C18", "stroke-width": "0.5" }));
        svg.appendChild(el("circle", { r: "39.3", fill: "none", stroke: "#3A2C18", "stroke-width": "0.3", opacity: "0.6" }));
        svg.appendChild(el("path", { d: pista.join(" "), stroke: "#2A1F12", "stroke-width": "1.1" }));
        const puntini = el("g", { fill: "#3A2C18" });
        for (let i = 0; i < DIVISIONI * 6; i++) {
            if (i % 6 === 0) continue;
            const [x, y] = polare(40.4, i * GRADI_TACCA / 6);
            puntini.appendChild(el("circle", { cx: x.toFixed(2), cy: y.toFixed(2), r: "0.35" }));
        }
        svg.appendChild(puntini);

        // Arco "oltre": dal segno alla lancetta, solo quando si è passata la soglia
        const oltre = el("path", { class: "orologio-scena__oltre", fill: "none", d: "" });
        svg.appendChild(oltre);

        // Glifi
        const glifi = el("g", {
            fill: "none", stroke: "#2A1F12", "stroke-width": "0.85",
            "stroke-linecap": "round", "stroke-linejoin": "round",
        });
        GLIFI.forEach(([d, punti], i) => {
            const [x, y] = polare(R_GLIFI, i * GRADI_TACCA);
            const g = el("g", { transform: `translate(${x.toFixed(2)} ${y.toFixed(2)}) scale(1.15)` });
            g.appendChild(el("path", { d }));
            punti.forEach(([px, py]) => g.appendChild(el("circle", { cx: px, cy: py, r: "0.7", fill: "#2A1F12", stroke: "none" })));
            glifi.appendChild(g);
        });
        svg.appendChild(glifi);

        // Segno della soglia: un cuneo di lacca rossa sulla pista
        const segno = el("path", { class: "orologio-scena__segno", d: "M0 -44 L-2.6 -38.6 L2.6 -38.6 Z" });
        svg.appendChild(segno);

        // Lancette Breguet in acciaio brunito
        const corta = el("g", { class: "orologio-scena__lancetta" }, [
            el("path", { d: "M-1.5 5 L-0.9 -11.5 L0.9 -11.5 L1.5 5 Z" }),
            el("path", { d: "M0 -21.5 C3.6 -17.8 3.4 -13.8 0 -11 C-3.4 -13.8 -3.6 -17.8 0 -21.5 Z" }),
        ]);
        const lunga = el("g", { class: "orologio-scena__lancetta" }, [
            el("circle", { cy: "8.5", r: "2.4" }),
            el("path", { d: "M-1.1 8 L-0.65 -25 L0.65 -25 L1.1 8 Z" }),
            el("circle", { cy: "-28", r: "3", fill: "none", "stroke-width": "1.2", class: "orologio-scena__luna" }),
            el("path", { d: "M-0.75 -30.8 L0 -39.5 L0.75 -30.8 Z" }),
        ]);
        svg.appendChild(corta);
        svg.appendChild(lunga);
        svg.appendChild(el("circle", { r: "2.6", fill: `url(#${id}-ottone)`, stroke: "#2E200C", "stroke-width": "0.4" }));
        svg.appendChild(el("circle", { r: "0.8", fill: "#2E200C" }));

        // Vetro: riflesso, graffi e la crepa che compare oltre la soglia
        const vetro = el("g", { "clip-path": `url(#${id}-clip)`, "pointer-events": "none" });
        vetro.appendChild(el("path", { d: "M-44 -6 A44 44 0 0 1 6 -44 L6 -30 A30 30 0 0 0 -30 -6 Z", fill: `url(#${id}-vetro)` }));
        vetro.appendChild(el("path", {
            d: "M-20 26 L-6 31 M12 -36 L22 -31 M-36 -10 L-33 2 M18 22 L30 14",
            stroke: "#FFFFFF", "stroke-width": "0.3", opacity: "0.22",
        }));
        vetro.appendChild(el("path", {
            class: "orologio-scena__crepa",
            d: "M44 -14 L31 -10 L26 -2 L17 1 L12 9 M31 -10 L28 -19 M26 -2 L30 6 M17 1 L15 -6",
        }));
        svg.appendChild(vetro);

        return { svg, segno, oltre, corta, lunga };
    }

    // opzioni.suSirena(): chiamata quando, durante la scena, le tacche passano
    // la soglia e il server dice che lì suona la sirena.
    function crea(contenitore, opzioni) {
        opzioni = opzioni || {};
        const parti = costruisciSvg();
        contenitore.appendChild(parti.svg);
        const ridotto = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        let mostrato = false;
        let scena = null;
        let tacche = 0;
        let soglia = null;
        let angoloLunga = 0;
        let animazione = null;

        function posa(angolo) {
            angoloLunga = angolo;
            parti.lunga.setAttribute("transform", `rotate(${angolo.toFixed(2)})`);
            // La corta fa un dodicesimo del giro della lunga, partendo da un'ora qualunque
            parti.corta.setAttribute("transform", `rotate(${(296 + angolo / DIVISIONI).toFixed(2)})`);
        }

        function scatta(verso) {
            cancelAnimationFrame(animazione);
            const da = angoloLunga;
            if (ridotto) { posa(verso); return; }
            const inizio = performance.now();
            // Ritorno elastico corto: lo scatto di uno scappamento
            const ease = t => 1 + 2.4 * Math.pow(t - 1, 3) + 1.4 * Math.pow(t - 1, 2);
            function passo(ora) {
                const t = Math.min(1, (ora - inizio) / DURATA_SCATTO);
                posa(da + (verso - da) * ease(t));
                if (t < 1) animazione = requestAnimationFrame(passo);
            }
            animazione = requestAnimationFrame(passo);
            contenitore.classList.remove("is-scatto");
            void contenitore.offsetWidth;
            contenitore.classList.add("is-scatto");
        }

        function disegnaSoglia() {
            const haSoglia = Number.isInteger(soglia) && soglia > 0;
            parti.segno.style.display = haSoglia ? "" : "none";
            if (haSoglia) parti.segno.setAttribute("transform", `rotate(${soglia * GRADI_TACCA})`);
            const oltre = haSoglia && tacche > soglia;
            contenitore.classList.toggle("is-oltre", oltre);
            parti.oltre.setAttribute("d", oltre
                ? arco(39.3, soglia * GRADI_TACCA, Math.min(tacche * GRADI_TACCA, soglia * GRADI_TACCA + 359))
                : "");
        }

        return {
            aggiorna(stato, nuovaScena) {
                if (!stato) {
                    if (mostrato) contenitore.hidden = true;
                    mostrato = false;
                    return;
                }
                const nuoveTacche = Math.max(0, stato.tacche | 0);
                const entrata = !mostrato || nuovaScena !== scena;
                const cambiate = nuoveTacche !== tacche;
                const superata = !entrata && Number.isInteger(stato.soglia) && stato.soglia > 0 &&
                    tacche <= stato.soglia && nuoveTacche > stato.soglia;
                scena = nuovaScena;
                tacche = nuoveTacche;
                soglia = stato.soglia;
                if (entrata) {
                    cancelAnimationFrame(animazione);
                    posa(tacche * GRADI_TACCA);
                    contenitore.hidden = false;
                    contenitore.classList.remove("is-entrata");
                    void contenitore.offsetWidth;
                    contenitore.classList.add("is-entrata");
                } else if (cambiate) {
                    scatta(tacche * GRADI_TACCA);
                }
                if (superata && stato.sirena && opzioni.suSirena) opzioni.suSirena();
                mostrato = true;
                disegnaSoglia();
            },
        };
    }

    // Alba: il tempo della partita. Nessun oggetto in scena, solo la luce
    // dello sfondo che sale dall'alba fredda al sole alto (--luce da 0 a 1 sul
    // contenitore). Non dipende dalla scena: cambiando scena la luce resta.
    // opzioni.suPasso(): chiamata a ogni tacca in più, se il server dice che
    // suona la sirena.
    function creaLuce(contenitore, opzioni) {
        opzioni = opzioni || {};
        let passi = null; // null: alba spenta

        return {
            aggiorna(stato) {
                if (stato === undefined) return;
                if (!stato) {
                    contenitore.classList.remove("tempo-attivo");
                    passi = null;
                    return;
                }
                const nuoviPassi = Math.max(0, stato.passi | 0);
                const luce = Math.min(1, Math.max(0, Number(stato.luce) || 0));
                if (passi === null) {
                    // Accesa ora (o pagina appena caricata): la luce è già
                    // quella giusta, niente lunga alba da rivedere
                    contenitore.classList.add("tempo-senza-transizione");
                    contenitore.style.setProperty("--luce", luce);
                    contenitore.classList.add("tempo-attivo");
                    void contenitore.offsetWidth;
                    contenitore.classList.remove("tempo-senza-transizione");
                } else {
                    contenitore.style.setProperty("--luce", luce);
                    if (nuoviPassi > passi && stato.sirena && opzioni.suPasso) opzioni.suPasso();
                }
                passi = nuoviPassi;
            },
        };
    }

    window.IndaginiOrologio = { crea, creaLuce };
})();
