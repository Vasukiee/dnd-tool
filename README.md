# Campaign Tool — Gestionale per campagne RPG single-player

Strumento locale per gestire lo stato di una campagna di gioco di ruolo
single-player: NPC, location, fazioni, quest, log di sessione e copioni.
Gira interamente sul tuo computer, senza connessioni esterne.

## Requisiti

- Python 3.8+
- Nessuna dipendenza esterna: il database è SQLite, incluso nella libreria standard di Python.

## Installazione

1. Estrai il progetto in una cartella locale.

2. Installa le dipendenze Python:
   ```
   pip install -r requirements.txt
   ```

3. Inizializza il database (crea il file `campagna.db` con tutte le tabelle):
   ```
   python3 db.py
   ```

4. (Opzionale) Popola il database con dati demo di esempio:
   ```
   python3 popola_iniziale.py
   ```
   Puoi usare lo script come punto di partenza e modificarlo con i dati
   della tua campagna, oppure inserire tutto direttamente dalla dashboard.

## Avvio

```
python3 app.py
```

Apri il browser su **http://127.0.0.1:5000**. Lascia il terminale aperto
finché usi la dashboard; per chiuderla, `Ctrl+C`.

Il file `campagna.db` viene creato nella stessa cartella di `app.py` e
contiene tutti i dati: fanne un backup periodico prima delle sessioni
importanti.

## Struttura della cartella

```
campaign_tool/
├── schema.sql           ← struttura del database (SQLite)
├── db.py                ← accesso al database
│
├── app.py               ← dashboard web (lancia questo)
├── templates/           ← pagine HTML della dashboard
├── static/style.css     ← stile visivo
│
├── aggiorna_sessione.py ← alternativa da terminale: aggiorna dati post-sessione
│
└── copioni/             ← script delle sessioni in markdown
```

## Usare la dashboard

La sidebar sinistra dà accesso a:

- **Sommario** — statistiche rapide e ultimi eventi
- **Personaggi** — schede NPC con tutti i campi (incluso livello Oripatia)
- **Fazioni**, **Luoghi**, **Incarichi** — cataloghi con form di modifica
- **Cronaca** — log delle sessioni
- **Verità accertate** — fatti di lore scoperti, slegati da una singola quest
- **Il Soggetto** — scheda del personaggio giocante
- **Copioni** — script delle sessioni in markdown
- **Audio** — tracce YouTube collegate a location e quest

## Usare lo script da terminale

Se preferisci non aprire il browser per aggiornare il database dopo una sessione:

```
python3 aggiorna_sessione.py
```

## Note

- **Backup**: il database è il file `campagna.db`. Copialo prima di ogni
  sessione per avere un punto di ripristino.
- **Modalità giocatrice**: la dashboard ha un toggle che nasconde NPC, location
  e quest non ancora sbloccate — utile se la giocatrice può vedere lo schermo.
  Imposta la password master con `python3 imposta_password.py`.
- **Personalizzazione colori**: usa il tasto tavolozza in basso a sinistra
  nella sidebar per cambiare la palette. I colori vengono salvati nel database.
- **Copioni**: i file `.md` in `copioni/` seguono una formattazione specifica;
  apri `copioni/sessione_00_showcase.md` per vedere il formato.
