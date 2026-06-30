import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "campagna.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


class EliminazioneBloccata(Exception):
    """Sollevata da delete_record quando FK impedisce la cancellazione.
    Il messaggio è già in italiano e leggibile dall'utente finale."""


# (ref_tabella, colonna_fk, label_singolare, label_plurale)
_FK_DIPENDENZE: dict[str, list[tuple[str, str, str, str]]] = {
    "fazioni": [
        ("locations", "fazione_controllante_id", "location",           "location"),
        ("npc",       "fazione_id",              "personaggio",         "personaggi"),
    ],
    "locations": [
        ("locations",    "location_padre_id",   "location figlia",      "location figlie"),
        ("npc",          "location_attuale_id", "personaggio",          "personaggi"),
        ("quest",        "location_id",         "incarico",             "incarichi"),
        ("eventi",       "location_id",         "evento",               "eventi"),
        ("tracce_audio", "location_id",         "traccia audio",        "tracce audio"),
        ("pg_stato",     "location_attuale_id", "personaggio giocante", "personaggi giocanti"),
    ],
    "npc": [
        ("quest_npc", "npc_id", "collegamento a incarico", "collegamenti a incarichi"),
    ],
    "quest": [
        ("quest_npc",    "quest_id", "collegamento a personaggio", "collegamenti a personaggi"),
        ("tracce_audio", "quest_id", "traccia audio",              "tracce audio"),
    ],
    "eventi":         [],
    "fatti_accertati": [],
}

# (descrizione entità, participio concordato per "è ancora ___ata/o a")
_ETICHETTE_TABELLE: dict[str, tuple[str, str]] = {
    "fazioni":         ("questa fazione",    "collegata"),
    "locations":       ("questa location",   "collegata"),
    "npc":             ("questo personaggio","collegato"),
    "quest":           ("questo incarico",   "collegato"),
    "eventi":          ("questo evento",     "collegato"),
    "fatti_accertati": ("questa verità",     "collegata"),
}


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _dictify(rows):
    return [dict(r) for r in rows]


def init_db():
    """Crea le tabelle (se non esistono) applicando lo schema.
    Sicuro da rilanciare più volte (CREATE TABLE IF NOT EXISTS)."""
    conn = get_connection()
    cur = conn.cursor()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    cur.executescript(schema)
    conn.commit()
    cur.close()
    conn.close()
    print("Database inizializzato.")


# QUERY DI LETTURA

