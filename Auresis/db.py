import base64
import datetime
import os
import secrets
import sqlite3

import psycopg2
import psycopg2.extras
import psycopg2.pool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

def is_sqlite():
    return not bool(DATABASE_URL)

def get_storage_mode():
    """Ritorna 'disk' o 'db'. Se non settato, default: 'disk' per SQLite, 'db' per Postgres."""
    mode = os.environ.get("STORAGE_MODE")
    if mode in ("disk", "db"):
        return mode
    return "disk" if is_sqlite() else "db"

_pg_pool = None


class _ConnessioneDalPool:
    """Proxy di una connessione Postgres: close() la restituisce al pool invece di chiuderla.

    putconn() esegue automaticamente il rollback delle transazioni rimaste aperte
    (es. dopo le sole letture), quindi le connessioni tornano al pool pulite.
    """

    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool
        self._restituita = False

    def close(self):
        if not self._restituita:
            self._restituita = True
            self._pool.putconn(self._conn)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _get_pg_connection():
    """Preleva una connessione dal pool, scartando quelle morte (pre-ping)."""
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = psycopg2.pool.ThreadedConnectionPool(1, 5, DATABASE_URL)
    for _ in range(2):
        conn = _pg_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return _ConnessioneDalPool(conn, _pg_pool)
        except psycopg2.Error:
            # connessione chiusa lato server (idle timeout): la scartiamo e riproviamo
            _pg_pool.putconn(conn, close=True)
    return _ConnessioneDalPool(_pg_pool.getconn(), _pg_pool)


