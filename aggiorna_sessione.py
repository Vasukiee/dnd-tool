import db


def chiedi(domanda, default=None):
    suffix = f" [{default}]" if default else ""
    risposta = input(f"{domanda}{suffix}: ").strip()
    return risposta if risposta else default


def chiedi_opzioni(domanda, opzioni, default=None):
    print(f"\n{domanda}")
    for i, opt in enumerate(opzioni, 1):
        print(f"  {i}. {opt}")
    suffix = f" (default: {default})" if default else ""
    while True:
        scelta = input(f"Scegli un numero{suffix}: ").strip()
        if scelta == "" and default:
            return default
        if scelta.isdigit() and 1 <= int(scelta) <= len(opzioni):
            return opzioni[int(scelta) - 1]
        print(f"  Input non valido, riprova.")


def menu_principale():
    print("\n" + "=" * 60)
    print("AGGIORNAMENTO POST-SESSIONE")
    print("=" * 60)
    azioni = [
        "Registra evento di sessione",
        "Aggiungi/aggiorna NPC",
        "Aggiungi/aggiorna location",
        "Aggiungi/aggiorna fazione",
        "Aggiungi/aggiorna quest",
        "Collega un NPC a una quest",
        "Aggiorna stato del PG",
        "Aggiungi fatto accertato",
        "Esci",
    ]
    for i, a in enumerate(azioni, 1):
        print(f"  {i}. {a}")
    scelta = input("\nCosa vuoi fare? ").strip()
    return scelta


def azione_evento():
    sessione = chiedi("Numero sessione")
    riassunto = chiedi("Riassunto dell'evento (1-3 frasi, fattuale)")
    conseguenze = chiedi("Conseguenze ancora attive da questo evento (opzionale)")
    location_nome = chiedi("Nome location dell'evento (opzionale)")
    location_id = None
    if location_nome:
        loc = db.get_location_by_nome(location_nome)
        location_id = loc["id"] if loc else None
        if not location_id:
            print(f"  (location '{location_nome}' non trovata, evento salvato senza location)")
    db.add_evento(sessione=int(sessione), riassunto=riassunto, conseguenze_attive=conseguenze, location_id=location_id)
    print("Evento registrato.")


def azione_npc():
    nome = chiedi("Nome NPC (nuovo o esistente)")
    ruolo = chiedi("Ruolo (opzionale, invio per non modificare)")
    stato = chiedi("Stato (vivo/morto/disperso/sconosciuto, invio per non modificare)")
    location_nome = chiedi("Location attuale (opzionale, invio per non modificare)")
    relazione_pg = chiedi("Relazione col PG (opzionale, invio per non modificare)")
    descrizione = chiedi("Descrizione breve (opzionale, invio per non modificare)")
    note_caratteriali = chiedi("Note caratteriali / tic verbali (opzionale, invio per non modificare)")

    kwargs = {}
    if ruolo: kwargs["ruolo"] = ruolo
    if stato: kwargs["stato"] = stato
    if relazione_pg: kwargs["relazione_pg"] = relazione_pg
    if descrizione: kwargs["descrizione_breve"] = descrizione
    if note_caratteriali: kwargs["note_caratteriali"] = note_caratteriali
    if location_nome:
        loc = db.get_location_by_nome(location_nome)
        if loc:
            kwargs["location_attuale_id"] = loc["id"]
        else:
            print(f"  (location '{location_nome}' non trovata, ignorata)")

    db.upsert_npc(nome, **kwargs)
    print(f"NPC '{nome}' salvato/aggiornato.")


def azione_location():
    nome = chiedi("Nome location (nuova o esistente)")
    tipo = chiedi("Tipo (città/quartiere/dungeon/regione..., invio per non modificare)")
    descrizione = chiedi("Descrizione breve (invio per non modificare)")
    stato_attuale = chiedi("Stato attuale (invio per non modificare)")
    fazione_nome = chiedi("Fazione controllante (opzionale, invio per non modificare)")

    kwargs = {}
    if tipo: kwargs["tipo"] = tipo
    if descrizione: kwargs["descrizione_breve"] = descrizione
    if stato_attuale: kwargs["stato_attuale"] = stato_attuale
    if fazione_nome:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM fazioni WHERE nome LIKE ?", (f"%{fazione_nome}%",))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            kwargs["fazione_controllante_id"] = row["id"]
        else:
            print(f"  (fazione '{fazione_nome}' non trovata, ignorata)")

    db.upsert_location(nome, **kwargs)
    print(f"Location '{nome}' salvata/aggiornata.")


def azione_fazione():
    nome = chiedi("Nome fazione (nuova o esistente)")
    nome_popolare = chiedi("Nome popolare (invio per non modificare)")
    ideologia = chiedi("Ideologia/principio guida (invio per non modificare)")
    territorio = chiedi("Territorio (invio per non modificare)")
    relazione_pg = chiedi_opzioni("Relazione col PG", ["alleata", "neutrale", "ostile", "sconosciuta"], default="neutrale")
    stato_attuale = chiedi("Stato attuale nella trama (invio per non modificare)")

    kwargs = {"relazione_pg": relazione_pg}
    if nome_popolare: kwargs["nome_popolare"] = nome_popolare
    if ideologia: kwargs["ideologia"] = ideologia
    if territorio: kwargs["territorio"] = territorio
    if stato_attuale: kwargs["stato_attuale"] = stato_attuale

    db.upsert_fazione(nome, **kwargs)
    print(f"Fazione '{nome}' salvata/aggiornata.")


