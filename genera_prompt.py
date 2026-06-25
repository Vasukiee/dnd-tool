"""
genera_prompt.py - Script interattivo per generare il prompt di sessione.

Lancia con: python3 genera_prompt.py

Ti fa domande passo-passo, interroga il database, e scrive un file
markdown pronto da copiare/incollare in una chat con Gemini.

(In alternativa, puoi usare la dashboard web: python3 app.py)
"""

import os
from datetime import datetime
import db
from prompt_builder import costruisci_prompt

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "prompt_generati")


def chiedi(domanda, default=None, opzioni=None, permetti_salto=True):
    """Helper per input interattivo con default opzionale e lista opzioni numerate.

    Se opzioni è fornito, richiede una scelta valida finché non la ottiene
    (a meno che permetti_salto=True e l'utente prema invio a vuoto, nel qual
    caso ritorna default).
    """
    if opzioni:
        print(f"\n{domanda}")
        for i, opt in enumerate(opzioni, 1):
            print(f"  {i}. {opt}")
        while True:
            testo_prompt = "Scegli un numero" + (" (invio per saltare): " if permetti_salto else ": ")
            scelta = input(testo_prompt).strip()
            if scelta == "" and permetti_salto:
                return default
            if scelta.isdigit() and 1 <= int(scelta) <= len(opzioni):
                return opzioni[int(scelta) - 1]
            print(f"  Input non valido. Scegli un numero tra 1 e {len(opzioni)}.")
    suffix = f" [{default}]" if default else ""
    risposta = input(f"{domanda}{suffix}: ").strip()
    return risposta if risposta else default


def chiedi_si_no(domanda, default_si=True):
    suffix = "[S/n]" if default_si else "[s/N]"
    risposta = input(f"{domanda} {suffix}: ").strip().lower()
    if not risposta:
        return default_si
    return risposta.startswith("s")


def chiedi_multilinea(domanda):
    print(f"\n{domanda}")
    print("(scrivi il testo, poi invio su una riga vuota per terminare)")
    righe = []
    while True:
        riga = input()
        if riga == "":
            break
        righe.append(riga)
    return "\n".join(righe)


def sezione_location():
    """Chiede la location corrente, mostrando le opzioni esistenti se disponibili."""
    locations = db.get_all_locations()
    if locations:
        nomi = [l["nome"] for l in locations]
        scelta = chiedi("In che location si svolge la scena?", opzioni=nomi + ["[Altra/nuova location]"], permetti_salto=False)
        if scelta == "[Altra/nuova location]":
            scelta = chiedi("Nome della location (nuova o non in lista)")
    else:
        scelta = chiedi("In che location si svolge la scena? (nessuna location ancora registrata nel DB)")

    location = db.get_location_by_nome(scelta) if scelta else None
    return location, scelta


def sezione_quest(location):
    """Mostra le quest attive rilevanti, lascia scegliere quali includere."""
    location_id = location["id"] if location else None
    quest_attive = db.get_quest_attive(location_id=location_id)
    quest_selezionate = []

    if not quest_attive:
        print("\n(Nessuna quest attiva trovata per questa location nel DB.)")
        return quest_selezionate

    print(f"\nQuest attive trovate ({len(quest_attive)}):")
    for q in quest_attive:
        print(f"  - {q['nome']} [{q['tipo']}]: {q.get('riassunto') or 'nessun riassunto'}")

    if chiedi_si_no("Includere tutte le quest attive trovate nel contesto?", default_si=True):
        quest_selezionate = quest_attive
    else:
        for q in quest_attive:
            if chiedi_si_no(f"  Includere '{q['nome']}'?", default_si=False):
                quest_selezionate.append(q)

    return quest_selezionate


def sezione_npc(location, quest_selezionate):
    """Raccoglie NPC dalla location corrente + quelli collegati alle quest selezionate."""
    npc_visti = {}

    if location:
        for npc in db.get_npc_in_location(location["id"]):
            npc_visti[npc["id"]] = npc

    for q in quest_selezionate:
        for npc in db.get_npc_per_quest(q["id"]):
            npc_visti[npc["id"]] = npc

    return list(npc_visti.values())


def sezione_tipo_scena():
    return chiedi(
        "Che tipo di scena è?",
        opzioni=["Dialogo/sociale", "Combattimento", "Esplorazione", "Puzzle/investigazione", "Transizione/viaggio", "Mista"],
        permetti_salto=False
    )


def sezione_tono():
    return chiedi(
        "Tono specifico per questa scena (opzionale, premi invio per saltare)",
        default=""
    )


def sezione_intento():
    return chiedi_multilinea(
        "Cosa deve succedere in questa scena? (l'intento narrativo che hai in mente, anche solo un'idea grezza)"
    )


def formatta_npc(npc_list):
    """Usata solo per l'anteprima a terminale (versione compatta)."""
    if not npc_list:
        return "_Nessun NPC specifico per questa scena._"
    return "\n".join(f"  - {n['nome']}" for n in npc_list)


def main():
    print("=" * 60)
    print("GENERATORE PROMPT SESSIONE")
    print("=" * 60)

    location, location_nome_raw = sezione_location()
    quest_selezionate = sezione_quest(location)
    npc_list = sezione_npc(location, quest_selezionate)
    tipo_scena = sezione_tipo_scena()
    tono = sezione_tono()
    intento = sezione_intento()

    fazioni = db.get_fazioni_rilevanti()
    fatti = db.get_fatti_accertati()
    eventi = db.get_eventi_recenti(n=5)
    pg_stato = db.get_pg_stato()

    contesto = {
        "location_nome": location["nome"] if location else (location_nome_raw or "Non specificata"),
        "location_descrizione": location.get("descrizione_breve", "") if location else "(location non ancora registrata nel DB)",
        "npc": npc_list,
        "quest": quest_selezionate,
        "fazioni": fazioni,
        "fatti": fatti,
        "eventi": eventi,
        "pg_stato": pg_stato,
        "tipo_scena": tipo_scena,
        "tono": tono,
        "intento": intento,
    }

    prompt = costruisci_prompt(contesto)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(OUTPUT_DIR, f"prompt_{timestamp}.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(prompt)

    print("\n" + "=" * 60)
    print(f"Prompt generato con successo:\n{output_path}")
    print("Apri il file, copia tutto il contenuto e incollalo nella chat con Gemini.")
    print("=" * 60)


if __name__ == "__main__":
    main()
