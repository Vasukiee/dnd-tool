"""
Seed script — Indagine "Mani che non sono sue" (Sessione 2)
Esegui da Auresis/: python seed_indagine_s2.py

Crea 17 nodi e 6 collegamenti derivati da copioni/sessione_02.md.
Struttura grafo:
  Scena 1 (11-14): radici, sempre visibili
  Scena 2 (21-24): radici, sempre visibili
  Scena 3 (31-34): 31 e 32 figli di 23; 33 e 34 figli di 32
  Scena 4 (41-44): 41, 42, 44 radici (GM sblocca manualmente al terzo corpo);
                   43 figlio di 33
  Scena 5 (51):   figlio di 43, tipo_speciale='rivelazione'

Cascade: sbloccare 23 → 31, 32 → 33, 34 → 43 → 51 (animazione rivelazione).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import db

TITOLO_INDAGINE = "Mani che non sono sue"
DESCRIZIONE_INDAGINE = (
    "Tre vittime nella Città Bassa, tutte collegate a una donna scomparsa. "
    "Le impronte appartengono a un uomo già sepolto. Qualcuno usa le mani dei morti."
)

NODI = [
    # numero, titolo, descrizione, regola_sblocco, tipo_speciale
    (11, "Il Corpo",
     "Cadavere di un Cotto in un vicolo della Città Bassa. Torace con crepa asimmetrica — forza "
     "eccessiva e mal calibrata. Impronte sul collo con trama quasi vetrosa, innaturalmente "
     "regolare: rilevate su carta trattata, affidate a un contatto per confronto. Il risultato "
     "richiederà giorni.",
     "TUTTI", None),

    (12, "Il Vicolo",
     "Una tenda smossa a una finestra del primo piano. Sora Calce, Cotta anziana, ha visto "
     "qualcosa: verso il cambio turno, un tonfo sordo e poi una voce d'uomo bassa che ripeteva "
     "qualcosa tra sé. Nessun volto, nessun nome.",
     "TUTTI", None),

    (13, "La Vittima",
     "Nessun profilo di rischio: turni in fonderia minore, nessun debito vistoso, nessun nemico "
     "noto. Tessera turni, poche monete di rame, un pezzo di pane. Scelta per dove e quando si "
     "trovava, non per chi era.",
     "TUTTI", None),

    (14, "Chi l'ha chiamata",
     "Biglietto anonimo su carta oleata di scarto, grafia incerta a matita di carbone. La Curia "
     "non si è presentata né lo farà: un omicidio nella Città Bassa senza vittime di rango non "
     "muove risorse ufficiali. Qualcuno ha chiamato una Cercatrice perché è l'unica giustizia "
     "disponibile.",
     "TUTTI", None),

    (21, "La Baracca",
     "Porta non chiusa a chiave. Una lettera mai spedita, indirizzata a un fratello o vecchio "
     "amico: si scusa per la moneta non mandata, parla di turni più lunghi e di una stanchezza "
     "che non passa. Nessun indizio investigativo — il ritratto onesto di una vita già stremata.",
     "TUTTI", None),

    (22, "La Fonderia",
     "Il caposquadra: puntuale, nessun nemico, 'non lo conosceva nessuno abbastanza da odiarlo'. "
     "Un operaio rivela sottovoce che la vittima voleva risparmiare per un reliquiario decente — "
     "non per sé, per qualcun altro. Sogno irraggiungibile con quei salari. Nessun indizio "
     "concreto.",
     "TUTTI", None),

    (23, "L'Osteria",
     "Il barista: beveva poco, parlava ancora meno. Un avventore anziano, non sollecitato, "
     "rivela che due mesi prima è morta un'altra persona — una donna, stessa storia: nessuna "
     "ferita normale, nessuna spiegazione, la Curia assente. Primo indizio di un pattern.",
     "TUTTI", None),

    (24, "Il Parente / Vicino",
     "Una vicina anziana da anni: 'un'anima buona, mai un guaio'. Commenta con amarezza il "
     "destino dei corpi dei poveri: fusi anonimi nelle Fonderie Nere, senza reliquiari, "
     "come se non fossero mai esistiti. Tema di classe, nessun indizio concreto.",
     "TUTTI", None),

    (31, "Il Corpo (Scena 3)",
     "Donna, seconda vittima: entrambe le gambe amputate appena sotto il bacino. Il taglio è "
     "netto, quasi misurato, angolazione ripetuta identica su entrambi i lati — precisione nel "
     "prelievo, totale indifferenza per la sopravvivenza. Contrasto netto con la violenza grezza "
     "del primo omicidio.",
     "TUTTI", None),

    (32, "Il Coroner — Bigetto",
     "Bigetto archivia con 'animali'. Se pressato, ammette di scrivere quello che gli conviene: "
     "'animali' chiude il caso senza ispezioni. Si lascia convincere facilmente — moneta, "
     "pressione, o far notare che un caso mal chiuso potrebbe riaprirsi peggio. Da lui passa "
     "l'accesso ai documenti d'archivio.",
     "TUTTI", None),

    (33, "I Documenti d'Archivio",
     "Accessibile solo con la collaborazione di Bigetto. In una richiesta di sepoltura condivisa "
     "emergono due nomi: la vittima e una donna senza indirizzo registrato. La data precede di "
     "poco la morte. Primo nome concreto collegato all'indagine.",
     "TUTTI", None),

    (34, "Perché nessuno l'ha reclamata",
     "Bigetto: 'Aspetto qualche mese, poi va alle Fonderie Nere con gli altri scarti. Gente "
     "sola, o famiglia senza moneta per il trasporto.' Rinforza il tema di classe e aggiunge "
     "urgenza: il tempo per dare dignità a questa vittima sta scadendo.",
     "TUTTI", None),

    (41, "Il Corpo e la Ferita",
     "Terza vittima: ampia porzione di pelle rimossa dal busto. Bordo netto, quasi sigillato — "
     "movimento unico e controllato, non strappata né tagliata a colpi. Area mancante quasi "
     "rettangolare e regolare: chi l'ha presa sapeva esattamente quanta superficie gli servisse.",
     "TUTTI", None),

    (42, "L'Ambiente",
     "Nessun segno di lotta. Traccia di passi nella polvere di basalto: andatura irregolare, a "
     "tratti normale, a tratti quasi strascicata — come di chi cammina senza essere presente a "
     "se stesso. Le tracce si perdono su terreno più duro.",
     "TUTTI", None),

    (43, "L'Identità della Vittima",
     "Lavorava come assistente in un piccolo dispensario di quartiere. Conosceva la donna del "
     "nome trovato nell'archivio — terzo punto del pattern. Un vicino riferisce la diceria: "
     "quella donna era malata, stigmatizzata, aveva detto 'parole di vendetta'. La teoria della "
     "moglie colpevole si cristallizza qui, costruita sullo stigma più che sui fatti.",
     "TUTTI", None),

    (44, "Come è stata trovata",
     "Trovata da un operaio che percorre quella strada ogni mattina. Non nascosta né coperta — "
     "esposta, come se chi l'ha lasciata lì non avesse fretta né paura di essere scoperto. Il "
     "testimone non ha visto né sentito nulla: pura indifferenza del killer verso il rischio.",
     "TUTTI", None),

    (51, "La Rivelazione",
     "Le impronte rilevate in Scena 1 appartengono a un uomo già sepolto da mesi prima del "
     "primo omicidio. Qualcuno usa le mani dei morti. La teoria della moglie crolla: non è lei. "
     "L'indagine è da ricominciare da zero.",
     "TUTTI", "rivelazione"),
]

# (etichetta_genitore, etichetta_figlio)
# etichetta = numero_nodo per riferimento interno
COLLEGAMENTI = [
    (23, 31),   # Osteria → corpo seconda vittima
    (23, 32),   # Osteria → Coroner
    (32, 33),   # Coroner → Documenti d'archivio
    (32, 34),   # Coroner → perché nessuno l'ha reclamata
    (33, 43),   # Documenti (nome) → Identità terza vittima
    (43, 51),   # Identità → Rivelazione (trigger animazione)
]


def main():
    print("Creazione indagine...")
    ind_id = db.add_indagine(TITOLO_INDAGINE, DESCRIZIONE_INDAGINE, attiva=True)
    print(f"  indagine id={ind_id} — {TITOLO_INDAGINE!r}")

    print("Creazione nodi...")
    numero_to_id = {}
    for numero, titolo, descrizione, regola, tipo in NODI:
        nodo_id = db.add_nodo(
            indagine_id=ind_id,
            numero_nodo=numero,
            titolo=titolo,
            descrizione=descrizione,
            regola_sblocco=regola,
            tipo_speciale=tipo,
        )
        numero_to_id[numero] = nodo_id
        tag = f" [{tipo}]" if tipo else ""
        print(f"  nodo {numero:>2} id={nodo_id} — {titolo}{tag}")

    print("Creazione collegamenti...")
    for num_genitore, num_figlio in COLLEGAMENTI:
        col_id = db.add_collegamento(
            indagine_id=ind_id,
            nodo_genitore_id=numero_to_id[num_genitore],
            nodo_figlio_id=numero_to_id[num_figlio],
        )
        print(f"  collegamento id={col_id} — {num_genitore} → {num_figlio}")

    print(f"\nFatto. Indagine id={ind_id}, 17 nodi, 6 collegamenti.")
    print("Aprila in /indagini per verificare la mappa.")


if __name__ == "__main__":
    main()
