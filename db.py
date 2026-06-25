import os
import psycopg2
import psycopg2.extras

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema_postgres.sql")

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "Variabile d'ambiente DATABASE_URL non impostata. "
        "Vedi il commento in cima a db.py per come configurarla."
    )

def get_connection():
    """Ritorna una connessione Postgres. Il cursore va creato con
    cursor_factory=RealDictCursor per ottenere righe-come-dizionario
    (vedi _dictify sotto, usata da tutte le funzioni di lettura)."""
    return psycopg2.connect(DATABASE_URL)


def _dictify(rows):
    """psycopg2.extras.RealDictRow si comporta già come un dict, ma lo
    convertiamo esplicitamente a dict puro per restare coerenti con
    l'interfaccia precedente (dict(r) su sqlite3.Row)."""
    return [dict(r) for r in rows]


def init_db():
    """Crea le tabelle (se non esistono) applicando lo schema.
    Sicuro da rilanciare più volte (CREATE TABLE IF NOT EXISTS)."""
    conn = get_connection()
    cur = conn.cursor()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    cur.execute(schema)
    conn.commit()
    cur.close()
    conn.close()
    print("Database inizializzato su Supabase.")


# ------------------------------------------------------------------
# QUERY DI LETTURA (per generare il context pack)
# ------------------------------------------------------------------

