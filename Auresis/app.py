import json
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response, abort
from urllib.parse import urlparse
from werkzeug.security import check_password_hash
import db
import copioni
from prompt_builder import costruisci_prompt

app = Flask(__name__)
app.secret_key = "campagna-locale-non-serve-sicurezza-vera"

# reset a True a ogni avvio del processo
modalita_giocatrice_attiva = True

@app.context_processor
def inietta_modalita_giocatrice():
    return {"modalita_giocatrice": modalita_giocatrice_attiva}

def _int_or_none(value):
    return int(value) if value else None


def _kwargs_da_form(form, campi):
    kwargs = {}
    for campo in campi:
        valore = form.get(campo, "").strip()
        if valore:
            kwargs[campo] = valore
    return kwargs

SESSIONE_TEMPLATE_NUMERO = 0

# --- HOME ---

@app.route("/")
def home():
    stats = db.get_stats_riepilogo()
    eventi_recenti = db.get_eventi_recenti(n=6)
    return render_template("home.html", active="home", stats=stats, eventi_recenti=eventi_recenti)

# --- COPIONI ---

@app.route("/copioni")
def copioni_indice():
    sessioni = copioni.elenca_sessioni()
    completate_map = db.get_sessioni_completate_map()

    if modalita_giocatrice_attiva:
        sessioni = [
            s for s in sessioni
            if s["numero"] == SESSIONE_TEMPLATE_NUMERO
               or completate_map.get(s["numero"], False)
        ]

    for s in sessioni:
        s["completata"] = completate_map.get(s["numero"], False)
        s["is_template"] = (s["numero"] == SESSIONE_TEMPLATE_NUMERO)

    return render_template("copioni_indice.html", active="copioni", sessioni=sessioni)


@app.route("/copioni/<int:numero_sessione>")
def copioni_dettaglio(numero_sessione):
    is_template = (numero_sessione == SESSIONE_TEMPLATE_NUMERO)
    completata = db.get_sessione_completata(numero_sessione)

    if modalita_giocatrice_attiva and not is_template and not completata:
        flash("Questa sessione non è ancora disponibile.")
        return redirect(url_for("copioni_indice"))

    titolo, html, heading_list = copioni.renderizza_sessione(numero_sessione)
    if html is None:
        flash(f"Nessun copione trovato per la sessione {numero_sessione}.")
        return redirect(url_for("copioni_indice"))

    sessioni = copioni.elenca_sessioni()
    return render_template(
        "copioni_dettaglio.html",
        active="copioni",
        numero_sessione=numero_sessione,
        titolo=titolo,
        contenuto_html=html,
        heading_list=heading_list,
        sessioni=sessioni,
        completata=completata,
        is_template=is_template,
    )


@app.route("/copioni/<int:numero_sessione>/modifica", methods=["GET", "POST"])
def copioni_modifica(numero_sessione):
    percorso = copioni.get_file_path_sessione(numero_sessione)
    if percorso is None:
        flash("File copione non trovato o sessione non esistente.")
        return redirect(url_for("copioni_dettaglio", numero_sessione=numero_sessione))
    if request.method == "POST":
        if request.is_json:
            testo = request.get_json(force=True).get("contenuto", "")
            with open(percorso, "w", encoding="utf-8") as fh:
                fh.write(testo)
            return {"ok": True}
        testo = request.form.get("contenuto", "")
        with open(percorso, "w", encoding="utf-8") as fh:
            fh.write(testo)
        flash("Copione salvato.")
        return redirect(url_for("copioni_dettaglio", numero_sessione=numero_sessione))
    with open(percorso, "r", encoding="utf-8") as fh:
        testo = fh.read()
    titolo = copioni.estrai_titolo(testo) or f"Sessione {numero_sessione}"
    tracce = db.get_all_tracce_audio()
    return render_template(
        "copioni_modifica.html",
        active="copioni",
        numero_sessione=numero_sessione,
        nome_file=os.path.basename(percorso),
        titolo=titolo,
        contenuto=testo,
        tracce=tracce
    )


@app.route("/copioni/<int:numero_sessione>/toggle-completata", methods=["POST"])
def copioni_toggle_completata(numero_sessione):
    nuovo_stato = not db.get_sessione_completata(numero_sessione)
    db.set_sessione_completata(numero_sessione, nuovo_stato)
    return redirect(url_for("copioni_dettaglio", numero_sessione=numero_sessione))


# --- NPC ---

@app.route("/npc")
def lista_npc():
    npc_list = db.get_all_npc_full()
    if modalita_giocatrice_attiva:
        npc_list = [n for n in npc_list if n.get("visibile_giocatrice")]
    return render_template("npc_lista.html", active="npc", npc_list=npc_list)


@app.route("/npc/<int:npc_id>")
def dettaglio_npc(npc_id):
    npc = db.get_npc_full(npc_id)
    if not npc:
        flash("Personaggio non trovato.")
        return redirect(url_for("lista_npc"))
    if modalita_giocatrice_attiva and not npc.get("visibile_giocatrice"):
        flash("Questo personaggio non è ancora disponibile.")
        return redirect(url_for("lista_npc"))
    return render_template("npc_dettaglio.html", active="npc", npc=npc)


