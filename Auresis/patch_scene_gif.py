import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("""
    CREATE TABLE IF NOT EXISTS scene_indagine (
        id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        indagine_id INTEGER NOT NULL REFERENCES indagini(id) ON DELETE CASCADE,
        numero_scena INTEGER NOT NULL,
        gif_url TEXT,
        UNIQUE (indagine_id, numero_scena)
    );
""")
conn.commit()
cur.close()
conn.close()
print("Success: tabella scene_indagine creata.")