def azione_quest():
    nome = chiedi("Nome quest (nuova o esistente)")
    tipo = chiedi_opzioni("Tipo", ["main", "side"], default="side")
    stato = chiedi_opzioni("Stato", ["attiva", "completata", "fallita", "in_pausa"], default="attiva")
    riassunto = chiedi("Riassunto/stato attuale fattuale (invio per non modificare)")
    obiettivo = chiedi("Obiettivo attuale per il PG (invio per non modificare)")
    location_nome = chiedi("Location collegata (opzionale, invio per non modificare)")

    kwargs = {"tipo": tipo, "stato": stato}
    if riassunto: kwargs["riassunto"] = riassunto
    if obiettivo: kwargs["obiettivo_attuale"] = obiettivo
    if location_nome:
        loc = db.get_location_by_nome(location_nome)
        if loc:
            kwargs["location_id"] = loc["id"]
        else:
            print(f"  (location '{location_nome}' non trovata, ignorata)")

    quest_id = db.upsert_quest(nome, **kwargs)
    print(f"Quest '{nome}' salvata/aggiornata (id {quest_id}).")


def azione_link_npc_quest():
    nome_quest = chiedi("Nome quest")
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM quest WHERE nome LIKE ?", (f"%{nome_quest}%",))
    quest_row = cur.fetchone()
    if not quest_row:
        print(f"  Quest '{nome_quest}' non trovata.")
        cur.close()
        conn.close()
        return
    nome_npc = chiedi("Nome NPC")
    cur.execute("SELECT id FROM npc WHERE nome LIKE ?", (f"%{nome_npc}%",))
    npc_row = cur.fetchone()
    cur.close()
    conn.close()
    if not npc_row:
        print(f"  NPC '{nome_npc}' non trovato.")
        return
    ruolo = chiedi("Ruolo dell'NPC in questa quest (es. obiettivo/alleato/informatore/ostacolo)")
    db.link_npc_quest(quest_row["id"], npc_row["id"], ruolo_nella_quest=ruolo)
    print(f"Collegato '{nome_npc}' alla quest '{nome_quest}'.")


def azione_pg_stato():
    pgs = db.get_all_pg()

    if not pgs:
        print("  Nessun personaggio ancora registrato. Verra' creato un nuovo personaggio.")
        pg_id = None
    elif len(pgs) == 1:
        pg_id = pgs[0]["id"]
        print(f"  Personaggio: {pgs[0]['nome'] or '(senza nome)'}")
    else:
        print("\n  Personaggi disponibili:")
        for i, pg in enumerate(pgs, 1):
            print(f"    {i}. {pg['nome'] or '(senza nome)'}")
        while True:
            scelta = input("  Quale vuoi aggiornare? Scegli un numero: ").strip()
            if scelta.isdigit() and 1 <= int(scelta) <= len(pgs):
                pg_id = pgs[int(scelta) - 1]["id"]
                break
            print("  Input non valido, riprova.")

    nome = chiedi("Nome PG (invio per non modificare)")
    condizione = chiedi("Condizione fisica attuale (invio per non modificare)")
    ferite = chiedi("Ferite attive (invio per non modificare)")
    equipaggiamento = chiedi("Equipaggiamento (invio per non modificare)")
    risorse = chiedi("Risorse/valuta (invio per non modificare)")
    abilita = chiedi("Abilità acquisite (invio per non modificare)")
    sessione = chiedi("Sessione corrente (numero, invio per non modificare)")
    location_nome = chiedi("Location attuale (invio per non modificare)")

    kwargs = {}
    if nome: kwargs["nome"] = nome
    if condizione: kwargs["condizione_fisica"] = condizione
    if ferite: kwargs["ferite_attive"] = ferite
    if equipaggiamento: kwargs["equipaggiamento"] = equipaggiamento
    if risorse: kwargs["risorse"] = risorse
    if abilita: kwargs["abilita_acquisite"] = abilita
    if sessione: kwargs["sessione_corrente"] = int(sessione)
    if location_nome:
        loc = db.get_location_by_nome(location_nome)
        if loc:
            kwargs["location_attuale_id"] = loc["id"]
        else:
            print(f"  (location '{location_nome}' non trovata, ignorata)")

    if not kwargs:
        print("Nessuna modifica inserita, niente da salvare.")
        return

    if pg_id is None:
        db.crea_pg(**kwargs)
        print("Personaggio creato.")
    else:
        db.aggiorna_pg(pg_id, **kwargs)
        print("Stato del PG aggiornato.")


def azione_fatto():
    descrizione = chiedi("Descrizione del fatto accertato")
    sessione = chiedi("Sessione in cui è stato scoperto (opzionale)")
    rilevanza = chiedi_opzioni("Rilevanza", ["alta", "media", "bassa"], default="media")
    db.add_fatto_accertato(
        descrizione,
        sessione=int(sessione) if sessione else None,
        rilevanza=rilevanza
    )
    print("Fatto accertato registrato.")


AZIONI = {
    "1": azione_evento,
    "2": azione_npc,
    "3": azione_location,
    "4": azione_fazione,
    "5": azione_quest,
    "6": azione_link_npc_quest,
    "7": azione_pg_stato,
    "8": azione_fatto,
}


def main():
    while True:
        scelta = menu_principale()
        if scelta == "9" or scelta.lower() in ("esci", "exit", "q"):
            print("A presto.")
            break
        funzione = AZIONI.get(scelta)
        if funzione:
            try:
                funzione()
            except Exception as e:
                print(f"Errore durante l'operazione: {e}")
        else:
            print("Scelta non valida.")


if __name__ == "__main__":
    main()