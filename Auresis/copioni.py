import os
import re

import markdown as md_lib
from markupsafe import escape

import db

COPIONI_DIR = os.path.join(os.path.dirname(__file__), "copioni")

# Esempi che deve riconoscere:
#   sessione_01.md
#   sessione_01_scena_00.md
#   sessione_12_qualunque_cosa.md
PATTERN_NOME_FILE = re.compile(r"^sessione_(\d+)(?:_.*)?\.md$", re.IGNORECASE)


def _assicura_cartella():
    os.makedirs(COPIONI_DIR, exist_ok=True)


def _estrai_numero_sessione(nome_file):
    """Ritorna il numero di sessione (int) da un nome file, o None se non combacia."""
    m = PATTERN_NOME_FILE.match(nome_file)
    if not m:
        return None
    return int(m.group(1))


def _estrai_titolo(testo_md):
    """Estrae il titolo del copione (il primo H1) e pulisce in automatico
    la dicitura 'Sessione #: ' lasciando solo il nome della sessione."""
    for riga in testo_md.splitlines():
        riga = riga.strip()
        if riga.startswith("# "):
            raw_titolo = riga.lstrip("#").strip()
            # Pulisce "Sessione 1:", "SESSIONE 12: ", ecc.
            return re.sub(r'(?i)^Sessione\s+\d+:\s*', '', raw_titolo)
    return None


