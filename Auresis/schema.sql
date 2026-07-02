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
                                                completata INTEGER DEFAULT 0  -- 0 = non completata (nascosta in modalità giocatrice), 1 = completata
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
