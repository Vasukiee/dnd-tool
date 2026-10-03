-- ============================================================
-- SCHEMA DATABASE CAMPAGNA DND
-- ============================================================

-- FAZIONI
CREATE TABLE IF NOT EXISTS fazioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    nome_popolare TEXT,              -- es. "I Gravitisti" vs nome ufficiale
    ideologia TEXT,                  -- breve descrizione del principio guida
    territorio TEXT,                 -- dove ha base/influenza
    relazione_pg TEXT DEFAULT 'neutrale',  -- alleata / neutrale / ostile / sconosciuta
    stato_attuale TEXT,              -- breve nota su cosa sta facendo ora nella trama
    note TEXT,
    attiva INTEGER DEFAULT 1         -- 0 se la fazione è stata distrutta/sciolta
);

-- LOCATIONS
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visibile_giocatrice INTEGER DEFAULT 0,  -- 1 = visibile in modalità giocatrice
    nome TEXT NOT NULL UNIQUE,
    tipo TEXT,                       -- città / quartiere / dungeon / regione...
    descrizione_breve TEXT,
    fazione_controllante_id INTEGER,
    location_padre_id INTEGER,       -- per gerarchie (es. quartiere dentro città)
    stato_attuale TEXT,              -- es. "in rovina dopo l'attacco", "in festa"
    note TEXT,
    FOREIGN KEY (fazione_controllante_id) REFERENCES fazioni(id),
    FOREIGN KEY (location_padre_id) REFERENCES locations(id)
);

-- NPC
CREATE TABLE IF NOT EXISTS palette_personalizzata (
    variabile VARCHAR(100) PRIMARY KEY,
    valore VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS npc (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visibile_giocatrice INTEGER DEFAULT 0,  -- 1 = visibile in modalità giocatrice
    nome TEXT NOT NULL,
    ruolo TEXT,                      -- es. "fornitore", "antagonista minore", "alleato"
    fazione_id INTEGER,
    location_attuale_id INTEGER,
    stato TEXT DEFAULT 'vivo',       -- vivo / morto / disperso / sconosciuto
    relazione_pg TEXT,               -- breve nota qualitativa ("fidato", "diffidente"...)
    descrizione_breve TEXT,          -- una riga, per riconoscerlo al volo
    note_caratteriali TEXT,          -- tic verbali, modo di parlare, per consistenza
    livello_contaminazione INTEGER DEFAULT 0,  -- 0-5, esposizione/avanzamento Auris Cancer
    ultima_apparizione_sessione INTEGER,
    note TEXT,
    FOREIGN KEY (fazione_id) REFERENCES fazioni(id),
    FOREIGN KEY (location_attuale_id) REFERENCES locations(id)
);

-- QUEST
CREATE TABLE IF NOT EXISTS quest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visibile_giocatrice INTEGER DEFAULT 0,  -- 1 = visibile in modalità giocatrice
    nome TEXT NOT NULL,
    tipo TEXT DEFAULT 'side',         -- main / side
    stato TEXT DEFAULT 'attiva',      -- attiva / completata / fallita / in_pausa
    location_id INTEGER,
    riassunto TEXT,                   -- stato fattuale attuale, breve
    obiettivo_attuale TEXT,           -- cosa deve fare il PG per progredire
    sessione_inizio INTEGER,
    sessione_fine INTEGER,
    note TEXT,
    FOREIGN KEY (location_id) REFERENCES locations(id)
);

-- Tabella ponte: NPC coinvolti in una quest (relazione molti-a-molti)

CREATE TABLE IF NOT EXISTS quest_locations (
    quest_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    ruolo TEXT,
    PRIMARY KEY (quest_id, location_id),
    FOREIGN KEY (quest_id) REFERENCES quest(id) ON DELETE CASCADE,
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE
);

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
    riassunto TEXT NOT NULL,          -- 1-3 frasi, fattuale
    conseguenze_attive TEXT,          -- cosa resta "vivo" da questo evento ora
    location_id INTEGER,
    data_inserimento TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (location_id) REFERENCES locations(id)
);

-- NOTE DEL MASTER (riservate, una per sessione; solo pagina /master/note)
CREATE TABLE IF NOT EXISTS note_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sessione INTEGER NOT NULL UNIQUE,
    ramo_giocato TEXT,
    note TEXT,
    aggiornato TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- STATO DEL PERSONAGGIO (singola riga aggiornata, single-player)
