#!/usr/bin/env python3
"""Imposta la password master per il toggle modalità giocatrice."""
import getpass
from werkzeug.security import generate_password_hash
import db


def main():
    pwd = getpass.getpass("Password master: ")
    conferma = getpass.getpass("Conferma password: ")
    if not pwd:
        print("Errore: la password non può essere vuota.")
        return
    if pwd != conferma:
        print("Errore: le password non coincidono.")
        return
    db.set_password_master(generate_password_hash(pwd))
    print("Password impostata.")


if __name__ == "__main__":
    main()
