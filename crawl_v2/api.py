"""Client minimale per l'API pubblica di Bluesky (nessun login).

Tutte le chiamate passano da qui: pausa fissa fra le richieste, nuovi tentativi con attesa
crescente su 429 e 5xx, nessun errore che interrompa il crawl (si restituisce None e si conta).
"""
import time

import requests

BASE = "https://public.api.bsky.app/xrpc/"
DELAY = 0.15          # ~6-7 richieste al secondo, sotto il limite pubblico di 3000 ogni 5 minuti
MAX_TRIES = 6

_session = requests.Session()
_session.headers["User-Agent"] = "unipi-sna-student-project/2.0 (research crawl)"
STATS = {"requests": 0, "errors": 0, "retries": 0}


def get(method, **params):
    for attempt in range(MAX_TRIES):
        time.sleep(DELAY)
        STATS["requests"] += 1
        try:
            r = _session.get(BASE + method, params=params, timeout=30)
        except requests.RequestException:
            r = None
        if r is not None and r.status_code == 200:
            return r.json()
        if r is not None and r.status_code in (400, 404):
            # post o account cancellato, bloccato o inesistente: non ha senso riprovare
            STATS["errors"] += 1
            return None
        STATS["retries"] += 1
        wait = 2 ** attempt
        if r is not None and r.status_code == 429:
            reset = r.headers.get("ratelimit-reset")
            if reset and reset.isdigit():
                wait = max(wait, int(reset) - int(time.time()) + 1)
        time.sleep(min(wait, 300))
    STATS["errors"] += 1
    return None