@app.route("/npc/nuovo", methods=["GET", "POST"])
def nuovo_npc():
    if request.method == "POST":
        kwargs = _kwargs_da_form(request.form, [
            "ruolo", "stato", "relazione_pg", "descrizione_breve", "note_caratteriali", "note"
        ])
        if request.form.get("fazione_id"):
            kwargs["fazione_id"] = int(request.form["fazione_id"])
        if request.form.get("location_attuale_id"):
            kwargs["location_attuale_id"] = int(request.form["location_attuale_id"])
        if request.form.get("livello_contaminazione"):
            kwargs["livello_contaminazione"] = int(request.form["livello_contaminazione"])
        if request.form.get("ultima_apparizione_sessione"):
            kwargs["ultima_apparizione_sessione"] = int(request.form["ultima_apparizione_sessione"])
        npc_id = db.upsert_npc(request.form["nome"], **kwargs)
        flash(f"Personaggio '{request.form['nome']}' salvato.")
        return redirect(url_for("dettaglio_npc", npc_id=npc_id))

    fazioni = db.get_all_fazioni_full()
    locations = db.get_all_locations()
    return render_template("npc_form.html", active="npc", npc=None, fazioni=fazioni, locations=locations)


@app.route("/npc/<int:npc_id>/edita", methods=["GET", "POST"])
def edita_npc(npc_id):
    npc = db.get_npc_full(npc_id)
    if not npc:
        flash("Personaggio non trovato.")
        return redirect(url_for("lista_npc"))

    if request.method == "POST":
        kwargs = _kwargs_da_form(request.form, [
            "ruolo", "stato", "relazione_pg", "descrizione_breve", "note_caratteriali", "note"
        ])
        kwargs["fazione_id"] = _int_or_none(request.form.get("fazione_id"))
        kwargs["location_attuale_id"] = _int_or_none(request.form.get("location_attuale_id"))
        kwargs["livello_contaminazione"] = int(request.form.get("livello_contaminazione") or 0)
        kwargs["ultima_apparizione_sessione"] = _int_or_none(request.form.get("ultima_apparizione_sessione"))
        db.upsert_npc(request.form["nome"], **kwargs)
        flash(f"Personaggio '{request.form['nome']}' aggiornato.")
        return redirect(url_for("dettaglio_npc", npc_id=npc_id))

    fazioni = db.get_all_fazioni_full()
    locations = db.get_all_locations()
    return render_template("npc_form.html", active="npc", npc=npc, fazioni=fazioni, locations=locations)


@app.route("/npc/<int:npc_id>/elimina", methods=["POST"])
def elimina_npc(npc_id):
    db.delete_record("npc", npc_id)
    flash("Personaggio eliminato dal registro.")
    return redirect(url_for("lista_npc"))


@app.route("/npc/<int:npc_id>/toggle-visibile", methods=["POST"])
def npc_toggle_visibile(npc_id):
    db.set_npc_visibile(npc_id, not db.get_npc_visibile(npc_id))
    return redirect(url_for("lista_npc"))


# --- FAZIONI ---

@app.route("/fazioni")
def lista_fazioni():
    fazioni_list = db.get_all_fazioni_full()
    return render_template("fazioni_lista.html", active="fazioni", fazioni_list=fazioni_list)


@app.route("/fazioni/<int:fazione_id>")
def dettaglio_fazione(fazione_id):
    fazione = db.get_fazione_full(fazione_id)
    if not fazione:
        flash("Fazione non trovata.")
        return redirect(url_for("lista_fazioni"))
    return render_template("fazioni_dettaglio.html", active="fazioni", fazione=fazione)


@app.route("/fazioni/nuova", methods=["GET", "POST"])
def nuova_fazione():
    if request.method == "POST":
        kwargs = _kwargs_da_form(request.form, ["nome_popolare", "ideologia", "territorio", "stato_attuale", "note"])
        kwargs["relazione_pg"] = request.form.get("relazione_pg", "neutrale")
        kwargs["attiva"] = int(request.form.get("attiva", 1))
        db.upsert_fazione(request.form["nome"], **kwargs)
        flash(f"Fazione '{request.form['nome']}' salvata.")
        return redirect(url_for("lista_fazioni"))
    return render_template("fazioni_form.html", active="fazioni", fazione=None)


@app.route("/fazioni/<int:fazione_id>/edita", methods=["GET", "POST"])
def edita_fazione(fazione_id):
    fazione = db.get_fazione_full(fazione_id)
    if not fazione:
        flash("Fazione non trovata.")
        return redirect(url_for("lista_fazioni"))

    if request.method == "POST":
        kwargs = _kwargs_da_form(request.form, ["nome_popolare", "ideologia", "territorio", "stato_attuale", "note"])
        kwargs["relazione_pg"] = request.form.get("relazione_pg", "neutrale")
        kwargs["attiva"] = int(request.form.get("attiva", 1))
        db.upsert_fazione(request.form["nome"], **kwargs)
        flash(f"Fazione '{request.form['nome']}' aggiornata.")
        return redirect(url_for("dettaglio_fazione", fazione_id=fazione_id))

    return render_template("fazioni_form.html", active="fazioni", fazione=fazione)


@app.route("/fazioni/<int:fazione_id>/elimina", methods=["POST"])
def elimina_fazione(fazione_id):
    db.delete_record("fazioni", fazione_id)
    flash("Fazione eliminata dal registro.")
    return redirect(url_for("lista_fazioni"))


# --- LOCATIONS ---

@app.route("/locations")
def lista_locations():
    locations_list = db.get_all_locations_full()
    if modalita_giocatrice_attiva:
        locations_list = [l for l in locations_list if l.get("visibile_giocatrice")]
    return render_template("locations_lista.html", active="locations", locations_list=locations_list)


