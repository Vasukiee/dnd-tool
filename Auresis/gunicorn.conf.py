"""Configurazione di gunicorn, letta da sola quando parte da questa cartella.

Sta qui e non nel comando di avvio perché il comando vive nella dashboard
dell'hosting e basta dimenticarlo (`gunicorn app:app` senza opzioni) per
restare con un solo worker sincrono: una richiesta alla volta, con il polling
di live view e player view in coda dietro a ogni download di un file audio.
"""
import os

# Pochi processi, più thread: il server gratuito ha una frazione di CPU e il
# tempo di una richiesta è quasi tutto attesa del database.
workers = int(os.environ.get("WEB_CONCURRENCY", 2))
# Non oltre db._POOL_MAX (5): ogni thread può tenere una connessione al database.
threads = int(os.environ.get("GUNICORN_THREADS", 4))
timeout = 60

# Durata di ogni richiesta nel log, in microsecondi (%(D)s).
accesslog = "-"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sus'
