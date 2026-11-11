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
    Genera le versioni minimizzate (.min.) dei file statici, al boot dell'app.

    Il .min si riscrive solo se il suo contenuto è diverso da quello atteso.
    Il confronto è sul contenuto e non sulle date dei file: dopo un `git clone`
    o un deploy le date sono quelle del checkout, e un .min vecchio rimasto nel
    repository risultava "aggiornato" pur non corrispondendo più al sorgente.
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

        with open(original_path, 'r', encoding='utf-8') as f:
            content = f.read()
        minimized_content = minify_css(content) if estensione == '.css' else content

        try:
            with open(min_path, 'r', encoding='utf-8') as f:
                if f.read() == minimized_content:
                    continue
        except OSError:
            pass

        # Scrittura atomica: con più worker gunicorn che partono insieme,
        # nessuno deve poter servire un file scritto a metà.
        tmp_path = f"{min_path}.{os.getpid()}.tmp"
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                f.write(minimized_content)
            os.replace(tmp_path, min_path)
        except OSError as e:
            # file system in sola lettura: si continua a servire il .min esistente
            print(f"[ASSETS] Impossibile aggiornare {min_filename}: {e}")
            continue

        print(f"[ASSETS] Minimizzato: {filename} -> {min_filename}")


SFONDO_LATO_MAX = 1920


def ottimizza_sfondo(data, mime, lato_max=SFONDO_LATO_MAX):
    """Ridimensiona uno sfondo a `lato_max` px e lo restituisce come WebP
    (o JPEG/WebP originale se già entro il limite). Le GIF animate diventano
    immagini statiche (primo fotogramma). Ritorna (data, mime); se Pillow manca
    o il file non è decodificabile, lascia i byte invariati."""
    try:
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        formato = (img.format or "").upper()
        animata = getattr(img, "is_animated", False)
        if formato in ("JPEG", "WEBP") and not animata and max(img.size) <= lato_max:
            return data, mime
        img.seek(0)
        img = img.convert("RGBA" if "A" in img.getbands() or img.mode == "P" else "RGB")
        img.thumbnail((lato_max, lato_max), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, "WEBP", quality=82, method=4)
        return out.getvalue(), "image/webp"
    except Exception as e:  # noqa: BLE001 - mai bloccare un upload per l'ottimizzazione
        print(f"[ASSETS] Sfondo non ottimizzato: {e}")
        return data, mime