@app.route("/locations/<int:location_id>")
def dettaglio_location(location_id):
    location = db.get_location_full(location_id)
    if not location:
        flash("Luogo non trovato.")
        return redirect(url_for("lista_locations"))
    if modalita_giocatrice_attiva and not location.get("visibile_giocatrice"):
        flash("Questo luogo non è ancora disponibile.")
        return redirect(url_for("lista_locations"))
    return render_template("locations_dettaglio.html", active="locations", location=location)


@app.route("/locations/nuova", methods=["GET", "POST"])
def nuova_location():
    if request.method == "POST":
        kwargs = _kwargs_da_form(request.form, ["tipo", "descrizione_breve", "stato_attuale", "note"])
        if request.form.get("fazione_controllante_id"):
            kwargs["fazione_controllante_id"] = int(request.form["fazione_controllante_id"])
        db.upsert_location(request.form["nome"], **kwargs)
        flash(f"Luogo '{request.form['nome']}' salvato.")
        return redirect(url_for("lista_locations"))

    fazioni = db.get_all_fazioni_full()
    return render_template("locations_form.html", active="locations", location=None, fazioni=fazioni)


@app.route("/locations/<int:location_id>/edita", methods=["GET", "POST"])
def edita_location(location_id):
    location = db.get_location_full(location_id)
    if not location:
        flash("Luogo non trovato.")
        return redirect(url_for("lista_locations"))

    if request.method == "POST":
        kwargs = _kwargs_da_form(request.form, ["tipo", "descrizione_breve", "stato_attuale", "note"])
        kwargs["fazione_controllante_id"] = _int_or_none(request.form.get("fazione_controllante_id"))
        db.upsert_location(request.form["nome"], **kwargs)
        flash(f"Luogo '{request.form['nome']}' aggiornato.")
        return redirect(url_for("dettaglio_location", location_id=location_id))

    fazioni = db.get_all_fazioni_full()
    return render_template("locations_form.html", active="locations", location=location, fazioni=fazioni)


@app.route("/locations/<int:location_id>/elimina", methods=["POST"])
def elimina_location(location_id):
    db.delete_record("locations", location_id)
    flash("Luogo eliminato dal registro.")
    return redirect(url_for("lista_locations"))


@app.route("/locations/<int:location_id>/toggle-visibile", methods=["POST"])
def location_toggle_visibile(location_id):
    db.set_location_visibile(location_id, not db.get_location_visibile(location_id))
    return redirect(url_for("lista_locations"))


# --- QUEST ---

@app.route("/quest")
def lista_quest():
    quest_list = db.get_all_quest_full()
    if modalita_giocatrice_attiva:
        quest_list = [q for q in quest_list if q.get("visibile_giocatrice")]
    return render_template("quest_lista.html", active="quest", quest_list=quest_list)


@app.route("/quest/<int:quest_id>")
def dettaglio_quest(quest_id):
    quest = db.get_quest_full(quest_id)
    if not quest:
        flash("Incarico non trovato.")
        return redirect(url_for("lista_quest"))
    if modalita_giocatrice_attiva and not quest.get("visibile_giocatrice"):
        flash("Questo incarico non è ancora disponibile.")
        return redirect(url_for("lista_quest"))
    return render_template("quest_dettaglio.html", active="quest", quest=quest)


@app.route("/quest/nuova", methods=["GET", "POST"])
def nuova_quest():
    if request.method == "POST":
        kwargs = _kwargs_da_form(request.form, ["riassunto", "obiettivo_attuale", "note"])
        kwargs["tipo"] = request.form.get("tipo", "side")
        kwargs["stato"] = request.form.get("stato", "attiva")
        if request.form.get("location_id"):
            kwargs["location_id"] = int(request.form["location_id"])
        if request.form.get("sessione_inizio"):
            kwargs["sessione_inizio"] = int(request.form["sessione_inizio"])
        if request.form.get("sessione_fine"):
            kwargs["sessione_fine"] = int(request.form["sessione_fine"])
        quest_id = db.upsert_quest(request.form["nome"], **kwargs)
        flash(f"Incarico '{request.form['nome']}' salvato.")
        return redirect(url_for("dettaglio_quest", quest_id=quest_id))

    locations = db.get_all_locations()
    return render_template("quest_form.html", active="quest", quest=None, locations=locations)


@app.route("/quest/<int:quest_id>/edita", methods=["GET", "POST"])
def edita_quest(quest_id):
    quest = db.get_quest_full(quest_id)
    if not quest:
        flash("Incarico non trovato.")
        return redirect(url_for("lista_quest"))

    if request.method == "POST":
        kwargs = _kwargs_da_form(request.form, ["riassunto", "obiettivo_attuale", "note"])
        kwargs["tipo"] = request.form.get("tipo", "side")
        kwargs["stato"] = request.form.get("stato", "attiva")
        kwargs["location_id"] = _int_or_none(request.form.get("location_id"))
        kwargs["sessione_inizio"] = _int_or_none(request.form.get("sessione_inizio"))
        kwargs["sessione_fine"] = _int_or_none(request.form.get("sessione_fine"))
        db.upsert_quest(request.form["nome"], **kwargs)
        flash(f"Incarico '{request.form['nome']}' aggiornato.")
        return redirect(url_for("dettaglio_quest", quest_id=quest_id))

    locations = db.get_all_locations()
    return render_template("quest_form.html", active="quest", quest=quest, locations=locations)