CREATE TABLE IF NOT EXISTS pg_stato (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- forziamo una sola riga
    nome TEXT,
    condizione_fisica TEXT,           -- es. "braccio meccanico, costola incrinata"
    ferite_attive TEXT,
    equipaggiamento TEXT,
    risorse TEXT,                     -- crediti, oggetti di valore, ecc.
    abilita_acquisite TEXT,
    sessione_corrente INTEGER DEFAULT 0,
    location_attuale_id INTEGER,
    note TEXT,
    FOREIGN KEY (location_attuale_id) REFERENCES locations(id)
);

-- FATTI ACCERTATI (cose scoperte/promesse fatte, slegate da una singola quest/npc)
CREATE TABLE IF NOT EXISTS fatti_accertati (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descrizione TEXT NOT NULL,
    sessione INTEGER,
    rilevanza TEXT DEFAULT 'media',   -- alta / media / bassa (per filtraggio futuro)
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
                                            nome TEXT NOT NULL,                  -- es. "Fonderia / Acciaieria"
                                            categoria TEXT NOT NULL,             -- es. "industriale", "tensione", "intimo", "orrore"
                                            tipo_sorgente TEXT NOT NULL DEFAULT 'youtube' CHECK (tipo_sorgente IN ('youtube', 'file')),
                                            youtube_id TEXT,                     -- solo l'ID del video, non l'URL intero (es. "P1rgc5FBPOM")
                                            file_path TEXT,                      -- nome file dentro static/audio/ (es. "sirena_fabbrica.mp3")
                                            timestamp_inizio INTEGER DEFAULT 0,  -- secondi da cui far partire il loop, opzionale
                                            note TEXT,                           -- "buono per scene in miniera, loop lungo"
                                            location_id INTEGER,                 -- opzionale: traccia legata a una location
                                            quest_id INTEGER,                    -- opzionale: traccia legata a una questline
                                            FOREIGN KEY (location_id) REFERENCES locations(id),
    FOREIGN KEY (quest_id) REFERENCES quest(id)
    );

CREATE INDEX IF NOT EXISTS idx_audio_categoria ON tracce_audio(categoria);
CREATE INDEX IF NOT EXISTS idx_audio_location ON tracce_audio(location_id);
CREATE INDEX IF NOT EXISTS idx_audio_quest ON tracce_audio(quest_id);

