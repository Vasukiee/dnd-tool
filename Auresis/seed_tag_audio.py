"""
Script una tantum per pre-popolare tag_audio con un vocabolario di partenza:
generi musicali classici + mood/atmosfere narrative.

Uso:
    python seed_tag_audio.py

Esegui dalla cartella Auresis/ con il venv attivato e le variabili
d'ambiente già puntate al DB che vuoi popolare (locale o produzione).
Lo script è idempotente: usa get_o_crea_tag, quindi rilanciarlo più volte
non crea duplicati.
"""

import db

# ---------------------------------------------------------------
# Generi musicali (in senso tecnico)
# ---------------------------------------------------------------
GENERI = [
    "ambient", "drone", "industrial", "dark ambient", "noise",
    "synth", "synthwave", "darksynth", "electronic", "idm",
    "classica", "orchestrale", "cinematica", "neoclassica",
    "piano solo", "cello solo", "corale", "gregoriano",
    "jazz", "jazz noir", "blues", "lounge",
    "folk", "folk dark", "celtico", "world",
    "rock", "post-rock", "shoegaze", "metal", "doom",
    "chiptune", "8-bit", "steampunk", "victoriana",
    "percussivo", "tribale", "ritualistico",
    "glitch", "experimental", "musique concrète",
]

# ---------------------------------------------------------------
# Mood / atmosfere narrative (coerenti con l'uso già fatto:
# industriale, tensione, intimo, orrore, transizione, ecc.)
# ---------------------------------------------------------------
MOOD = [
    "tensione", "suspense", "ansia crescente", "minaccia",
    "orrore", "terrore", "disturbante", "inquietante",
    "intimo", "malinconia", "nostalgia", "lutto",
    "transizione", "fine sessione", "apertura sessione",
    "trionfo", "epico", "climax", "battaglia", "scontro",
    "rivelazione", "colpo di scena", "mistero", "indagine",
    "industriale", "fonderia", "miniera", "fabbrica",
    "urbano", "metropoli", "decadenza", "rovina",
    "sacro", "profano", "rituale", "cerimonia",
    "speranza", "redenzione", "perdita", "solitudine",
    "calma", "quiete", "contemplativo", "meditativo",
    "caos", "frenesia", "inseguimento", "fuga",
    "romantico", "sensuale", "onirico", "surreale",
]

TUTTI_I_TAG = GENERI + MOOD


def main():
    print(f"Inserimento/verifica di {len(TUTTI_I_TAG)} tag...\n")

    for nome_tag in TUTTI_I_TAG:
        db.get_o_crea_tag(nome_tag)
        print(f"  ok: {nome_tag}")

    print(f"\nFatto. {len(TUTTI_I_TAG)} tag verificati/creati in tag_audio.")
    print("Lo script è idempotente: rilanciarlo non crea duplicati, grazie a get_o_crea_tag.")


if __name__ == "__main__":
    main()