@app.route("/quest/<int:quest_id>/elimina", methods=["POST"])
def elimina_quest(quest_id):
    db.delete_record("quest", quest_id)
    flash("Incarico eliminato dal registro.")
    return redirect(url_for("lista_quest"))


@app.route("/quest/<int:quest_id>/toggle-visibile", methods=["POST"])
def quest_toggle_visibile(quest_id):
    db.set_quest_visibile(quest_id, not db.get_quest_visibile(quest_id))
    return redirect(url_for("lista_quest"))


@app.route("/quest/<int:quest_id>/collega-npc", methods=["GET", "POST"])
def collega_npc_quest(quest_id):
    quest = db.get_quest_full(quest_id)
    if not quest:
        flash("Incarico non trovato.")
        return redirect(url_for("lista_quest"))

    if request.method == "POST":
        npc_id = int(request.form["npc_id"])
        ruolo = request.form.get("ruolo_nella_quest", "").strip() or None
        db.link_npc_quest(quest_id, npc_id, ruolo_nella_quest=ruolo)
        flash("Personaggio collegato all'incarico.")
        return redirect(url_for("dettaglio_quest", quest_id=quest_id))

    npc_list = db.get_all_npc_full()
    return render_template("quest_collega_npc.html", active="quest", quest=quest, npc_list=npc_list)


# --- EVENTI ---

@app.route("/eventi")
def lista_eventi():
    eventi_list = db.get_all_eventi()
    return render_template("eventi_lista.html", active="eventi", eventi_list=eventi_list)


@app.route("/eventi/nuovo", methods=["GET", "POST"])
def nuovo_evento():
    if request.method == "POST":
        location_id = _int_or_none(request.form.get("location_id"))
        db.add_evento(
            sessione=int(request.form["sessione"]),
            riassunto=request.form["riassunto"],
            conseguenze_attive=request.form.get("conseguenze_attive", "").strip() or None,
            location_id=location_id,
        )
        flash("Evento registrato nella cronaca.")
        return redirect(url_for("lista_eventi"))

    locations = db.get_all_locations()
    return render_template("eventi_form.html", active="eventi", locations=locations)


@app.route("/eventi/<int:evento_id>/elimina", methods=["POST"])
def elimina_evento(evento_id):
    db.delete_record("eventi", evento_id)
    flash("Evento eliminato dalla cronaca.")
    return redirect(url_for("lista_eventi"))


# --- FATTI ACCERTATI ---

@app.route("/fatti")
def lista_fatti():
    fatti_list = db.get_all_fatti()
    return render_template("fatti_lista.html", active="fatti", fatti_list=fatti_list)


@app.route("/fatti/nuovo", methods=["GET", "POST"])
def nuovo_fatto():
    if request.method == "POST":
        sessione = _int_or_none(request.form.get("sessione"))
        db.add_fatto_accertato(
            descrizione=request.form["descrizione"],
            sessione=sessione,
            rilevanza=request.form.get("rilevanza", "media"),
        )
        flash("Verità accertata registrata.")
        return redirect(url_for("lista_fatti"))
    return render_template("fatti_form.html", active="fatti")


@app.route("/fatti/<int:fatto_id>/elimina", methods=["POST"])
def elimina_fatto(fatto_id):
    db.delete_record("fatti_accertati", fatto_id)
    flash("Verità eliminata dal registro.")
    return redirect(url_for("lista_fatti"))


# --- INDAGINI ---

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


@app.route("/indagini")
def lista_indagini():
    indagini = db.get_all_indagini(solo_visibili=modalita_giocatrice_attiva)
    return render_template("indagini_lista.html", active="indagini", indagini=indagini)


@app.route("/indagini/nuova", methods=["GET", "POST"])
def nuova_indagine():
    if modalita_giocatrice_attiva:
        return redirect(url_for("home"))
    if request.method == "POST":
        titolo = request.form["titolo"].strip()
        descrizione = request.form.get("descrizione", "").strip() or None
        attiva = request.form.get("attiva") == "1"
        visibile_giocatrice = request.form.get("visibile_giocatrice") == "1"
        ind_id = db.add_indagine(titolo, descrizione, attiva, visibile_giocatrice)
        flash(f"Indagine '{titolo}' creata.")
        return redirect(url_for("indagini_editor", indagine_id=ind_id))
    return render_template("indagini_form.html", active="indagini", indagine=None)


@app.route("/indagini/<int:indagine_id>/edita", methods=["GET", "POST"])
def edita_indagine(indagine_id):
    if modalita_giocatrice_attiva:
        return redirect(url_for("home"))
    indagine = db.get_indagine(indagine_id)
    if not indagine:
        flash("Indagine non trovata.")
        return redirect(url_for("lista_indagini"))
    if request.method == "POST":
        titolo = request.form["titolo"].strip()
        descrizione = request.form.get("descrizione", "").strip() or None
        attiva = request.form.get("attiva") == "1"
        visibile_giocatrice = request.form.get("visibile_giocatrice") == "1"
        db.update_indagine(indagine_id, titolo=titolo, descrizione=descrizione, attiva=attiva, visibile_giocatrice=visibile_giocatrice)
        flash(f"Indagine '{titolo}' aggiornata.")
        return redirect(url_for("lista_indagini"))
    return render_template("indagini_form.html", active="indagini", indagine=indagine)


@app.route("/indagini/<int:indagine_id>/elimina", methods=["POST"])
def elimina_indagine(indagine_id):
    if modalita_giocatrice_attiva:
        return redirect(url_for("home"))
    db.delete_indagine(indagine_id)
    flash("Indagine eliminata.")
    return redirect(url_for("lista_indagini"))


