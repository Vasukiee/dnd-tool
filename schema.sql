-- ============================================================
-- SCHEMA DATABASE CAMPAGNA DND
-- ============================================================

-- FAZIONI
CREATE TABLE IF NOT EXISTS fazioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    nome_popolare TEXT,
    ideologia TEXT,
    territorio TEXT,
    relazione_pg TEXT DEFAULT 'neutrale',
    stato_attuale TEXT,
    note TEXT,
    attiva INTEGER DEFAULT 1         -- 0 se la fazione è stata distrutta/sciolta
);

-- LOCATIONS
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    ruolo TEXT,
    fazione_id INTEGER,
    location_attuale_id INTEGER,
    stato TEXT DEFAULT 'vivo',       -- vivo / morto / disperso / sconosciuto
    relazione_pg TEXT,
    descrizione_breve TEXT,
    note_caratteriali TEXT,
    livello_contaminazione INTEGER DEFAULT 0,  -- 0-5, progressione Oripatia
    ultima_apparizione_sessione INTEGER,
    note TEXT,
    visibile_giocatrice INTEGER DEFAULT 0,
    FOREIGN KEY (fazione_id) REFERENCES fazioni(id),
    FOREIGN KEY (location_attuale_id) REFERENCES locations(id)
);

-- QUEST
CREATE TABLE IF NOT EXISTS quest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    ruolo_nella_quest TEXT,           -- es. "obiettivo", "alleato", "informatore"
    PRIMARY KEY (quest_id, npc_id),
    FOREIGN KEY (quest_id) REFERENCES quest(id),
    FOREIGN KEY (npc_id) REFERENCES npc(id)
);

-- EVENTI (log di sessione, append-only)
CREATE TABLE IF NOT EXISTS eventi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sessione INTEGER NOT NULL,
    riassunto TEXT NOT NULL,
    conseguenze_attive TEXT,
    location_id INTEGER,
    data_inserimento TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (location_id) REFERENCES locations(id)
);

-- STATO DEI PERSONAGGI (una riga per personaggio giocante)
CREATE TABLE IF NOT EXISTS pg_stato (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    classe TEXT,
    razza TEXT,
    condizione_fisica TEXT,
    ferite_attive TEXT,
    equipaggiamento TEXT,
    risorse TEXT,
    abilita_acquisite TEXT,
    sessione_corrente INTEGER DEFAULT 0,
    location_attuale_id INTEGER,
    note TEXT,
    hp_correnti            INTEGER,
    hp_massimi             INTEGER,
    background             TEXT,
    stadio_oripatia        INTEGER DEFAULT 0,
    oripatia_agente        TEXT,
    oripatia_vettore       TEXT,
    oripatia_progressione  TEXT,
    oripatia_risposta_arti TEXT,
    oripatia_prognosi      TEXT,
    oripatia_note          TEXT,
    stato                  TEXT DEFAULT 'sconosciuto',
    FOREIGN KEY (location_attuale_id) REFERENCES locations(id)
);

-- STATISTICHE DEI PERSONAGGI (valori liberi 1-10, N per PG)
CREATE TABLE IF NOT EXISTS pg_statistiche (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pg_id           INTEGER NOT NULL,
    nome_statistica TEXT    NOT NULL,
    valore          INTEGER NOT NULL DEFAULT 5,
    posizione       INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (pg_id) REFERENCES pg_stato(id) ON DELETE CASCADE
);

-- ABILITÀ SPECIALI DEI PERSONAGGI (N per PG, nome + descrizione libera)
CREATE TABLE IF NOT EXISTS pg_abilita (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pg_id       INTEGER NOT NULL,
    nome        TEXT NOT NULL,
    descrizione TEXT,
    FOREIGN KEY (pg_id) REFERENCES pg_stato(id) ON DELETE CASCADE
);

-- FATTI ACCERTATI
CREATE TABLE IF NOT EXISTS fatti_accertati (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descrizione TEXT NOT NULL,
    sessione INTEGER,
    rilevanza TEXT DEFAULT 'media',
    note TEXT
);

-- Indici utili per le query di filtraggio più comuni
CREATE INDEX IF NOT EXISTS idx_npc_location ON npc(location_attuale_id);
CREATE INDEX IF NOT EXISTS idx_npc_stato ON npc(stato);
CREATE INDEX IF NOT EXISTS idx_quest_stato ON quest(stato);
CREATE INDEX IF NOT EXISTS idx_quest_location ON quest(location_id);
CREATE INDEX IF NOT EXISTS idx_eventi_sessione ON eventi(sessione);

-- ============================================================
-- YOUTUBE
-- ============================================================

CREATE TABLE IF NOT EXISTS tracce_audio (
                                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                                            nome TEXT NOT NULL,
                                            categoria TEXT NOT NULL,
                                            youtube_id TEXT NOT NULL,            -- solo l'ID del video, non l'URL intero (es. "P1rgc5FBPOM")
                                            timestamp_inizio INTEGER DEFAULT 0,
                                            note TEXT,
                                            location_id INTEGER,
                                            quest_id INTEGER,
                                            FOREIGN KEY (location_id) REFERENCES locations(id),
    FOREIGN KEY (quest_id) REFERENCES quest(id)
    );

CREATE INDEX IF NOT EXISTS idx_audio_categoria ON tracce_audio(categoria);
CREATE INDEX IF NOT EXISTS idx_audio_location ON tracce_audio(location_id);
CREATE INDEX IF NOT EXISTS idx_audio_quest ON tracce_audio(quest_id);

-- ============================================================
-- COPIONI CHECKED
-- ============================================================

CREATE TABLE IF NOT EXISTS sessioni_copioni (
                                                numero_sessione INTEGER PRIMARY KEY,
                                                completata INTEGER DEFAULT 0  -- 0 = bozza, 1 = visibile
);

CREATE TABLE IF NOT EXISTS palette_personalizzata (
    variabile TEXT PRIMARY KEY,
    valore    TEXT NOT NULL
);

-- PASSWORD MASTER per il toggle modalità giocatrice
CREATE TABLE IF NOT EXISTS impostazioni_sicurezza (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    password_master TEXT
);
