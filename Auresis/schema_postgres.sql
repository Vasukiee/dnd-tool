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
CREATE TABLE IF NOT EXISTS palette_personalizzata (
    variabile VARCHAR(100) PRIMARY KEY,
    valore VARCHAR(50) NOT NULL
);

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
    tipo_sorgente TEXT NOT NULL DEFAULT 'youtube' CHECK (tipo_sorgente IN ('youtube', 'file')),
    youtube_id TEXT,
    file_path TEXT,
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
ALTER TABLE tracce_audio ALTER COLUMN youtube_id DROP NOT NULL;
ALTER TABLE tracce_audio ADD COLUMN IF NOT EXISTS tipo_sorgente TEXT NOT NULL DEFAULT 'youtube' CHECK (tipo_sorgente IN ('youtube', 'file'));
ALTER TABLE tracce_audio ADD COLUMN IF NOT EXISTS file_path TEXT;

-- TAG AUDIO (sistema many-to-many)
-- NOTA: tracce_audio.categoria è mantenuta ma non più scritta da nuovo codice.
-- I dati storici restano per migrazione manuale.
CREATE TABLE IF NOT EXISTS tag_audio (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS traccia_audio_tag (
    traccia_id INTEGER NOT NULL REFERENCES tracce_audio(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tag_audio(id) ON DELETE CASCADE,
    PRIMARY KEY (traccia_id, tag_id)
);

-- Migrazioni per DB già esistenti
CREATE TABLE IF NOT EXISTS tag_audio (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS traccia_audio_tag (
    traccia_id INTEGER NOT NULL REFERENCES tracce_audio(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tag_audio(id) ON DELETE CASCADE,
    PRIMARY KEY (traccia_id, tag_id)
);

-- Indici utili per le query di filtraggio più comuni
CREATE INDEX IF NOT EXISTS idx_npc_location ON npc(location_attuale_id);
CREATE INDEX IF NOT EXISTS idx_npc_stato ON npc(stato);
CREATE INDEX IF NOT EXISTS idx_quest_stato ON quest(stato);
CREATE INDEX IF NOT EXISTS idx_quest_location ON quest(location_id);
CREATE INDEX IF NOT EXISTS idx_eventi_sessione ON eventi(sessione);
CREATE INDEX IF NOT EXISTS idx_audio_categoria ON tracce_audio(categoria);
CREATE INDEX IF NOT EXISTS idx_audio_location ON tracce_audio(location_id);
CREATE INDEX IF NOT EXISTS idx_audio_quest ON tracce_audio(quest_id);

-- ============================================================
-- INDAGINI (mappa a nodi stile Detroit: Become Human)
-- ============================================================

CREATE TABLE IF NOT EXISTS indagini (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    titolo TEXT NOT NULL,
    descrizione TEXT,
    attiva BOOLEAN NOT NULL DEFAULT TRUE,
    visibile_giocatrice BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS nodi_indagine (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    indagine_id INTEGER NOT NULL REFERENCES indagini(id) ON DELETE CASCADE,
    numero_nodo INTEGER NOT NULL,
    titolo TEXT NOT NULL,
    descrizione TEXT,
    immagine_url TEXT,
    scoperto BOOLEAN NOT NULL DEFAULT FALSE,
    sbloccato_manualmente BOOLEAN NOT NULL DEFAULT FALSE,
    regola_sblocco TEXT NOT NULL DEFAULT 'TUTTI' CHECK (regola_sblocco IN ('TUTTI', 'ALMENO_UNO'))
);

CREATE TABLE IF NOT EXISTS collegamenti_nodi (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    indagine_id INTEGER NOT NULL REFERENCES indagini(id) ON DELETE CASCADE,
    nodo_genitore_id INTEGER NOT NULL REFERENCES nodi_indagine(id) ON DELETE CASCADE,
    nodo_figlio_id INTEGER NOT NULL REFERENCES nodi_indagine(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_nodi_indagine ON nodi_indagine(indagine_id);
CREATE INDEX IF NOT EXISTS idx_collegamenti_indagine ON collegamenti_nodi(indagine_id);
CREATE INDEX IF NOT EXISTS idx_collegamenti_figlio ON collegamenti_nodi(nodo_figlio_id);

ALTER TABLE nodi_indagine ADD COLUMN IF NOT EXISTS tipo_speciale TEXT DEFAULT NULL CHECK (tipo_speciale IN ('rivelazione', NULL));
ALTER TABLE nodi_indagine ADD COLUMN IF NOT EXISTS livello_sfx INTEGER CHECK (livello_sfx IN (1, 2, 3));
ALTER TABLE nodi_indagine ADD COLUMN IF NOT EXISTS livello_sfx_manuale BOOLEAN NOT NULL DEFAULT FALSE;

-- Rimuove le colonne di stato che ora vivono in stato_nodi_cronologia
ALTER TABLE nodi_indagine DROP COLUMN IF EXISTS scoperto;
ALTER TABLE nodi_indagine DROP COLUMN IF EXISTS sbloccato_manualmente;

CREATE TABLE IF NOT EXISTS cronologie_indagine (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    indagine_id INTEGER NOT NULL REFERENCES indagini(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    attiva BOOLEAN NOT NULL DEFAULT FALSE,
    creata_il TIMESTAMP NOT NULL DEFAULT NOW(),
    scena_corrente INTEGER NOT NULL DEFAULT 0,
    sipario_aperto BOOLEAN NOT NULL DEFAULT FALSE
);
-- Migrazione per DB esistenti
ALTER TABLE cronologie_indagine ADD COLUMN IF NOT EXISTS scena_corrente INTEGER NOT NULL DEFAULT 0;
ALTER TABLE cronologie_indagine ALTER COLUMN scena_corrente SET DEFAULT 0;
ALTER TABLE cronologie_indagine ADD COLUMN IF NOT EXISTS sipario_aperto BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS stato_nodi_cronologia (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cronologia_id INTEGER NOT NULL REFERENCES cronologie_indagine(id) ON DELETE CASCADE,
    nodo_id INTEGER NOT NULL REFERENCES nodi_indagine(id) ON DELETE CASCADE,
    scoperto BOOLEAN NOT NULL DEFAULT FALSE,
    sbloccato_manualmente BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (cronologia_id, nodo_id)
);

CREATE INDEX IF NOT EXISTS idx_cronologie_indagine ON cronologie_indagine(indagine_id);
CREATE INDEX IF NOT EXISTS idx_stato_nodi_cron ON stato_nodi_cronologia(cronologia_id);

-- GIF di sfondo per ogni scena di un'indagine.
-- L'immagine caricata da file vive in gif_data (BYTEA): il filesystem di
-- Render è effimero e i file salvati su disco spariscono a ogni deploy.
CREATE TABLE IF NOT EXISTS scene_indagine (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    indagine_id INTEGER NOT NULL REFERENCES indagini(id) ON DELETE CASCADE,
    numero_scena INTEGER NOT NULL,
    gif_url TEXT,
    gif_data BYTEA,
    gif_mime TEXT,
    gif_data_aggiornata TIMESTAMPTZ,
    UNIQUE (indagine_id, numero_scena)
);
-- Migrazione per DB esistenti
ALTER TABLE scene_indagine ADD COLUMN IF NOT EXISTS gif_data BYTEA;
ALTER TABLE scene_indagine ADD COLUMN IF NOT EXISTS gif_mime TEXT;
ALTER TABLE scene_indagine ADD COLUMN IF NOT EXISTS gif_data_aggiornata TIMESTAMPTZ;

-- Migrazione per testo dei copioni salvato nel database
ALTER TABLE sessioni_copioni ADD COLUMN IF NOT EXISTS testo_md TEXT;

CREATE TABLE IF NOT EXISTS impostazioni_globali (
    chiave TEXT PRIMARY KEY,
    valore_text TEXT,
    valore_bytea BYTEA,
    valore_mime TEXT
);
ALTER TABLE sessioni_copioni ADD COLUMN IF NOT EXISTS data_modifica TIMESTAMP DEFAULT NOW();