@app.route("/indagini/<int:indagine_id>/editor")
def indagini_editor(indagine_id):
    if modalita_giocatrice_attiva:
        flash("Sezione non disponibile in modalità giocatrice.")
        return redirect(url_for("home"))
    indagine = db.get_indagine(indagine_id)
    if not indagine:
        flash("Indagine non trovata.")
        return redirect(url_for("lista_indagini"))
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
                "indagini_scena_sfondo",
                indagine_id=indagine_id,
                numero_scena=numero,
                v=info["versione"],
            )
        elif info["gif_url"]:
            out[numero] = info["gif_url"]
    return out


def _url_sfondo_interno(gif_url, indagine_id, numero_scena):
    return gif_url.startswith(f"/indagini/{indagine_id}/scene/{numero_scena}/sfondo")


@app.route("/indagini/<int:indagine_id>/scene/<int:numero_scena>/gif", methods=["POST"])
def indagini_salva_scena_gif(indagine_id, numero_scena):
    if modalita_giocatrice_attiva:
        return redirect(url_for("home"))

    uploaded = request.files.get("gif_file")
    gif_url = request.form.get("gif_url", "").strip()

    if uploaded and uploaded.filename:
        ext = os.path.splitext(uploaded.filename)[1].lower()
        mime = _IMAGE_MIME_PER_EXT.get(ext)
        if not mime:
            flash("Formato non supportato. Usa GIF, JPG o PNG.")
            return redirect(url_for("indagini_editor", indagine_id=indagine_id))
        data = uploaded.read()
        if len(data) > _MAX_SCENA_GIF_BYTES:
            flash("Immagine troppo grande (max 10 MB).")
            return redirect(url_for("indagini_editor", indagine_id=indagine_id))
        # nel DB, non su disco: il filesystem di Render è effimero
        db.save_scena_gif_file(indagine_id, numero_scena, data, mime)
    elif _url_sfondo_interno(gif_url, indagine_id, numero_scena):
        # l'URL nel campo è quello dell'immagine già salvata nel DB: non toccare nulla
        pass
    else:
        db.upsert_scena_gif(indagine_id, numero_scena, gif_url)

    return redirect(url_for("indagini_editor", indagine_id=indagine_id))


@app.route("/indagini/<int:indagine_id>/scene/<int:numero_scena>/sfondo")
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


@app.route("/indagini/<int:indagine_id>/nodi/nuovo", methods=["POST"])
def indagini_nuovo_nodo(indagine_id):
    if modalita_giocatrice_attiva:
        return redirect(url_for("home"))
    titolo = request.form["titolo"].strip()
    numero_nodo = int(request.form.get("numero_nodo") or 0)
    descrizione = request.form.get("descrizione", "").strip() or None
    immagine_url = request.form.get("immagine_url", "").strip() or None
    regola_sblocco = request.form.get("regola_sblocco", "TUTTI")
    tipo_speciale = request.form.get("tipo_speciale", "").strip() or None
    db.add_nodo(indagine_id, numero_nodo, titolo, descrizione, immagine_url, regola_sblocco, tipo_speciale)
    return redirect(url_for("indagini_editor", indagine_id=indagine_id))


@app.route("/indagini/<int:indagine_id>/nodi/<int:nodo_id>/edita", methods=["POST"])
def indagini_edita_nodo(indagine_id, nodo_id):
    if modalita_giocatrice_attiva:
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
    return redirect(url_for("indagini_editor", indagine_id=indagine_id))


@app.route("/indagini/<int:indagine_id>/nodi/<int:nodo_id>/ricalcola-sfx", methods=["POST"])
def indagini_ricalcola_sfx(indagine_id, nodo_id):
    if modalita_giocatrice_attiva:
        return redirect(url_for("home"))
    db.ricalcola_livello_sfx_singolo(nodo_id)
    return redirect(url_for("indagini_editor", indagine_id=indagine_id))


@app.route("/indagini/<int:indagine_id>/nodi/<int:nodo_id>/elimina", methods=["POST"])
def indagini_elimina_nodo(indagine_id, nodo_id):
    if modalita_giocatrice_attiva:
        return redirect(url_for("home"))
    db.delete_nodo(nodo_id)
    return redirect(url_for("indagini_editor", indagine_id=indagine_id))


@app.route("/indagini/<int:indagine_id>/collegamenti/nuovo", methods=["POST"])
def indagini_nuovo_collegamento(indagine_id):
    if modalita_giocatrice_attiva:
        return redirect(url_for("home"))
    genitore_id = int(request.form["nodo_genitore_id"])
    figlio_id = int(request.form["nodo_figlio_id"])
    if genitore_id != figlio_id:
        db.add_collegamento(indagine_id, genitore_id, figlio_id)
    return redirect(url_for("indagini_editor", indagine_id=indagine_id))


@app.route("/indagini/<int:indagine_id>/collegamenti/<int:collegamento_id>/elimina", methods=["POST"])
def indagini_elimina_collegamento(indagine_id, collegamento_id):
    if modalita_giocatrice_attiva:
        return redirect(url_for("home"))
    db.delete_collegamento(collegamento_id)
    return redirect(url_for("indagini_editor", indagine_id=indagine_id))


