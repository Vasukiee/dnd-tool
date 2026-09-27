import json
import math
import re
from datetime import datetime

import db
from auth import richiedi_master, utente_e_master, vista_ristretta
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for, \
    Response

bp = Blueprint("indagini", __name__, url_prefix="/indagini")


def _json_per_script(obj):
    """Serializza in JSON reso sicuro per l'inserimento dentro un tag <script>.
    json.dumps NON escapa <, >, &: senza questo un valore utente come
    '</script>...' potrebbe chiudere il tag e iniettare HTML (XSS)."""
    return (
        json.dumps(obj, default=str)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )


def _calcola_stati_nodi(nodi, collegamenti, stati_sblocco, scena_corrente=None):
    """Calcola lo stato visivo di ogni nodo: ASSENTE, BLOCCATO_VISIBILE, SCOPERTO.
    stati_sblocco: dict {nodo_id: {scoperto, sbloccato_manualmente}} dalla cronologia attiva.
    scena_corrente: se fornita, i nodi di scene future vengono forzati ad ASSENTE (Concetto 3).
    Ritorna un dict {nodo_id: stato_str}.

    Addendum 9: dentro una scena già raggiunta ogni nodo è sempre BLOCCATO_VISIBILE
    indipendentemente dai genitori. La gerarchia genitore→figlio non è più un gatekeeper
    per lo sblocco — serve solo a decidere quando disegnare una freccia (lato frontend).

    Un nodo già scoperto resta SCOPERTO anche se la scena corrente torna indietro:
    le scene si possono giocare fuori ordine (es. sessione 3, piste 2-3-4).
    """
    stati = {}
    for nodo in nodi:
        nid = nodo["id"]
        if stati_sblocco.get(nid, {}).get("scoperto"):
            stati[nid] = "SCOPERTO"
        elif scena_corrente is not None and nodo["numero_nodo"] // 10 > scena_corrente:
            stati[nid] = "ASSENTE"
        else:
            stati[nid] = "BLOCCATO_VISIBILE"
    return stati


