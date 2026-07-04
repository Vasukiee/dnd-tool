# Auresis modernizzazione

Tasklist viva da aggiornare passo passo mentre trasformiamo l'app in una cabina di regia più moderna, mantenendo Flask,
Render e Supabase.

## Ora

- [x] Supportare più luoghi per incarico con tabella ponte quest_locations.
- [x] Aumentare spazio tra Accessi rapidi e briefing inferiore.
- [x] Scambiare posizione dashboard tra Cronaca/Accessi rapidi e briefing a tre pannelli.
- [x] Ripristinare la palette lore-wise originale.
- [x] Salvare questa tasklist nel repo.
- [x] Correggere layout Accessi rapidi nella dashboard.
- [x] Command palette v2: trigger visibile, azioni dirette, navigazione tastiera più affidabile.
- [x] Dashboard v2: pannello pre-sessione con quest attive, indagini aperte e NPC critici.

## Prossimi passi

- [x] Recuperare palette lore-wise esatta confrontandola con la versione precedente al primo restyling.
- [x] Rimuovere glow verde e linee metriche multicolore dalla dashboard.
- [x] Riavviare Flask per caricare template e route aggiornati in questa sessione browser.
- [x] Verificare nel browser home, sidebar, command palette e responsive.
- [x] Restyling liste principali: NPC, quest, locations, fazioni.
- [x] Aggiungere filtri rapidi e ricerca locale nelle liste.
- [x] Introdurre drawer laterale per dettagli rapidi.
- [x] Ritirare la Modalità sessione live: esperimento scartato e rimosso dalla UI.
- [x] Valutare mappa relazionale interattiva con una libreria JS dedicata.
- [x] Hardening Render/Supabase: query calde, pool Postgres, cold start.

## Fine tuning cinematografico

- [x] Trasformare lo spotlight da tracciamento cursore ad animazione lenta dello sfondo.
- [x] Rimuovere la pagina Sessione live dalla navigazione e dalla command palette.
- [x] Reindirizzare /sessione-live alla home per far sparire la pagina senza rompere vecchi link.
- [x] Estendere React motion layer a tutto il sito, non solo alla mappa.
- [x] Aggiungere animazioni diffuse per entrata pagina, superfici, sidebar, bottoni e stati hover.
- [x] Ripristinare colori distinti per i nodi della mappa usando solo la palette lore-wise.
- [x] Aggiungere una React island non bloccante per dare vita alla mappa relazionale.
- [x] Aggiungere animazioni leggere con rispetto di prefers-reduced-motion.
- [x] Aggiungere profondità controllata con ombre calde, velature leggere e bordi più sottili.
- [x] Rendere hero/dashboard più scenici ma compatti.
- [x] Rifinire sidebar, trigger Ctrl K e command palette.
- [x] Uniformare liste, drawer e stati vuoti con lo stesso ritmo visivo.
- [x] Migliorare contrasto e leggibilità della mappa senza cambiare architettura.
- [x] Rendere la sessione live più cockpit cinematografico.
- [x] Mantenere il vincolo palette: niente verde acceso, azzurro, viola o linee metriche multicolore.

## Note di direzione

- Hardening completato: indici su relazioni, filtri e colonne calde; pool Postgres gia presente con pre-ping; Flask
  resta layer server-side davanti a Supabase.

- Tenere Flask come backend e layer sicuro davanti a Supabase.
- Evitare una migrazione React completa finche non serve davvero.
- Usare React come layer progressivo per movimento/viste ricche, senza migrare tutta l'app.
- Conservare la palette narrativa esistente: miniera, fucina, oro ossidato, contaminazione.

## Modalità sessione live

Decisione: esperimento scartato. La pagina /sessione-live viene reindirizzata alla home, i link sono rimossi da sidebar
e command palette, template e JS dedicati sono eliminati.

## Mappa relazionale

- [x] Filtro mappa per incarico collegato.
- [x] Aggiungere ricerca, filtri relazione e modalità focus a 1 grado.
- [x] Rendere la mappa relazionale effettivamente interattiva: layout a forze, pan, zoom, trascinamento nodi e reset
  vista.
  Decisione: costruire una prima vista con SVG/JS custom, senza introdurre subito React. I dati disponibili bastano per
  un grafo utile: NPC -> fazioni, NPC -> luoghi, quest -> luoghi, quest <-> NPC, luoghi -> fazioni e gerarchie tra
  luoghi.
  Decisione mappa: restiamo su SVG/JS custom finche il grafo resta gestibile con ricerca, filtri e focus. Se supera
  circa 80-100 nodi o serve clustering/virtualizzazione, rivalutiamo Cytoscape.js o Sigma.js solo per questa vista.

- [x] Aggiungere endpoint JSON /mappa-relazioni.json filtrato per modalità giocatrice.
- [x] Aggiungere route/template /mappa-relazioni.
- [x] Disegnare grafo SVG leggero, con filtri per tipo nodo.
- [x] Mostrare pannello rapido quando si seleziona un nodo.
- [x] Valutare una libreria dedicata solo se il grafo custom diventa troppo rigido.
