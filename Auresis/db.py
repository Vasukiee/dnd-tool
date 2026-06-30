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


def get_all_tracce_audio(tag=None):
    """Tutte le tracce con la lista dei loro tag, opzionalmente filtrate per un tag."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if tag:
        cur.execute(
            """
            SELECT t.*,
                   ARRAY_AGG(ta.nome ORDER BY ta.nome) FILTER (WHERE ta.nome IS NOT NULL) AS tags
            FROM tracce_audio t
            LEFT JOIN traccia_audio_tag tat ON tat.traccia_id = t.id
            LEFT JOIN tag_audio ta ON ta.id = tat.tag_id
            WHERE t.id IN (
                SELECT tat2.traccia_id FROM traccia_audio_tag tat2
                JOIN tag_audio ta2 ON ta2.id = tat2.tag_id
                WHERE LOWER(ta2.nome) = LOWER(%s)
            )
            GROUP BY t.id
            ORDER BY t.nome
            """,
            (tag,),
        )
    else:
        cur.execute(
            """
            SELECT t.*,
                   ARRAY_AGG(ta.nome ORDER BY ta.nome) FILTER (WHERE ta.nome IS NOT NULL) AS tags
            FROM tracce_audio t
            LEFT JOIN traccia_audio_tag tat ON tat.traccia_id = t.id
            LEFT JOIN tag_audio ta ON ta.id = tat.tag_id
            GROUP BY t.id
            ORDER BY t.nome
            """
        )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    result = _dictify(rows)
    for r in result:
        if r.get('tags') is None:
            r['tags'] = []
    return result


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


def get_tutti_tag_audio():
    """Tutti i tag esistenti ordinati alfabeticamente."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT nome FROM tag_audio ORDER BY nome")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]


def get_o_crea_tag(nome):
    """Cerca un tag per nome (case-insensitive, trim). Lo crea se non esiste. Ritorna l'id."""
    nome = nome.strip()
    if not nome:
        return None
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM tag_audio WHERE LOWER(nome) = LOWER(%s)", (nome,))
    row = cur.fetchone()
    if row:
        tag_id = row[0]
    else:
        cur.execute("INSERT INTO tag_audio (nome) VALUES (%s) RETURNING id", (nome,))
        tag_id = cur.fetchone()[0]
        conn.commit()
    cur.close()
    conn.close()
    return tag_id


def get_tag_di_traccia(traccia_id):
    """Lista di nomi tag associati a una traccia."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT ta.nome FROM tag_audio ta
           JOIN traccia_audio_tag tat ON tat.tag_id = ta.id
           WHERE tat.traccia_id = %s ORDER BY ta.nome""",
        (traccia_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]