def get_location_by_nome(nome):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM locations WHERE nome LIKE ?", (f"%{nome}%",))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_npc_in_location(location_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT npc.*, fazioni.nome as fazione_nome
           FROM npc
                    LEFT JOIN fazioni ON npc.fazione_id = fazioni.id
           WHERE npc.location_attuale_id = ? AND npc.stato != 'morto'""",
        (location_id,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_quest_attive(location_id=None):
    conn = get_connection()
    cur = conn.cursor()
    if location_id:
        cur.execute(
            "SELECT * FROM quest WHERE stato = 'attiva' AND (location_id = ? OR location_id IS NULL)",
            (location_id,)
        )
    else:
        cur.execute("SELECT * FROM quest WHERE stato = 'attiva'")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_npc_per_quest(quest_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT npc.*, quest_npc.ruolo_nella_quest
           FROM quest_npc
                    JOIN npc ON quest_npc.npc_id = npc.id
           WHERE quest_npc.quest_id = ?""",
        (quest_id,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_eventi_recenti(n=5):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM eventi ORDER BY sessione DESC, id DESC LIMIT ?", (n,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_all_pg():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM pg_stato ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_pg_by_id(pg_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM pg_stato WHERE id = ?", (pg_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def crea_pg(**kwargs):
    if not kwargs:
        return None
    conn = get_connection()
    cur = conn.cursor()
    cols = ", ".join(kwargs.keys())
    placeholders = ", ".join(["?"] * len(kwargs))
    cur.execute(f"INSERT INTO pg_stato ({cols}) VALUES ({placeholders})", tuple(kwargs.values()))
    new_id = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return new_id


def aggiorna_pg(pg_id, **kwargs):
    if not kwargs:
        return
    conn = get_connection()
    cur = conn.cursor()
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    cur.execute(f"UPDATE pg_stato SET {set_clause} WHERE id = ?", (*kwargs.values(), pg_id))
    conn.commit()
    cur.close()
    conn.close()


def delete_pg(pg_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM pg_statistiche WHERE pg_id = ?", (pg_id,))
    cur.execute("DELETE FROM pg_abilita WHERE pg_id = ?", (pg_id,))
    cur.execute("DELETE FROM pg_stato WHERE id = ?", (pg_id,))
    conn.commit()
    cur.close()
    conn.close()


def get_statistiche_pg(pg_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM pg_statistiche WHERE pg_id = ? ORDER BY posizione, id", (pg_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def aggiungi_statistica_pg(pg_id, nome, valore):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(posizione), -1) + 1 FROM pg_statistiche WHERE pg_id = ?", (pg_id,))
    prossima = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO pg_statistiche (pg_id, nome_statistica, valore, posizione) VALUES (?, ?, ?, ?)",
        (pg_id, nome, valore, prossima)
    )
    conn.commit()
    cur.close()
    conn.close()


def aggiorna_posizione_statistica(stat_id, posizione):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE pg_statistiche SET posizione = ? WHERE id = ?", (posizione, stat_id))
    conn.commit()
    cur.close()
    conn.close()


def aggiorna_statistica_pg(stat_id, valore):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE pg_statistiche SET valore = ? WHERE id = ?", (valore, stat_id))
    conn.commit()
    cur.close()
    conn.close()


def delete_statistica_pg(stat_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM pg_statistiche WHERE id = ?", (stat_id,))
    conn.commit()
    cur.close()
    conn.close()


def get_abilita_pg(pg_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM pg_abilita WHERE pg_id = ? ORDER BY id", (pg_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def aggiungi_abilita_pg(pg_id, nome, descrizione):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO pg_abilita (pg_id, nome, descrizione) VALUES (?, ?, ?)",
        (pg_id, nome, descrizione or None)
    )
    conn.commit()
    cur.close()
    conn.close()


def aggiorna_abilita_pg(abilita_id, nome, descrizione):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE pg_abilita SET nome = ?, descrizione = ? WHERE id = ?",
        (nome, descrizione or None, abilita_id)
    )
    conn.commit()
    cur.close()
    conn.close()


def delete_abilita_pg(abilita_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM pg_abilita WHERE id = ?", (abilita_id,))
    conn.commit()
    cur.close()
    conn.close()


def get_fazioni_rilevanti(location_id=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM fazioni WHERE attiva = 1")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_fatti_accertati(rilevanza_minima=None):
    conn = get_connection()
    cur = conn.cursor()
    if rilevanza_minima:
        cur.execute(
            "SELECT * FROM fatti_accertati WHERE rilevanza = ? ORDER BY sessione DESC",
            (rilevanza_minima,)
        )
    else:
        cur.execute("SELECT * FROM fatti_accertati ORDER BY sessione DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_all_locations():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, nome, tipo FROM locations ORDER BY nome")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_all_quest(stato=None):
    conn = get_connection()
    cur = conn.cursor()
    if stato:
        cur.execute("SELECT id, nome, tipo, stato FROM quest WHERE stato = ? ORDER BY nome", (stato,))
    else:
        cur.execute("SELECT id, nome, tipo, stato FROM quest ORDER BY nome")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_all_tracce_audio(categoria=None):
    conn = get_connection()
    cur = conn.cursor()
    if categoria:
        cur.execute("SELECT * FROM tracce_audio WHERE categoria = ? ORDER BY nome", (categoria,))
    else:
        cur.execute("SELECT * FROM tracce_audio ORDER BY categoria, nome")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_tracce_audio_per_location(location_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tracce_audio WHERE location_id = ? ORDER BY nome", (location_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_tracce_audio_per_quest(quest_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tracce_audio WHERE quest_id = ? ORDER BY nome", (quest_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_categorie_audio_esistenti():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT categoria FROM tracce_audio ORDER BY categoria")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]


def add_traccia_audio(nome, categoria, youtube_id, timestamp_inizio=0,
                      note=None, location_id=None, quest_id=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO tracce_audio
           (nome, categoria, youtube_id, timestamp_inizio, note, location_id, quest_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (nome, categoria, youtube_id, timestamp_inizio, note, location_id, quest_id),
    )
    new_id = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return new_id


def update_traccia_audio(traccia_id, **campi):
    if not campi:
        return
    colonne = ", ".join(f"{k} = ?" for k in campi)
    valori = list(campi.values()) + [traccia_id]
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"UPDATE tracce_audio SET {colonne} WHERE id = ?", valori)
    conn.commit()
    cur.close()
    conn.close()


def delete_traccia_audio(traccia_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tracce_audio WHERE id = ?", (traccia_id,))
    conn.commit()
    cur.close()
    conn.close()


# QUERY COMPLETE PER LA DASHBOARD WEB

def get_all_npc_full():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT npc.*, fazioni.nome as fazione_nome, locations.nome as location_nome
           FROM npc
                    LEFT JOIN fazioni ON npc.fazione_id = fazioni.id
                    LEFT JOIN locations ON npc.location_attuale_id = locations.id
           ORDER BY npc.nome"""
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_npc_full(npc_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT npc.*, fazioni.nome as fazione_nome, locations.nome as location_nome
           FROM npc
                    LEFT JOIN fazioni ON npc.fazione_id = fazioni.id
                    LEFT JOIN locations ON npc.location_attuale_id = locations.id
           WHERE npc.id = ?""",
        (npc_id,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return None
    npc = dict(row)
    cur.execute(
        """SELECT quest.id, quest.nome, quest.stato, quest_npc.ruolo_nella_quest
           FROM quest_npc JOIN quest ON quest_npc.quest_id = quest.id
           WHERE quest_npc.npc_id = ?""",
        (npc_id,)
    )
    npc["quest_collegate"] = _dictify(cur.fetchall())
    cur.close()
    conn.close()
    return npc


def get_all_fazioni_full():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM fazioni ORDER BY nome")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_fazione_full(fazione_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM fazioni WHERE id = ?", (fazione_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return None
    fazione = dict(row)
    cur.execute("SELECT id, nome, stato FROM npc WHERE fazione_id = ?", (fazione_id,))
    fazione["membri"] = _dictify(cur.fetchall())
    cur.execute("SELECT id, nome FROM locations WHERE fazione_controllante_id = ?", (fazione_id,))
    fazione["territori"] = _dictify(cur.fetchall())
    cur.close()
    conn.close()
    return fazione


def get_all_quest_full():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT quest.*, locations.nome as location_nome
           FROM quest LEFT JOIN locations ON quest.location_id = locations.id
           ORDER BY
               CASE quest.stato WHEN 'attiva' THEN 0 ELSE 1 END,
               CASE quest.tipo WHEN 'main' THEN 0 ELSE 1 END,
               quest.nome"""
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_quest_full(quest_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT quest.*, locations.nome as location_nome
           FROM quest LEFT JOIN locations ON quest.location_id = locations.id
           WHERE quest.id = ?""",
        (quest_id,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return None
    quest = dict(row)
    cur.execute(
        """SELECT npc.id, npc.nome, npc.stato, quest_npc.ruolo_nella_quest
           FROM quest_npc JOIN npc ON quest_npc.npc_id = npc.id
           WHERE quest_npc.quest_id = ?""",
        (quest_id,)
    )
    quest["npc_coinvolti"] = _dictify(cur.fetchall())
    cur.close()
    conn.close()
    return quest


def get_all_locations_full():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT locations.*, fazioni.nome as fazione_nome
           FROM locations LEFT JOIN fazioni ON locations.fazione_controllante_id = fazioni.id
           ORDER BY locations.nome"""
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_location_full(location_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT locations.*, fazioni.nome as fazione_nome
           FROM locations LEFT JOIN fazioni ON locations.fazione_controllante_id = fazioni.id
           WHERE locations.id = ?""",
        (location_id,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return None
    location = dict(row)
    cur.execute("SELECT id, nome, stato FROM npc WHERE location_attuale_id = ?", (location_id,))
    location["npc_presenti"] = _dictify(cur.fetchall())
    cur.execute("SELECT id, nome, stato FROM quest WHERE location_id = ?", (location_id,))
    location["quest_collegate"] = _dictify(cur.fetchall())
    cur.execute(
        "SELECT id, sessione, riassunto FROM eventi WHERE location_id = ? ORDER BY sessione DESC",
        (location_id,)
    )
    location["eventi_qui"] = _dictify(cur.fetchall())
    cur.close()
    conn.close()
    return location


def get_all_eventi():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT eventi.*, locations.nome as location_nome
           FROM eventi LEFT JOIN locations ON eventi.location_id = locations.id
           ORDER BY eventi.sessione DESC, eventi.id DESC"""
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_all_fatti():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM fatti_accertati ORDER BY sessione DESC, id DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def delete_record(tabella, record_id):
    tabelle_consentite = {"npc", "fazioni", "locations", "quest", "eventi", "fatti_accertati"}
    if tabella not in tabelle_consentite:
        raise ValueError(f"Tabella non consentita: {tabella}")

    conn = get_connection()
    cur = conn.cursor()
    try:
        blocchi = []
        for ref_tab, colonna, label_sing, label_plur in _FK_DIPENDENZE.get(tabella, []):
            cur.execute(f"SELECT COUNT(*) FROM {ref_tab} WHERE {colonna} = ?", (record_id,))
            count = cur.fetchone()[0]
            if count > 0:
                blocchi.append(f"{count} {label_sing if count == 1 else label_plur}")

        if blocchi:
            entita, coniug = _ETICHETTE_TABELLE.get(tabella, ("questo elemento", "collegato"))
            if len(blocchi) == 1:
                lista = blocchi[0]
            elif len(blocchi) == 2:
                lista = f"{blocchi[0]} e {blocchi[1]}"
            else:
                lista = ", ".join(blocchi[:-1]) + f" e {blocchi[-1]}"
            raise EliminazioneBloccata(
                f"Non puoi eliminare {entita}: è ancora {coniug} a {lista}. "
                f"Rimuovi o sposta prima quei collegamenti."
            )

        cur.execute(f"DELETE FROM {tabella} WHERE id = ?", (record_id,))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_stats_riepilogo():
    conn = get_connection()
    cur = conn.cursor()

    def scalare(query):
        cur.execute(query)
        row = cur.fetchone()
        assert row is not None
        return row[0]

    stats = {
        "npc_totali": scalare("SELECT COUNT(*) FROM npc"),
        "npc_vivi": scalare("SELECT COUNT(*) FROM npc WHERE stato = 'vivo'"),
        "quest_attive": scalare("SELECT COUNT(*) FROM quest WHERE stato = 'attiva'"),
        "quest_completate": scalare("SELECT COUNT(*) FROM quest WHERE stato = 'completata'"),
        "fazioni_totali": scalare("SELECT COUNT(*) FROM fazioni WHERE attiva = 1"),
        "locations_totali": scalare("SELECT COUNT(*) FROM locations"),
        "sessioni_giocate": scalare("SELECT COALESCE(MAX(sessione), 0) FROM eventi"),
    }
    cur.close()
    conn.close()
    return stats


# QUERY DI SCRITTURA

def upsert_fazione(nome, **kwargs):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM fazioni WHERE nome = ?", (nome,))
    existing = cur.fetchone()
    if existing:
        if kwargs:
            set_clause = ", ".join(f"{k} = ?" for k in kwargs)
            cur.execute(f"UPDATE fazioni SET {set_clause} WHERE nome = ?", (*kwargs.values(), nome))
    else:
        cols = ", ".join(["nome"] + list(kwargs.keys()))
        placeholders = ", ".join(["?"] * (1 + len(kwargs)))
        cur.execute(f"INSERT INTO fazioni ({cols}) VALUES ({placeholders})", (nome, *kwargs.values()))
    conn.commit()
    cur.close()
    conn.close()


def upsert_location(nome, **kwargs):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM locations WHERE nome = ?", (nome,))
    existing = cur.fetchone()
    if existing:
        if kwargs:
            set_clause = ", ".join(f"{k} = ?" for k in kwargs)
            cur.execute(f"UPDATE locations SET {set_clause} WHERE nome = ?", (*kwargs.values(), nome))
    else:
        cols = ", ".join(["nome"] + list(kwargs.keys()))
        placeholders = ", ".join(["?"] * (1 + len(kwargs)))
        cur.execute(f"INSERT INTO locations ({cols}) VALUES ({placeholders})", (nome, *kwargs.values()))
    conn.commit()
    cur.close()
    conn.close()


def upsert_npc(nome, **kwargs):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM npc WHERE nome = ?", (nome,))
    existing = cur.fetchone()
    if existing:
        if kwargs:
            set_clause = ", ".join(f"{k} = ?" for k in kwargs)
            cur.execute(f"UPDATE npc SET {set_clause} WHERE nome = ?", (*kwargs.values(), nome))
        npc_id = existing[0]
    else:
        cols = ", ".join(["nome"] + list(kwargs.keys()))
        placeholders = ", ".join(["?"] * (1 + len(kwargs)))
        cur.execute(
            f"INSERT INTO npc ({cols}) VALUES ({placeholders})",
            (nome, *kwargs.values())
        )
        npc_id = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return npc_id


def upsert_quest(nome, **kwargs):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM quest WHERE nome = ?", (nome,))
    existing = cur.fetchone()
    if existing:
        if kwargs:
            set_clause = ", ".join(f"{k} = ?" for k in kwargs)
            cur.execute(f"UPDATE quest SET {set_clause} WHERE nome = ?", (*kwargs.values(), nome))
        quest_id = existing[0]
    else:
        cols = ", ".join(["nome"] + list(kwargs.keys()))
        placeholders = ", ".join(["?"] * (1 + len(kwargs)))
        cur.execute(
            f"INSERT INTO quest ({cols}) VALUES ({placeholders})",
            (nome, *kwargs.values())
        )
        quest_id = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return quest_id


def aggiorna_quest(quest_id, nome, **kwargs):
    conn = get_connection()
    cur = conn.cursor()
    kwargs["nome"] = nome
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    cur.execute(f"UPDATE quest SET {set_clause} WHERE id = ?", (*kwargs.values(), quest_id))
    conn.commit()
    cur.close()
    conn.close()


def link_npc_quest(quest_id, npc_id, ruolo_nella_quest=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO quest_npc (quest_id, npc_id, ruolo_nella_quest)
           VALUES (?, ?, ?)
               ON CONFLICT (quest_id, npc_id) DO UPDATE SET ruolo_nella_quest = excluded.ruolo_nella_quest""",
        (quest_id, npc_id, ruolo_nella_quest)
    )
    conn.commit()
    cur.close()
    conn.close()


def unlink_npc_quest(quest_id, npc_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM quest_npc WHERE quest_id = ? AND npc_id = ?",
        (quest_id, npc_id)
    )
    conn.commit()
    cur.close()
    conn.close()


def add_evento(sessione, riassunto, conseguenze_attive=None, location_id=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO eventi (sessione, riassunto, conseguenze_attive, location_id)
           VALUES (?, ?, ?, ?)""",
        (sessione, riassunto, conseguenze_attive, location_id)
    )
    conn.commit()
    cur.close()
    conn.close()




def add_fatto_accertato(descrizione, sessione=None, rilevanza='media', note=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO fatti_accertati (descrizione, sessione, rilevanza, note)
           VALUES (?, ?, ?, ?)""",
        (descrizione, sessione, rilevanza, note)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_sessione_completata(numero_sessione):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT completata FROM sessioni_copioni WHERE numero_sessione = ?",
        (numero_sessione,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return bool(row[0]) if row else False


def get_sessioni_completate_map():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT numero_sessione, completata FROM sessioni_copioni")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {r[0]: bool(r[1]) for r in rows}


def set_sessione_completata(numero_sessione, completata):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO sessioni_copioni (numero_sessione, completata)
           VALUES (?, ?)
               ON CONFLICT (numero_sessione) DO UPDATE SET completata = excluded.completata""",
        (numero_sessione, 1 if completata else 0),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_npc_visibile(npc_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT visibile_giocatrice FROM npc WHERE id = ?", (npc_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return bool(row[0]) if row else False


def set_npc_visibile(npc_id, visibile):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE npc SET visibile_giocatrice = ? WHERE id = ?", (1 if visibile else 0, npc_id))
    conn.commit()
    cur.close()
    conn.close()


def get_location_visibile(location_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT visibile_giocatrice FROM locations WHERE id = ?", (location_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return bool(row[0]) if row else False


def set_location_visibile(location_id, visibile):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE locations SET visibile_giocatrice = ? WHERE id = ?", (1 if visibile else 0, location_id))
    conn.commit()
    cur.close()
    conn.close()


def get_quest_visibile(quest_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT visibile_giocatrice FROM quest WHERE id = ?", (quest_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return bool(row[0]) if row else False


def set_quest_visibile(quest_id, visibile):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE quest SET visibile_giocatrice = ? WHERE id = ?", (1 if visibile else 0, quest_id))
    conn.commit()
    cur.close()
    conn.close()


def get_password_master():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT password_master FROM impostazioni_sicurezza WHERE id = 1")
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


def set_password_master(password_hash):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM impostazioni_sicurezza WHERE id = 1")
    if cur.fetchone():
        cur.execute("UPDATE impostazioni_sicurezza SET password_master = ? WHERE id = 1", (password_hash,))
    else:
        cur.execute("INSERT INTO impostazioni_sicurezza (id, password_master) VALUES (1, ?)", (password_hash,))
    conn.commit()
    cur.close()
    conn.close()


def get_palette():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT variabile, valore FROM palette_personalizzata")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {r[0]: r[1] for r in rows}


def set_palette_colore(variabile, valore):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO palette_personalizzata (variabile, valore)
           VALUES (?, ?)
               ON CONFLICT (variabile) DO UPDATE SET valore = excluded.valore""",
        (variabile, valore),
    )
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    init_db()