-- TAG AUDIO (sistema many-to-many)
-- NOTA: tracce_audio.categoria è mantenuta ma non più scritta da nuovo codice.
CREATE TABLE IF NOT EXISTS tag_audio (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS traccia_audio_tag (
    traccia_id INTEGER NOT NULL REFERENCES tracce_audio(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tag_audio(id) ON DELETE CASCADE,
    PRIMARY KEY (traccia_id, tag_id)
);

-- ============================================================
-- COPIONI CHECKED
-- ============================================================

CREATE TABLE IF NOT EXISTS sessioni_copioni (
                                                numero_sessione INTEGER PRIMARY KEY,
                                                completata INTEGER DEFAULT 0, -- 0 = non completata (nascosta in modalità giocatrice), 1 = completata
                                                testo_md TEXT,                -- testo del copione quando STORAGE_MODE=db
                                                data_modifica TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- IMPOSTAZIONI GLOBALI (secret key, sfondo di default, ecc.)
-- ============================================================

CREATE TABLE IF NOT EXISTS impostazioni_globali (
    chiave TEXT PRIMARY KEY,
    valore_text TEXT,
    valore_bytea BLOB,
    valore_mime TEXT
);

CREATE TABLE IF NOT EXISTS impostazioni_sicurezza (
    id INTEGER PRIMARY KEY,
    password_master TEXT
);

-- ============================================================
-- INDAGINI (versione SQLite dello schema Postgres: stessi nomi e colonne)
-- ============================================================

CREATE TABLE IF NOT EXISTS indagini (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titolo TEXT NOT NULL,
    descrizione TEXT,
    attiva BOOLEAN NOT NULL DEFAULT 1,
    visibile_giocatrice BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS nodi_indagine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indagine_id INTEGER NOT NULL REFERENCES indagini(id) ON DELETE CASCADE,
    numero_nodo INTEGER NOT NULL,
    titolo TEXT NOT NULL,
    descrizione TEXT,
    immagine_url TEXT,
    regola_sblocco TEXT NOT NULL DEFAULT 'TUTTI' CHECK (regola_sblocco IN ('TUTTI', 'ALMENO_UNO')),
    tipo_speciale TEXT DEFAULT NULL CHECK (tipo_speciale IN ('rivelazione', NULL)),
    livello_sfx INTEGER CHECK (livello_sfx IN (1, 2, 3)),
    livello_sfx_manuale BOOLEAN NOT NULL DEFAULT 0,
    punto_interesse TEXT
);

CREATE TABLE IF NOT EXISTS collegamenti_nodi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indagine_id INTEGER NOT NULL REFERENCES indagini(id) ON DELETE CASCADE,
    nodo_genitore_id INTEGER NOT NULL REFERENCES nodi_indagine(id) ON DELETE CASCADE,
    nodo_figlio_id INTEGER NOT NULL REFERENCES nodi_indagine(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cronologie_indagine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indagine_id INTEGER NOT NULL REFERENCES indagini(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    attiva BOOLEAN NOT NULL DEFAULT 0,
    creata_il TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    scena_corrente INTEGER NOT NULL DEFAULT 0,
    sipario_aperto BOOLEAN NOT NULL DEFAULT 0,
    punti_extra_esaminati TEXT,
    liste_mostrate TEXT,
    lavagna TEXT,
    lavagna_versione INTEGER NOT NULL DEFAULT 0,
    lavagna_aperta BOOLEAN NOT NULL DEFAULT 0,
    orologio_offset TEXT
);

CREATE TABLE IF NOT EXISTS stato_nodi_cronologia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cronologia_id INTEGER NOT NULL REFERENCES cronologie_indagine(id) ON DELETE CASCADE,
    nodo_id INTEGER NOT NULL REFERENCES nodi_indagine(id) ON DELETE CASCADE,
    scoperto BOOLEAN NOT NULL DEFAULT 0,
    sbloccato_manualmente BOOLEAN NOT NULL DEFAULT 0,
    UNIQUE (cronologia_id, nodo_id)
);

CREATE TABLE IF NOT EXISTS scene_indagine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indagine_id INTEGER NOT NULL REFERENCES indagini(id) ON DELETE CASCADE,
    numero_scena INTEGER NOT NULL,
    gif_url TEXT,
    gif_data BLOB,
    gif_mime TEXT,
    gif_data_aggiornata TIMESTAMP,
    punti_extra TEXT,
    location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    lavagna BOOLEAN NOT NULL DEFAULT 0,
    orologio BOOLEAN NOT NULL DEFAULT 0,
    orologio_soglia INTEGER,
    orologio_sirena BOOLEAN NOT NULL DEFAULT 0,
    orologio_manuale BOOLEAN NOT NULL DEFAULT 0,
    UNIQUE (indagine_id, numero_scena)
);

CREATE TABLE IF NOT EXISTS sfondi_location (
    location_id INTEGER PRIMARY KEY REFERENCES locations(id) ON DELETE CASCADE,
    url TEXT,
    data BLOB,
    mime TEXT,
    aggiornato TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_nodi_indagine ON nodi_indagine(indagine_id);
CREATE INDEX IF NOT EXISTS idx_collegamenti_indagine ON collegamenti_nodi(indagine_id);
CREATE INDEX IF NOT EXISTS idx_collegamenti_figlio ON collegamenti_nodi(nodo_figlio_id);
CREATE INDEX IF NOT EXISTS idx_cronologie_indagine ON cronologie_indagine(indagine_id);
CREATE INDEX IF NOT EXISTS idx_stato_nodi_cron ON stato_nodi_cronologia(cronologia_id);

-- ============================================================
-- INDICI PERFORMANCE / MAPPA RELAZIONALE
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_npc_fazione ON npc(fazione_id);
CREATE INDEX IF NOT EXISTS idx_npc_location ON npc(location_attuale_id);
CREATE INDEX IF NOT EXISTS idx_npc_stato ON npc(stato);
CREATE INDEX IF NOT EXISTS idx_quest_stato ON quest(stato);
CREATE INDEX IF NOT EXISTS idx_quest_tipo ON quest(tipo);
CREATE INDEX IF NOT EXISTS idx_quest_location ON quest(location_id);
CREATE INDEX IF NOT EXISTS idx_quest_locations_location ON quest_locations(location_id);
CREATE INDEX IF NOT EXISTS idx_quest_npc_npc ON quest_npc(npc_id);
CREATE INDEX IF NOT EXISTS idx_locations_fazione ON locations(fazione_controllante_id);
CREATE INDEX IF NOT EXISTS idx_locations_padre ON locations(location_padre_id);
CREATE INDEX IF NOT EXISTS idx_eventi_location ON eventi(location_id);
CREATE INDEX IF NOT EXISTS idx_eventi_sessione ON eventi(sessione);
CREATE INDEX IF NOT EXISTS idx_audio_location ON tracce_audio(location_id);
CREATE INDEX IF NOT EXISTS idx_audio_quest ON tracce_audio(quest_id);
