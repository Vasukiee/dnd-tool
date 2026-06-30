"""
popola_iniziale.py - Popola il database con dati demo di esempio.

Lancia con: python3 popola_iniziale.py

Crea 2 fazioni, 3 location, 3 NPC, 1 quest e 1 evento di esempio.
Pensato per essere lanciato una volta su un database vuoto.
Se lo rilanci su dati esistenti, gli upsert aggiorneranno le voci
con lo stesso nome invece di duplicarle.
"""

import db


def main():
    print("Popolamento dati di esempio...")

    # ============================================================
    # FAZIONI
    # ============================================================
    db.upsert_fazione(
        "Gilda dei Mercanti",
        nome_popolare="I Mercanti",
        ideologia="Controllo delle rotte commerciali e delle risorse strategiche. "
                  "Sostengono che la prosperità collettiva passi per l'ordine economico "
                  "centralizzato. In pratica, difendono i propri monopoli.",
        territorio="Città Alta e principali porti commerciali",
        relazione_pg="neutrale",
        stato_attuale="Gestisce i flussi di merci nella regione; ha interessi diretti "
                      "nell'area del Crocevia.",
        attiva=1,
    )

    db.upsert_fazione(
        "Alleanza Popolare",
        nome_popolare="I Liberi",
        ideologia="Mutuo soccorso e accesso diretto alle risorse, senza intermediari. "
                  "Rete informale di artigiani, commercianti indipendenti e lavoratori "
                  "che si organizzano per aggirare i monopoli della Gilda.",
        territorio="Diffusa nel Quartiere Basso e nelle comunità periferiche",
        relazione_pg="neutrale",
        stato_attuale="In fermento dopo la scomparsa di un loro membro nel Crocevia.",
        attiva=1,
    )

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM fazioni WHERE nome = 'Gilda dei Mercanti'")
    row = cur.fetchone()
    assert row is not None
    fazione_gilda_id = row[0]
    cur.execute("SELECT id FROM fazioni WHERE nome = 'Alleanza Popolare'")
    row = cur.fetchone()
    assert row is not None
    fazione_alleanza_id = row[0]
    cur.close()
    conn.close()

    # ============================================================
    # LOCATIONS
    # ============================================================
    db.upsert_location(
        "Crocevia",
        tipo="città/hub commerciale",
        descrizione_breve="Nodo centrale della regione. Qui convergono le rotte "
                          "commerciali principali, il mercato coperto e la sede "
                          "locale della Gilda. Il PG opera da qui.",
        fazione_controllante_id=fazione_gilda_id,
        stato_attuale="Tensione latente dopo la scomparsa del corriere dell'Alleanza.",
    )

    db.upsert_location(
        "Fortezza del Consiglio",
        tipo="fortezza/sede istituzionale",
        descrizione_breve="Sede del potere centrale della Gilda dei Mercanti. "
                          "Accesso ristretto, sorveglianza costante. "
                          "Architettura imponente, deliberatamente intimidatoria.",
        fazione_controllante_id=fazione_gilda_id,
    )

    db.upsert_location(
        "Quartiere Basso",
        tipo="quartiere popolare",
        descrizione_breve="Periferia del Crocevia, fuori dal controllo diretto "
                          "della Gilda. L'Alleanza Popolare ha qui le sue reti "
                          "informali più dense. Vita dura, solidarietà reale.",
        fazione_controllante_id=fazione_alleanza_id,
    )

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM locations WHERE nome = 'Crocevia'")
    row = cur.fetchone()
    assert row is not None
    loc_crocevia_id = row[0]
    cur.execute("SELECT id FROM locations WHERE nome = 'Fortezza del Consiglio'")
    row = cur.fetchone()
    assert row is not None
    loc_fortezza_id = row[0]
    cur.execute("SELECT id FROM locations WHERE nome = 'Quartiere Basso'")
    row = cur.fetchone()
    assert row is not None
    loc_quartiere_id = row[0]
    cur.close()
    conn.close()

    # ============================================================
    # NPC
    # ============================================================
    npc_marta_id = db.upsert_npc(
        "Marta Sellai",
        ruolo="alleata del PG, mercante indipendente",
        fazione_id=None,
        location_attuale_id=loc_crocevia_id,
        stato="vivo",
        relazione_pg="fidata — conosce il PG da anni, lo aiuta senza secondi fini",
        descrizione_breve="Commerciante indipendente che opera nel Crocevia. "
                          "Tiene i piedi in due staffe senza stare con nessuno.",
        note_caratteriali="Parla diretto, non fa giri di parole. "
                          "Non si fida della Gilda, ma non lo dice apertamente a chi non conosce.",
        livello_contaminazione=0,
        ultima_apparizione_sessione=1,
    )

    npc_aldren_id = db.upsert_npc(
        "Consigliere Aldren",
        ruolo="funzionario della Gilda, antagonista minore",
        fazione_id=fazione_gilda_id,
        location_attuale_id=loc_fortezza_id,
        stato="vivo",
        relazione_pg="sconosciuto; risponde alle domande con mezze verità",
        descrizione_breve="Gestisce i registri commerciali della Gilda nel Crocevia. "
                          "Sa più di quanto ammette sulla scomparsa del corriere.",
        note_caratteriali="Tono burocratico anche fuori contesto. Non mente apertamente, "
                          "ma omette con cura. Difende le procedure anche quando sa "
                          "che non reggono.",
        livello_contaminazione=0,
        ultima_apparizione_sessione=1,
    )

    npc_edo_id = db.upsert_npc(
        "Edo",
        ruolo="contatto dell'Alleanza, informatore",
        fazione_id=fazione_alleanza_id,
        location_attuale_id=loc_quartiere_id,
        stato="vivo",
        relazione_pg="disponibile ma cauto — aiuta se si guadagna la fiducia",
        descrizione_breve="Figura di riferimento dell'Alleanza nel Quartiere Basso. "
                          "Conosce il corriere scomparso e vuole risposte.",
        note_caratteriali="Poco incline a fidarsi dei nuovi arrivati. "
                          "Se vede coerenza nelle azioni del PG, si apre gradualmente.",
        livello_contaminazione=0,
        ultima_apparizione_sessione=1,
    )

    # ============================================================
    # QUEST DI APERTURA
    # ============================================================
    quest_id = db.upsert_quest(
        "La scomparsa del corriere",
        tipo="main",
        stato="attiva",
        location_id=loc_crocevia_id,
        riassunto="Un corriere dell'Alleanza Popolare è sparito nel Crocevia tre giorni fa "
                  "con documenti che non dovevano finire nelle mani della Gilda. "
                  "Nessuno ha dichiarato nulla ufficialmente. La Gilda nega di sapere qualcosa; "
                  "l'Alleanza sospetta ma non ha prove.",
        obiettivo_attuale="Scoprire dove si trova il corriere e cosa è successo ai documenti, "
                          "senza fidarsi ciecamente di nessuna delle due versioni.",
        sessione_inizio=1,
    )

    db.link_npc_quest(quest_id, npc_marta_id, ruolo_nella_quest="fonte attendibile/punto di partenza")
    db.link_npc_quest(quest_id, npc_aldren_id, ruolo_nella_quest="fonte parziale/possibile coinvolto")
    db.link_npc_quest(quest_id, npc_edo_id, ruolo_nella_quest="contatto Alleanza/motivazione")

    # ============================================================
    # EVENTO DI APERTURA
    # ============================================================
    db.add_evento(
        sessione=1,
        riassunto="Il corriere dell'Alleanza è scomparso nel Crocevia. "
                  "Nessuna testimonianza diretta, nessuna dichiarazione ufficiale.",
        conseguenze_attive="La sparizione è irrisolta. Entrambe le fazioni trattengono informazioni.",
        location_id=loc_crocevia_id,
    )

    # ============================================================
    # STATO INIZIALE DEL PG
    # ============================================================
    db.set_pg_stato(
        nome="",
        condizione_fisica="integra, nessuna condizione particolare",
        ferite_attive="",
        equipaggiamento="Equipaggiamento standard",
        risorse="Risorse limitate",
        abilita_acquisite="",
        sessione_corrente=1,
        location_attuale_id=loc_crocevia_id,
        note="",
    )

    print("\nPopolamento completato:")
    print("  - 2 fazioni (Gilda dei Mercanti, Alleanza Popolare)")
    print("  - 3 location (Crocevia, Fortezza del Consiglio, Quartiere Basso)")
    print("  - 3 NPC (Marta Sellai, Consigliere Aldren, Edo)")
    print("  - 1 quest di apertura (La scomparsa del corriere)")
    print("  - 1 evento di sessione 1")
    print("  - Stato PG iniziale impostato (nome da decidere)")


if __name__ == "__main__":
    main()
