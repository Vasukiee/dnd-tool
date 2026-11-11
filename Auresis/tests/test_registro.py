"""Test del Registro: permessi, modifica delle schede, vista giocatrice."""
import pytest

import app as app_module
import db


def _id(tabella, nome):
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT id FROM {tabella} WHERE nome = %s", (nome,))
    riga = cur.fetchone()
    conn.close()
    return riga[0] if riga else None


def _conta(tabella):
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {tabella}")
    totale = cur.fetchone()[0]
    conn.close()
    return totale


# --- pagine e permessi ------------------------------------------------------

PAGINE_PUBBLICHE = ["/", "/npc", "/fazioni", "/locations", "/quest", "/eventi", "/fatti",
                    "/soggetto", "/copioni", "/indagini/", "/mappa-relazioni",
                    "/mappa-relazioni.json", "/cerca?q=oro", "/sblocca-modalita"]
PAGINE_MASTER = ["/npc/nuovo", "/fazioni/nuova", "/locations/nuova", "/quest/nuova",
                 "/eventi/nuovo", "/fatti/nuovo", "/audio", "/master/note"]


@pytest.mark.parametrize("url", PAGINE_PUBBLICHE)
def test_pagine_pubbliche_rispondono(anonimo, url):
    assert anonimo.get(url).status_code == 200


@pytest.mark.parametrize("url", PAGINE_PUBBLICHE + PAGINE_MASTER)
def test_pagine_master_rispondono(master, url):
    assert master.get(url).status_code == 200


@pytest.mark.parametrize("url", PAGINE_MASTER)
def test_anonimo_non_entra_nelle_pagine_master(anonimo, url):
    assert anonimo.get(url).status_code in (302, 404)


def test_anonimo_non_puo_scrivere(anonimo):
    risposta = anonimo.post("/npc/nuovo", {"nome": "Intruso"})
    assert risposta.status_code == 302
    assert "/sblocca-modalita" in risposta.headers["Location"]
    assert _conta("npc") == 0


def test_post_senza_csrf_rifiutato(master):
    risposta = master.client.post("/npc/nuovo", data={"nome": "Senza token"})
    assert risposta.status_code == 400
    assert _conta("npc") == 0


def test_password_sbagliata_e_lockout(anonimo):
    for _ in range(app_module._MAX_TENTATIVI_SBLOCCO):
        assert anonimo.post("/sblocca-modalita", {"password": "no"}).status_code == 200
    assert anonimo.post("/sblocca-modalita", {"password": "no"}).status_code == 429
    assert anonimo.get("/npc/nuovo").status_code == 302


@pytest.mark.parametrize("destinazione", ["//altro.sito", "https://altro.sito", "/\\altro.sito"])
def test_sblocco_non_rimanda_fuori_dal_sito(anonimo, destinazione):
    pagina = anonimo.get("/sblocca-modalita", query_string={"next": destinazione})
    assert "altro.sito" not in pagina.get_data(as_text=True)
    risposta = anonimo.post("/sblocca-modalita",
                            {"password": "parola-d-ordine", "next": destinazione})
    assert "altro.sito" not in risposta.get_data(as_text=True)


def test_destinazione_interna_conservata(anonimo):
    risposta = anonimo.post("/sblocca-modalita",
                            {"password": "parola-d-ordine", "next": "/npc?x=1"})
    assert "/npc?x=1" in risposta.get_data(as_text=True)


def test_header_di_sicurezza(anonimo):
    risposta = anonimo.get("/")
    assert risposta.headers["X-Content-Type-Options"] == "nosniff"
    assert risposta.headers["X-Frame-Options"] == "SAMEORIGIN"


def test_pagina_404_con_grafica_del_sito(anonimo):
    risposta = anonimo.get("/non-esiste")
    assert risposta.status_code == 404
    assert "Pagina non trovata" in risposta.get_data(as_text=True)


def test_404_json_per_le_chiamate_da_script(anonimo):
    risposta = anonimo.get("/non-esiste", headers={"Accept": "application/json"})
    assert risposta.status_code == 404
    assert risposta.get_json()["ok"] is False


def test_salute_passa_dal_database(anonimo):
    dati = anonimo.get("/salute").get_json()
    assert dati["ok"] is True and dati["db_ms"] >= 0


def test_sommario_conta_solo_cio_che_la_giocatrice_vede(master, anonimo):
    master.post("/npc/nuovo", {"nome": "Tessa"})
    master.post("/npc/nuovo", {"nome": "Dario"})
    db.set_npc_visibile(_id("npc", "Tessa"), True)
    assert db.get_home_dashboard_data(solo_visibili=False)["stats"]["npc_totali"] == 2
    assert db.get_home_dashboard_data(solo_visibili=True)["stats"]["npc_totali"] == 1
    assert anonimo.get("/").status_code == 200


# --- schede: creazione e modifica -------------------------------------------

