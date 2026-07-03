"""Autenticazione minimale condivisa tra app.py e i blueprint.

Modello: un utente è "master" (accesso in scrittura) SOLO se ha superato lo
sblocco con la password master, che imposta ``session["sbloccato"]`` (vedi
``app.sblocca_modalita``). Il default — inclusi i visitatori anonimi — è sola
lettura: ogni rotta di scrittura viene rifiutata finché non ci si autentica.
"""
from functools import wraps
from urllib.parse import urlparse

from flask import flash, jsonify, redirect, request, session, url_for


def utente_e_master():
    """True se l'utente ha sbloccato la modalità master con la password."""
    return bool(session.get("sbloccato"))


def _richiesta_json():
    return request.is_json or request.accept_mimetypes.best == "application/json"


def richiedi_master(view):
    """Consente la rotta solo al master autenticato.

    I client JSON ricevono 403; le pagine normali vengono rimandate allo sblocco
    con password, conservando la destinazione in ``next``.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not utente_e_master():
            if _richiesta_json():
                return jsonify({"ok": False, "errore": "Autenticazione master richiesta"}), 403
            flash("Sblocca la modalità master per eseguire questa azione.")
            if request.method == "GET":
                prossima = request.path
            else:
                prossima = urlparse(request.referrer or "").path or url_for("home")
            return redirect(url_for("sblocca_modalita", next=prossima))
        return view(*args, **kwargs)
    return wrapped