@app.route("/indagini/<int:indagine_id>/live")
def indagini_live(indagine_id):
    if modalita_giocatrice_attiva:
        flash("Sezione non disponibile in modalità giocatrice.")
        return redirect(url_for("home"))
    indagine = db.get_indagine(indagine_id)
    if not indagine:
        flash("Indagine non trovata.")
        return redirect(url_for("lista_indagini"))
    nodi = db.get_nodi_indagine(indagine_id)
    collegamenti = db.get_collegamenti(indagine_id)
    cronologia_attiva = db.get_cronologia_attiva(indagine_id)
    stati_sblocco = db.get_stato_nodi_cronologia(cronologia_attiva["id"]) if cronologia_attiva else {}
    scena_corrente_val = cronologia_attiva.get("scena_corrente", 1) if cronologia_attiva else 1
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


@app.route("/indagini/<int:indagine_id>/reset", methods=["POST"])
def indagini_reset(indagine_id):
    if modalita_giocatrice_attiva:
        return redirect(url_for("home"))
    db.disattiva_cronologia_attiva(indagine_id)
    flash("Cronologia archiviata. La prossima indagine partirà da zero al primo sblocco.")
    return redirect(url_for("indagini_live", indagine_id=indagine_id))


@app.route("/indagini/<int:indagine_id>/nodi/<int:nodo_id>/sblocca", methods=["POST"])
def indagini_sblocca_nodo(indagine_id, nodo_id):
    if modalita_giocatrice_attiva:
        return jsonify({"error": "non autorizzato"}), 403
    nodo = db.get_nodo(nodo_id)
    if not nodo or nodo["indagine_id"] != indagine_id:
        return jsonify({"error": "nodo non trovato"}), 404
    manuale = request.json.get("manuale", True) if request.is_json else True

    # creazione lazy della cronologia al primo sblocco
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
    scena_corrente_val = cronologia_attiva.get("scena_corrente", 1)
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


@app.route("/indagini/<int:indagine_id>/cronologie/<int:cronologia_id>/attiva", methods=["POST"])
def indagini_attiva_cronologia(indagine_id, cronologia_id):
    if modalita_giocatrice_attiva:
        return redirect(url_for("home"))
    db.attiva_cronologia(cronologia_id, indagine_id)
    return redirect(url_for("indagini_live", indagine_id=indagine_id))


@app.route("/indagini/<int:indagine_id>/cronologie/<int:cronologia_id>/elimina", methods=["POST"])
def indagini_elimina_cronologia(indagine_id, cronologia_id):
    if modalita_giocatrice_attiva:
        return redirect(url_for("home"))
    db.elimina_cronologia(cronologia_id)
    return redirect(url_for("indagini_live", indagine_id=indagine_id))


@app.route("/indagini/<int:indagine_id>/cronologie/<int:cronologia_id>/rinomina", methods=["POST"])
def indagini_rinomina_cronologia(indagine_id, cronologia_id):
    if modalita_giocatrice_attiva:
        return jsonify({"error": "non autorizzato"}), 403
    nome = (request.json.get("nome", "") if request.is_json else request.form.get("nome", "")).strip()
    if not nome:
        return jsonify({"error": "nome vuoto"}), 400
    db.rinomina_cronologia(cronologia_id, nome)
    return jsonify({"nome": nome})


@app.route("/indagini/<int:indagine_id>/avanza-scena", methods=["POST"])
def indagini_avanza_scena(indagine_id):
    if modalita_giocatrice_attiva:
        return jsonify({"error": "non autorizzato"}), 403
    nuova_scena = (request.json.get("scena_corrente") if request.is_json else None) or 2

    cronologia_attiva = db.get_cronologia_attiva(indagine_id)
    cronologia_nuova = None
    if not cronologia_attiva:
        nome = f"Cronologia del {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        cronologia_nuova = db.crea_cronologia(indagine_id, nome)
        cronologia_attiva = cronologia_nuova

    db.avanza_scena_cronologia(cronologia_attiva["id"], nuova_scena)

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


@app.route("/indagini/<int:indagine_id>/player")
def indagini_player(indagine_id):
    """Pagina player-facing: mostra solo gli indizi scoperti, senza controlli DM.
    Pensata per screenshare Discord — si aggiorna via polling."""
    indagine = db.get_indagine(indagine_id)
    if not indagine:
        flash("Indagine non trovata.")
        return redirect(url_for("lista_indagini"))
    nodi = db.get_nodi_indagine(indagine_id)
    collegamenti = db.get_collegamenti(indagine_id)
    cronologia_attiva = db.get_cronologia_attiva(indagine_id)
    stati_sblocco = db.get_stato_nodi_cronologia(cronologia_attiva["id"]) if cronologia_attiva else {}
    scena_corrente_val = cronologia_attiva.get("scena_corrente", 1) if cronologia_attiva else 1
    nodi = _merge_sblocco_in_nodi(nodi, stati_sblocco)
    scoperti_ids = [nid for nid, stato in stati_sblocco.items() if stato.get("scoperto")]
    scene_gifs = _scene_gifs_display(indagine_id)
    # converti chiavi in stringhe per compatibilità JSON
    scene_gifs_str = {str(k): v for k, v in scene_gifs.items()}
    graph_data = json.dumps({
        "nodi": nodi,
        "collegamenti": collegamenti,
        "scoperti_ids": scoperti_ids,
        "scena_corrente": scena_corrente_val,
        "scene_gifs": scene_gifs_str,
    }, default=str)
    return render_template(
        "indagini_player.html",
        indagine=indagine,
        graph_data=graph_data,
    )


