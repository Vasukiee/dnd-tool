"""
Seed script — Indagine DEMO "Il Manuale dei Casi"
Esegui da Auresis/: python seed_indagine_demo.py

Dimostra TUTTI i comportamenti della vista live:

  Caso 1  — Nodo BLOCCATO_VISIBILE (bottone Sblocca, numero oscurato)
  Caso 2  — Nodo SCOPERTO normale (titolo, descrizione, badge verde automatico)
  Caso 3  — Nodo SCOPERTO con immagine (icona 🖼 in alto a destra)
  Caso 4  — Nodo sbloccato manualmente (badge dorato invece di verde)
  Caso 5  — Freccia ambigua (nodo scoperto senza figli scoperti → freccia grigia)
  Caso 6  — Arco reale singolo (freccia ambigua → arco dagre quando il figlio si sblocca)
  Caso 7  — Arco reale doppio (genitore con due figli scoperti → due archi)
  Caso 8  — Cascata a due livelli (sbloccare A → B visibile → sbloccare B → C visibile)
  Caso 9  — Cross-scena (genitore in scena X, figlio in scena Y > X)
  Caso 10 — Scena senza radici proprie (tutti i nodi sono figli cross-scena → layout virtuale dagre)
  Caso 11 — Nodo richiamato (scena vecchia sparisce, ritorna con animazione quando un figlio è scoperto)
  Caso 12 — Macroriquadro scena corrente (bordo dorato tratteggiato)
  Caso 13 — Macroriquadro scena chiusa (fill scuro, bordo solido, opacity 0.7)
  Caso 14 — Bottone "Avanza →" (compare quando esiste almeno una scena successiva)
  Caso 15 — Scene future invisibili (la scena 4 non si vede finché non si avanza)
  Caso 16 — tipo_speciale='rivelazione' (animazione stella + ghost query con ?)
  Caso 17 — Cronologie (lista in basso, tag ATTUALE, rinomina inline)

Struttura grafo:
  Scena 1 (11-15): cinque radici — sempre BLOCCATO_VISIBILE all'apertura
    11 → foglia, dimostra freccia ambigua permanente
    12 → ha immagine_url, foglia, dimostra icona 🖼 + freccia ambigua
    13 → padre di 21 e 23: dimostra arco reale doppio dopo sblocco
    14 → padre di 31 (cross-scena 1→3): sparisce in scena 3, richiamato quando 31 è scoperto
    15 → padre di 32 (cross-scena 1→3→4): porta alla rivelazione

  Scena 2 (21-23): figli di 13
    21 → figlio di 13; padre di 22 — cascata a due livelli
    22 → figlio di 21 — sblocco di 21 lo porta in BLOCCATO_VISIBILE
    23 → figlio di 13 — secondo figlio, completa l'arco reale doppio di 13

  Scena 3 (31-32): NESSUNA radice propria — tutti figli cross-scena (caso layout virtuale)
    31 → figlio di 14 — dimostra nodo richiamato su 14
    32 → figlio di 15; padre di 41 — bridge verso la rivelazione

  Scena 4 (41): nodo rivelazione
    41 → figlio di 32, tipo_speciale='rivelazione' — animazione stella + ghost query

Percorso per vedere tutto:
  1. Apri la vista live → scena 1 con 5 nodi BLOCCATO_VISIBILE (Caso 1, 14)
  2. Sblocca 11 → SCOPERTO con freccia ambigua (Caso 2, 5)
  3. Sblocca 12 → SCOPERTO con icona 🖼 (Caso 3)
  4. Sblocca 13 → 21 e 23 diventano BLOCCATO_VISIBILE; 13 mostra freccia ambigua (Caso 1, 5)
  5. Sblocca 21 → arco reale 13→21; 22 diventa BLOCCATO_VISIBILE (Caso 6, 1, 8)
  6. Sblocca 23 → arco reale doppio 13→21 e 13→23 (Caso 7)
  7. Sblocca 22 → arco reale 21→22 (Caso 6); 22 ha badge dorato (Caso 4)
  8. Sblocca 14 e 15 → frecce ambigue (Caso 5)
  9. Clicca "Avanza →" → scena 2 chiusa, scena 3 attiva (Caso 12, 13)
     Nota: 14 e 15 spariscono in scena 3 (nodi di scena 1, corrente è 3) (Caso 11 parziale)
  10. Sblocca 31 → 14 ricompare con "da S.1" e animazione slideIn (Caso 11)
  11. Sblocca 32 → 41 diventa BLOCCATO_VISIBILE
  12. Clicca "Avanza →" → scena 4 appare (Caso 15 negativo, scena 4 era invisibile prima)
  13. Sblocca 41 → animazione rivelazione: esplosione → "!" → stella + ghost "?" (Caso 16)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import db

TITOLO_INDAGINE = "DEMO — Il Manuale dei Casi"
DESCRIZIONE_INDAGINE = (
    "Indagine dimostrativa. Ogni nodo mostra un comportamento specifico della vista live: "
    "sblocchi, cascate, frecce ambigue, archi reali, cross-scena, nodi richiamati e rivelazione. "
    "Segui il percorso nei commenti del seed per vedere ogni caso in sequenza."
)

# (numero_nodo, titolo, descrizione, regola_sblocco, tipo_speciale, immagine_url)
NODI = [
    # ── SCENA 1 ─────────────────────────────────────────────────────────────────
    # Cinque radici: BLOCCATO_VISIBILE all'apertura (Caso 1).
    # Sbloccarle una a una dimostra i casi 2–9.

    (11, "Foglia",
     "CASO 5 — Freccia ambigua. Questo nodo non ha figli: una volta scoperto mostra "
     "la freccia grigia orizzontale verso destra invece di un arco reale. La freccia rimane "
     "finché non viene collegato almeno un figlio scoperto.",
     "TUTTI", None, None),

    (12, "Con Immagine",
     "CASO 3 — Icona immagine. Il campo immagine_url è valorizzato: dopo lo sblocco compare "
     "l'icona 🖼 in alto a destra del nodo. Anche questo nodo è foglia: dimostra freccia ambigua "
     "insieme all'icona.",
     "TUTTI", None, "https://picsum.photos/seed/demo/400/300"),

    (13, "Padre di Due Figli",
     "CASO 7 — Arco reale doppio. Questo nodo ha due figli nella scena 2 (nodi 21 e 23). "
     "Sblocca prima 21: la freccia ambigua diventa un arco reale singolo 13→21. "
     "Poi sblocca 23: compare il secondo arco reale 13→23. "
     "CASO 8 — Cascata: sbloccare questo nodo porta 21 e 23 in BLOCCATO_VISIBILE.",
     "TUTTI", None, None),

    (14, "Padre Richiamato",
     "CASO 11 — Nodo richiamato. Questo nodo ha un figlio nella scena 3 (nodo 31). "
     "In scena 3 e 4 (corrente ≥ 3) sparisce dal grafo perché la sua scena (1) è "
     "≤ corrente − 2 e non ha ancora figli scoperti. Sblocca 31: il nodo riappare "
     "con animazione slideIn e l'etichetta 'da S.1' sopra il riquadro.",
     "TUTTI", None, None),

    (15, "Via della Rivelazione",
     "CASO 9 — Cross-scena. Questo nodo è in scena 1 ma il suo figlio (nodo 32) è in scena 3. "
     "Il collegamento attraversa due scene. Sblocca questo nodo per avere la freccia ambigua, "
     "poi avanza alla scena 3 e sblocca 32 per vedere l'arco cross-scena e la catena verso "
     "la rivelazione.",
     "TUTTI", None, None),

    # ── SCENA 2 ─────────────────────────────────────────────────────────────────
    # Tre nodi figli di 13: dimostrano cascata a due livelli e arco reale doppio.
    # BLOCCATO_VISIBILE non appena 13 viene sbloccato.

    (21, "Primo Figlio (Cascata)",
     "CASO 8 — Cascata a due livelli. Diventa BLOCCATO_VISIBILE quando 13 è scoperto (Caso 1). "
     "Sblocca questo nodo: compare l'arco reale 13→21 (Caso 6) e il nodo 22 diventa "
     "BLOCCATO_VISIBILE. Il badge è dorato perché sbloccato manualmente (Caso 4).",
     "TUTTI", None, None),

    (22, "Secondo Livello (Cascata)",
     "CASO 8 — Secondo livello della cascata. Diventa BLOCCATO_VISIBILE solo dopo che il nodo "
     "21 è scoperto. Badge dorato dopo lo sblocco manuale (Caso 4). Nodo foglia: mostra "
     "la freccia ambigua (Caso 5).",
     "TUTTI", None, None),

    (23, "Secondo Figlio (Arco Doppio)",
     "CASO 7 — Secondo figlio di 13. Diventa BLOCCATO_VISIBILE insieme a 21 quando 13 è "
     "scoperto. Sbloccarlo dopo il nodo 21 fa apparire il secondo arco reale 13→23, "
     "completando il pattern 'arco reale doppio'. Nodo foglia: freccia ambigua (Caso 5).",
     "TUTTI", None, None),

    # ── SCENA 3 ─────────────────────────────────────────────────────────────────
    # CASO 10 — Scena senza radici proprie: 31 e 32 sono entrambi figli cross-scena.
    # Il layout dagre usa nodi virtuali per garantire il rank corretto.

    (31, "Cross-Scena da 14",
     "CASO 10 — Questo nodo appartiene alla scena 3 ma il suo genitore (14) è nella scena 1. "
     "La scena 3 non ha radici proprie: dagre usa un nodo virtuale per forzare il rank. "
     "CASO 11 — Sbloccare questo nodo fa tornare visibile il nodo 14 con animazione slideIn "
     "e l'etichetta 'da S.1'. Nodo foglia: freccia ambigua.",
     "TUTTI", None, None),

    (32, "Bridge verso Rivelazione",
     "CASO 9 — Figlio cross-scena di 15 (scena 1), padre di 41 (scena 4). "
     "CASO 10 — Scena 3 senza radici. Sbloccare questo nodo porta 41 (Rivelazione) in "
     "BLOCCATO_VISIBILE nella scena 4. Nodo con freccia ambigua finché 41 non è scoperto.",
     "TUTTI", None, None),

    # ── SCENA 4 ─────────────────────────────────────────────────────────────────
    # CASO 16 — Nodo rivelazione: animazione a tre fasi (esplosione → "!" → stella + ghost "?")

    (41, "RIVELAZIONE",
     "CASO 16 — tipo_speciale='rivelazione'. Finché bloccato appare come nodo normale oscurato. "
     "Cliccando Sblocca: (1) il rettangolo esplode verso l'esterno, (2) compare un '!' gigante, "
     "(3) appare la stella rossa con il titolo e una ghost query '?' collegata da una freccia "
     "tratteggiata. Non ha ulteriori figli: la ghost query rimane.",
     "TUTTI", "rivelazione", None),
]

# (numero_genitore, numero_figlio)
COLLEGAMENTI = [
    (13, 21),   # Cascata: 13 → primo figlio
    (13, 23),   # Arco doppio: 13 → secondo figlio
    (21, 22),   # Cascata 2° livello: 21 → 22
    (14, 31),   # Cross-scena 1→3: padre richiamato
    (15, 32),   # Cross-scena 1→3: bridge rivelazione
    (32, 41),   # Verso rivelazione
]


def main():
    print("Creazione indagine DEMO...")
    ind_id = db.add_indagine(TITOLO_INDAGINE, DESCRIZIONE_INDAGINE, attiva=True)
    print(f"  indagine id={ind_id} — {TITOLO_INDAGINE!r}")

    print("Creazione nodi...")
    numero_to_id = {}
    for numero, titolo, descrizione, regola, tipo, img in NODI:
        nodo_id = db.add_nodo(
            indagine_id=ind_id,
            numero_nodo=numero,
            titolo=titolo,
            descrizione=descrizione,
            regola_sblocco=regola,
            tipo_speciale=tipo,
            immagine_url=img,
        )
        numero_to_id[numero] = nodo_id
        tag = f" [{tipo}]" if tipo else ""
        img_tag = " [IMG]" if img else ""
        print(f"  nodo {numero:>2} id={nodo_id} — {titolo}{tag}{img_tag}")

    print("Creazione collegamenti...")
    for num_genitore, num_figlio in COLLEGAMENTI:
        col_id = db.add_collegamento(
            indagine_id=ind_id,
            nodo_genitore_id=numero_to_id[num_genitore],
            nodo_figlio_id=numero_to_id[num_figlio],
        )
        print(f"  collegamento id={col_id} — {num_genitore} → {num_figlio}")

    print(f"\nFatto. Indagine id={ind_id}, {len(NODI)} nodi, {len(COLLEGAMENTI)} collegamenti.")
    print(f"Aprila in /indagini e segui il percorso nei commenti del seed per vedere ogni caso.")
    print()
    print("Percorso rapido per verificare tutti i casi:")
    print("  1. Sblocca 11 (foglia, freccia ambigua)")
    print("  2. Sblocca 12 (icona immagine + freccia ambigua)")
    print("  3. Sblocca 13 → 21 e 23 in BLOCCATO_VISIBILE")
    print("  4. Sblocca 21 → arco reale 13→21; 22 in BLOCCATO_VISIBILE")
    print("  5. Sblocca 23 → arco reale doppio 13→21 e 13→23")
    print("  6. Sblocca 22 (badge dorato, foglia)")
    print("  7. Sblocca 14 e 15 (frecce ambigue, cross-scena)")
    print("  8. Avanza → scena 2 chiusa (fill scuro), scena 3 attiva")
    print("     → 14 e 15 spariscono (scena 1, corrente=3)")
    print("  9. Sblocca 31 → 14 riappare con 'da S.1' (nodo richiamato)")
    print(" 10. Sblocca 32 → 41 in BLOCCATO_VISIBILE")
    print(" 11. Avanza → scena 4 appare")
    print(" 12. Sblocca 41 → animazione rivelazione (stella + ghost ?)")


if __name__ == "__main__":
    main()
