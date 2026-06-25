from flask import Flask, render_template, request, redirect, url_for, flash, session
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

@app.route("/audio")
def audio_lista():
    categoria_filtro = request.args.get("categoria")
    tracce = db.get_all_tracce_audio(categoria=categoria_filtro)
    categorie = db.get_categorie_audio_esistenti()
    return render_template(
        "audio_lista.html",
        active="audio",
        tracce=tracce,
        categorie=categorie,
        categoria_attiva=categoria_filtro,
    )


@app.route("/audio/nuova", methods=["GET", "POST"])
def audio_nuova():
    if request.method == "POST":
        db.add_traccia_audio(
            nome=request.form["nome"],
            categoria=request.form["categoria"],
            youtube_id=request.form["youtube_id"],
            timestamp_inizio=int(request.form.get("timestamp_inizio") or 0),
            note=request.form.get("note") or None,
            location_id=request.form.get("location_id") or None,
            quest_id=request.form.get("quest_id") or None,
        )
        return redirect(url_for("audio_lista"))

    categorie = db.get_categorie_audio_esistenti()
    locations = db.get_all_locations()
    quest = db.get_all_quest()
    return render_template(
        "audio_form.html",
        categorie=categorie,
        locations=locations,
        quest=quest,
        traccia=None,
    )


@app.route("/audio/<int:traccia_id>/elimina", methods=["POST"])
def audio_elimina(traccia_id):
    db.delete_traccia_audio(traccia_id)
    return redirect(url_for("audio_lista"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
