import json
import os
from datetime import datetime

import db
from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for, \
    Response

bp = Blueprint("indagini", __name__, url_prefix="/indagini")


def _calcola_stati_nodi(nodi, collegamenti, stati_sblocco, scena_corrente=None):
    """Calcola lo stato visivo di ogni nodo: ASSENTE, BLOCCATO_VISIBILE, SCOPERTO.
    stati_sblocco: dict {nodo_id: {scoperto, sbloccato_manualmente}} dalla cronologia attiva.
    scena_corrente: se fornita, i nodi di scene future vengono forzati ad ASSENTE (Concetto 3).
    Ritorna un dict {nodo_id: stato_str}.

    Addendum 9: dentro una scena già raggiunta ogni nodo è sempre BLOCCATO_VISIBILE
    indipendentemente dai genitori. La gerarchia genitore→figlio non è più un gatekeeper
    per lo sblocco — serve solo a decidere quando disegnare una freccia (lato frontend).
    """
    stati = {}
    for nodo in nodi:
        nid = nodo["id"]
        if scena_corrente is not None and nodo["numero_nodo"] // 10 > scena_corrente:
            stati[nid] = "ASSENTE"
        elif stati_sblocco.get(nid, {}).get("scoperto"):
            stati[nid] = "SCOPERTO"
        else:
            stati[nid] = "BLOCCATO_VISIBILE"
    return stati


def _merge_sblocco_in_nodi(nodi, stati_sblocco):
    """Inietta scoperto/sbloccato_manualmente dalla cronologia nei dict nodo."""
    for n in nodi:
        s = stati_sblocco.get(n["id"], {})
        n["scoperto"] = s.get("scoperto", False)
        n["sbloccato_manualmente"] = s.get("sbloccato_manualmente", False)
    return nodi