def test_rinominare_un_personaggio_non_crea_doppioni(master):
    master.post("/npc/nuovo", {"nome": "Tessa", "ruolo": "minatrice"})
    npc_id = _id("npc", "Tessa")
    master.post(f"/npc/{npc_id}/edita", {"nome": "Tessa Bruciaterra", "ruolo": "minatrice"})
    assert _conta("npc") == 1
    assert db.get_npc_full(npc_id)["nome"] == "Tessa Bruciaterra"


def test_rinominare_con_un_nome_gia_usato_non_tocca_l_altra_scheda(master):
    master.post("/npc/nuovo", {"nome": "Dario", "ruolo": "caposquadra"})
    master.post("/npc/nuovo", {"nome": "Voll", "ruolo": "sovrintendente"})
    dario, voll = _id("npc", "Dario"), _id("npc", "Voll")
    master.post(f"/npc/{dario}/edita", {"nome": "Voll", "ruolo": "impostore"})
    assert db.get_npc_full(dario)["nome"] == "Dario"
    assert db.get_npc_full(voll)["ruolo"] == "sovrintendente"


@pytest.mark.parametrize("percorso, tabella, lettura", [
    ("fazioni", "fazioni", db.get_fazione_full),
    ("locations", "locations", db.get_location_full),
])
def test_rinominare_fazioni_e_luoghi(master, percorso, tabella, lettura):
    nuova = "nuova"
    master.post(f"/{percorso}/{nuova}", {"nome": "Vecchio nome"})
    voce_id = _id(tabella, "Vecchio nome")
    master.post(f"/{percorso}/{voce_id}/edita", {"nome": "Nuovo nome"})
    assert _conta(tabella) == 1
    assert lettura(voce_id)["nome"] == "Nuovo nome"


def test_rinominare_un_luogo_conserva_i_legami(master):
    master.post("/locations/nuova", {"nome": "Calderaviva"})
    luogo = _id("locations", "Calderaviva")
    master.post("/npc/nuovo", {"nome": "Tessa", "location_attuale_id": str(luogo)})
    master.post(f"/locations/{luogo}/edita", {"nome": "Calderaviva Bassa"})
    assert db.get_npc_full(_id("npc", "Tessa"))["location_nome"] == "Calderaviva Bassa"


def test_campo_svuotato_in_modifica_torna_null(master):
    master.post("/npc/nuovo", {"nome": "Tessa", "note": "da cancellare"})
    npc_id = _id("npc", "Tessa")
    master.post(f"/npc/{npc_id}/edita", {"nome": "Tessa", "note": ""})
    assert db.get_npc_full(npc_id)["note"] is None


def test_numeri_scritti_male_non_fanno_cadere_la_pagina(master):
    risposta = master.post("/npc/nuovo", {"nome": "Tessa", "livello_contaminazione": "tanto",
                                          "ultima_apparizione_sessione": "ieri"})
    assert risposta.status_code == 302
    assert master.post("/eventi/nuovo", {"sessione": "prima", "riassunto": "x"}).status_code == 302
    assert _conta("eventi") == 0


def test_contaminazione_resta_nella_scala(master):
    master.post("/npc/nuovo", {"nome": "Tessa", "livello_contaminazione": "42"})
    assert db.get_npc_full(_id("npc", "Tessa"))["livello_contaminazione"] == 5


def test_eliminare_un_luogo_non_elimina_chi_ci_vive(master):
    master.post("/locations/nuova", {"nome": "Calderaviva"})
    luogo = _id("locations", "Calderaviva")
    master.post("/npc/nuovo", {"nome": "Tessa", "location_attuale_id": str(luogo)})
    master.post(f"/locations/{luogo}/elimina")
    assert _conta("locations") == 0
    assert db.get_npc_full(_id("npc", "Tessa"))["location_attuale_id"] is None


def test_toggle_visibilita_risponde_json_agli_script(master):
    master.post("/npc/nuovo", {"nome": "Tessa"})
    npc_id = _id("npc", "Tessa")
    risposta = master.post(f"/npc/{npc_id}/toggle-visibile", headers={"Accept": "application/json"})
    assert risposta.get_json() == {"ok": True, "visibile": True}
    assert master.post(f"/npc/{npc_id}/toggle-visibile").status_code == 302
    assert not db.get_npc_visibile(npc_id)


# --- vista giocatrice: niente trapela ---------------------------------------