def set_tag_traccia(traccia_id, lista_tag_id):
    """Sostituisce tutti i tag della traccia con la lista fornita di id."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM traccia_audio_tag WHERE traccia_id = %s", (traccia_id,))
    for tag_id in lista_tag_id:
        cur.execute(
            "INSERT INTO traccia_audio_tag (traccia_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (traccia_id, tag_id),
        )
    conn.commit()
    cur.close()
    conn.close()


def get_traccia_audio(traccia_id):
    """Singola traccia per id."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM tracce_audio WHERE id = %s", (traccia_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_tag_con_conteggio_uso():
    """Tutti i tag con quante tracce li usano."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT ta.id, ta.nome, COUNT(tat.traccia_id) AS uso
           FROM tag_audio ta
           LEFT JOIN traccia_audio_tag tat ON tat.tag_id = ta.id
           GROUP BY ta.id, ta.nome
           ORDER BY ta.nome"""
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def delete_tag(tag_id):
    """Elimina un tag (le associazioni in traccia_audio_tag vengono rimosse via ON DELETE CASCADE)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tag_audio WHERE id = %s", (tag_id,))
    conn.commit()
    cur.close()
    conn.close()


def get_file_audio_disponibili():
    """Lista ordinata dei file audio in static/audio/. Crea la cartella se mancante."""
    audio_dir = os.path.join(os.path.dirname(__file__), "static", "audio")
    os.makedirs(audio_dir, exist_ok=True)
    estensioni = {".mp3", ".ogg", ".wav", ".m4a"}
    try:
        files = [
            f for f in os.listdir(audio_dir)
            if os.path.splitext(f)[1].lower() in estensioni
        ]
        return sorted(files)
    except OSError:
        return []


def add_traccia_audio(nome, categoria, youtube_id=None, timestamp_inizio=0,
                      note=None, location_id=None, quest_id=None,
                      tipo_sorgente='youtube', file_path=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO tracce_audio
           (nome, categoria, tipo_sorgente, youtube_id, file_path, timestamp_inizio, note, location_id, quest_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
        (nome, categoria, tipo_sorgente, youtube_id, file_path, timestamp_inizio, note, location_id, quest_id),
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


# ------------------------------------------------------------------
# INDAGINI
# ------------------------------------------------------------------

def get_all_indagini():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM indagini ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_indagine(indagine_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM indagini WHERE id = %s", (indagine_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def add_indagine(titolo, descrizione=None, attiva=True):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO indagini (titolo, descrizione, attiva) VALUES (%s, %s, %s) RETURNING id",
        (titolo, descrizione, attiva),
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return new_id


def update_indagine(indagine_id, **kwargs):
    if not kwargs:
        return
    cols = ", ".join(f"{k} = %s" for k in kwargs)
    vals = list(kwargs.values()) + [indagine_id]
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"UPDATE indagini SET {cols} WHERE id = %s", vals)
    conn.commit()
    cur.close()
    conn.close()


def delete_indagine(indagine_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM indagini WHERE id = %s", (indagine_id,))
    conn.commit()
    cur.close()
    conn.close()


def get_nodi_indagine(indagine_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM nodi_indagine WHERE indagine_id = %s ORDER BY numero_nodo",
        (indagine_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_nodo(nodo_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM nodi_indagine WHERE id = %s", (nodo_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def calcola_profondita_nodi(indagine_id):
    """Restituisce {nodo_id: livello_sfx} con profondità massima dal DAG, cap a 3.
    Nodi isolati (senza genitori né figli) ricevono livello 1."""
    from collections import deque
    nodi = get_nodi_indagine(indagine_id)
    collegamenti = get_collegamenti(indagine_id)
    if not nodi:
        return {}
    nodo_ids = [n["id"] for n in nodi]
    figli_di = {}
    genitori_di = {}
    for c in collegamenti:
        pid, fid = c["nodo_genitore_id"], c["nodo_figlio_id"]
        figli_di.setdefault(pid, []).append(fid)
        genitori_di.setdefault(fid, []).append(pid)
    # Kahn topological sort
    in_degree = {nid: len(genitori_di.get(nid, [])) for nid in nodo_ids}
    queue = deque(nid for nid in nodo_ids if in_degree[nid] == 0)
    topo_order = []
    while queue:
        nid = queue.popleft()
        topo_order.append(nid)
        for fid in figli_di.get(nid, []):
            in_degree[fid] -= 1
            if in_degree[fid] == 0:
                queue.append(fid)
    profondita = {nid: 0 for nid in nodo_ids}
    for nid in nodo_ids:
        if nid not in genitori_di:
            profondita[nid] = 1
    for nid in topo_order:
        for fid in figli_di.get(nid, []):
            profondita[fid] = max(profondita[fid], profondita[nid] + 1)
    return {nid: min(max(profondita.get(nid, 1), 1), 3) for nid in nodo_ids}


def ricalcola_livelli_sfx(indagine_id, forza_tutti=False):
    """Ricalcola e aggiorna livello_sfx sui nodi non marcati come manuali.
    Con forza_tutti=True aggiorna anche quelli manuali."""
    livelli = calcola_profondita_nodi(indagine_id)
    if not livelli:
        return
    conn = get_connection()
    cur = conn.cursor()
    if forza_tutti:
        nodo_ids_da_aggiornare = list(livelli.keys())
    else:
        cur.execute(
            "SELECT id FROM nodi_indagine WHERE indagine_id = %s AND livello_sfx_manuale = FALSE",
            (indagine_id,),
        )
        nodo_ids_da_aggiornare = [r[0] for r in cur.fetchall()]
    for nid in nodo_ids_da_aggiornare:
        if nid in livelli:
            cur.execute(
                "UPDATE nodi_indagine SET livello_sfx = %s WHERE id = %s",
                (livelli[nid], nid),
            )
    conn.commit()
    cur.close()
    conn.close()


def ricalcola_livello_sfx_singolo(nodo_id):
    """Ricalcola e aggiorna livello_sfx per un solo nodo, resettando il flag manuale."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT indagine_id FROM nodi_indagine WHERE id = %s", (nodo_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return
    indagine_id = row[0]
    livelli = calcola_profondita_nodi(indagine_id)
    livello = livelli.get(nodo_id, 1)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE nodi_indagine SET livello_sfx = %s, livello_sfx_manuale = FALSE WHERE id = %s",
        (livello, nodo_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def add_nodo(indagine_id, numero_nodo, titolo, descrizione=None,
             immagine_url=None, regola_sblocco='TUTTI', tipo_speciale=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO nodi_indagine
           (indagine_id, numero_nodo, titolo, descrizione, immagine_url, regola_sblocco, tipo_speciale)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (indagine_id, numero_nodo, titolo, descrizione, immagine_url, regola_sblocco, tipo_speciale),
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    ricalcola_livelli_sfx(indagine_id)
    return new_id


def update_nodo(nodo_id, **kwargs):
    if not kwargs:
        return
    cols = ", ".join(f"{k} = %s" for k in kwargs)
    vals = list(kwargs.values()) + [nodo_id]
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"UPDATE nodi_indagine SET {cols} WHERE id = %s", vals)
    conn.commit()
    cur.close()
    conn.close()


def delete_nodo(nodo_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM nodi_indagine WHERE id = %s", (nodo_id,))
    conn.commit()
    cur.close()
    conn.close()


def get_collegamenti(indagine_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM collegamenti_nodi WHERE indagine_id = %s ORDER BY id",
        (indagine_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def add_collegamento(indagine_id, nodo_genitore_id, nodo_figlio_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO collegamenti_nodi (indagine_id, nodo_genitore_id, nodo_figlio_id)
           VALUES (%s, %s, %s) RETURNING id""",
        (indagine_id, nodo_genitore_id, nodo_figlio_id),
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    ricalcola_livelli_sfx(indagine_id)
    return new_id


def delete_collegamento(collegamento_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT indagine_id FROM collegamenti_nodi WHERE id = %s", (collegamento_id,))
    row = cur.fetchone()
    indagine_id = row[0] if row else None
    cur.execute("DELETE FROM collegamenti_nodi WHERE id = %s", (collegamento_id,))
    conn.commit()
    cur.close()
    conn.close()
    if indagine_id:
        ricalcola_livelli_sfx(indagine_id)


# ------------------------------------------------------------------
# CRONOLOGIE INDAGINE
# ------------------------------------------------------------------

def get_cronologie_indagine(indagine_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM cronologie_indagine WHERE indagine_id = %s ORDER BY creata_il DESC",
        (indagine_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return _dictify(rows)


def get_cronologia_attiva(indagine_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM cronologie_indagine WHERE indagine_id = %s AND attiva = TRUE LIMIT 1",
        (indagine_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_stato_nodi_cronologia(cronologia_id):
    """Ritorna {nodo_id: {scoperto, sbloccato_manualmente}} per la cronologia."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT nodo_id, scoperto, sbloccato_manualmente FROM stato_nodi_cronologia WHERE cronologia_id = %s",
        (cronologia_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {r["nodo_id"]: {"scoperto": r["scoperto"], "sbloccato_manualmente": r["sbloccato_manualmente"]} for r in rows}


def crea_cronologia(indagine_id, nome):
    """Crea una nuova cronologia attiva, disattivando quella corrente."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE cronologie_indagine SET attiva = FALSE WHERE indagine_id = %s AND attiva = TRUE",
        (indagine_id,),
    )
    cur.execute(
        "INSERT INTO cronologie_indagine (indagine_id, nome, attiva) VALUES (%s, %s, TRUE) RETURNING id, nome, creata_il",
        (indagine_id, nome),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {"id": row[0], "nome": row[1], "creata_il": row[2], "indagine_id": indagine_id, "attiva": True}


def disattiva_cronologia_attiva(indagine_id):
    """Imposta attiva=FALSE sulla cronologia corrente (reset lazy)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE cronologie_indagine SET attiva = FALSE WHERE indagine_id = %s AND attiva = TRUE",
        (indagine_id,),
    )
    conn.commit()
    cur.close()
    conn.close()


def attiva_cronologia(cronologia_id, indagine_id):
    """Switcha la cronologia attiva per l'indagine."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE cronologie_indagine SET attiva = FALSE WHERE indagine_id = %s",
        (indagine_id,),
    )
    cur.execute(
        "UPDATE cronologie_indagine SET attiva = TRUE WHERE id = %s",
        (cronologia_id,),
    )
    conn.commit()
    cur.close()
    conn.close()


def elimina_cronologia(cronologia_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM cronologie_indagine WHERE id = %s", (cronologia_id,))
    conn.commit()
    cur.close()
    conn.close()


def rinomina_cronologia(cronologia_id, nome):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE cronologie_indagine SET nome = %s WHERE id = %s", (nome, cronologia_id))
    conn.commit()
    cur.close()
    conn.close()


def avanza_scena_cronologia(cronologia_id, nuova_scena):
    """Aggiorna scena_corrente per la cronologia — chiamato dal GM manualmente."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE cronologie_indagine SET scena_corrente = %s WHERE id = %s",
        (nuova_scena, cronologia_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def sblocca_nodo(nodo_id, manuale, cronologia_id):
    """Segna un nodo come scoperto in una cronologia.
    I figli diretti diventeranno BLOCCATO_VISIBILE per effetto di _calcola_stati_nodi —
    nessuna propagazione automatica: ogni sblocco è manuale."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """INSERT INTO stato_nodi_cronologia (cronologia_id, nodo_id, scoperto, sbloccato_manualmente)
           VALUES (%s, %s, TRUE, %s)
           ON CONFLICT (cronologia_id, nodo_id)
           DO UPDATE SET scoperto = TRUE, sbloccato_manualmente = %s""",
        (cronologia_id, nodo_id, manuale, manuale),
    )

    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    init_db()