_IMAGE_MIME_PER_EXT = {
    ".gif": "image/gif",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
_MAX_SCENA_GIF_BYTES = 10 * 1024 * 1024


def _scene_gifs_display(indagine_id):
    """URL di visualizzazione degli sfondi scena: la route interna se
    l'immagine è nel DB, altrimenti l'eventuale URL esterno."""
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


def _url_sfondo_interno(gif_url, indagine_id, numero_scena):
    return gif_url.startswith(f"/indagini/{indagine_id}/scene/{numero_scena}/sfondo")


@bp.route("/")
def lista_indagini():
    indagini = db.get_all_indagini(solo_visibili=session.get("modalita_giocatrice"))
    return render_template("indagini_lista.html", active="indagini", indagini=indagini)


@bp.route("/nuova", methods=["GET", "POST"])
def nuova_indagine():
    if session.get("modalita_giocatrice"):
        return redirect(url_for("home"))
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
def edita_indagine(indagine_id):
    if session.get("modalita_giocatrice"):
        return redirect(url_for("home"))
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
def elimina_indagine(indagine_id):
    if session.get("modalita_giocatrice"):
        return redirect(url_for("home"))
    db.delete_indagine(indagine_id)
    flash("Indagine eliminata.")
    return redirect(url_for(".lista_indagini"))


@bp.route("/<int:indagine_id>/editor")
def indagini_editor(indagine_id):
    if session.get("modalita_giocatrice"):
        flash("Sezione non disponibile in modalità giocatrice.")
        return redirect(url_for("home"))
    indagine = db.get_indagine(indagine_id)
    if not indagine:
        flash("Indagine non trovata.")
        return redirect(url_for(".lista_indagini"))
    nodi = db.get_nodi_indagine(indagine_id)
    collegamenti = db.get_collegamenti(indagine_id)
    scene_gifs = _scene_gifs_display(indagine_id)
    scene_numeri = sorted(set(n["numero_nodo"] // 10 for n in nodi)) if nodi else []
    graph_data = json.dumps({
        "nodi": nodi,
        "collegamenti": collegamenti,
    }, default=str)
    return render_template(
        "indagini_editor.html",
        active="indagini",
        indagine=indagine,
        nodi=nodi,
        collegamenti=collegamenti,
        graph_data=graph_data,
        scene_numeri=scene_numeri,
        scene_gifs=scene_gifs,
    )


@bp.route("/<int:indagine_id>/scene/<int:numero_scena>/gif", methods=["POST"])
def indagini_salva_scena_gif(indagine_id, numero_scena):
    if session.get("modalita_giocatrice"):
        return redirect(url_for("home"))

    uploaded = request.files.get("gif_file")
    gif_url = request.form.get("gif_url", "").strip()

    if uploaded and uploaded.filename:
        ext = os.path.splitext(uploaded.filename)[1].lower()
        mime = _IMAGE_MIME_PER_EXT.get(ext)
        if not mime:
            flash("Formato non supportato. Usa GIF, JPG o PNG.")
            return redirect(url_for(".indagini_editor", indagine_id=indagine_id))
        data = uploaded.read()
        if len(data) > _MAX_SCENA_GIF_BYTES:
            flash("Immagine troppo grande (max 10 MB).")
            return redirect(url_for(".indagini_editor", indagine_id=indagine_id))
        if db.get_storage_mode() == "disk":
            gif_dir = os.path.join(current_app.root_path, "static", "scene_gifs")
            os.makedirs(gif_dir, exist_ok=True)
            filename = f"indagine_{indagine_id}_scena_{numero_scena}{ext}"
            file_path = os.path.join(gif_dir, filename)
            with open(file_path, "wb") as f:
                f.write(data)
            db.upsert_scena_gif(indagine_id, numero_scena, f"/static/scene_gifs/{filename}")
        else:
            db.save_scena_gif_file(indagine_id, numero_scena, data, mime)
    elif _url_sfondo_interno(gif_url, indagine_id, numero_scena):
        pass
    else:
        db.upsert_scena_gif(indagine_id, numero_scena, gif_url)

    return redirect(url_for(".indagini_editor", indagine_id=indagine_id))


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
def indagini_nuovo_nodo(indagine_id):
    if session.get("modalita_giocatrice"):
        return redirect(url_for("home"))
    titolo = request.form["titolo"].strip()
    numero_nodo = int(request.form.get("numero_nodo") or 0)
    descrizione = request.form.get("descrizione", "").strip() or None
    immagine_url = request.form.get("immagine_url", "").strip() or None
    regola_sblocco = request.form.get("regola_sblocco", "TUTTI")
    tipo_speciale = request.form.get("tipo_speciale", "").strip() or None
    db.add_nodo(indagine_id, numero_nodo, titolo, descrizione, immagine_url, regola_sblocco, tipo_speciale)
    return redirect(url_for(".indagini_editor", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/nodi/<int:nodo_id>/edita", methods=["POST"])
def indagini_edita_nodo(indagine_id, nodo_id):
    if session.get("modalita_giocatrice"):
        return redirect(url_for("home"))
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
    )
    livello_sfx_str = request.form.get("livello_sfx", "").strip()
    if livello_sfx_str in ("1", "2", "3"):
        kwargs["livello_sfx"] = int(livello_sfx_str)
        kwargs["livello_sfx_manuale"] = True
    db.update_nodo(nodo_id, **kwargs)
    return redirect(url_for(".indagini_editor", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/nodi/<int:nodo_id>/ricalcola-sfx", methods=["POST"])
def indagini_ricalcola_sfx(indagine_id, nodo_id):
    if session.get("modalita_giocatrice"):
        return redirect(url_for("home"))
    db.ricalcola_livello_sfx_singolo(nodo_id)
    return redirect(url_for(".indagini_editor", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/nodi/<int:nodo_id>/elimina", methods=["POST"])
def indagini_elimina_nodo(indagine_id, nodo_id):
    if session.get("modalita_giocatrice"):
        return redirect(url_for("home"))
    db.delete_nodo(nodo_id)
    return redirect(url_for(".indagini_editor", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/collegamenti/nuovo", methods=["POST"])
def indagini_nuovo_collegamento(indagine_id):
    if session.get("modalita_giocatrice"):
        return redirect(url_for("home"))
    genitore_id = int(request.form["nodo_genitore_id"])
    figlio_id = int(request.form["nodo_figlio_id"])
    if genitore_id != figlio_id:
        db.add_collegamento(indagine_id, genitore_id, figlio_id)
    return redirect(url_for(".indagini_editor", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/collegamenti/<int:collegamento_id>/elimina", methods=["POST"])
def indagini_elimina_collegamento(indagine_id, collegamento_id):
    if session.get("modalita_giocatrice"):
        return redirect(url_for("home"))
    db.delete_collegamento(collegamento_id)
    return redirect(url_for(".indagini_editor", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/live")
def indagini_live(indagine_id):
    if session.get("modalita_giocatrice"):
        flash("Sezione non disponibile in modalità giocatrice.")
        return redirect(url_for("home"))
    indagine = db.get_indagine(indagine_id)
    if not indagine:
        flash("Indagine non trovata.")
        return redirect(url_for(".lista_indagini"))
    nodi = db.get_nodi_indagine(indagine_id)
    collegamenti = db.get_collegamenti(indagine_id)
    cronologia_attiva = db.get_cronologia_attiva(indagine_id)
    stati_sblocco = db.get_stato_nodi_cronologia(cronologia_attiva["id"]) if cronologia_attiva else {}
    scena_corrente_val = cronologia_attiva.get("scena_corrente", 0) if cronologia_attiva else 0
    nodi = _merge_sblocco_in_nodi(nodi, stati_sblocco)
    stati = _calcola_stati_nodi(nodi, collegamenti, stati_sblocco, scena_corrente=scena_corrente_val)
    cronologie = db.get_cronologie_indagine(indagine_id)
    graph_data = json.dumps({
        "nodi": nodi,
        "collegamenti": collegamenti,
        "stati": stati,
        "cronologia_id": cronologia_attiva["id"] if cronologia_attiva else None,
        "scena_corrente": scena_corrente_val,
    }, default=str)
    return render_template(
        "indagini_live.html",
        active="indagini",
        indagine=indagine,
        cronologia_attiva=cronologia_attiva,
        cronologie=cronologie,
        graph_data=graph_data,
    )


@bp.route("/<int:indagine_id>/reset", methods=["POST"])
def indagini_reset(indagine_id):
    if session.get("modalita_giocatrice"):
        return redirect(url_for("home"))
    db.disattiva_cronologia_attiva(indagine_id)
    flash("Cronologia archiviata. La prossima indagine partirà da zero al primo sblocco.")
    return redirect(url_for(".indagini_live", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/nodi/<int:nodo_id>/sblocca", methods=["POST"])
def indagini_sblocca_nodo(indagine_id, nodo_id):
    if session.get("modalita_giocatrice"):
        return jsonify({"error": "non autorizzato"}), 403
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
    scena_corrente_val = cronologia_attiva.get("scena_corrente", 0)
    nodi = _merge_sblocco_in_nodi(nodi, stati_sblocco)
    stati = _calcola_stati_nodi(nodi, collegamenti, stati_sblocco, scena_corrente=scena_corrente_val)
    return jsonify({
        "nodi": nodi,
        "stati": stati,
        "cronologia_nuova": {
            "id": cronologia_nuova["id"],
            "nome": cronologia_nuova["nome"],
            "creata_il": str(cronologia_nuova["creata_il"]),
        } if cronologia_nuova else None,
    })


@bp.route("/<int:indagine_id>/cronologie/<int:cronologia_id>/attiva", methods=["POST"])
def indagini_attiva_cronologia(indagine_id, cronologia_id):
    if session.get("modalita_giocatrice"):
        return redirect(url_for("home"))
    db.attiva_cronologia(cronologia_id, indagine_id)
    return redirect(url_for(".indagini_live", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/cronologie/<int:cronologia_id>/elimina", methods=["POST"])
def indagini_elimina_cronologia(indagine_id, cronologia_id):
    if session.get("modalita_giocatrice"):
        return redirect(url_for("home"))
    db.elimina_cronologia(cronologia_id)
    return redirect(url_for(".indagini_live", indagine_id=indagine_id))


@bp.route("/<int:indagine_id>/cronologie/<int:cronologia_id>/rinomina", methods=["POST"])
def indagini_rinomina_cronologia(indagine_id, cronologia_id):
    if session.get("modalita_giocatrice"):
        return jsonify({"error": "non autorizzato"}), 403
    nome = (request.json.get("nome", "") if request.is_json else request.form.get("nome", "")).strip()
    if not nome:
        return jsonify({"error": "nome vuoto"}), 400
    db.rinomina_cronologia(cronologia_id, nome)
    return jsonify({"nome": nome})


@bp.route("/<int:indagine_id>/avanza-scena", methods=["POST"])
def indagini_avanza_scena(indagine_id):
    if session.get("modalita_giocatrice"):
        return jsonify({"error": "non autorizzato"}), 403

    req_scena = request.json.get("scena_corrente") if request.is_json else None
    nuova_scena = int(req_scena) if req_scena is not None else 2

    cronologia_attiva = db.get_cronologia_attiva(indagine_id)
    cronologia_nuova = None
    if not cronologia_attiva:
        nome = f"Cronologia del {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        cronologia_nuova = db.crea_cronologia(indagine_id, nome)
        cronologia_attiva = cronologia_nuova

    db.avanza_scena_cronologia(cronologia_attiva["id"], nuova_scena)
    if nuova_scena == 0:
        db.set_sipario_aperto(cronologia_attiva["id"], True)

    nodi = db.get_nodi_indagine(indagine_id)
    collegamenti = db.get_collegamenti(indagine_id)
    stati_sblocco = db.get_stato_nodi_cronologia(cronologia_attiva["id"])
    nodi = _merge_sblocco_in_nodi(nodi, stati_sblocco)
    stati = _calcola_stati_nodi(nodi, collegamenti, stati_sblocco, scena_corrente=nuova_scena)

    return jsonify({
        "scena_corrente": nuova_scena,
        "stati": stati,
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
    scena_corrente_val = cronologia_attiva.get("scena_corrente", 0) if cronologia_attiva else 0
    nodi = _merge_sblocco_in_nodi(nodi, stati_sblocco)
    scoperti_ids = [nid for nid, stato in stati_sblocco.items() if stato.get("scoperto")]
    scene_gifs = _scene_gifs_display(indagine_id)
    scene_gifs_str = {str(k): v for k, v in scene_gifs.items()}
    graph_data = json.dumps({
        "nodi": nodi,
        "collegamenti": collegamenti,
        "scoperti_ids": scoperti_ids,
        "scena_corrente": scena_corrente_val,
        "sipario_aperto": cronologia_attiva.get("sipario_aperto", False) if cronologia_attiva else False,
        "scene_gifs": scene_gifs_str,
    }, default=str)
    return render_template(
        "indagini_player.html",
        indagine=indagine,
        graph_data=graph_data,
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
        return jsonify({"scoperti_ids": [], "scena_corrente": 0})
    stati_sblocco = db.get_stato_nodi_cronologia(cronologia_attiva["id"])
    scoperti_ids = [nodo_id for nodo_id, stato in stati_sblocco.items() if stato.get("scoperto")]
    return jsonify({
        "scoperti_ids": scoperti_ids,
        "scena_corrente": cronologia_attiva.get("scena_corrente", 0),
        "sipario_aperto": cronologia_attiva.get("sipario_aperto", False),
    })


@bp.route("/<int:indagine_id>/sipario", methods=["POST"])
def indagini_sipario(indagine_id):
    if session.get("modalita_giocatrice"):
        return "Accesso negato", 403
    cronologia = db.get_cronologia_attiva(indagine_id)
    if not cronologia:
        return jsonify({"error": "Nessuna cronologia attiva"}), 400
    nuovo_stato = db.toggle_sipario(indagine_id)
    return jsonify({"success": True, "sipario_aperto": nuovo_stato})