def _prima_scena_nodi(nodi):
    scene = [n["numero_nodo"] // 10 for n in nodi]
    return min(scene) if scene else 0


def _scena_corrente_effettiva(nodi, cronologia_attiva):
    scena = cronologia_attiva.get("scena_corrente", 0) if cronologia_attiva else 0
    return scena if scena > 0 else _prima_scena_nodi(nodi)


def _redigi_nodi_non_scoperti(nodi):
    """Versione player-safe della lista nodi: i non scoperti diventano stub
    con i soli campi necessari al layout (id, numero_nodo). Titoli, descrizioni
    e immagini dei nodi non ancora rivelati NON devono raggiungere il browser:
    la player view è pubblica e il sorgente della pagina è leggibile da chiunque.
    """
    redatti = []
    for n in nodi:
        if n.get("scoperto"):
            redatti.append(n)
        else:
            redatti.append({
                "id": n["id"],
                "numero_nodo": n["numero_nodo"],
                "titolo": "",
                "descrizione": None,
                "immagine_url": None,
                "tipo_speciale": None,
                "scoperto": False,
                "sbloccato_manualmente": False,
            })
    return redatti


# Articoli iniziali ignorati nell'ordinamento: "Il letto" va sotto la L.
_ARTICOLO_INIZIALE = re.compile(r"^(?:(?:il|lo|la|i|gli|le|un|uno|una)\s+|l'|un')", re.IGNORECASE)


def _chiave_punto_extra(scena, etichetta):
    return f"{scena}|{etichetta.strip().casefold()}"


def _punti_interesse(nodi, stati_sblocco, scena_corrente, punti_extra, extra_esaminati, per_master=False):
    """Cosa si può esaminare nella scena corrente, per la lista "Da esaminare".

    Le voci vengono dall'etichetta player-safe dei nodi (punto_interesse) e dalle
    esche della scena (cose da guardare che non nascondono indizi). Solo la scena
    in corso, mai titoli o descrizioni. Più indizi con la stessa etichetta sono
    una voce sola, esaminata appena uno è scoperto: la lista non tradisce quanti
    indizi nasconde un oggetto. L'ordine è alfabetico, così le esche non si
    riconoscono dalla posizione. Il flag "esca" va solo al master."""
    voci = {}

    def voce(etichetta):
        return voci.setdefault(etichetta.casefold(), {"etichetta": etichetta, "esaminato": False, "nodi": 0})

    for n in nodi:
        etichetta = (n.get("punto_interesse") or "").strip()
        if not etichetta or n["numero_nodo"] // 10 != scena_corrente:
            continue
        v = voce(etichetta)
        v["nodi"] += 1
        if stati_sblocco.get(n["id"], {}).get("scoperto"):
            v["esaminato"] = True
    for etichetta in punti_extra.get(scena_corrente, []):
        v = voce(etichetta)
        if v["nodi"] == 0 and _chiave_punto_extra(scena_corrente, etichetta) in extra_esaminati:
            v["esaminato"] = True

    ordinate = sorted(voci.values(), key=lambda v: _ARTICOLO_INIZIALE.sub("", v["etichetta"].casefold()))
    if per_master:
        return [{"etichetta": v["etichetta"], "esaminato": v["esaminato"], "esca": v["nodi"] == 0} for v in ordinate]
    return [{"etichetta": v["etichetta"], "esaminato": v["esaminato"]} for v in ordinate]


def _lista_mostrata(cronologia, scena):
    """La lista di una scena compare ai giocatori solo dopo che il master l'ha
    mostrata (bottone @esamina del copione o interruttore della vista live)."""
    mostrate = cronologia.get("liste_mostrate") if cronologia else None
    return bool(mostrate) and scena in json.loads(mostrate)


def _punti_interesse_indagine(indagine_id, nodi, stati_sblocco, cronologia, scena_corrente, per_master=False):
    if not per_master and not _lista_mostrata(cronologia, scena_corrente):
        return []
    esaminati = cronologia.get("punti_extra_esaminati") if cronologia else None
    return _punti_interesse(
        nodi, stati_sblocco, scena_corrente,
        db.get_punti_extra(indagine_id),
        set(json.loads(esaminati)) if esaminati else set(),
        per_master=per_master,
    )


def _merge_sblocco_in_nodi(nodi, stati_sblocco):
    """Inietta scoperto/sbloccato_manualmente dalla cronologia nei dict nodo."""
    for n in nodi:
        s = stati_sblocco.get(n["id"], {})
        n["scoperto"] = s.get("scoperto", False)
        n["sbloccato_manualmente"] = s.get("sbloccato_manualmente", False)
    return nodi


def _scene_gifs_dirette(indagine_id):
    """Solo le immagini impostate sulla scena stessa (per i campi dell'editor)."""
    out = {}
    for numero, info in db.get_scene_gifs(indagine_id).items():
        if info["has_file"]:
            out[numero] = url_for(
                ".indagini_scena_sfondo",
                indagine_id=indagine_id,
                numero_scena=numero,
                v=info["versione"],
            )
        elif info["gif_url"]:
            out[numero] = info["gif_url"]
    return out


def _scene_gifs_ereditate(indagine_id):
    """Sfondi ereditati dal luogo della scena (o dal primo antenato che ne ha uno).
    {numero_scena: (url, nome_luogo)}"""
    out = {}
    for numero, info in db.get_sfondi_ereditati(indagine_id).items():
        if info["has_file"]:
            url = url_for("indagini.sfondo_location", location_id=info["location_id"], v=info["versione"])
        else:
            url = info["url"]
        out[numero] = (url, info["location_nome"])
    return out


def _scene_gifs_display(indagine_id):
    """Sfondo effettivo per scena: immagine propria, altrimenti quella del luogo.
    Le scene senza nessuno dei due cadono sullo sfondo di default lato client."""
    out = {n: url for n, (url, _) in _scene_gifs_ereditate(indagine_id).items()}
    out.update(_scene_gifs_dirette(indagine_id))
    return out


LAVAGNA_MAX_FILI = 500


def _coordinata(v):
    """Frazione 0..1 della bacheca; None se non è un numero finito."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return min(1.0, max(0.0, float(v)))


def _normalizza_lavagna(raw, ammessi):
    """Riduce lo stato della bacheca ai soli indizi in `ammessi` (gli scoperti
    della cronologia) e scarta tutto ciò che non ha la forma attesa. Si usa sia
    in scrittura (dati dal client) sia in lettura (la player view è pubblica)."""
    raw = raw if isinstance(raw, dict) else {}

    posizioni = {}
    pos_raw = raw.get("posizioni")
    if isinstance(pos_raw, dict):
        for k, v in pos_raw.items():
            try:
                nid = int(k)
            except (TypeError, ValueError):
                continue
            if nid not in ammessi or not isinstance(v, (list, tuple)) or len(v) != 2:
                continue
            x, y = _coordinata(v[0]), _coordinata(v[1])
            if x is not None and y is not None:
                posizioni[str(nid)] = [round(x, 4), round(y, 4)]

    rimossi = []
    rim_raw = raw.get("rimossi")
    if isinstance(rim_raw, list):
        for v in rim_raw:
            if isinstance(v, int) and not isinstance(v, bool) and v in ammessi and v not in rimossi:
                rimossi.append(v)

    fili, visti = [], set()
    fili_raw = raw.get("fili")
    if isinstance(fili_raw, list):
        for f in fili_raw:
            if not isinstance(f, (list, tuple)) or len(f) != 2:
                continue
            a, b = f
            if not all(isinstance(v, int) and not isinstance(v, bool) for v in (a, b)):
                continue
            chiave = (min(a, b), max(a, b))
            if a == b or a not in ammessi or b not in ammessi or chiave in visti:
                continue
            visti.add(chiave)
            fili.append(list(chiave))
            if len(fili) >= LAVAGNA_MAX_FILI:
                break

    return {"posizioni": posizioni, "rimossi": rimossi, "fili": fili}


def _lavagna_player(indagine_id, cronologia_attiva, scena_corrente, scoperti_ids):
    """Stato della lavagna per la player view. Dice solo se la scena CORRENTE
    è una lavagna: l'elenco delle scene marcate anticiperebbe il copione."""
    attiva = db.scena_e_lavagna(indagine_id, scena_corrente)
    out = {"attiva": attiva, "versione": 0, "cronologia": None}
    if attiva and cronologia_attiva:
        out["cronologia"] = cronologia_attiva["id"]
        out["versione"] = cronologia_attiva.get("lavagna_versione") or 0
        out.update(_normalizza_lavagna(db.get_lavagna(cronologia_attiva), set(scoperti_ids)))
    return out


@bp.route("/")
def lista_indagini():
    indagini = db.get_all_indagini(solo_visibili=vista_ristretta())
    return render_template("indagini_lista.html", active="indagini", indagini=indagini)


@bp.route("/nuova", methods=["GET", "POST"])
@richiedi_master
def nuova_indagine():
    if request.method == "POST":
        titolo = request.form["titolo"].strip()
        descrizione = request.form.get("descrizione", "").strip() or None
        attiva = request.form.get("attiva") == "1"
        visibile_giocatrice = request.form.get("visibile_giocatrice") == "1"
        ind_id = db.add_indagine(titolo, descrizione, attiva, visibile_giocatrice)
        flash(f"Indagine '{titolo}' creata.")
        return redirect(url_for(".indagini_editor", indagine_id=ind_id))
    return render_template("indagini_form.html", active="indagini", indagine=None)


@bp.route("/<int:indagine_id>/edita", methods=["GET", "POST"])
@richiedi_master
def edita_indagine(indagine_id):
    indagine = db.get_indagine(indagine_id)
    if not indagine:
        flash("Indagine non trovata.")
        return redirect(url_for(".lista_indagini"))
    if request.method == "POST":
        titolo = request.form["titolo"].strip()
        descrizione = request.form.get("descrizione", "").strip() or None
        attiva = request.form.get("attiva") == "1"
        visibile_giocatrice = request.form.get("visibile_giocatrice") == "1"
        db.update_indagine(indagine_id, titolo=titolo, descrizione=descrizione, attiva=attiva, visibile_giocatrice=visibile_giocatrice)
        flash(f"Indagine '{titolo}' aggiornata.")
        return redirect(url_for(".lista_indagini"))
    return render_template("indagini_form.html", active="indagini", indagine=indagine)


@bp.route("/<int:indagine_id>/elimina", methods=["POST"])
@richiedi_master
def elimina_indagine(indagine_id):
    db.delete_indagine(indagine_id)
    flash("Indagine eliminata.")
    return redirect(url_for(".lista_indagini"))


@bp.route("/<int:indagine_id>/editor")
@richiedi_master
def indagini_editor(indagine_id):
    indagine = db.get_indagine(indagine_id)
    if not indagine:
        flash("Indagine non trovata.")
        return redirect(url_for(".lista_indagini"))
    nodi = db.get_nodi_indagine(indagine_id)
    collegamenti = db.get_collegamenti(indagine_id)
    scene_gifs = _scene_gifs_dirette(indagine_id)
    scene_ereditate = _scene_gifs_ereditate(indagine_id)
    info_scene = db.get_scene_gifs(indagine_id)
    scene_location = {n: info["location_id"] for n, info in info_scene.items()}
    scene_lavagna = {n for n, info in info_scene.items() if info["lavagna"]}
    # Anche le scene senza indizi (i buchi nella numerazione) vanno mostrate:
    # il copione può passarci con @scena e hanno comunque bisogno di un luogo.
    # Più una scena oltre l'ultima: di solito è lì che va la lavagna di fine sessione.
    scene_note = {n["numero_nodo"] // 10 for n in nodi} | set(scene_location)
    scene_numeri = sorted(set(range(1, max(scene_note) + 2)) | scene_note) if scene_note else [1]
    graph_data = _json_per_script({
        "nodi": nodi,
        "collegamenti": collegamenti,
    })
    return render_template(
        "indagini_editor.html",
        active="indagini",
        indagine=indagine,
        nodi=nodi,
        collegamenti=collegamenti,
        graph_data=graph_data,
        scene_numeri=scene_numeri,
        scene_gifs=scene_gifs,
        scene_ereditate=scene_ereditate,
        scene_location=scene_location,
        punti_extra=db.get_punti_extra(indagine_id),
        scene_lavagna=scene_lavagna,
        locations=db.get_all_locations(),
    )


@bp.route("/<int:indagine_id>/scene/<int:numero_scena>/gif", methods=["POST"])
@richiedi_master
def indagini_salva_scena_gif(indagine_id, numero_scena):
    """Collega la scena a un luogo: lo sfondo si sceglie nella pagina del luogo.
    Le immagini salvate in passato sulla scena restano (e hanno la precedenza)
    finché non vengono rimosse da qui."""
    db.set_scena_location(indagine_id, numero_scena, request.form.get("location_id", type=int))
    # Checkbox: se non è spuntata il browser non manda nulla.
    db.set_scena_lavagna(indagine_id, numero_scena, request.form.get("lavagna") == "1")
    if request.form.get("rimuovi_immagine") == "1":
        db.upsert_scena_gif(indagine_id, numero_scena, None)
    return redirect(url_for(".indagini_editor", indagine_id=indagine_id))


@bp.route("/sfondi-luogo/<int:location_id>")
def sfondo_location(location_id):
    """Serve lo sfondo di un luogo salvato nel DB. Pubblico come quello di scena:
    la player view ne ha bisogno."""
    risultato = db.get_sfondo_location_file(location_id)
    if not risultato:
        abort(404)
    data, mime = risultato
    resp = Response(data, mimetype=mime or "application/octet-stream")
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


@bp.route("/<int:indagine_id>/scene/<int:numero_scena>/sfondo")
def indagini_scena_sfondo(indagine_id, numero_scena):
    """Serve l'immagine di sfondo salvata nel DB. Accessibile anche in
    modalità giocatrice: la player view ne ha bisogno."""
    risultato = db.get_scena_gif_file(indagine_id, numero_scena)
    if not risultato:
        abort(404)
    data, mime = risultato
    resp = Response(data, mimetype=mime or "application/octet-stream")
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


@bp.route("/<int:indagine_id>/nodi/nuovo", methods=["POST"])
@richiedi_master
def indagini_nuovo_nodo(indagine_id):
    titolo = request.form["titolo"].strip()
    numero_nodo = int(request.form.get("numero_nodo") or 0)
    descrizione = request.form.get("descrizione", "").strip() or None
    immagine_url = request.form.get("immagine_url", "").strip() or None
    regola_sblocco = request.form.get("regola_sblocco", "TUTTI")
    tipo_speciale = request.form.get("tipo_speciale", "").strip() or None
    punto_interesse = request.form.get("punto_interesse", "").strip() or None
    db.add_nodo(indagine_id, numero_nodo, titolo, descrizione, immagine_url, regola_sblocco, tipo_speciale,
                punto_interesse)
    return redirect(url_for(".indagini_editor", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/nodi/<int:nodo_id>/edita", methods=["POST"])
@richiedi_master
def indagini_edita_nodo(indagine_id, nodo_id):
    titolo = request.form["titolo"].strip()
    numero_nodo = int(request.form.get("numero_nodo") or 0)
    descrizione = request.form.get("descrizione", "").strip() or None
    immagine_url = request.form.get("immagine_url", "").strip() or None
    regola_sblocco = request.form.get("regola_sblocco", "TUTTI")
    tipo_speciale = request.form.get("tipo_speciale", "").strip() or None
    kwargs = dict(
        titolo=titolo,
        numero_nodo=numero_nodo,
        descrizione=descrizione,
        immagine_url=immagine_url,
        regola_sblocco=regola_sblocco,
        tipo_speciale=tipo_speciale,
        punto_interesse=request.form.get("punto_interesse", "").strip() or None,
    )
    livello_sfx_str = request.form.get("livello_sfx", "").strip()
    if livello_sfx_str in ("1", "2", "3"):
        kwargs["livello_sfx"] = int(livello_sfx_str)
        kwargs["livello_sfx_manuale"] = True
    db.update_nodo(nodo_id, **kwargs)
    return redirect(url_for(".indagini_editor", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/nodi/<int:nodo_id>/ricalcola-sfx", methods=["POST"])
@richiedi_master
def indagini_ricalcola_sfx(indagine_id, nodo_id):
    db.ricalcola_livello_sfx_singolo(nodo_id)
    return redirect(url_for(".indagini_editor", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/nodi/<int:nodo_id>/elimina", methods=["POST"])
@richiedi_master
def indagini_elimina_nodo(indagine_id, nodo_id):
    db.delete_nodo(nodo_id)
    return redirect(url_for(".indagini_editor", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/collegamenti/nuovo", methods=["POST"])
@richiedi_master
def indagini_nuovo_collegamento(indagine_id):
    genitore_id = int(request.form["nodo_genitore_id"])
    figlio_id = int(request.form["nodo_figlio_id"])
    if genitore_id != figlio_id:
        db.add_collegamento(indagine_id, genitore_id, figlio_id)
    return redirect(url_for(".indagini_editor", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/collegamenti/<int:collegamento_id>/elimina", methods=["POST"])
@richiedi_master
def indagini_elimina_collegamento(indagine_id, collegamento_id):
    db.delete_collegamento(collegamento_id)
    return redirect(url_for(".indagini_editor", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/live")
@richiedi_master
def indagini_live(indagine_id):
    indagine = db.get_indagine(indagine_id)
    if not indagine:
        flash("Indagine non trovata.")
        return redirect(url_for(".lista_indagini"))
    nodi = db.get_nodi_indagine(indagine_id)
    collegamenti = db.get_collegamenti(indagine_id)
    cronologia_attiva = db.get_cronologia_attiva(indagine_id)
    stati_sblocco = db.get_stato_nodi_cronologia(cronologia_attiva["id"]) if cronologia_attiva else {}
    scena_corrente_val = _scena_corrente_effettiva(nodi, cronologia_attiva)
    nodi = _merge_sblocco_in_nodi(nodi, stati_sblocco)
    stati = _calcola_stati_nodi(nodi, collegamenti, stati_sblocco, scena_corrente=scena_corrente_val)
    cronologie = db.get_cronologie_indagine(indagine_id)
    graph_data = _json_per_script({
        "nodi": nodi,
        "collegamenti": collegamenti,
        "stati": stati,
        "cronologia_id": cronologia_attiva["id"] if cronologia_attiva else None,
        "scena_corrente": scena_corrente_val,
        "sipario_aperto": cronologia_attiva.get("sipario_aperto", False) if cronologia_attiva else False,
        "punti_interesse": _punti_interesse_indagine(
            indagine_id, nodi, stati_sblocco, cronologia_attiva, scena_corrente_val, per_master=True),
        "lista_mostrata": _lista_mostrata(cronologia_attiva, scena_corrente_val),
    })
    return render_template(
        "indagini_live.html",
        active="indagini",
        indagine=indagine,
        cronologia_attiva=cronologia_attiva,
        cronologie=cronologie,
        graph_data=graph_data,
    )


@bp.route("/<int:indagine_id>/stato-live")
@richiedi_master
def indagini_stato_live(indagine_id):
    """API JSON per sincronizzare la vista live master con comandi esterni
    come copione, player controls e toggle sipario."""
    indagine = db.get_indagine(indagine_id)
    if not indagine:
        return jsonify({"error": "non trovata"}), 404
    nodi = db.get_nodi_indagine(indagine_id)
    collegamenti = db.get_collegamenti(indagine_id)
    cronologia_attiva = db.get_cronologia_attiva(indagine_id)
    stati_sblocco = db.get_stato_nodi_cronologia(cronologia_attiva["id"]) if cronologia_attiva else {}
    scena_corrente_val = _scena_corrente_effettiva(nodi, cronologia_attiva)
    stati = _calcola_stati_nodi(nodi, collegamenti, stati_sblocco, scena_corrente=scena_corrente_val)
    return jsonify({
        "cronologia_id": cronologia_attiva["id"] if cronologia_attiva else None,
        "scena_corrente": scena_corrente_val,
        "sipario_aperto": cronologia_attiva.get("sipario_aperto", False) if cronologia_attiva else False,
        "stati": stati,
        "punti_interesse": _punti_interesse_indagine(
            indagine_id, nodi, stati_sblocco, cronologia_attiva, scena_corrente_val, per_master=True),
        "lista_mostrata": _lista_mostrata(cronologia_attiva, scena_corrente_val),
    })


@bp.route("/<int:indagine_id>/reset", methods=["POST"])
@richiedi_master
def indagini_reset(indagine_id):
    db.disattiva_cronologia_attiva(indagine_id)
    flash("Cronologia archiviata. La prossima indagine partirà da zero al primo sblocco.")
    return redirect(url_for(".indagini_live", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/nodi/<int:nodo_id>/sblocca", methods=["POST"])
@richiedi_master
def indagini_sblocca_nodo(indagine_id, nodo_id):
    nodo = db.get_nodo(nodo_id)
    if not nodo or nodo["indagine_id"] != indagine_id:
        return jsonify({"error": "nodo non trovato"}), 404
    manuale = request.json.get("manuale", True) if request.is_json else True

    cronologia_attiva = db.get_cronologia_attiva(indagine_id)
    cronologia_nuova = None
    if not cronologia_attiva:
        nome = f"Cronologia del {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        cronologia_nuova = db.crea_cronologia(indagine_id, nome)
        cronologia_attiva = cronologia_nuova

    db.sblocca_nodo(nodo_id, manuale, cronologia_attiva["id"])

    nodi = db.get_nodi_indagine(indagine_id)
    collegamenti = db.get_collegamenti(indagine_id)
    stati_sblocco = db.get_stato_nodi_cronologia(cronologia_attiva["id"])
    scena_corrente_val = _scena_corrente_effettiva(nodi, cronologia_attiva)
    nodi = _merge_sblocco_in_nodi(nodi, stati_sblocco)
    stati = _calcola_stati_nodi(nodi, collegamenti, stati_sblocco, scena_corrente=scena_corrente_val)
    return jsonify({
        "nodi": nodi,
        "stati": stati,
        "punti_interesse": _punti_interesse_indagine(
            indagine_id, nodi, stati_sblocco, cronologia_attiva, scena_corrente_val, per_master=True),
        "cronologia_nuova": {
            "id": cronologia_nuova["id"],
            "nome": cronologia_nuova["nome"],
            "creata_il": str(cronologia_nuova["creata_il"]),
        } if cronologia_nuova else None,
    })


@bp.route("/<int:indagine_id>/cronologie/<int:cronologia_id>/attiva", methods=["POST"])
@richiedi_master
def indagini_attiva_cronologia(indagine_id, cronologia_id):
    db.attiva_cronologia(cronologia_id, indagine_id)
    return redirect(url_for(".indagini_live", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/cronologie/<int:cronologia_id>/elimina", methods=["POST"])
@richiedi_master
def indagini_elimina_cronologia(indagine_id, cronologia_id):
    db.elimina_cronologia(cronologia_id)
    return redirect(url_for(".indagini_live", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/cronologie/<int:cronologia_id>/rinomina", methods=["POST"])
@richiedi_master
def indagini_rinomina_cronologia(indagine_id, cronologia_id):
    nome = (request.json.get("nome", "") if request.is_json else request.form.get("nome", "")).strip()
    if not nome:
        return jsonify({"error": "nome vuoto"}), 400
    db.rinomina_cronologia(cronologia_id, nome)
    return jsonify({"nome": nome})


@bp.route("/<int:indagine_id>/avanza-scena", methods=["POST"])
@richiedi_master
def indagini_avanza_scena(indagine_id):
    req_scena = request.json.get("scena_corrente") if request.is_json else None
    nuova_scena = int(req_scena) if req_scena is not None else 2

    cronologia_attiva = db.get_cronologia_attiva(indagine_id)
    cronologia_nuova = None
    if not cronologia_attiva:
        nome = f"Cronologia del {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        cronologia_nuova = db.crea_cronologia(indagine_id, nome)
        cronologia_attiva = cronologia_nuova

    sipario_aperto = cronologia_attiva.get("sipario_aperto", False)
    db.avanza_scena_cronologia(cronologia_attiva["id"], nuova_scena)
    if nuova_scena == 0:
        db.set_sipario_aperto(cronologia_attiva["id"], True)
        sipario_aperto = True

    nodi = db.get_nodi_indagine(indagine_id)
    collegamenti = db.get_collegamenti(indagine_id)
    stati_sblocco = db.get_stato_nodi_cronologia(cronologia_attiva["id"])
    nodi = _merge_sblocco_in_nodi(nodi, stati_sblocco)
    stati = _calcola_stati_nodi(nodi, collegamenti, stati_sblocco, scena_corrente=nuova_scena)

    return jsonify({
        "scena_corrente": nuova_scena,
        "sipario_aperto": sipario_aperto,
        "stati": stati,
        "punti_interesse": _punti_interesse_indagine(
            indagine_id, nodi, stati_sblocco, cronologia_attiva, nuova_scena, per_master=True),
        "lista_mostrata": _lista_mostrata(db.get_cronologia_attiva(indagine_id), nuova_scena),
        "cronologia_nuova": {
            "id": cronologia_nuova["id"],
            "nome": cronologia_nuova["nome"],
            "creata_il": str(cronologia_nuova["creata_il"]),
        } if cronologia_nuova else None,
    })


@bp.route("/<int:indagine_id>/player")
def indagini_player(indagine_id):
    """Pagina player-facing: mostra solo gli indizi scoperti, senza controlli DM.
    Pensata per screenshare Discord — si aggiorna via polling."""
    indagine = db.get_indagine(indagine_id)
    if not indagine:
        flash("Indagine non trovata.")
        return redirect(url_for(".lista_indagini"))
    nodi = db.get_nodi_indagine(indagine_id)
    collegamenti = db.get_collegamenti(indagine_id)
    cronologia_attiva = db.get_cronologia_attiva(indagine_id)
    stati_sblocco = db.get_stato_nodi_cronologia(cronologia_attiva["id"]) if cronologia_attiva else {}
    scena_corrente_val = _scena_corrente_effettiva(nodi, cronologia_attiva)
    punti_interesse = _punti_interesse_indagine(indagine_id, nodi, stati_sblocco, cronologia_attiva, scena_corrente_val)
    nodi = _redigi_nodi_non_scoperti(_merge_sblocco_in_nodi(nodi, stati_sblocco))
    scoperti_ids = [nid for nid, stato in stati_sblocco.items() if stato.get("scoperto")]
    scene_gifs = _scene_gifs_display(indagine_id)
    scene_gifs_str = {str(k): v for k, v in scene_gifs.items()}
    graph_data = _json_per_script({
        "nodi": nodi,
        "collegamenti": collegamenti,
        "scoperti_ids": scoperti_ids,
        "scena_corrente": scena_corrente_val,
        "sipario_aperto": cronologia_attiva.get("sipario_aperto", False) if cronologia_attiva else False,
        "scene_gifs": scene_gifs_str,
        "punti_interesse": punti_interesse,
        "lavagna": _lavagna_player(indagine_id, cronologia_attiva, scena_corrente_val, scoperti_ids),
    })
    return render_template(
        "indagini_player.html",
        indagine=indagine,
        graph_data=graph_data,
        puo_gestire_lavagna=utente_e_master(),
    )


@bp.route("/<int:indagine_id>/stato-player")
def indagini_stato_player(indagine_id):
    """API JSON leggera per il polling della player view.
    Ritorna solo gli ID dei nodi scoperti e la scena corrente."""
    indagine = db.get_indagine(indagine_id)
    if not indagine:
        return jsonify({"error": "non trovata"}), 404
    cronologia_attiva = db.get_cronologia_attiva(indagine_id)
    if not cronologia_attiva:
        nodi = db.get_nodi_indagine(indagine_id)
        prima_scena = _prima_scena_nodi(nodi)
        return jsonify({
            "scoperti_ids": [],
            "scena_corrente": prima_scena,
            "sipario_aperto": False,
            "nodi": [],
            "punti_interesse": _punti_interesse_indagine(indagine_id, nodi, {}, None, prima_scena),
            "lavagna": _lavagna_player(indagine_id, None, prima_scena, []),
        })
    stati_sblocco = db.get_stato_nodi_cronologia(cronologia_attiva["id"])
    scoperti_ids = [nodo_id for nodo_id, stato in stati_sblocco.items() if stato.get("scoperto")]
    scene_gifs = _scene_gifs_display(indagine_id)
    scene_gifs_str = {str(k): v for k, v in scene_gifs.items()}
    # La pagina player riceve al primo caricamento solo stub dei nodi non
    # scoperti: qui alleghiamo i dati completi dei nodi ormai scoperti, così
    # il frontend può renderizzare quelli rivelati durante la sessione.
    nodi = _merge_sblocco_in_nodi(db.get_nodi_indagine(indagine_id), stati_sblocco)
    nodi_scoperti = [n for n in nodi if n.get("scoperto")]
    scena_corrente_val = _scena_corrente_effettiva(nodi, cronologia_attiva)
    return jsonify({
        "scoperti_ids": scoperti_ids,
        "scena_corrente": scena_corrente_val,
        "sipario_aperto": cronologia_attiva.get("sipario_aperto", False),
        "nodi": nodi_scoperti,
        "scene_gifs": scene_gifs_str,
        "punti_interesse": _punti_interesse_indagine(
            indagine_id, nodi, stati_sblocco, cronologia_attiva, scena_corrente_val),
        "lavagna": _lavagna_player(indagine_id, cronologia_attiva, scena_corrente_val, scoperti_ids),
    })


@bp.route("/<int:indagine_id>/scene/<int:numero_scena>/punti-extra", methods=["POST"])
@richiedi_master
def indagini_salva_punti_extra(indagine_id, numero_scena):
    db.set_punti_extra_scena(indagine_id, numero_scena, request.form.get("punti_extra", ""))
    return redirect(url_for(".indagini_editor", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/punti-extra/esaminato", methods=["POST"])
@richiedi_master
def indagini_toggle_punto_extra(indagine_id):
    """Barra (o ripristina) un'esca della scena corrente: non avendo un nodo
    da sbloccare, la segna a mano il master dalla vista live."""
    etichetta = ((request.json or {}).get("etichetta") or "").strip() if request.is_json else ""
    if not etichetta:
        return jsonify({"error": "etichetta vuota"}), 400
    cronologia = db.get_cronologia_attiva(indagine_id)
    if not cronologia:
        nome = f"Cronologia del {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        cronologia = db.crea_cronologia(indagine_id, nome)
    nodi = db.get_nodi_indagine(indagine_id)
    scena = _scena_corrente_effettiva(nodi, cronologia)
    db.toggle_punto_extra_esaminato(cronologia["id"], _chiave_punto_extra(scena, etichetta))
    cronologia = db.get_cronologia_attiva(indagine_id)
    stati_sblocco = db.get_stato_nodi_cronologia(cronologia["id"])
    return jsonify({
        "punti_interesse": _punti_interesse_indagine(
            indagine_id, nodi, stati_sblocco, cronologia, scena, per_master=True),
    })


@bp.route("/<int:indagine_id>/lista-esamina", methods=["POST"])
@richiedi_master
def indagini_lista_esamina(indagine_id):
    """Mostra (o nasconde) ai giocatori la lista "Da esaminare" di una scena.
    JSON: {"scena": n (default: scena corrente), "mostra": true/false (default true)}."""
    dati = request.json if request.is_json else {}
    cronologia = db.get_cronologia_attiva(indagine_id)
    if not cronologia:
        nome = f"Cronologia del {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        cronologia = db.crea_cronologia(indagine_id, nome)
    nodi = db.get_nodi_indagine(indagine_id)
    scena_corrente = _scena_corrente_effettiva(nodi, cronologia)
    scena = int(dati["scena"]) if dati.get("scena") is not None else scena_corrente
    db.set_lista_mostrata(cronologia["id"], scena, dati.get("mostra", True) is not False)
    cronologia = db.get_cronologia_attiva(indagine_id)
    stati_sblocco = db.get_stato_nodi_cronologia(cronologia["id"])
    return jsonify({
        "scena": scena,
        "scena_corrente": scena_corrente,
        "lista_mostrata": _lista_mostrata(cronologia, scena_corrente),
        "punti_interesse": _punti_interesse_indagine(
            indagine_id, nodi, stati_sblocco, cronologia, scena_corrente, per_master=True),
    })


def _lavagna_corrente(indagine_id):
    """(cronologia attiva, scena corrente, id scoperti) per le rotte della lavagna."""
    cronologia = db.get_cronologia_attiva(indagine_id)
    nodi = db.get_nodi_indagine(indagine_id)
    scena = _scena_corrente_effettiva(nodi, cronologia)
    scoperti = []
    if cronologia:
        stati = db.get_stato_nodi_cronologia(cronologia["id"])
        scoperti = [nid for nid, s in stati.items() if s.get("scoperto")]
    return cronologia, scena, scoperti


@bp.route("/<int:indagine_id>/lavagna")
def indagini_lavagna(indagine_id):
    """Stato della lavagna, per l'aggiornamento rapido mentre è aperta.
    Pubblico come stato-player: contiene solo indizi già scoperti."""
    cronologia, scena, scoperti = _lavagna_corrente(indagine_id)
    return jsonify(_lavagna_player(indagine_id, cronologia, scena, scoperti))


# Spostare le carte e tendere o tagliare i fili è il gioco della lavagna, e lo
# fa anche la giocatrice; togliere o rimettere indizi resta del master.
LAVAGNA_OP_GIOCATRICE = {"sposta", "collega", "taglia"}
LAVAGNA_OP_MASTER = LAVAGNA_OP_GIOCATRICE | {"togli", "rimetti"}


def _id_intero(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _applica_op_lavagna(stato, dati, scoperti):
    """Applica un'operazione allo stato corrente (già letto sotto lock).
    `posizioni`, facoltativo su ogni operazione, fissa le carte ancora nella
    griglia predefinita: il client la manda prima di cambiare la disposizione."""
    stato = _normalizza_lavagna(stato, scoperti)
    nuove = _normalizza_lavagna({"posizioni": dati.get("posizioni")}, scoperti)["posizioni"]
    stato["posizioni"].update(nuove)

    op = dati["op"]
    if op in ("collega", "taglia"):
        a, b = _id_intero(dati.get("a")), _id_intero(dati.get("b"))
        if a is None or b is None or a == b or a not in scoperti or b not in scoperti:
            return stato
        filo = [min(a, b), max(a, b)]
        if op == "collega" and filo not in stato["fili"] and len(stato["fili"]) < LAVAGNA_MAX_FILI:
            stato["fili"].append(filo)
        elif op == "taglia":
            stato["fili"] = [f for f in stato["fili"] if f != filo]
    elif op in ("togli", "rimetti"):
        nid = _id_intero(dati.get("id"))
        if nid is None or nid not in scoperti:
            return stato
        stato["posizioni"].pop(str(nid), None)
        if op == "togli" and nid not in stato["rimossi"]:
            stato["rimossi"].append(nid)
        elif op == "rimetti":
            stato["rimossi"] = [x for x in stato["rimossi"] if x != nid]
    return stato


@bp.route("/<int:indagine_id>/lavagna", methods=["POST"])
def indagini_modifica_lavagna(indagine_id):
    """Una modifica alla lavagna: {"op": ..., "posizioni"?: {...}, ...}.
    Si modifica solo mentre la scena corrente è una lavagna, e solo con
    indizi scoperti nella cronologia attiva."""
    dati = request.get_json(silent=True)
    if not isinstance(dati, dict) or dati.get("op") not in LAVAGNA_OP_MASTER:
        return jsonify({"error": "operazione non valida"}), 400
    if dati["op"] not in LAVAGNA_OP_GIOCATRICE and not utente_e_master():
        return jsonify({"ok": False, "errore": "Autenticazione master richiesta"}), 403
    cronologia, scena, scoperti = _lavagna_corrente(indagine_id)
    if not cronologia or not db.scena_e_lavagna(indagine_id, scena):
        return jsonify({"error": "la lavagna non è aperta"}), 409
    ammessi = set(scoperti)
    versione, stato = db.modifica_lavagna(
        cronologia["id"], lambda s: _applica_op_lavagna(s, dati, ammessi))
    if versione is None:
        return jsonify({"error": "nessuna cronologia attiva"}), 409
    return jsonify({"attiva": True, "cronologia": cronologia["id"], "versione": versione, **stato})


@bp.route("/<int:indagine_id>/sipario", methods=["POST"])
@richiedi_master
def indagini_sipario(indagine_id):
    cronologia = db.get_cronologia_attiva(indagine_id)
    if not cronologia:
        nome = f"Cronologia del {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        cronologia = db.crea_cronologia(indagine_id, nome)
    nuovo_stato = db.toggle_sipario(indagine_id)
    return jsonify({"success": True, "sipario_aperto": nuovo_stato})
