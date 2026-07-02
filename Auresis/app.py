import os
from functools import wraps
from urllib.parse import urlparse

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from werkzeug.security import check_password_hash

import copioni
import db
from blueprints.indagini import bp as indagini_bp

app = Flask(__name__)

_secret_key = os.environ.get("SECRET_KEY")
if not _secret_key:
    try:
        _secret_key = db.get_o_crea_secret_key()
    except Exception as e:
        # DB non raggiungibile: chiave effimera pur di avviarsi (le sessioni non sopravvivono al riavvio)
        print(f"ATTENZIONE: impossibile leggere la SECRET_KEY dal database ({e}), uso una chiave temporanea.")
        _secret_key = os.urandom(24)
app.secret_key = _secret_key

@app.context_processor
def inietta_modalita_giocatrice():
    return {"modalita_giocatrice": session.get("modalita_giocatrice")}

@app.context_processor
def inietta_palette():
    try:
        return {"palette_personalizzata": db.get_palette()}
    except Exception:
        return {"palette_personalizzata": {}}

app.register_blueprint(indagini_bp)

def solo_master(view):
    """Blocca la rotta quando è attiva la modalità giocatrice."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("modalita_giocatrice"):
            if request.is_json or request.accept_mimetypes.best == "application/json":
                return jsonify({"ok": False, "errore": "Accesso negato"}), 403
            flash("Questa azione non è disponibile in modalità giocatrice.")
            return redirect(url_for("home"))
        return view(*args, **kwargs)
    return wrapped


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

    if session.get("modalita_giocatrice"):
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

    if session.get("modalita_giocatrice") and not is_template and not completata:
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


@app.route("/copioni/nuovo", methods=["POST"])
@solo_master
def nuovo_copione():
    numero_sessione = int(request.form.get("numero_sessione", 0))
    esistente = copioni.get_testo_sessione(numero_sessione)
    if not esistente:
        titolo = f"Sessione {numero_sessione}: Nuovo Capitolo"
        testo_base = f"# {titolo}\n\n(Master) Inizia a scrivere qui il nuovo copione..."
        copioni.salva_testo_sessione(numero_sessione, testo_base)
    return redirect(url_for("copioni_modifica", numero_sessione=numero_sessione))


@app.route("/copioni/<int:numero_sessione>/modifica", methods=["GET", "POST"])
@solo_master
def copioni_modifica(numero_sessione):
    if request.method == "POST":
        if request.is_json:
            testo = request.get_json(force=True).get("contenuto", "")
            copioni.salva_testo_sessione(numero_sessione, testo)
            return {"ok": True}
        testo = request.form.get("contenuto", "")
        copioni.salva_testo_sessione(numero_sessione, testo)
        flash("Copione salvato.")
        return redirect(url_for("copioni_dettaglio", numero_sessione=numero_sessione))

    testo = copioni.get_testo_sessione(numero_sessione)
    if not testo.strip():
        flash("File copione non trovato o sessione non esistente.")
        return redirect(url_for("copioni_indice"))

    titolo = copioni.estrai_titolo(testo) or f"Sessione {numero_sessione}"
    tracce = db.get_all_tracce_audio()
    nome_file_label = f"sessione_{numero_sessione}.md ({'DB' if db.get_storage_mode() == 'db' else 'Disk'})"
    
    indagini_db = db.get_all_indagini()
    indagini_con_nodi = []
    for ind in indagini_db:
        nodi = db.get_nodi_indagine(ind["id"])
        # estrai le scene (es. nodo 12 -> scena 1)
        scene = sorted(list(set(n["numero_nodo"] // 10 for n in nodi)))
        # Aggiungiamo sempre la scena 0 ("intro") all'inizio
        if 0 not in scene:
            scene.insert(0, 0)
        indagini_con_nodi.append({
            "indagine": ind,
            "nodi": nodi,
            "scene": scene
        })

    return render_template(
        "copioni_modifica.html",
        active="copioni",
        numero_sessione=numero_sessione,
        nome_file=nome_file_label,
        titolo=titolo,
        contenuto=testo,
        tracce=tracce,
        indagini_con_nodi=indagini_con_nodi
    )


@app.route("/copioni/<int:numero_sessione>/toggle-completata", methods=["POST"])
@solo_master
def copioni_toggle_completata(numero_sessione):
    nuovo_stato = not db.get_sessione_completata(numero_sessione)
    db.set_sessione_completata(numero_sessione, nuovo_stato)
    return redirect(url_for("copioni_dettaglio", numero_sessione=numero_sessione))


# --- NPC ---

@app.route("/npc")
def lista_npc():
    npc_list = db.get_all_npc_full()
    if session.get("modalita_giocatrice"):
        npc_list = [n for n in npc_list if n.get("visibile_giocatrice")]
    return render_template("npc_lista.html", active="npc", npc_list=npc_list)


@app.route("/npc/<int:npc_id>")
def dettaglio_npc(npc_id):
    npc = db.get_npc_full(npc_id)
    if not npc:
        flash("Personaggio non trovato.")
        return redirect(url_for("lista_npc"))
    if session.get("modalita_giocatrice") and not npc.get("visibile_giocatrice"):
        flash("Questo personaggio non è ancora disponibile.")
        return redirect(url_for("lista_npc"))
    return render_template("npc_dettaglio.html", active="npc", npc=npc)


@app.route("/npc/nuovo", methods=["GET", "POST"])
@solo_master
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
@solo_master
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
@solo_master
def elimina_npc(npc_id):
    db.delete_record("npc", npc_id)
    flash("Personaggio eliminato dal registro.")
    return redirect(url_for("lista_npc"))


@app.route("/npc/<int:npc_id>/toggle-visibile", methods=["POST"])
@solo_master
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
@solo_master
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
@solo_master
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
@solo_master
def elimina_fazione(fazione_id):
    db.delete_record("fazioni", fazione_id)
    flash("Fazione eliminata dal registro.")
    return redirect(url_for("lista_fazioni"))


# --- LOCATIONS ---

@app.route("/locations")
def lista_locations():
    locations_list = db.get_all_locations_full()
    if session.get("modalita_giocatrice"):
        locations_list = [l for l in locations_list if l.get("visibile_giocatrice")]
    return render_template("locations_lista.html", active="locations", locations_list=locations_list)


@app.route("/locations/<int:location_id>")
def dettaglio_location(location_id):
    location = db.get_location_full(location_id)
    if not location:
        flash("Luogo non trovato.")
        return redirect(url_for("lista_locations"))
    if session.get("modalita_giocatrice") and not location.get("visibile_giocatrice"):
        flash("Questo luogo non è ancora disponibile.")
        return redirect(url_for("lista_locations"))
    return render_template("locations_dettaglio.html", active="locations", location=location)


@app.route("/locations/nuova", methods=["GET", "POST"])
@solo_master
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
@solo_master
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
@solo_master
def elimina_location(location_id):
    db.delete_record("locations", location_id)
    flash("Luogo eliminato dal registro.")
    return redirect(url_for("lista_locations"))


@app.route("/locations/<int:location_id>/toggle-visibile", methods=["POST"])
@solo_master
def location_toggle_visibile(location_id):
    db.set_location_visibile(location_id, not db.get_location_visibile(location_id))
    return redirect(url_for("lista_locations"))


# --- QUEST ---

@app.route("/quest")
def lista_quest():
    quest_list = db.get_all_quest_full()
    if session.get("modalita_giocatrice"):
        quest_list = [q for q in quest_list if q.get("visibile_giocatrice")]
    return render_template("quest_lista.html", active="quest", quest_list=quest_list)


@app.route("/quest/<int:quest_id>")
def dettaglio_quest(quest_id):
    quest = db.get_quest_full(quest_id)
    if not quest:
        flash("Incarico non trovato.")
        return redirect(url_for("lista_quest"))
    if session.get("modalita_giocatrice") and not quest.get("visibile_giocatrice"):
        flash("Questo incarico non è ancora disponibile.")
        return redirect(url_for("lista_quest"))
    return render_template("quest_dettaglio.html", active="quest", quest=quest)


@app.route("/quest/nuova", methods=["GET", "POST"])
@solo_master
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
@solo_master
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
@solo_master
def elimina_quest(quest_id):
    db.delete_record("quest", quest_id)
    flash("Incarico eliminato dal registro.")
    return redirect(url_for("lista_quest"))


@app.route("/quest/<int:quest_id>/toggle-visibile", methods=["POST"])
@solo_master
def quest_toggle_visibile(quest_id):
    db.set_quest_visibile(quest_id, not db.get_quest_visibile(quest_id))
    return redirect(url_for("lista_quest"))


@app.route("/quest/<int:quest_id>/collega-npc", methods=["GET", "POST"])
@solo_master
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
@solo_master
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
@solo_master
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
@solo_master
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
@solo_master
def elimina_fatto(fatto_id):
    db.delete_record("fatti_accertati", fatto_id)
    flash("Verità eliminata dal registro.")
    return redirect(url_for("lista_fatti"))


# --- INDAGINI: vedi blueprints/indagini.py ---

@app.route("/impostazioni/sipario_globale_toggle", methods=["POST"])
@solo_master
def sipario_globale_toggle():
    nuovo_stato = db.toggle_sipario_globale()
    return jsonify({"success": True, "sipario_aperto": nuovo_stato})

@app.route("/impostazioni/sfondo_default", methods=["GET", "POST"])
def sfondo_default():
    if request.method == "POST":
        if session.get("modalita_giocatrice"):
            return "Accesso negato", 403
        file = request.files.get("file")
        if file and file.filename:
            data = file.read()
            mime = file.mimetype
            db.set_impostazione_bytea("sfondo_default", data, mime)
            flash("Sfondo di default aggiornato con successo.")
        return redirect(url_for('indagini.lista_indagini'))
        
    else:
        # GET return the image
        img = db.get_impostazione("sfondo_default")
        if img and img.get("valore_bytea"):
            response = make_response(img["valore_bytea"])
            response.headers.set("Content-Type", img["valore_mime"])
            # Cache headers
            response.headers.set("Cache-Control", "public, max-age=31536000")
            return response
        else:
            return redirect(url_for('static', filename='sfondo_default.jpg'))



# --- STATO DEL PG ---

@app.route("/soggetto", methods=["GET", "POST"])
def pg_stato_page():
    if request.method == "POST":
        if session.get("modalita_giocatrice"):
            flash("Questa azione non è disponibile in modalità giocatrice.")
            return redirect(url_for("pg_stato_page"))
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
    if session.get("modalita_giocatrice"):
        # per disattivare serve sia il flag di sessione che quello di sessionStorage
        if session.get("sbloccato") and request.form.get("sbloccato_tab") == "1":
            session.pop("modalita_giocatrice", None)
        else:
            ritorna = urlparse(request.referrer or "/").path or "/"
            return redirect(url_for("sblocca_modalita", next=ritorna))
    else:
        session["modalita_giocatrice"] = True
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
            session.pop("modalita_giocatrice", None)
            session["sbloccato"] = True
            return render_template("sblocca_redirect.html", next_url=next_url)
        flash("Password non corretta.")
        return render_template("sblocca_modalita.html", next_url=next_url)

    return render_template("sblocca_modalita.html", next_url=next_url)



_VARIABILI_PALETTE = [
    "--ink", "--ink-raised", "--ink-line", "--bone", "--bone-dim",
    "--gold", "--gold-bright", "--rust", "--rust-bright",
    "--verdigris", "--verdigris-bright"
]

@app.route("/palette", methods=["POST"])
def salva_palette():
    data = request.get_json()
    if not data:
        return {"ok": False}, 400
        
    if data.get("action") == "reset":
        db.reset_palette()
        return {"ok": True}
        
    variabile = data.get("variabile", "").strip()
    valore = data.get("valore", "").strip()
    if variabile not in _VARIABILI_PALETTE:
        return {"ok": False}, 400
    db.set_palette_colore(variabile, valore)
    return {"ok": True}

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
@solo_master
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
@solo_master
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
@solo_master
def audio_elimina(traccia_id):
    db.delete_traccia_audio(traccia_id)
    return redirect(url_for("audio_lista"))


@app.route("/audio/tag")
def audio_tag_lista():
    tag = db.get_tag_con_conteggio_uso()
    return render_template("audio_tag_lista.html", active="audio", tag=tag)


@app.route("/audio/tag/<int:tag_id>/elimina", methods=["POST"])
@solo_master
def audio_tag_elimina(tag_id):
    db.delete_tag(tag_id)
    return redirect(url_for("audio_tag_lista"))


@app.route("/ping")
def ping():
    return '', 204


if __name__ == "__main__":
    app.run(debug=True, port=5000)
