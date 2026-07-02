import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("ALTER TABLE indagini ADD COLUMN IF NOT EXISTS visibile_giocatrice BOOLEAN NOT NULL DEFAULT FALSE;")
conn.commit()
print("Success")