@app.route("/indagini/<int:indagine_id>/stato-player")
def indagini_stato_player(indagine_id):
    """API JSON leggera per il polling della player view.
    Ritorna solo gli ID dei nodi scoperti e la scena corrente."""
    indagine = db.get_indagine(indagine_id)
    if not indagine:
        return jsonify({"error": "non trovata"}), 404
    cronologia_attiva = db.get_cronologia_attiva(indagine_id)
    if not cronologia_attiva:
        return jsonify({"scoperti_ids": [], "scena_corrente": 1})
    stati_sblocco = db.get_stato_nodi_cronologia(cronologia_attiva["id"])
    scoperti_ids = [nodo_id for nodo_id, stato in stati_sblocco.items() if stato.get("scoperto")]
    return jsonify({
        "scoperti_ids": scoperti_ids,
        "scena_corrente": cronologia_attiva.get("scena_corrente", 1),
    })


# --- STATO DEL PG ---

@app.route("/soggetto", methods=["GET", "POST"])
def pg_stato_page():
    if request.method == "POST":
        kwargs = _kwargs_da_form(request.form, [
            "nome", "condizione_fisica", "ferite_attive", "equipaggiamento", "risorse", "abilita_acquisite", "note"
        ])
        kwargs["sessione_corrente"] = int(request.form.get("sessione_corrente") or 0)
        kwargs["location_attuale_id"] = _int_or_none(request.form.get("location_attuale_id"))
        db.set_pg_stato(**kwargs)
        flash("Stato del personaggio aggiornato.")
        return redirect(url_for("pg_stato_page"))

    pg = db.get_pg_stato()
    locations = db.get_all_locations()
    return render_template("pg_stato.html", active="pg", pg=pg, locations=locations)


# --- MODALITÀ GIOCATRICE ---

@app.route("/toggle-modalita-giocatrice", methods=["POST"])
def toggle_modalita_giocatrice():
    global modalita_giocatrice_attiva
    if modalita_giocatrice_attiva:
        # per disattivare serve sia il flag di sessione che quello di sessionStorage
        if session.get("sbloccato") and request.form.get("sbloccato_tab") == "1":
            modalita_giocatrice_attiva = False
        else:
            ritorna = urlparse(request.referrer or "/").path or "/"
            return redirect(url_for("sblocca_modalita", next=ritorna))
    else:
        modalita_giocatrice_attiva = True
        session.pop("sbloccato", None)
    return redirect(request.referrer or url_for("home"))


@app.route("/sblocca-modalita", methods=["GET", "POST"])
def sblocca_modalita():
    next_url = request.args.get("next") or "/"
    if not next_url.startswith("/"):
        next_url = "/"

    if request.method == "POST":
        next_url = request.form.get("next") or "/"
        if not next_url.startswith("/"):
            next_url = "/"
        password = request.form.get("password", "")
        hash_salvato = db.get_password_master()
        if not hash_salvato:
            flash("Nessuna password impostata. Usa imposta_password.py per configurarla.")
            return render_template("sblocca_modalita.html", next_url=next_url)
        if check_password_hash(hash_salvato, password):
            global modalita_giocatrice_attiva
            modalita_giocatrice_attiva = False
            session["sbloccato"] = True
            return render_template("sblocca_redirect.html", next_url=next_url)
        flash("Password non corretta.")
        return render_template("sblocca_modalita.html", next_url=next_url)

    return render_template("sblocca_modalita.html", next_url=next_url)


# --- GENERA PROMPT ---

@app.route("/genera-prompt", methods=["GET", "POST"])
def genera_prompt_page():
    if modalita_giocatrice_attiva:
        flash("Pagina non disponibile in modalità giocatrice.")
        return redirect(url_for("home"))

    locations = db.get_all_locations()

    prompt_generato = None
    quest_attive = []

    location_id_selezionata = request.form.get("location_id") if request.method == "POST" else request.args.get("location_id")

    if location_id_selezionata:
        quest_attive = db.get_quest_attive(location_id=int(location_id_selezionata))
    else:
        quest_attive = db.get_quest_attive()

    if request.method == "POST":
        location_id = int(request.form["location_id"])
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM locations WHERE id = %s", (location_id,))
        location_row = cur.fetchone()
        cur.close()
        conn.close()
        location = dict(location_row) if location_row else None

        quest_ids = [int(q) for q in request.form.getlist("quest_ids")]
        quest_selezionate = [q for q in db.get_all_quest_full() if q["id"] in quest_ids]

        npc_visti = {}
        for npc in db.get_npc_in_location(location_id):
            npc_visti[npc["id"]] = npc
        for q in quest_selezionate:
            for npc in db.get_npc_per_quest(q["id"]):
                npc_visti[npc["id"]] = npc

        contesto = {
            "location_nome": location["nome"] if location else "Non specificata",
            "location_descrizione": location.get("descrizione_breve", "") if location else "",
            "npc": list(npc_visti.values()),
            "quest": quest_selezionate,
            "fazioni": db.get_fazioni_rilevanti(),
            "fatti": db.get_fatti_accertati(),
            "eventi": db.get_eventi_recenti(n=5),
            "pg_stato": db.get_pg_stato(),
            "tipo_scena": request.form.get("tipo_scena", ""),
            "tono": request.form.get("tono", "").strip(),
            "intento": request.form.get("intento", "").strip(),
        }
        prompt_generato = costruisci_prompt(contesto)

    return render_template(
        "genera_prompt.html",
        active="genera",
        locations=locations,
        quest_attive=quest_attive,
        prompt_generato=prompt_generato,
    )