@pytest.fixture
def campagna(master):
    """Una fazione, un luogo e un personaggio visibili; accanto a loro un
    luogo, un personaggio e un incarico ancora segreti."""
    master.post("/fazioni/nuova", {"nome": "Curia Aurea"})
    fazione = _id("fazioni", "Curia Aurea")
    master.post("/locations/nuova", {"nome": "Calderaviva", "fazione_controllante_id": str(fazione)})
    master.post("/locations/nuova", {"nome": "Cripta Segreta", "fazione_controllante_id": str(fazione)})
    aperto, segreto = _id("locations", "Calderaviva"), _id("locations", "Cripta Segreta")
    master.post("/npc/nuovo", {"nome": "Tessa", "fazione_id": str(fazione),
                               "location_attuale_id": str(aperto)})
    master.post("/npc/nuovo", {"nome": "Infiltrato Occulto", "fazione_id": str(fazione),
                               "location_attuale_id": str(aperto)})
    master.post("/npc/nuovo", {"nome": "Dario", "location_attuale_id": str(segreto)})
    master.post("/quest/nuova", {"nome": "Il crollo", "location_ids": [str(aperto), str(segreto)]})
    master.post("/quest/nuova", {"nome": "Complotto Taciuto", "location_ids": [str(aperto)]})
    ids = {
        "fazione": fazione, "aperto": aperto, "segreto": segreto,
        "tessa": _id("npc", "Tessa"), "infiltrato": _id("npc", "Infiltrato Occulto"),
        "dario": _id("npc", "Dario"),
        "crollo": _id("quest", "Il crollo"), "complotto": _id("quest", "Complotto Taciuto"),
    }
    for npc in ("tessa", "infiltrato", "dario"):
        for quest in ("crollo", "complotto"):
            db.link_npc_quest(ids[quest], ids[npc])
    db.set_location_visibile(aperto, True)
    db.set_npc_visibile(ids["tessa"], True)
    db.set_npc_visibile(ids["dario"], True)
    db.set_quest_visibile(ids["crollo"], True)
    return ids


SEGRETI = ["Cripta Segreta", "Infiltrato Occulto", "Complotto Taciuto"]


def _pagine_giocatrice(ids):
    return ["/", "/npc", "/locations", "/quest", "/fazioni", "/mappa-relazioni.json",
            f"/npc/{ids['tessa']}", f"/npc/{ids['dario']}", f"/fazioni/{ids['fazione']}",
            f"/locations/{ids['aperto']}", f"/quest/{ids['crollo']}",
            "/cerca?q=Segreta", "/cerca?q=Occulto", "/cerca?q=Taciuto"]


def test_la_giocatrice_non_vede_nomi_segreti(anonimo, campagna):
    for url in _pagine_giocatrice(campagna):
        risposta = anonimo.get(url)
        assert risposta.status_code == 200, url
        testo = risposta.get_data(as_text=True)
        for segreto in SEGRETI:
            assert segreto not in testo, f"{segreto!r} trapela da {url}"


def test_la_giocatrice_vede_cio_che_e_visibile(anonimo, campagna):
    testo = anonimo.get(f"/fazioni/{campagna['fazione']}").get_data(as_text=True)
    assert "Tessa" in testo and "Calderaviva" in testo
    testo = anonimo.get(f"/quest/{campagna['crollo']}").get_data(as_text=True)
    assert "Tessa" in testo and "Dario" in testo


def test_il_master_vede_tutto(master, campagna):
    testo = master.get(f"/fazioni/{campagna['fazione']}").get_data(as_text=True)
    for nome in ("Tessa", "Infiltrato Occulto", "Cripta Segreta"):
        assert nome in testo


def test_schede_segrete_non_raggiungibili_dalla_giocatrice(anonimo, campagna):
    for url in (f"/npc/{campagna['infiltrato']}", f"/locations/{campagna['segreto']}",
                f"/quest/{campagna['complotto']}"):
        assert anonimo.get(url).status_code == 302


def test_la_giocatrice_non_vede_i_comandi_del_master(anonimo, master, campagna):
    url = f"/npc/{campagna['tessa']}"
    assert "/elimina" not in anonimo.get(url).get_data(as_text=True)
    assert "/elimina" in master.get(url).get_data(as_text=True)


def test_mappa_relazioni_completa_per_il_master(master, campagna):
    dati = master.get("/mappa-relazioni.json").get_json()
    assert len(dati["nodes"]) == 8
    coinvolge = [l for l in dati["links"] if l["kind"] == "coinvolge"]
    scenario = [l for l in dati["links"] if l["kind"] == "scenario"]
    assert len(coinvolge) == 6 and len(scenario) == 3


# --- copioni ----------------------------------------------------------------

def test_copione_bozza_nascosto_finche_non_e_completato(master, anonimo):
    master.post("/copioni/nuovo", {"numero_sessione": "3"})
    assert master.get("/copioni/3").status_code == 200
    assert anonimo.get("/copioni/3").status_code == 302
    master.post("/copioni/3/toggle-completata")
    assert anonimo.get("/copioni/3").status_code == 200


def test_backup_solo_per_il_master(master, anonimo):
    assert anonimo.get("/esporta-backup").status_code == 302
    dump = master.get("/esporta-backup").get_json()
    assert "npc" in dump and "impostazioni_sicurezza" not in dump