def get_connection():
    """Ritorna una connessione Postgres (dal pool) o SQLite a seconda della configurazione."""
    if not is_sqlite():
        return _get_pg_connection()
    else:
        db_path = os.path.join(os.path.dirname(__file__), "campagna.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        original_cursor = conn.cursor
        def patched_cursor(*args, **kwargs):
            # Ignoriamo cursor_factory=... passato da psycopg2
            cur = original_cursor()
            original_execute = cur.execute
            
            def execute_wrapper(query, params=None):
                query = query.replace("%s", "?")
                query = query.replace(" ILIKE ", " LIKE ")
                query = query.replace(" NOW()", " CURRENT_TIMESTAMP")
                query = query.replace(" TRUE", " 1").replace(" FALSE", " 0")
                if params is not None:
                    return original_execute(query, params)
                return original_execute(query)
                
            cur.execute = execute_wrapper
            return cur
            
        conn.cursor = patched_cursor
        return conn

def _dictify(rows):
    """psycopg2.extras.RealDictRow o sqlite3.Row si comporta già come un dict, ma lo
    convertiamo esplicitamente a dict puro per coerenza."""
    return [dict(r) for r in rows]

def init_db():
    """Crea le tabelle (se non esistono) applicando lo schema appropriato."""
    conn = get_connection()
    cur = conn.cursor()
    schema_file = "schema.sql" if is_sqlite() else "schema_postgres.sql"
    schema_path = os.path.join(os.path.dirname(__file__), schema_file)
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = f.read()
    if is_sqlite():
        cur.executescript(schema)
    else:
        cur.execute(schema)
    conn.commit()
    cur.close()
    conn.close()
    print(f"Database inizializzato ({'SQLite' if is_sqlite() else 'Postgres'}).")

# --- IMPOSTAZIONI GLOBALI ---
def get_impostazione(chiave):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM impostazioni_globali WHERE chiave = %s", (chiave,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None

def set_impostazione_bytea(chiave, data, mime):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO impostazioni_globali (chiave, valore_bytea, valore_mime)
        VALUES (%s, %s, %s)
        ON CONFLICT (chiave) DO UPDATE SET 
            valore_bytea = EXCLUDED.valore_bytea,
            valore_mime = EXCLUDED.valore_mime
        """,
        (chiave, data, mime)
    )
    conn.commit()
    cur.close()
    conn.close()

def _assicura_tabella_impostazioni(cur):
    """Crea impostazioni_globali se manca (i db creati con schemi vecchi non la hanno)."""
    tipo_blob = "BLOB" if is_sqlite() else "BYTEA"
    cur.execute(
        f"""CREATE TABLE IF NOT EXISTS impostazioni_globali (
            chiave TEXT PRIMARY KEY,
            valore_text TEXT,
            valore_bytea {tipo_blob},
            valore_mime TEXT
        )"""
    )


def get_o_crea_secret_key():
    """Ritorna la SECRET_KEY persistente dell'app, generandola al primo avvio.

    Persistere la chiave (invece di os.urandom a ogni avvio) evita che le sessioni
    si invalidino a ogni riavvio e che i worker gunicorn abbiano chiavi diverse.
    """
    conn = get_connection()
    cur = conn.cursor()
    _assicura_tabella_impostazioni(cur)
    cur.execute("SELECT valore_text FROM impostazioni_globali WHERE chiave = %s", ("secret_key",))
    row = cur.fetchone()
    if row and row[0]:
        cur.close()
        conn.close()
        return row[0]

    nuova = secrets.token_hex(32)
    cur.execute(
        "INSERT INTO impostazioni_globali (chiave, valore_text) VALUES (%s, %s) ON CONFLICT (chiave) DO NOTHING",
        ("secret_key", nuova),
    )
    conn.commit()
    # Rilettura: se un altro worker ha generato la chiave nel frattempo, usiamo la sua
    cur.execute("SELECT valore_text FROM impostazioni_globali WHERE chiave = %s", ("secret_key",))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row and row[0] else nuova


# --- SIPARIO ---
def toggle_sipario(indagine_id):
    # Nota: assume esistenza di get_cronologia_attiva definita altrove
    cronologia = get_cronologia_attiva(indagine_id)
    if not cronologia:
        return False
    
    conn = get_connection()
    cur = conn.cursor()
    
    nuovo_stato = not cronologia.get("sipario_aperto", False)
    
    cur.execute(
        "UPDATE cronologie_indagine SET sipario_aperto = %s WHERE id = %s",
        (nuovo_stato, cronologia["id"])
    )
    conn.commit()
    cur.close()
    conn.close()
    return nuovo_stato

def toggle_sipario_globale():
    """Inverte lo stato del sipario per tutte le cronologie attive (solitamente 1)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, sipario_aperto FROM cronologie_indagine WHERE attiva = TRUE")
    rows = cur.fetchall()
    
    # Se ce ne sono di miste, li portiamo tutti a False o True, per semplicità invertiamo il primo trovato e applichiamo a tutti
    if not rows:
        cur.close()
        conn.close()
        return False
        
    nuovo_stato = not rows[0]["sipario_aperto"]
    ids = [r["id"] for r in rows]
    
    cur.execute(
        "UPDATE cronologie_indagine SET sipario_aperto = %s WHERE id = ANY(%s)",
        (nuovo_stato, ids)
    )
    conn.commit()
    cur.close()
    conn.close()
    return nuovo_stato

# --- RICERCA GLOBALE ---

# (tabella, campi di testo in cui cercare, colonna di visibilità per la modalità giocatrice)
_SPECIFICHE_RICERCA = [
    ("npc", ["nome", "ruolo", "descrizione_breve", "note_caratteriali", "note"], "visibile_giocatrice"),
    ("fazioni", ["nome", "nome_popolare", "ideologia", "territorio", "stato_attuale", "note"], None),
    ("locations", ["nome", "tipo", "descrizione_breve", "stato_attuale", "note"], "visibile_giocatrice"),
    ("quest", ["nome", "riassunto", "obiettivo_attuale", "note"], "visibile_giocatrice"),
    ("eventi", ["riassunto", "conseguenze_attive"], None),
    ("fatti_accertati", ["descrizione", "note"], None),
    ("indagini", ["titolo", "descrizione"], "visibile_giocatrice"),
    ("tracce_audio", ["nome", "note"], None),
]


def ricerca_globale(testo, solo_visibili=False):
    """Cerca il testo (case-insensitive) in tutte le entità della campagna.

    Ritorna {tabella: [righe]} con le sole tabelle che hanno risultati.
    Con solo_visibili=True (modalità giocatrice) filtra gli elementi nascosti.
    """
    like = f"%{testo}%"
    risultati = {}
    conn = get_connection()
    for tabella, campi, colonna_visibilita in _SPECIFICHE_RICERCA:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        condizioni = " OR ".join(f"{campo} ILIKE %s" for campo in campi)
        query = f"SELECT * FROM {tabella} WHERE ({condizioni})"
        if solo_visibili and colonna_visibilita:
            query += f" AND {colonna_visibilita} = TRUE"
        try:
            cur.execute(query, [like] * len(campi))
            righe = _dictify(cur.fetchall())
        except Exception:
            # tabella o colonna assente in questo schema: la saltiamo
            conn.rollback()
            righe = []
        cur.close()
        if righe:
            risultati[tabella] = righe
    conn.close()
    return risultati


# --- BACKUP / EXPORT ---

# impostazioni_sicurezza è esclusa di proposito: hash password e secret key
# non servono a ripristinare la campagna e non vanno messi in un file scaricabile.
_TABELLE_EXPORT = [
    "fazioni", "locations", "npc", "quest", "quest_npc", "eventi",
    "pg_stato", "fatti_accertati", "tracce_audio", "tag_audio",
    "traccia_audio_tag", "sessioni_copioni",
    "indagini", "nodi_indagine", "collegamenti_nodi", "cronologie_indagine",
    "stato_nodi_cronologia", "scene_indagine", "impostazioni_globali",
]


def _valore_esportabile(v):
    if isinstance(v, (bytes, memoryview)):
        return {"__base64__": base64.b64encode(bytes(v)).decode("ascii")}
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.isoformat()
    return v


def export_tutto():
    """Dump di tutte le tabelle in un dict JSON-serializzabile, per il backup."""
    dump = {}
    conn = get_connection()
    for tabella in _TABELLE_EXPORT:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(f"SELECT * FROM {tabella}")
            righe = [
                {k: _valore_esportabile(v) for k, v in dict(r).items()}
                for r in cur.fetchall()
            ]
            if tabella == "impostazioni_globali":
                righe = [r for r in righe if r.get("chiave") != "secret_key"]
            dump[tabella] = righe
        except Exception:
            # tabella assente in questo schema (db creato con versioni vecchie)
            conn.rollback()
        cur.close()
    conn.close()
    return dump


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


def get_traccia_audio_by_nome(nome):
    """Cerca una traccia audio per nome (case-insensitive) per l'integrazione nei copioni."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # L'uso di ILIKE rende la ricerca insensibile a maiuscole/minuscole
    cur.execute("SELECT * FROM tracce_audio WHERE nome ILIKE %s LIMIT 1", (nome,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


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


def get_stats_riepilogo(solo_visibili=False):
    """Numeri di riepilogo per la home della dashboard.

    Con solo_visibili=True (modalità giocatrice) i conteggi contano solo
    gli elementi con visibile_giocatrice = TRUE, coerentemente con quanto
    mostrato nelle liste dell'interfaccia giocatrice.
    """
    conn = get_connection()
    cur = conn.cursor()

    def scalare(query):
        cur.execute(query)
        return cur.fetchone()[0]

    filtro_npc = " AND visibile_giocatrice = 1" if solo_visibili else ""
    filtro_quest = " AND visibile_giocatrice = 1" if solo_visibili else ""
    filtro_locations = " WHERE visibile_giocatrice = 1" if solo_visibili else ""

    stats = {
        "npc_totali": scalare(f"SELECT COUNT(*) FROM npc WHERE 1=1{filtro_npc}"),
        "npc_vivi": scalare(f"SELECT COUNT(*) FROM npc WHERE stato = 'vivo'{filtro_npc}"),
        "quest_attive": scalare(f"SELECT COUNT(*) FROM quest WHERE stato = 'attiva'{filtro_quest}"),
        "quest_completate": scalare(f"SELECT COUNT(*) FROM quest WHERE stato = 'completata'{filtro_quest}"),
        "fazioni_totali": scalare("SELECT COUNT(*) FROM fazioni WHERE attiva = 1"),
        "locations_totali": scalare(f"SELECT COUNT(*) FROM locations{filtro_locations}"),
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


def get_sessione_testo(numero_sessione):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT testo_md FROM sessioni_copioni WHERE numero_sessione = %s",
        (numero_sessione,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


def upsert_sessione_testo(numero_sessione, testo_md):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO sessioni_copioni (numero_sessione, testo_md, data_modifica)
           VALUES (%s, %s, NOW())
               ON CONFLICT (numero_sessione) DO UPDATE SET 
                  testo_md = excluded.testo_md,
                  data_modifica = NOW()""",
        (numero_sessione, testo_md),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_all_sessioni_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT numero_sessione FROM sessioni_copioni WHERE testo_md IS NOT NULL")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]


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


def _assicura_tabella_sicurezza(cur):
    """Crea impostazioni_sicurezza se manca (i db creati con schemi vecchi non la hanno)."""
    cur.execute(
        """CREATE TABLE IF NOT EXISTS impostazioni_sicurezza (
            id INTEGER PRIMARY KEY,
            password_master TEXT
        )"""
    )


def get_password_master():
    conn = get_connection()
    cur = conn.cursor()
    _assicura_tabella_sicurezza(cur)
    cur.execute("SELECT password_master FROM impostazioni_sicurezza WHERE id = 1")
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


def set_password_master(password_hash):
    conn = get_connection()
    cur = conn.cursor()
    _assicura_tabella_sicurezza(cur)
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

def get_all_indagini(solo_visibili=False):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if solo_visibili:
        cur.execute("SELECT * FROM indagini WHERE visibile_giocatrice = TRUE ORDER BY id DESC")
    else:
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


def add_indagine(titolo, descrizione=None, attiva=True, visibile_giocatrice=False):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO indagini (titolo, descrizione, attiva, visibile_giocatrice) VALUES (%s, %s, %s, %s) RETURNING id",
        (titolo, descrizione, attiva, visibile_giocatrice),
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


def get_scene_gifs(indagine_id):
    """Restituisce {numero_scena: {"gif_url", "has_file", "versione"}} per
    un'indagine. "has_file" indica che l'immagine è salvata nel DB (gif_data);
    "versione" è un epoch usato come cache-buster negli URL."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT numero_scena, gif_url,
                  (gif_data IS NOT NULL) AS has_file,
                  COALESCE(EXTRACT(EPOCH FROM gif_data_aggiornata)::bigint, 0) AS versione
           FROM scene_indagine WHERE indagine_id = %s""",
        (indagine_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {
        row["numero_scena"]: {
            "gif_url": row["gif_url"],
            "has_file": row["has_file"],
            "versione": row["versione"],
        }
        for row in rows
    }


def upsert_scena_gif(indagine_id, numero_scena, gif_url):
    """Salva o aggiorna l'URL (esterno) di sfondo per una scena.
    Rimuove l'eventuale immagine caricata nel DB: URL e file sono alternativi."""
    conn = get_connection()
    cur = conn.cursor()
    gif_val = gif_url.strip() if gif_url and gif_url.strip() else None
    cur.execute(
        """INSERT INTO scene_indagine (indagine_id, numero_scena, gif_url)
           VALUES (%s, %s, %s)
           ON CONFLICT (indagine_id, numero_scena)
           DO UPDATE SET gif_url = EXCLUDED.gif_url,
                         gif_data = NULL,
                         gif_mime = NULL,
                         gif_data_aggiornata = NULL""",
        (indagine_id, numero_scena, gif_val),
    )
    conn.commit()
    cur.close()
    conn.close()


def save_scena_gif_file(indagine_id, numero_scena, data, mime):
    """Salva i byte dell'immagine di sfondo nel DB (persistente tra i deploy,
    a differenza del filesystem di Render). Azzera l'eventuale gif_url."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO scene_indagine (indagine_id, numero_scena, gif_url, gif_data, gif_mime, gif_data_aggiornata)
           VALUES (%s, %s, NULL, %s, %s, NOW())
           ON CONFLICT (indagine_id, numero_scena)
           DO UPDATE SET gif_url = NULL,
                         gif_data = EXCLUDED.gif_data,
                         gif_mime = EXCLUDED.gif_mime,
                         gif_data_aggiornata = NOW()""",
        (indagine_id, numero_scena, psycopg2.Binary(data), mime),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_scena_gif_file(indagine_id, numero_scena):
    """Restituisce (data, mime) dell'immagine salvata nel DB, o None."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT gif_data, gif_mime FROM scene_indagine
           WHERE indagine_id = %s AND numero_scena = %s AND gif_data IS NOT NULL""",
        (indagine_id, numero_scena),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return bytes(row["gif_data"]), row["gif_mime"]


if __name__ == "__main__":
    init_db()
def set_sipario_aperto(cronologia_id, stato):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE cronologie_indagine SET sipario_aperto = %s WHERE id = %s", (stato, cronologia_id))
    conn.commit()
    cur.close()
    conn.close()
