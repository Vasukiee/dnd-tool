"""Ambiente dei test: sempre un database SQLite temporaneo, mai quello vero.

Le variabili vanno impostate prima di importare `db` e `app`: un eventuale
`.env` con DATABASE_URL non deve poter puntare i test al database in cloud
(load_dotenv non sovrascrive le variabili già presenti).
"""
import os
import sys
import tempfile

_cartella = tempfile.mkdtemp(prefix="registro-test-")
os.environ["DATABASE_URL"] = ""
os.environ["SQLITE_PATH"] = os.path.join(_cartella, "test.db")
os.environ["STORAGE_MODE"] = "db"
os.environ["SECRET_KEY"] = "chiave-solo-per-i-test"
os.environ.pop("RENDER", None)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
import db  # noqa: E402

PASSWORD = "parola-d-ordine"

_TABELLE_DA_SVUOTARE = [
    "quest_npc", "quest_locations", "eventi", "fatti_accertati", "npc", "quest",
    "locations", "fazioni", "sessioni_copioni",
]


@pytest.fixture(autouse=True)
def database_pulito():
    conn = db.get_connection()
    cur = conn.cursor()
    for tabella in _TABELLE_DA_SVUOTARE:
        cur.execute(f"DELETE FROM {tabella}")
    conn.commit()
    conn.close()
    db.set_password_master(generate_password_hash(PASSWORD))
    app_module._tentativi_sblocco.clear()
    yield


class Cliente:
    """Client di test che aggiunge da solo il token CSRF alle richieste mutanti."""

    def __init__(self):
        self.client = app_module.app.test_client()

    def _token(self):
        self.client.get("/ping")
        with self.client.session_transaction() as sessione:
            return sessione["_csrf_token"]

    def get(self, *args, **kwargs):
        return self.client.get(*args, **kwargs)

    def post(self, url, data=None, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        headers.setdefault("X-CSRFToken", self._token())
        return self.client.post(url, data=data or {}, headers=headers, **kwargs)

    def sblocca(self):
        risposta = self.post("/sblocca-modalita", {"password": PASSWORD, "next": "/"})
        assert risposta.status_code == 200
        return self


@pytest.fixture
def anonimo():
    return Cliente()


@pytest.fixture
def master():
    return Cliente().sblocca()
