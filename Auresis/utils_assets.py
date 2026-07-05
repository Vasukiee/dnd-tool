import os
import re


def minify_css(css: str) -> str:
    """Minimizza rudimentalmente un foglio di stile CSS senza librerie esterne."""
    # Rimuovi i commenti /* ... */
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
    # Rimuovi a capo e tab
    css = re.sub(r'[\n\r\t]', '', css)
    # Riduci gli spazi multipli a spazio singolo
    css = re.sub(r'\s+', ' ', css)
    # Rimuovi spazi attorno a caratteri chiave
    css = re.sub(r'\s*([\{\}\:\;\,\>])\s*', r'\1', css)
    return css.strip()


def ottimizza_e_minimizza_assets(app):
    """
    Scansiona i file statici e genera le versioni minimizzate (.min.)
    solo se il file originale è stato modificato più di recente o se il .min non esiste.
    Viene chiamato al boot dell'app.
    """
    static_folder = app.static_folder
    if not static_folder or not os.path.isdir(static_folder):
        return

    # File CSS da minimizzare
    assets_da_minimizzare = [
        "style.css",
    ]

    for filename in assets_da_minimizzare:
        original_path = os.path.join(static_folder, filename)
        if not os.path.exists(original_path):
            continue

        nome, estensione = os.path.splitext(filename)
        min_filename = f"{nome}.min{estensione}"
        min_path = os.path.join(static_folder, min_filename)

        necessita_aggiornamento = True
        if os.path.exists(min_path):
            mtime_original = os.path.getmtime(original_path)
            mtime_min = os.path.getmtime(min_path)
            # Aggiungiamo un piccolo buffer per via della precisione filesystem
            if mtime_min >= mtime_original - 1:
                necessita_aggiornamento = False

        if necessita_aggiornamento:
            with open(original_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if estensione == '.css':
                minimized_content = minify_css(content)
            else:
                # Fallback, passa il contenuto com'è se non riconosciamo il tipo
                minimized_content = content

            with open(min_path, 'w', encoding='utf-8') as f:
                f.write(minimized_content)

            print(f"[ASSETS] Minimizzato: {filename} -> {min_filename}")
