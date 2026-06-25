# Strumento Campagna DnD — Guida d'uso

Questo strumento gestisce in locale (gratis, nessun costo cloud) lo stato della
tua campagna. Hai **due modi equivalenti** di usarlo: una dashboard web con
interfaccia grafica (consigliata, "Il Registro") oppure due script da terminale.
Entrambi leggono e scrivono lo stesso database, quindi puoi alternarli liberamente.

## Cosa contiene la cartella

```
dnd_tool/
├── schema.sql              ← struttura del database (non serve toccarlo)
├── db.py                   ← funzioni di accesso al database (non serve toccarlo)
├── prompt_builder.py        ← logica di costruzione del prompt (non serve toccarlo)
├── campagna.db               ← il tuo database vero, si crea/aggiorna da solo
│
├── app.py                   ← DASHBOARD WEB: lancia questo per l'interfaccia grafica
├── templates/                ← le pagine HTML della dashboard (non serve toccarle)
├── static/style.css          ← lo stile visivo della dashboard (non serve toccarlo)
│
├── genera_prompt.py          ← ALTERNATIVA DA TERMINALE: genera il prompt a domande
├── aggiorna_sessione.py      ← ALTERNATIVA DA TERMINALE: registra eventi a menu
│
├── documenti_statici/
│   ├── bible_universo.md     ← la Bible di Aetheleon (da popolare tu)
│   ├── bible_pianeta.md      ← la Bible del nuovo pianeta (da popolare tu)
│   └── regole_risoluzione.md  ← le regole di combattimento/risoluzione (da popolare tu)
└── prompt_generati/          ← qui finiscono i prompt salvati dallo script da terminale
```

## Setup iniziale (una volta sola)

1. Assicurati di avere Python 3 installato.
2. Installa Flask (serve solo per la dashboard web):
   ```
   pip install flask
   ```
   (se il comando dà errore su Mac/Linux, prova `pip install flask --break-system-packages`)
3. Apri i tre file in `documenti_statici/` e sostituisci il placeholder con il
   contenuto vero (copia/incolla da Google Docs). Questi vengono inclusi
   **integralmente** in ogni prompt generato — aggiornali quando la lore
   cambia in modo strutturale (gli eventi di sessione vanno nel database, non qui).

## Uso: la dashboard web (consigliata)

```
python3 app.py
```

Poi apri il browser su **http://127.0.0.1:5000**. Lascia il terminale aperto
in background mentre usi la dashboard (è il server che la fa funzionare); per
chiuderla, torna al terminale e premi `Ctrl+C`.

La sidebar a sinistra ti porta tra:
- **Sommario** — i numeri della campagna a colpo d'occhio (NPC vivi, quest attive, sessioni giocate) e gli ultimi eventi.
- **Personaggi** — schede NPC. Il bordo dorato a sinistra di ogni card si allarga in base al livello di Auris Cancer registrato.
- **Fazioni**, **Luoghi**, **Incarichi** — cataloghi con dettaglio e form di modifica.
- **Cronaca** — il log delle sessioni giocate (eventi).
- **Verità accertate** — fatti di lore scoperti, indipendenti da una singola quest.
- **Il Soggetto** — la scheda del tuo personaggio.
- **→ Genera prompt sessione** — la pagina più importante: scegli location, quest da includere, tipo di scena, tono e intento, poi premi "Genera prompt". Il testo pronto compare sotto, con un bottone "Copia negli appunti" per incollarlo direttamente in Gemini.

Tutte le liste hanno un bottone "+" per aggiungere nuove voci, e ogni pagina di
dettaglio ha "Modifica" ed "Elimina".

## Uso: gli script da terminale (alternativa)

Se preferisci non aprire il browser, gli script originali restano disponibili
e fanno esattamente le stesse cose:

```
python3 genera_prompt.py      # genera il prompt a domande, salva un file .md
python3 aggiorna_sessione.py  # menu per registrare eventi/NPC/quest dopo aver giocato
```

## Note pratiche

- **Il database è un singolo file** (`campagna.db`). Fanne periodicamente una
  copia di backup prima di sessioni importanti.
- **Se vuoi vedere/modificare i dati a colpo d'occhio in modo grezzo** (tipo
  foglio di calcolo, utile per correzioni puntuali), puoi anche scaricare
  gratuitamente "DB Browser for SQLite" e aprire `campagna.db` con quello.
- **Niente di tutto questo consuma credito API o costa soldi**: dashboard e
  script girano interamente in locale sul tuo computer. L'unico posto dove
  "spendi" è la chat con Gemini Pro via abbonamento normale, non a consumo.
- **Livello di contaminazione (Auris Cancer)**: ogni NPC ha un campo numerico
  da 0 a 5. È puramente per tracciamento/visualizzazione — sta a te (o a
  Gemini, se gli dai le regole nel documento delle Regole di Risoluzione)
  decidere quando e come un personaggio avanza in quella scala.

## Se qualcosa non funziona

- **La dashboard non si apre**: verifica che il terminale mostri `Running on
  http://127.0.0.1:5000` senza errori sopra. Se manca Flask, installalo come
  indicato nel setup.
- **Una pagina dà errore**: il messaggio nel terminale (dove hai lanciato
  `app.py`) di solito indica la riga e il problema.
- **Hai scritto un nome con un typo** diverso da come era stato salvato la
  prima volta: aprilo dalla dashboard (è più facile cercarlo visivamente) e
  correggilo da lì.
- **Il file `campagna.db` non esiste ancora**: lancia `python3 db.py` una volta.

