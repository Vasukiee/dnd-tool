# Strumento Campagna DnD - Guida d'uso

Questo strumento fa da interfaccia per gestire lo stato della tua campagna. Hai **due modi equivalenti** di usarlo: una dashboard web con interfaccia grafica (consigliata, "Il Registro") oppure due script da terminale. Entrambi leggono e scrivono lo stesso database (in locale o in cloud), quindi puoi alternarli liberamente.

## Cosa contiene la cartella

Tutto il codice principale è stato raggruppato all'interno della cartella `Auresis/`:

```text
dnd_tool/
└── Auresis/
    ├── schema.sql              ← struttura del database locale (SQLite)
    ├── schema_postgres.sql     ← struttura del database cloud (Postgres)
    ├── db.py                   ← astrazione e connessione dinamica al database
    ├── copioni.py              ← motore di lettura e parsing dei copioni
    │
    ├── app.py                  ← DASHBOARD WEB: lancia questo per l'interfaccia grafica
    ├── templates/              ← le pagine HTML della dashboard
    ├── static/                 ← stile (CSS), script (JS) e risorse multimediali (audio, gif)
    ├── copioni/                ← i file testuali delle sessioni (.md)
    │
    ├── aggiorna_sessione.py    ← ALTERNATIVA DA TERMINALE: registra eventi
    │
    └── documenti_statici/
        ├── bible_universo.md     ← la Bible di Aetheleon (da popolare tu)
        ├── bible_pianeta.md      ← la Bible di Auresis (da popolare tu)
        └── regole_risoluzione.md ← le regole di combattimento/risoluzione (da popolare tu)
```

## Setup iniziale (una volta sola)

1. Assicurati di avere Python 3 installato.
2. Entra nella cartella del progetto:
   ```bash
   cd Auresis
   ```
3. Installa le librerie necessarie:
   ```bash
   pip install -r requirements.txt
   ```
4. **Zero configurazioni per il locale**: l'app crea automaticamente un database SQLite (`campagna.db`) nel tuo computer per iniziare subito a giocare. 
   *(Opzionale)* Se intendi usare il progetto in **cloud** su piattaforme dal file system effimero (Render, Supabase), crea un file `.env` dentro la cartella `Auresis/` e inserisci il link al tuo database Postgres:
   ```env
   DATABASE_URL="postgresql://utente:password@host:porta/dbname"
   ```
   L'app rileverà il link e salverà copioni e immagini in cloud invece che in locale.
5. I file in `documenti_statici/` contengono la lore principale. Aggiornali quando l'ambientazione cambia in modo strutturale.

## Uso: la dashboard web (consigliata)

Entra nella cartella `Auresis/` ed esegui:
```bash
python3 app.py
```

Poi apri il browser su **http://127.0.0.1:5000**. Lascia il terminale aperto in background mentre usi la dashboard (è il server che la fa funzionare); per chiuderla, torna al terminale e premi `Ctrl+C`. 

La sidebar a sinistra ti porta tra:
- **Sommario**: i numeri della campagna a colpo d'occhio (NPC vivi, quest attive, sessioni giocate).
- **Personaggi**: schede NPC. Il bordo dorato a sinistra di ogni card si allarga in base al livello di Auris Cancer registrato.
- **Fazioni**, **Luoghi**, **Incarichi**: cataloghi con dettaglio e form di modifica.
- **Cronaca**: il log delle sessioni giocate (eventi) e dei Fatti Accertati.
- **Indagini**: pagine dinamiche (Editor e Live) per gestire puzzle e investigazioni, con mappe visive, sblocchi e sfondi scena animati (GIF).
- **I Copioni**: dove puoi leggere le trascrizioni romanzate delle sessioni arricchite dall'audio ambientale in background.
- **Il Soggetto**: la scheda del tuo personaggio.

## Uso: gli script da terminale (alternativa)

Se preferisci non aprire il browser, assicurati di essere in `Auresis/` e lancia:

```bash
python3 aggiorna_sessione.py  # menu per registrare eventi/NPC/quest dopo aver giocato
```

## Note pratiche

- **Architettura Ibrida**: Se cloni il progetto e lo usi sul tuo computer, l'app usa `campagna.db` (SQLite) e salva copioni come file Markdown e immagini su disco in `static/scene_gifs`. Se usi il `.env` con un `DATABASE_URL` (es. Supabase), l'app si connette a Postgres e memorizza file e testo nel database per garantirne la persistenza in hosting come Render.
- **Multimedialità**: Puoi associare tracce audio e GIF di sfondo alle tue Indagini e Copioni. Il codice gestisce automaticamente il caching per un'esperienza fluida.
- **Auris Cancer**: ogni NPC ha un campo contaminazione (0-5) puramente narrativo, starà a te tracciarne il peso.

## Se qualcosa non funziona

- **La dashboard non si apre**: verifica che il terminale mostri `Running on http://127.0.0.1:5000`. Se stai usando Supabase in cloud e ti dà errore di connessione, verifica che la variabile `DATABASE_URL` nel `.env` sia corretta.
- **Una pagina dà errore**: il messaggio nel terminale di solito indica la riga esatta in cui l'app si è bloccata.
