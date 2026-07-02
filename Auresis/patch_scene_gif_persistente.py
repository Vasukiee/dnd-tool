import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("""
    ALTER TABLE scene_indagine ADD COLUMN IF NOT EXISTS gif_data BYTEA;
    ALTER TABLE scene_indagine ADD COLUMN IF NOT EXISTS gif_mime TEXT;
    ALTER TABLE scene_indagine ADD COLUMN IF NOT EXISTS gif_data_aggiornata TIMESTAMPTZ;
""")
conn.commit()
cur.close()
conn.close()
print("Success: colonne gif_data/gif_mime/gif_data_aggiornata aggiunte a scene_indagine.")