# --- AUDIO ---

def _salva_tag_da_form(traccia_id, stringa_tag):
    """Parsa la stringa tag (separati da virgola), crea tag mancanti, aggiorna associazioni."""
    nomi = [t.strip() for t in stringa_tag.split(",") if t.strip()]
    ids = [db.get_o_crea_tag(n) for n in nomi]
    ids = [i for i in ids if i is not None]
    db.set_tag_traccia(traccia_id, ids)


@app.route("/audio")
def audio_lista():
    tag_filtro = request.args.get("tag")
    tracce = db.get_all_tracce_audio(tag=tag_filtro)
    tag_disponibili = db.get_tutti_tag_audio()
    return render_template(
        "audio_lista.html",
        active="audio",
        tracce=tracce,
        tag_disponibili=tag_disponibili,
        tag_attivo=tag_filtro,
    )


@app.route("/audio/nuova", methods=["GET", "POST"])
def audio_nuova():
    if request.method == "POST":
        tipo_sorgente = request.form.get("tipo_sorgente", "youtube")
        if tipo_sorgente == "file":
            file_path = request.form.get("file_path", "").strip()
            disponibili = db.get_file_audio_disponibili()
            if not file_path or file_path not in disponibili:
                flash("File non valido o non trovato in static/audio/.")
                return redirect(url_for("audio_nuova"))
            traccia_id = db.add_traccia_audio(
                nome=request.form["nome"],
                categoria="",
                tipo_sorgente="file",
                file_path=file_path,
                youtube_id=None,
                timestamp_inizio=0,
                note=request.form.get("note") or None,
                location_id=request.form.get("location_id") or None,
                quest_id=request.form.get("quest_id") or None,
            )
        else:
            traccia_id = db.add_traccia_audio(
                nome=request.form["nome"],
                categoria="",
                tipo_sorgente="youtube",
                youtube_id=request.form["youtube_id"],
                timestamp_inizio=int(request.form.get("timestamp_inizio") or 0),
                note=request.form.get("note") or None,
                location_id=request.form.get("location_id") or None,
                quest_id=request.form.get("quest_id") or None,
            )
        _salva_tag_da_form(traccia_id, request.form.get("tag", ""))
        return redirect(url_for("audio_lista"))

    tag_disponibili = db.get_tutti_tag_audio()
    locations = db.get_all_locations()
    quest = db.get_all_quest()
    file_audio_disponibili = db.get_file_audio_disponibili()
    return render_template(
        "audio_form.html",
        tag_disponibili=tag_disponibili,
        locations=locations,
        quest=quest,
        traccia=None,
        tag_attuali="",
        file_audio_disponibili=file_audio_disponibili,
    )


@app.route("/audio/<int:traccia_id>/modifica", methods=["GET", "POST"])
def audio_modifica(traccia_id):
    traccia = db.get_traccia_audio(traccia_id)
    if not traccia:
        flash("Traccia non trovata.")
        return redirect(url_for("audio_lista"))

    if request.method == "POST":
        tipo_sorgente = request.form.get("tipo_sorgente", "youtube")
        campi = dict(
            nome=request.form["nome"],
            tipo_sorgente=tipo_sorgente,
            note=request.form.get("note") or None,
            location_id=_int_or_none(request.form.get("location_id")),
            quest_id=_int_or_none(request.form.get("quest_id")),
        )
        if tipo_sorgente == "file":
            file_path = request.form.get("file_path", "").strip()
            disponibili = db.get_file_audio_disponibili()
            if not file_path or file_path not in disponibili:
                flash("File non valido o non trovato in static/audio/.")
                return redirect(url_for("audio_modifica", traccia_id=traccia_id))
            campi["file_path"] = file_path
            campi["youtube_id"] = None
            campi["timestamp_inizio"] = 0
        else:
            campi["youtube_id"] = request.form["youtube_id"]
            campi["timestamp_inizio"] = int(request.form.get("timestamp_inizio") or 0)
            campi["file_path"] = None
        db.update_traccia_audio(traccia_id, **campi)
        _salva_tag_da_form(traccia_id, request.form.get("tag", ""))
        return redirect(url_for("audio_lista"))

    tag_disponibili = db.get_tutti_tag_audio()
    tag_attuali = ", ".join(db.get_tag_di_traccia(traccia_id))
    locations = db.get_all_locations()
    quest = db.get_all_quest()
    file_audio_disponibili = db.get_file_audio_disponibili()
    return render_template(
        "audio_form.html",
        tag_disponibili=tag_disponibili,
        locations=locations,
        quest=quest,
        traccia=traccia,
        tag_attuali=tag_attuali,
        file_audio_disponibili=file_audio_disponibili,
    )


@app.route("/audio/<int:traccia_id>/elimina", methods=["POST"])
def audio_elimina(traccia_id):
    db.delete_traccia_audio(traccia_id)
    return redirect(url_for("audio_lista"))


@app.route("/audio/tag")
def audio_tag_lista():
    tag = db.get_tag_con_conteggio_uso()
    return render_template("audio_tag_lista.html", active="audio", tag=tag)


@app.route("/audio/tag/<int:tag_id>/elimina", methods=["POST"])
def audio_tag_elimina(tag_id):
    db.delete_tag(tag_id)
    return redirect(url_for("audio_tag_lista"))


@app.route("/ping")
def ping():
    return '', 204


if __name__ == "__main__":
    app.run(debug=True, port=5000)
