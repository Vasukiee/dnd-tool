"""
popola_iniziale.py - Popola il database con i dati di apertura della campagna.

Lancia con: python3 popola_iniziale.py

Crea: 2 fazioni, 3 location (isole), alcuni NPC chiave legati all'incipit
(il crollo in miniera a Calderaviva), la quest di apertura, e lo stato
iniziale del PG. Pensato per essere lanciato UNA VOLTA su un database vuoto.
Se lo rilanci su dati esistenti, gli upsert aggiorneranno le voci con lo
stesso nome invece di duplicarle.

NOTA: nessuna fazione è "buona" o "cattiva" - sono coalizioni di interessi
individuali divergenti, non blocchi morali coerenti. Vedi Bible del Pianeta,
sezione 6, e Regole di Risoluzione, Parte 6.
"""

import db


def main():
    print("Popolamento dati di apertura della campagna...")

    # ============================================================
    # FAZIONI
    # ============================================================
    db.upsert_fazione(
        "Curia Aurea",
        nome_popolare="Gli Aurei",
        ideologia="Ufficialmente: la capacita di sopportare l'oro e segno di superiorita "
                  "naturale. In realta una coalizione di interessi divergenti - alcuni "
                  "credono sinceramente di proteggere l'economia dell'arcipelago, altri "
                  "proteggono solo se stessi, altri usano il potere per vantaggio personale. "
                  "Nessuna linea ufficiale e del tutto vera o del tutto falsa.",
        territorio="Ossidiana Alta, con presidi su quasi ogni isola estrattrice",
        relazione_pg="neutrale",
        stato_attuale="Gestisce l'estrazione e la lavorazione dell'oro su scala arcipelagica; "
                      "a Calderaviva controlla la miniera principale tramite un Sovrintendente locale.",
        attiva=1,
    )

    db.upsert_fazione(
        "Collettivo della Brace",
        nome_popolare="I Brace",
        ideologia="Mutuo soccorso, rifiuto dello status legato all'oro, sospetti (non provati) "
                  "su cosa accada ai resti dei minatori morti di AC. La solidarieta che "
                  "professano non e incondizionata: chi vi appartiene ha comunque una "
                  "famiglia da proteggere e un salario da non perdere, e spesso il sostegno "
                  "sincero nell'emergenza non sopravvive quando la causa richiede un rischio "
                  "prolungato.",
        territorio="Diffuso tra Calderaviva e Bassa Marea, cellule informali",
        relazione_pg="neutrale",
        stato_attuale="Attivi nell'organizzare mutuo soccorso dopo gli incidenti in miniera; "
                      "diffidenti verso chiunque non sia gia un volto conosciuto.",
        attiva=1,
    )

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM fazioni WHERE nome = 'Curia Aurea'")
    fazione_curia_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM fazioni WHERE nome = 'Collettivo della Brace'")
    fazione_brace_id = cur.fetchone()[0]
    cur.close()
    conn.close()

    # ============================================================
    # LOCATIONS (isole)
    # ============================================================
    db.upsert_location(
        "Calderaviva",
        tipo="isola/citta mineraria",
        descrizione_breve="Isola vulcanica ancora attiva. Qui si trova la miniera principale "
                          "dell'arcipelago e una fucina di medie dimensioni. L'aria odora "
                          "costantemente di zolfo e polvere di silice. Il PG vive e lavora qui.",
        fazione_controllante_id=fazione_curia_id,
        stato_attuale="Nelle ultime ore: un crollo nella galleria principale della miniera, causa non ancora chiara.",
    )

    db.upsert_location(
        "Ossidiana Alta",
        tipo="isola/citta fortezza",
        descrizione_breve="Sede del potere centrale della Curia Aurea. Costruita su un vulcano "
                          "spento da generazioni, riscaldato artificialmente con il calore "
                          "convogliato dalle isole vicine. Architettura ricca, ordinata, fredda "
                          "nei modi anche quando l'aria e calda.",
        fazione_controllante_id=fazione_curia_id,
    )

    db.upsert_location(
        "Bassa Marea",
        tipo="isola/villaggio periferico",
        descrizione_breve="Isola povera e periferica, ai margini delle rotte commerciali "
                          "principali. Il vulcano locale e debole e instabile, la vita e dura. "
                          "I Collettivi qui operano con meno controllo dall'alto.",
        fazione_controllante_id=fazione_brace_id,
    )

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM locations WHERE nome = 'Calderaviva'")
    loc_calderaviva_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM locations WHERE nome = 'Ossidiana Alta'")
    loc_ossidiana_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM locations WHERE nome = 'Bassa Marea'")
    loc_bassamarea_id = cur.fetchone()[0]
    cur.close()
    conn.close()

    # ============================================================
    # NPC
    # ============================================================

    db.upsert_npc(
        "Tessa Bruciaterra",
        ruolo="minatrice, persona cara al PG",
        fazione_id=None,
        location_attuale_id=loc_calderaviva_id,
        stato="vivo",
        relazione_pg="persona cara - collega di lunga data, quasi famiglia",
        descrizione_breve="Minatrice esperta, ha insegnato al PG i rudimenti del lavoro anni fa. "
                          "Gravemente ferita nel crollo della galleria principale.",
        note_caratteriali="Diretta, poco incline a lamentarsi anche quando dovrebbe. "
                          "Non si fida facilmente della Curia, ma non ne parla apertamente.",
        livello_contaminazione=2,
        ultima_apparizione_sessione=1,
    )

    db.upsert_npc(
        "Sovrintendente Voll",
        ruolo="sovrintendente della miniera, antagonista minore",
        fazione_id=fazione_curia_id,
        location_attuale_id=loc_calderaviva_id,
        stato="vivo",
        relazione_pg="sconosciuto; le sue risposte saranno parzialmente vere, mai una confessione completa",
        descrizione_breve="Gestisce la miniera di Calderaviva per conto della Curia. Monocolo "
                          "intessuto d'oro, gia ai primi stadi visibili di Auris Cancer che "
                          "nasconde con cura. Le ispezioni di sicurezza che ha autorizzato negli "
                          "ultimi mesi erano reali sulla carta, ma sottofinanziate - una scelta "
                          "presa piu in alto di lui, che lui ha eseguito senza opporsi con convinzione.",
        note_caratteriali="Parla per numeri e quote di produzione anche quando si discute di "
                          "vite umane - ma non e sadico, e non sta mentendo quando dice di aver "
                          "fatto cio che gli e stato permesso di fare. Sinceramente convinto che "
                          "fermare l'estrazione per eccesso di cautela avrebbe affamato piu "
                          "famiglie di quante il rischio strutturale ne abbia mai minacciate. "
                          "Potrebbe avere ragione, in parte. Questo non lo rende innocente.",
        livello_contaminazione=3,
        ultima_apparizione_sessione=1,
    )

    db.upsert_npc(
        "Dario Cenere",
        ruolo="caposquadra, contatto dei Collettivi",
        fazione_id=fazione_brace_id,
        location_attuale_id=loc_calderaviva_id,
        stato="vivo",
        relazione_pg="ha aiutato con sincerita nei soccorsi; si tirera indietro se l'indagine diventa rischiosa",
        descrizione_breve="Ex minatore, ora caposquadra informale del Collettivo della Brace a "
                          "Calderaviva. E stato tra i primi a scavare a mani nude per tirare fuori "
                          "i sopravvissuti, incluso, probabilmente, Tessa. Ha una moglie e due "
                          "figli piccoli a Calderaviva.",
        note_caratteriali="Parla poco e con calma anche nel caos - nell'emergenza e stato una "
                          "roccia vera, non finta. Ma quando l'indagine inizia a puntare verso "
                          "la Curia in modo concreto, diventa evasivo: non vuole perdere il "
                          "lavoro, non vuole che la sua famiglia paghi il prezzo di una sua presa "
                          "di posizione. Non e un bugiardo: e qualcuno che ha gia dato quello che "
                          "poteva dare, e ora ha paura.",
        livello_contaminazione=1,
        ultima_apparizione_sessione=1,
    )

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM npc WHERE nome = 'Tessa Bruciaterra'")
    npc_tessa_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM npc WHERE nome = 'Sovrintendente Voll'")
    npc_voll_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM npc WHERE nome = 'Dario Cenere'")
    npc_dario_id = cur.fetchone()[0]
    cur.close()
    conn.close()

    # ============================================================
    # QUEST DI APERTURA
    # ============================================================
    quest_id = db.upsert_quest(
        "Il crollo della galleria nove",
        tipo="main",
        stato="attiva",
        location_id=loc_calderaviva_id,
        riassunto="Un crollo improvviso nella galleria principale della miniera di Calderaviva "
                  "ha ferito gravemente Tessa Bruciaterra e altri minatori. La causa non e ancora "
                  "chiara: alcuni sussurrano di negligenza della Curia nelle ispezioni strutturali, "
                  "altri di un cedimento naturale del terreno vulcanico, altri ancora insinuano che "
                  "qualcuno tra i Collettivi conoscesse il rischio e non l'abbia segnalato per paura "
                  "di ritorsioni. Nessuna di queste versioni e ancora confermata.",
        obiettivo_attuale="Scoprire cosa e davvero successo nella galleria nove - sapendo che ogni "
                          "fonte avra una versione parziale, filtrata dal proprio interesse.",
        sessione_inizio=1,
    )

    db.link_npc_quest(quest_id, npc_tessa_id, ruolo_nella_quest="vittima/motivazione")
    db.link_npc_quest(quest_id, npc_voll_id, ruolo_nella_quest="fonte parziale/possibile responsabile")
    db.link_npc_quest(quest_id, npc_dario_id, ruolo_nella_quest="alleato nei soccorsi, limiti propri")

    # ============================================================
    # EVENTO DI APERTURA (sessione 1, pre-gioco - il crollo stesso)
    # ============================================================
    db.add_evento(
        sessione=1,
        riassunto="Crollo improvviso nella galleria principale della miniera di Calderaviva. "
                  "Tessa Bruciaterra gravemente ferita; Dario Cenere tra i primi soccorritori, "
                  "sinceramente e senza esitazione.",
        conseguenze_attive="Tessa e in condizioni critiche, non ancora chiaro se sopravvivera. "
                           "La miniera e temporaneamente chiusa per 'ispezione di sicurezza'. "
                           "La causa del crollo resta controversa e irrisolta.",
        location_id=loc_calderaviva_id,
    )

    # ============================================================
    # STATO INIZIALE DEL PG
    # ============================================================
    db.set_pg_stato(
        nome="",  # da decidere dal giocatore
        condizione_fisica="integra, nessuna esposizione significativa all'oro finora",
        ferite_attive="",
        equipaggiamento="Attrezzi da minatore standard, lampada a carburo",
        risorse="Pochi spiccioli, salario da minatore",
        abilita_acquisite="Conoscenza pratica della miniera e delle gallerie di Calderaviva",
        sessione_corrente=1,
        location_attuale_id=loc_calderaviva_id,
        note="Lavoratore della miniera di Calderaviva, mai interessato a politica o fazioni "
             "finche il crollo della galleria nove non ha coinvolto Tessa.",
    )

    print("\nPopolamento completato:")
    print("  - 2 fazioni (Curia Aurea, Collettivo della Brace) - nessuna buona o cattiva")
    print("  - 3 location (Calderaviva, Ossidiana Alta, Bassa Marea)")
    print("  - 3 NPC (Tessa Bruciaterra, Sovrintendente Voll, Dario Cenere)")
    print("  - 1 quest di apertura, causa del crollo deliberatamente irrisolta")
    print("  - 1 evento di sessione 1")
    print("  - Stato PG iniziale impostato (nome da decidere)")


if __name__ == "__main__":
    main()