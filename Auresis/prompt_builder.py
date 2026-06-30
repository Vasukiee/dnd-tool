"""
prompt_builder.py - Logica di formattazione e costruzione del prompt di sessione.

Condiviso tra genera_prompt.py (script da terminale) e app.py (dashboard web),
così la formattazione resta identica indipendentemente da dove viene generato
il prompt.
"""

import os
from datetime import datetime

DOCUMENTI_STATICI_DIR = os.path.join(os.path.dirname(__file__), "documenti_statici")


def leggi_file_statico(nome_file):
    path = os.path.join(DOCUMENTI_STATICI_DIR, nome_file)
    if not os.path.exists(path):
        return f"[ATTENZIONE: file {nome_file} non trovato in {DOCUMENTI_STATICI_DIR}]"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def formatta_npc(npc_list):
    if not npc_list:
        return "_Nessun NPC specifico per questa scena._"
    blocchi = []
    for n in npc_list:
        riga = f"**{n['nome']}**"
        if n.get('ruolo'):
            riga += f" ({n['ruolo']})"
        riga += f" — stato: {n.get('stato', 'vivo')}"
        if n.get('fazione_nome'):
            riga += f", fazione: {n['fazione_nome']}"
        if n.get('descrizione_breve'):
            riga += f"\n  {n['descrizione_breve']}"
        if n.get('relazione_pg'):
            riga += f"\n  Relazione col PG: {n['relazione_pg']}"
        if n.get('note_caratteriali'):
            riga += f"\n  Tratti caratteriali: {n['note_caratteriali']}"
        if n.get('livello_contaminazione'):
            riga += f"\n  Livello contaminazione Auris Cancer: {n['livello_contaminazione']}/5"
        blocchi.append(riga)
    return "\n\n".join(blocchi)


def formatta_quest(quest_list):
    if not quest_list:
        return "_Nessuna quest attiva selezionata per questa scena._"
    blocchi = []
    for q in quest_list:
        riga = f"**{q['nome']}** [{q['tipo']}]"
        if q.get('riassunto'):
            riga += f"\n  Stato attuale: {q['riassunto']}"
        if q.get('obiettivo_attuale'):
            riga += f"\n  Obiettivo corrente: {q['obiettivo_attuale']}"
        blocchi.append(riga)
    return "\n\n".join(blocchi)


def formatta_eventi(eventi_list):
    if not eventi_list:
        return "_Nessun evento registrato ancora._"
    blocchi = []
    for e in reversed(eventi_list):  # ordine cronologico nel testo
        riga = f"- (Sessione {e['sessione']}) {e['riassunto']}"
        if e.get('conseguenze_attive'):
            riga += f" [conseguenze ancora attive: {e['conseguenze_attive']}]"
        blocchi.append(riga)
    return "\n".join(blocchi)


def formatta_pg_stato(pg):
    if not pg:
        return "_Stato del PG non ancora registrato nel DB._"
    righe = []
    for campo, label in [
        ("nome", "Nome"), ("condizione_fisica", "Condizione fisica"),
        ("ferite_attive", "Ferite attive"), ("equipaggiamento", "Equipaggiamento"),
        ("risorse", "Risorse"), ("abilita_acquisite", "Abilità acquisite"),
    ]:
        if pg.get(campo):
            righe.append(f"- **{label}**: {pg[campo]}")
    return "\n".join(righe) if righe else "_Nessun dato disponibile._"


def formatta_fazioni(fazioni_list):
    if not fazioni_list:
        return "_Nessuna fazione registrata._"
    blocchi = []
    for f in fazioni_list:
        riga = f"**{f['nome']}**"
        if f.get('nome_popolare'):
            riga += f" ({f['nome_popolare']})"
        riga += f" — relazione col PG: {f.get('relazione_pg', 'neutrale')}"
        if f.get('stato_attuale'):
            riga += f"\n  Stato attuale: {f['stato_attuale']}"
        blocchi.append(riga)
    return "\n\n".join(blocchi)


def formatta_fatti(fatti_list):
    if not fatti_list:
        return "_Nessun fatto accertato registrato._"
    return "\n".join(f"- {f['descrizione']}" for f in fatti_list)


def costruisci_prompt(contesto):
    """
    contesto è un dizionario con le chiavi:
    location_nome, location_descrizione, npc, quest, fazioni, fatti,
    eventi, pg_stato, tipo_scena, tono, intento
    """
    bible_universo = leggi_file_statico("bible_universo.md")
    bible_pianeta = leggi_file_statico("bible_pianeta.md")
    regole = leggi_file_statico("regole_risoluzione.md")

    prompt = f"""# PROMPT SESSIONE — Generato il {datetime.now().strftime('%Y-%m-%d %H:%M')}

## ISTRUZIONI PER IL MASTER (Gemini)

Sei il master di una campagna DnD personalizzata, single-player, story-driven.
Segui RIGOROSAMENTE i documenti di lore e le regole di risoluzione forniti sotto.
Il combattimento è narrativo-causale, NON matematico: niente tiri di dado, le
conseguenze derivano dalle capacità reali dei personaggi e dalla logica della scena.
Non introdurre regole, oggetti o eventi che contraddicano i documenti statici.
Se manca un'informazione necessaria, chiedi piuttosto che inventare canon nuovo
senza segnalarlo.

---

## 1. BIBLE UNIVERSO (statica)

{bible_universo}

---

## 2. BIBLE PIANETA (statica)

{bible_pianeta}

---

## 3. REGOLE DI RISOLUZIONE (statiche)

{regole}

---

## 4. STATO ATTUALE DEL PERSONAGGIO

{formatta_pg_stato(contesto['pg_stato'])}

---

## 5. LOCATION CORRENTE

**{contesto['location_nome']}**
{contesto['location_descrizione']}

---

## 6. NPC RILEVANTI IN SCENA

{formatta_npc(contesto['npc'])}

---

## 7. QUEST ATTIVE RILEVANTI

{formatta_quest(contesto['quest'])}

---

## 8. FAZIONI RILEVANTI

{formatta_fazioni(contesto['fazioni'])}

---

## 9. FATTI ACCERTATI (canon scoperto finora)

{formatta_fatti(contesto['fatti'])}

---

## 10. EVENTI RECENTI (log sessioni precedenti)

{formatta_eventi(contesto['eventi'])}

---

## 11. ISTRUZIONI PER QUESTA SCENA

- **Tipo di scena**: {contesto['tipo_scena']}
- **Tono specifico**: {contesto['tono'] or 'nessuna indicazione particolare, segui il tono generale della campagna'}

**Intento narrativo per questa scena:**
{contesto['intento'] or 'Nessun intento specifico fornito: usa il tuo giudizio narrativo basandoti sul contesto sopra.'}

---

Scrivi ora la prossima scena della sessione, mantenendo coerenza assoluta con
tutto il contesto fornito sopra.
"""
    return prompt