def elenca_sessioni():
    """Scansiona la cartella copioni/ e il database, ritorna una lista di dict:
    [{"numero": 1, "titolo": "...", "file_count": 2}, ...]
    ordinata per numero di sessione decrescente (la più recente prima)."""
    _assicura_cartella()
    sessioni = {}  # numero -> {"titolo": str|None, "files": [nomi_file ordinati]}

    # 1. Carica le sessioni dal database (se in modalità db)
    if db.get_storage_mode() == "db":
        sessioni_db = db.get_all_sessioni_db()
        for numero in sessioni_db:
            testo_db = db.get_sessione_testo(numero)
            titolo_db = _estrai_titolo(testo_db) if testo_db else None
            sessioni[numero] = {"titolo": titolo_db, "files": [], "in_db": True}

    # 2. Scansiona i file locali
    nomi_file = sorted(os.listdir(COPIONI_DIR))  # ordine alfabetico, garantisce scena_00 prima di scena_01
    for nome_file in nomi_file:
        numero = _estrai_numero_sessione(nome_file)
        if numero is None:
            continue  # file che non segue la convenzione, ignorato silenziosamente
        if numero not in sessioni:
            sessioni[numero] = {"titolo": None, "files": [], "in_db": False}
        sessioni[numero]["files"].append(nome_file)

    risultato = []
    for numero, dati in sessioni.items():
        if dati["titolo"] is None and dati["files"] and not dati.get("in_db", False):
            primo_file = dati["files"][0]
            path = os.path.join(COPIONI_DIR, primo_file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    testo = f.read()
                dati["titolo"] = _estrai_titolo(testo)
            except OSError:
                pass
        risultato.append({
            "numero": numero,
            "titolo": dati["titolo"] or f"Sessione {numero}",
            "file_count": len(dati["files"]),
            "in_db": dati.get("in_db", False)
        })

    risultato.sort(key=lambda s: s["numero"], reverse=True)
    return risultato


def estrai_titolo(testo_md):
    """Versione pubblica di _estrai_titolo."""
    return _estrai_titolo(testo_md)


def get_file_path_sessione(numero_sessione):
    """Ritorna il percorso del primo file .md per la sessione, o None se non esiste."""
    _assicura_cartella()
    file_sessione = sorted([
        f for f in os.listdir(COPIONI_DIR)
        if f.endswith(".md") and _estrai_numero_sessione(f) == numero_sessione
    ])
    if not file_sessione:
        return None
    return os.path.join(COPIONI_DIR, file_sessione[0])


def salva_testo_sessione(numero_sessione, testo):
    """Salva il testo del copione sul DB o su disco in base allo STORAGE_MODE."""
    if db.get_storage_mode() == "db":
        db.upsert_sessione_testo(numero_sessione, testo)
    else:
        percorso = get_file_path_sessione(numero_sessione)
        if not percorso:
            _assicura_cartella()
            percorso = os.path.join(COPIONI_DIR, f"sessione_{numero_sessione:02d}.md")
        with open(percorso, "w", encoding="utf-8") as f:
            f.write(testo)


def get_testo_sessione(numero_sessione):
    """Ritorna il testo completo della sessione."""
    if db.get_storage_mode() == "db":
        testo_db = db.get_sessione_testo(numero_sessione)
        if testo_db is not None:
            return testo_db
        
    _assicura_cartella()
    nomi_file = sorted([
        f for f in os.listdir(COPIONI_DIR)
        if _estrai_numero_sessione(f) == numero_sessione
    ])
    if not nomi_file:
        return ""
        
    testo_completo = []
    for nome_file in nomi_file:
        path = os.path.join(COPIONI_DIR, nome_file)
        with open(path, "r", encoding="utf-8") as f:
            testo_completo.append(f.read())
    return "\n\n---\n\n".join(testo_completo)


_RE_IMG = re.compile(r'!\[([^\]|]*)((?:\|[^\]|]+)*)\]\(([^)]+)\)')

_ALIGN_MAP = {
    "sx": "left", "left": "left",
    "centro": "center", "center": "center",
    "dx": "right", "right": "right",
}


def _processa_audio_tags(testo_md):
    """Cerca tag testuali tipo @audio: Nome Traccia e li sostituisce
    con pulsanti interattivi. Pesca i dati interrogando il db audio."""
    pattern = re.compile(r"@audio:\s*([^\n]+)")
    
    def sostituisci(m):
        nome_traccia = m.group(1).strip()
        traccia = db.get_traccia_audio_by_nome(nome_traccia)
        if traccia:
            traccia_id = traccia['id']
            tipo = traccia['tipo_sorgente']
            path = traccia.get('file_path', '') or ''
            yt_id = traccia.get('youtube_id', '') or ''
            start_time = traccia.get('timestamp_inizio', 0) or 0
            
            return (f'<span class="audio-recommendation-wrapper">'
                    f'<span class="audio-recommendation-label">Musica consigliata:</span> '
                    f'<button class="btn-inline-audio btn-audio-large" '
                    f'data-audio-id="{traccia_id}" '
                    f'data-audio-tipo="{tipo}" '
                    f'data-audio-path="{path}" '
                    f'data-audio-yt="{yt_id}" '
                    f'data-audio-start="{start_time}" '
                    f'data-audio-nome="{nome_traccia}" '
                    f'title="Riproduci {nome_traccia}">{nome_traccia}</button>'
                    f'</span>')
        else:
            return (f'<span class="audio-recommendation-wrapper">'
                    f'<span class="audio-recommendation-label">Musica consigliata:</span> '
                    f'<button class="btn-inline-audio btn-audio-large btn-audio-not-found" '
                    f'title="Traccia \'{nome_traccia}\' non trovata nel database" disabled>'
                    f'{nome_traccia}</button>'
                    f'</span>')
    return pattern.sub(sostituisci, testo_md)


def _processa_indizi_tags(testo_md):
    pattern = re.compile(r"@indizio:\s*(\d+)-(\d+)\s*\|\s*([^\n]+)")
    
    def sostituisci(m):
        indagine_id = m.group(1)
        nodo_id = m.group(2)
        nome = m.group(3).strip()
        
        return (f'<span class="audio-recommendation-wrapper">'
                f'<span class="audio-recommendation-label" style="color:var(--gold);">Indizio da sbloccare:</span> '
                f'<button class="btn-inline-indizio btn-audio-large" '
                f'data-indagine-id="{indagine_id}" '
                f'data-nodo-id="{nodo_id}" '
                f'title="Sblocca indizio: {nome}">{nome}</button>'
                f'</span>')

    return pattern.sub(sostituisci, testo_md)


def _processa_scene_tags(testo_md):
    pattern = re.compile(r"@scena:\s*(\d+)-(\d+)\s*\|\s*([^\n]+)")
    
    def sostituisci(m):
        indagine_id = m.group(1)
        scena_id = m.group(2)
        nome = m.group(3).strip()
        
        return (f'<span class="audio-recommendation-wrapper">'
                f'<span class="audio-recommendation-label" style="color:var(--gold);">Cambio scena:</span> '
                f'<button class="btn-inline-scena btn-audio-large" '
                f'data-indagine-id="{indagine_id}" '
                f'data-scena-id="{scena_id}" '
                f'title="Passa alla scena: {nome}">{nome}</button>'
                f'</span>')

    return pattern.sub(sostituisci, testo_md)


def _processa_sipario_tags(testo_md):
    pattern = re.compile(r"@sipario:\s*toggle", re.IGNORECASE)
    
    def sostituisci(m):
        return (f'<span class="audio-recommendation-wrapper">'
                f'<span class="audio-recommendation-label" style="color:var(--gold);">Azione master:</span> '
                f'<button class="btn-inline-sipario btn-audio-large" '
                f'title="Apri/Chiudi il sipario">🎭 Attiva Sipario</button>'
                f'</span>')

    return pattern.sub(sostituisci, testo_md)


def _processa_immagini(testo_md):
    """Converte la sintassi immagine Markdown in tag <img> con larghezza e
    allineamento opzionali. Attributi dopo l'alt separati da '|':
      ![alt](url)          → max-width:100%, allineata a sinistra
      ![alt|400](url)      → larghezza max 400px
      ![alt|centro](url)   → centrata
      ![alt|400|dx](url)   → larghezza 400px, allineata a destra
    """
    def sostituisci(m):
        alt, opts, src = m.group(1), m.group(2), m.group(3)
        larghezza = None
        align = "left"
        for tok in opts.split("|"):
            tok = tok.strip()
            if not tok:
                continue
            if tok.isdigit():
                larghezza = tok
            elif tok.lower() in _ALIGN_MAP:
                align = _ALIGN_MAP[tok.lower()]
        stile = ["display:block"]
        if larghezza:
            stile += [f"max-width:{larghezza}px", "width:100%"]
        else:
            stile.append("max-width:100%")
        if align == "center":
            stile += ["margin-left:auto", "margin-right:auto"]
        elif align == "right":
            stile += ["margin-left:auto", "margin-right:0"]
        else:
            stile += ["margin-left:0", "margin-right:auto"]
        return f'<img src="{escape(src)}" alt="{escape(alt)}" style="{";".join(stile)}">'
    return _RE_IMG.sub(sostituisci, testo_md)


def _proteggi_blocchi_master_e_personaggi(testo_md):
    """Sostituisce **(Master)** e **NomePersonaggio** con marcatori HTML
    PRIMA della conversione markdown, così il convertitore li lascia stare
    e possiamo applicarci classi CSS dedicate.

    Regola di distinzione: se il contenuto dentro **...** inizia con "(",
    è un blocco Master. Altrimenti è il nome di un personaggio.
    """

    def sostituisci(m):
        contenuto = m.group(1)
        if contenuto.startswith("("):
            return f'<span class="copione-master">{contenuto}</span>'
        else:
            return f'<span class="copione-personaggio">{contenuto}</span>'

    # **qualcosa** ma non a inizio riga di un titolo (#...) - i titoli non
    # usano ** quindi questo pattern semplice va bene per il nostro caso.
    pattern = re.compile(r"\*\*([^*]+)\*\*")
    return pattern.sub(sostituisci, testo_md)


def renderizza_sessione(numero_sessione):
    """Legge e concatena tutti i file di una sessione, applica il
    riconoscimento Master/personaggio, converte in HTML, ed estrae la
    lista degli heading H2 (per l'indice di navigazione laterale).

    Ritorna (titolo, html, heading_list) oppure (None, None, None) se la
    sessione non esiste. heading_list è una lista di dict:
    [{"id": "scena-0-...", "testo": "SCENA 0: ..."}, ...]

    Nota tecnica: l'estensione 'toc' di python-markdown si interrompe
    silenziosamente (smette di popolare toc_tokens dopo il primo titolo)
    quando il testo contiene tag HTML grezzi inline come i nostri <span>
    di Master/personaggio - è un comportamento limite della libreria
    quando mescola HTML raw con il parsing dei titoli. Per questo motivo
    estraiamo gli heading H2 parsando direttamente l'HTML già generato con
    BeautifulSoup, invece di fidarci di toc_tokens.
    """
    sessioni = elenca_sessioni()
    info = next((s for s in sessioni if s["numero"] == numero_sessione), None)
    if info is None:
        return None, None, None

    testo_unito = get_testo_sessione(numero_sessione)
    if not testo_unito.strip():
        return None, None, None

    testo_protetto = _processa_immagini(testo_unito)
    testo_protetto = _proteggi_blocchi_master_e_personaggi(testo_protetto)
    testo_protetto = _processa_audio_tags(testo_protetto)
    testo_protetto = _processa_indizi_tags(testo_protetto)
    testo_protetto = _processa_scene_tags(testo_protetto)
    testo_protetto = _processa_sipario_tags(testo_protetto)

    # toc ci serve solo per assegnare id univoci agli heading (gestisce da
    # sola le collisioni, es. titoli duplicati -> id_1, id_2...), anche se
    # non possiamo fidarci della sua lista toc_tokens per il motivo sopra.
    html = md_lib.markdown(testo_protetto, extensions=["nl2br", "toc"])

    heading_list = _estrai_h2_da_html(html)

    return info["titolo"], html, heading_list


def _estrai_h2_da_html(html):
    """Estrae {id, testo} di ogni <h2> dall'HTML già renderizzato.
    Salta gli H2 che contengono formattazione (* o **) per distinguerli
    dalle scene (h2 puliti)."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    risultato = []
    for h2 in soup.find_all("h2"):
        # Se contiene tag di formattazione, lo ignoriamo
        if h2.find(['strong', 'em', 'span']):
            continue
        risultato.append({
            "id": h2.get("id", ""),
            "testo": h2.get_text(strip=True),
        })
    return risultato