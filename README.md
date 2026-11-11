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
    ├── auth.py                 ← chi è master e chi vede solo la vista giocatrice
    ├── blueprints/indagini.py  ← le pagine delle Indagini (editor, live, vista giocatrice)
    ├── templates/              ← le pagine HTML della dashboard
    ├── static/                 ← stile (CSS), script (JS) e risorse multimediali (audio, gif)
    ├── copioni/                ← i file testuali delle sessioni (.md), creati al primo uso
    ├── tests/                  ← test automatici (vedi "Test" più sotto)
    │
    ├── imposta_password.py     ← imposta la password master (da fare una volta)
    ├── popola_iniziale.py      ← dati di apertura della campagna (facoltativo)
    ├── seed_indagine_demo.py   ← un'indagine dimostrativa con tutti i casi della vista live
    └── aggiorna_sessione.py    ← ALTERNATIVA DA TERMINALE: registra eventi
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
   Nello stesso `.env` puoi anche impostare una `SECRET_KEY` per firmare le sessioni; se non lo fai, l'app ne genera una al primo avvio e la salva nel database, quindi non è obbligatorio.
5. **Imposta la password master** (serve per poter scrivere, vedi sotto):
   ```bash
   python3 imposta_password.py
   ```

## Master e giocatrice

Chi apre il Registro senza password è in **vista giocatrice**: sola lettura, e solo di ciò che il master ha reso visibile. Personaggi, luoghi, incarichi e indagini nascono nascosti; li riveli uno alla volta dalla rispettiva lista (il pulsante *Nascosto / Mostrabile alla giocatrice* cambia stato sul posto, senza ricaricare la pagina). Una voce nascosta non compare da nessuna parte nella vista giocatrice: né nelle liste, né nella ricerca, né nella mappa, né tra i collegamenti delle schede visibili (i membri di una fazione, chi si trova in un luogo, i personaggi di un incarico).

Per lavorare come master clicca l'icona dell'occhio in fondo alla barra laterale e inserisci la password. Dalla stessa icona torni alla vista giocatrice, per controllare cosa vedrà lei. Dopo 5 password sbagliate lo sblocco si blocca per 15 minuti.

Cronaca, Verità accertate, Fazioni e Il Soggetto sono sempre visibili a entrambe.

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

Qualche comodità mentre lavori:
- **Ctrl+K** apre la ricerca rapida da qualunque pagina.
- **Ctrl+S** salva la scheda che stai modificando; se provi a uscire con modifiche non salvate, il browser ti avvisa.
- Cambiare il nome di una scheda la rinomina (collegamenti compresi); se il nome è già usato da un'altra voce, il Registro te lo dice invece di sovrascriverla.
- **Backup** (in fondo alla barra laterale) scarica tutta la campagna in un file JSON. Fallo prima di ogni sessione importante.

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
- **"Sblocca la modalità master"**: non hai ancora inserito la password, o non l'hai mai impostata (`python3 imposta_password.py`).


## Variabili d'ambiente

Tutte facoltative; vanno nel file `Auresis/.env` o nelle impostazioni dell'hosting.

| Variabile | A cosa serve |
|---|---|
| `DATABASE_URL` | Collegamento a Postgres. Se manca, si usa SQLite in locale. |
| `SECRET_KEY` | Chiave che firma le sessioni. Se manca, viene generata e salvata nel database. |
| `STORAGE_MODE` | `disk` o `db`: dove salvare copioni e immagini. Di default `disk` con SQLite, `db` con Postgres. |
| `SQLITE_PATH` | Percorso alternativo per il file SQLite (di default `Auresis/campagna.db`). |
| `SESSION_COOKIE_SECURE` | `1` per inviare il cookie solo su HTTPS (su Render è automatico). |
| `SUPABASE_URL`, `SUPABASE_BUCKET` | Per elencare gli effetti sonori caricati su Supabase Storage. |
| `FLASK_DEBUG` | `1` per il debugger di Flask. Solo in locale. |
| `DEBUG_TIMING` | `1` per stampare nel log, per ogni richiesta, tempo totale, CPU, numero di query e tempo passato sul database. |

## Test

```bash
cd Auresis
pip install -r requirements-dev.txt
python3 -m pytest tests
```

I test girano su un database SQLite temporaneo: non toccano `campagna.db` né il database in cloud, anche se hai un `.env` configurato. Controllano i permessi (chi non è master non scrive), la modifica delle schede e soprattutto che nella vista giocatrice non trapeli nulla di nascosto. Su GitHub partono da soli a ogni push e pull request.

## Deploy su Render (free)

Root directory `Auresis/`, start command:

```bash
gunicorn app:app
```

Worker, thread, timeout e formato del log (con la durata di ogni richiesta, `%(D)s`, in microsecondi) stanno in `Auresis/gunicorn.conf.py`, che gunicorn legge da solo: 2 worker da 4 thread. Senza quel file il comando qui sopra avvierebbe un solo worker che serve una richiesta alla volta.

Il ping keep-alive (`heartbeat.js`) gira solo sulla pagina del copione: live view e player view non lo caricano.

### Limiti del piano gratuito, e cosa aspettarsi

- **Render** spegne il servizio dopo 15 minuti senza visite; la prima pagina dopo lo spegnimento impiega circa un minuto. Durante una sessione non succede (live view e player view interrogano il server di continuo): basta aprire il sito un minuto prima di giocare.
- **Supabase** mette in pausa il progetto dopo una settimana senza attività sul database, e da lì l'app non funziona finché non lo riattivi dalla dashboard di Supabase. Per evitarlo c'è `.github/workflows/keepalive.yml`, che visita `/salute` una volta al giorno: si attiva impostando nel repository la variabile `REGISTRO_URL` con l'indirizzo del sito.
- **La distanza tra server e database** è ciò che decide la velocità: ogni query è un viaggio di rete, e una pagina ne fa da 1 a 13. Crea il servizio Render nella regione più vicina a quella del progetto Supabase (per un progetto in Irlanda, Francoforte). Per misurarla apri `/salute`: `db_ms` è il tempo di una query minima. Sotto i 30 ms va tutto bene; sopra i 100 ms le azioni della live view superano il secondo.

Note di performance: la vista giocatrice ridisegna solo quando `stato-player` cambia (ETag + confronto del contenuto), gli sfondi caricati vengono ridimensionati a max 1920px e salvati in WebP (le GIF animate diventano statiche) e le route sfondo servono `Cache-Control` + `ETag`.