def get_location_by_nome(nome):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM locations WHERE nome ILIKE %s", (f"%{nome}%",))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_npc_in_location(location_id):
    """NPC attualmente presenti in una location, solo se vivi/rilevanti."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT npc.*, fazioni.nome as fazione_nome
           FROM npc
                    LEFT JOIN fazioni ON npc.fazione_id = fazioni.id
           WHERE npc.location_attuale_id = %s AND npc.stato != 'morto'""",
        (location_id,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_quest_attive(location_id=None):
    """Quest attive, opzionalmente filtrate per location."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if location_id:
        cur.execute(
            "SELECT * FROM quest WHERE stato = 'attiva' AND (location_id = %s OR location_id IS NULL)",
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
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT npc.*, quest_npc.ruolo_nella_quest
           FROM quest_npc
                    JOIN npc ON quest_npc.npc_id = npc.id
           WHERE quest_npc.quest_id = %s""",
        (quest_id,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_eventi_recenti(n=5):
    """Ultimi N eventi per numero di sessione decrescente."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM eventi ORDER BY sessione DESC, id DESC LIMIT %s", (n,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_pg_stato():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM pg_stato WHERE id = 1")
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_fazioni_rilevanti(location_id=None):
    """Tutte le fazioni attive; se data una location, prima quella controllante."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM fazioni WHERE attiva = 1")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_fatti_accertati(rilevanza_minima=None):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if rilevanza_minima:
        cur.execute(
            "SELECT * FROM fatti_accertati WHERE rilevanza = %s ORDER BY sessione DESC",
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
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, nome, tipo FROM locations ORDER BY nome")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_all_quest(stato=None):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if stato:
        cur.execute("SELECT id, nome, tipo, stato FROM quest WHERE stato = %s ORDER BY nome", (stato,))
    else:
        cur.execute("SELECT id, nome, tipo, stato FROM quest ORDER BY nome")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_all_tracce_audio(categoria=None):
    """Tutte le tracce, opzionalmente filtrate per categoria."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if categoria:
        cur.execute("SELECT * FROM tracce_audio WHERE categoria = %s ORDER BY nome", (categoria,))
    else:
        cur.execute("SELECT * FROM tracce_audio ORDER BY categoria, nome")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_tracce_audio_per_location(location_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM tracce_audio WHERE location_id = %s ORDER BY nome", (location_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_tracce_audio_per_quest(quest_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM tracce_audio WHERE quest_id = %s ORDER BY nome", (quest_id,))
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
           VALUES (%s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
        (nome, categoria, youtube_id, timestamp_inizio, note, location_id, quest_id),
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return new_id


def update_traccia_audio(traccia_id, **campi):
    if not campi:
        return
    colonne = ", ".join(f"{k} = %s" for k in campi)
    valori = list(campi.values()) + [traccia_id]
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"UPDATE tracce_audio SET {colonne} WHERE id = %s", valori)
    conn.commit()
    cur.close()
    conn.close()


def delete_traccia_audio(traccia_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tracce_audio WHERE id = %s", (traccia_id,))
    conn.commit()
    cur.close()
    conn.close()


# ------------------------------------------------------------------
# QUERY COMPLETE PER LA DASHBOARD WEB (tutti i campi, nessun filtro)
# ------------------------------------------------------------------

def get_all_npc_full():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT npc.*, fazioni.nome as fazione_nome, locations.nome as location_nome
           FROM npc
                    LEFT JOIN fazioni ON npc.fazione_id = fazioni.id
                    LEFT JOIN locations ON npc.location_attuale_id = locations.id
           WHERE npc.id = %s""",
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
           WHERE quest_npc.npc_id = %s""",
        (npc_id,)
    )
    npc["quest_collegate"] = _dictify(cur.fetchall())
    cur.close()
    conn.close()
    return npc


def get_all_fazioni_full():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM fazioni ORDER BY nome")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_fazione_full(fazione_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM fazioni WHERE id = %s", (fazione_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return None
    fazione = dict(row)
    cur.execute("SELECT id, nome, stato FROM npc WHERE fazione_id = %s", (fazione_id,))
    fazione["membri"] = _dictify(cur.fetchall())
    cur.execute("SELECT id, nome FROM locations WHERE fazione_controllante_id = %s", (fazione_id,))
    fazione["territori"] = _dictify(cur.fetchall())
    cur.close()
    conn.close()
    return fazione


def get_all_quest_full():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT quest.*, locations.nome as location_nome
           FROM quest LEFT JOIN locations ON quest.location_id = locations.id
           WHERE quest.id = %s""",
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
           WHERE quest_npc.quest_id = %s""",
        (quest_id,)
    )
    quest["npc_coinvolti"] = _dictify(cur.fetchall())
    cur.close()
    conn.close()
    return quest


def get_all_locations_full():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT locations.*, fazioni.nome as fazione_nome
           FROM locations LEFT JOIN fazioni ON locations.fazione_controllante_id = fazioni.id
           WHERE locations.id = %s""",
        (location_id,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return None
    location = dict(row)
    cur.execute("SELECT id, nome, stato FROM npc WHERE location_attuale_id = %s", (location_id,))
    location["npc_presenti"] = _dictify(cur.fetchall())
    cur.execute("SELECT id, nome, stato FROM quest WHERE location_id = %s", (location_id,))
    location["quest_collegate"] = _dictify(cur.fetchall())
    cur.execute(
        "SELECT id, sessione, riassunto FROM eventi WHERE location_id = %s ORDER BY sessione DESC",
        (location_id,)
    )
    location["eventi_qui"] = _dictify(cur.fetchall())
    cur.close()
    conn.close()
    return location


def get_all_eventi():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM fatti_accertati ORDER BY sessione DESC, id DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def delete_record(tabella, record_id):
    """Cancellazione generica per id, usata dalle route di delete della dashboard."""
    tabelle_consentite = {"npc", "fazioni", "locations", "quest", "eventi", "fatti_accertati"}
    if tabella not in tabelle_consentite:
        raise ValueError(f"Tabella non consentita: {tabella}")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {tabella} WHERE id = %s", (record_id,))
    conn.commit()
    cur.close()
    conn.close()


def get_stats_riepilogo():
    """Numeri di riepilogo per la home della dashboard."""
    conn = get_connection()
    cur = conn.cursor()

    def scalare(query):
        cur.execute(query)
        return cur.fetchone()[0]

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


# ------------------------------------------------------------------
# QUERY DI SCRITTURA (per popolare/aggiornare)
# ------------------------------------------------------------------

def upsert_fazione(nome, **kwargs):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM fazioni WHERE nome = %s", (nome,))
    existing = cur.fetchone()
    if existing:
        if kwargs:
            set_clause = ", ".join(f"{k} = %s" for k in kwargs)
            cur.execute(f"UPDATE fazioni SET {set_clause} WHERE nome = %s", (*kwargs.values(), nome))
    else:
        cols = ", ".join(["nome"] + list(kwargs.keys()))
        placeholders = ", ".join(["%s"] * (1 + len(kwargs)))
        cur.execute(f"INSERT INTO fazioni ({cols}) VALUES ({placeholders})", (nome, *kwargs.values()))
    conn.commit()
    cur.close()
    conn.close()


def upsert_location(nome, **kwargs):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM locations WHERE nome = %s", (nome,))
    existing = cur.fetchone()
    if existing:
        if kwargs:
            set_clause = ", ".join(f"{k} = %s" for k in kwargs)
            cur.execute(f"UPDATE locations SET {set_clause} WHERE nome = %s", (*kwargs.values(), nome))
    else:
        cols = ", ".join(["nome"] + list(kwargs.keys()))
        placeholders = ", ".join(["%s"] * (1 + len(kwargs)))
        cur.execute(f"INSERT INTO locations ({cols}) VALUES ({placeholders})", (nome, *kwargs.values()))
    conn.commit()
    cur.close()
    conn.close()


def upsert_npc(nome, **kwargs):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM npc WHERE nome = %s", (nome,))
    existing = cur.fetchone()
    if existing:
        if kwargs:
            set_clause = ", ".join(f"{k} = %s" for k in kwargs)
            cur.execute(f"UPDATE npc SET {set_clause} WHERE nome = %s", (*kwargs.values(), nome))
        npc_id = existing[0]
    else:
        cols = ", ".join(["nome"] + list(kwargs.keys()))
        placeholders = ", ".join(["%s"] * (1 + len(kwargs)))
        cur.execute(
            f"INSERT INTO npc ({cols}) VALUES ({placeholders}) RETURNING id",
            (nome, *kwargs.values())
        )
        npc_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return npc_id


def upsert_quest(nome, **kwargs):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM quest WHERE nome = %s", (nome,))
    existing = cur.fetchone()
    if existing:
        if kwargs:
            set_clause = ", ".join(f"{k} = %s" for k in kwargs)
            cur.execute(f"UPDATE quest SET {set_clause} WHERE nome = %s", (*kwargs.values(), nome))
        quest_id = existing[0]
    else:
        cols = ", ".join(["nome"] + list(kwargs.keys()))
        placeholders = ", ".join(["%s"] * (1 + len(kwargs)))
        cur.execute(
            f"INSERT INTO quest ({cols}) VALUES ({placeholders}) RETURNING id",
            (nome, *kwargs.values())
        )
        quest_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return quest_id


def link_npc_quest(quest_id, npc_id, ruolo_nella_quest=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO quest_npc (quest_id, npc_id, ruolo_nella_quest)
           VALUES (%s, %s, %s)
               ON CONFLICT (quest_id, npc_id) DO UPDATE SET ruolo_nella_quest = excluded.ruolo_nella_quest""",
        (quest_id, npc_id, ruolo_nella_quest)
    )
    conn.commit()
    cur.close()
    conn.close()


def add_evento(sessione, riassunto, conseguenze_attive=None, location_id=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO eventi (sessione, riassunto, conseguenze_attive, location_id)
           VALUES (%s, %s, %s, %s)""",
        (sessione, riassunto, conseguenze_attive, location_id)
    )
    conn.commit()
    cur.close()
    conn.close()


def set_pg_stato(**kwargs):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM pg_stato WHERE id = 1")
    existing = cur.fetchone()
    if existing:
        if kwargs:
            set_clause = ", ".join(f"{k} = %s" for k in kwargs)
            cur.execute(f"UPDATE pg_stato SET {set_clause} WHERE id = 1", tuple(kwargs.values()))
    else:
        cols = ", ".join(["id"] + list(kwargs.keys()))
        placeholders = ", ".join(["%s"] * (1 + len(kwargs)))
        cur.execute(f"INSERT INTO pg_stato ({cols}) VALUES ({placeholders})", (1, *kwargs.values()))
    conn.commit()
    cur.close()
    conn.close()


def add_fatto_accertato(descrizione, sessione=None, rilevanza='media', note=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO fatti_accertati (descrizione, sessione, rilevanza, note)
           VALUES (%s, %s, %s, %s)""",
        (descrizione, sessione, rilevanza, note)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_sessione_completata(numero_sessione):
    """True/False se la sessione è marcata come completata.
    Se non esiste ancora una riga (sessione mai toccata), default False."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT completata FROM sessioni_copioni WHERE numero_sessione = %s",
        (numero_sessione,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return bool(row[0]) if row else False


def get_sessioni_completate_map():
    """Dict {numero_sessione: bool} per TUTTE le sessioni che hanno una riga
    nella tabella. Comodo per l'indice, per non fare una query per ogni
    sessione elencata (N+1 query)."""
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
           VALUES (%s, %s)
               ON CONFLICT (numero_sessione) DO UPDATE SET completata = excluded.completata""",
        (numero_sessione, 1 if completata else 0),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_npc_visibile(npc_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT visibile_giocatrice FROM npc WHERE id = %s", (npc_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return bool(row[0]) if row else False


def set_npc_visibile(npc_id, visibile):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE npc SET visibile_giocatrice = %s WHERE id = %s", (1 if visibile else 0, npc_id))
    conn.commit()
    cur.close()
    conn.close()


def get_location_visibile(location_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT visibile_giocatrice FROM locations WHERE id = %s", (location_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return bool(row[0]) if row else False


def set_location_visibile(location_id, visibile):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE locations SET visibile_giocatrice = %s WHERE id = %s", (1 if visibile else 0, location_id))
    conn.commit()
    cur.close()
    conn.close()


def get_quest_visibile(quest_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT visibile_giocatrice FROM quest WHERE id = %s", (quest_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return bool(row[0]) if row else False


def set_quest_visibile(quest_id, visibile):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE quest SET visibile_giocatrice = %s WHERE id = %s", (1 if visibile else 0, quest_id))
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
        cur.execute("UPDATE impostazioni_sicurezza SET password_master = %s WHERE id = 1", (password_hash,))
    else:
        cur.execute("INSERT INTO impostazioni_sicurezza (id, password_master) VALUES (1, %s)", (password_hash,))
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    init_db()