-- ============================================================
-- SCHEMA DATABASE CAMPAGNA DND — VERSIONE POSTGRES (Supabase)
-- ============================================================
-- Convertito da schema.sql (SQLite). Stessa struttura logica,
-- sintassi adattata a Postgres. Differenze principali:
--   - INTEGER PRIMARY KEY AUTOINCREMENT -> GENERATED ALWAYS AS IDENTITY
--   - datetime('now') -> NOW()
--   - i FOREIGN KEY sono sempre attivi in Postgres, non serve PRAGMA
-- ============================================================

-- FAZIONI
CREATE TABLE IF NOT EXISTS fazioni (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    nome_popolare TEXT,
    ideologia TEXT,
    territorio TEXT,
    relazione_pg TEXT DEFAULT 'neutrale',
    stato_attuale TEXT,
    note TEXT,
    attiva INTEGER DEFAULT 1
);

-- LOCATIONS
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE,
    tipo TEXT,
    descrizione_breve TEXT,
    fazione_controllante_id INTEGER,
    location_padre_id INTEGER,
    stato_attuale TEXT,
    note TEXT,
    visibile_giocatrice INTEGER DEFAULT 0,
    FOREIGN KEY (fazione_controllante_id) REFERENCES fazioni(id),
    FOREIGN KEY (location_padre_id) REFERENCES locations(id)
);

-- NPC
CREATE TABLE IF NOT EXISTS npc (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome TEXT NOT NULL,
    ruolo TEXT,
    fazione_id INTEGER,
    location_attuale_id INTEGER,
    stato TEXT DEFAULT 'vivo',
    relazione_pg TEXT,
    descrizione_breve TEXT,
    note_caratteriali TEXT,
    livello_contaminazione INTEGER DEFAULT 0,
    ultima_apparizione_sessione INTEGER,
    note TEXT,
    visibile_giocatrice INTEGER DEFAULT 0,
    FOREIGN KEY (fazione_id) REFERENCES fazioni(id),
    FOREIGN KEY (location_attuale_id) REFERENCES locations(id)
);

-- QUEST
CREATE TABLE IF NOT EXISTS quest (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome TEXT NOT NULL,
    tipo TEXT DEFAULT 'side',
    stato TEXT DEFAULT 'attiva',
    location_id INTEGER,
    riassunto TEXT,
    obiettivo_attuale TEXT,
    sessione_inizio INTEGER,
    sessione_fine INTEGER,
    note TEXT,
    visibile_giocatrice INTEGER DEFAULT 0,
    FOREIGN KEY (location_id) REFERENCES locations(id)
);

-- Tabella ponte: NPC coinvolti in una quest (relazione molti-a-molti)
CREATE TABLE IF NOT EXISTS quest_npc (
    quest_id INTEGER NOT NULL,
    npc_id INTEGER NOT NULL,
    ruolo_nella_quest TEXT,
    PRIMARY KEY (quest_id, npc_id),
    FOREIGN KEY (quest_id) REFERENCES quest(id),
    FOREIGN KEY (npc_id) REFERENCES npc(id)
);

-- EVENTI (log di sessione, append-only)
CREATE TABLE IF NOT EXISTS eventi (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sessione INTEGER NOT NULL,
    riassunto TEXT NOT NULL,
    conseguenze_attive TEXT,
    location_id INTEGER,
    data_inserimento TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (location_id) REFERENCES locations(id)
);

-- STATO DEL PERSONAGGIO (singola riga aggiornata, single-player)
CREATE TABLE IF NOT EXISTS pg_stato (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    nome TEXT,
    condizione_fisica TEXT,
    ferite_attive TEXT,
    equipaggiamento TEXT,
    risorse TEXT,
    abilita_acquisite TEXT,
    sessione_corrente INTEGER DEFAULT 0,
    location_attuale_id INTEGER,
    note TEXT,
    FOREIGN KEY (location_attuale_id) REFERENCES locations(id)
);

-- FATTI ACCERTATI
CREATE TABLE IF NOT EXISTS fatti_accertati (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    descrizione TEXT NOT NULL,
    sessione INTEGER,
    rilevanza TEXT DEFAULT 'media',
    note TEXT
);

-- TRACCE AUDIO
CREATE TABLE IF NOT EXISTS tracce_audio (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome TEXT NOT NULL,
    categoria TEXT NOT NULL,
    youtube_id TEXT NOT NULL,
    timestamp_inizio INTEGER DEFAULT 0,
    note TEXT,
    location_id INTEGER,
    quest_id INTEGER,
    FOREIGN KEY (location_id) REFERENCES locations(id),
    FOREIGN KEY (quest_id) REFERENCES quest(id)
);

-- SESSIONI COPIONI (stato completata/mostrabile)
CREATE TABLE IF NOT EXISTS sessioni_copioni (
    numero_sessione INTEGER PRIMARY KEY,
    completata INTEGER DEFAULT 0
);

-- PASSWORD MASTER per il toggle modalità giocatrice
CREATE TABLE IF NOT EXISTS impostazioni_sicurezza (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    password_master TEXT
);

-- Migrazioni per DB già esistenti
ALTER TABLE npc ADD COLUMN IF NOT EXISTS visibile_giocatrice INTEGER DEFAULT 0;
ALTER TABLE locations ADD COLUMN IF NOT EXISTS visibile_giocatrice INTEGER DEFAULT 0;
ALTER TABLE quest ADD COLUMN IF NOT EXISTS visibile_giocatrice INTEGER DEFAULT 0;

-- Indici utili per le query di filtraggio più comuni
CREATE INDEX IF NOT EXISTS idx_npc_location ON npc(location_attuale_id);
CREATE INDEX IF NOT EXISTS idx_npc_stato ON npc(stato);
CREATE INDEX IF NOT EXISTS idx_quest_stato ON quest(stato);
CREATE INDEX IF NOT EXISTS idx_quest_location ON quest(location_id);
CREATE INDEX IF NOT EXISTS idx_eventi_sessione ON eventi(sessione);
CREATE INDEX IF NOT EXISTS idx_audio_categoria ON tracce_audio(categoria);
CREATE INDEX IF NOT EXISTS idx_audio_location ON tracce_audio(location_id);
CREATE INDEX IF NOT EXISTS idx_audio_quest ON tracce_audio(quest_id);
