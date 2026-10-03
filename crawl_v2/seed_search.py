"""Passo 1 del nuovo crawl: ricerca dei post seme per parola chiave.

E' l'unico passo che richiede il login (searchPosts non e' disponibile sull'API pubblica).
Le risposte sono lette come JSON grezzo, senza i modelli della libreria atproto: la versione
installata scarta un'intera pagina di risultati quando un post contiene un tipo di contenuto che
non conosce (per esempio le gallerie di immagini, app.bsky.embed.gallery).
Salva SOLO i metadati dei post trovati in private/v2/seeds.json; nessuna credenziale viene salvata.

Uso (dalla root del worktree):
    python crawl_v2/seed_search.py --handle TUO_HANDLE.bsky.social --password-file PERCORSO/my_password.txt
"""
import argparse
import json
import os
import time
from datetime import datetime, timezone

import requests

# Temi misti, due parole chiave per tema (piano approvato il 2026-10-01)
QUERIES = {
    "politics": ["trump", "election"],
    "sports": ["nfl", "football"],
    "technology": ["ai", "iphone"],
    "entertainment": ["movie", "music"],
}
# Finestra temporale dichiarata: due settimane, chiusa qualche giorno fa perche' i thread siano maturi
SINCE = "2026-09-14T00:00:00Z"
UNTIL = "2026-09-28T00:00:00Z"
CANDIDATES_PER_QUERY = 150   # riserva: il crawl ne usa una parte e aggiunge semi se servono nodi
MIN_REPLIES = 5              # thread senza conversazione non servono
PAGE_DELAY = 1.0


ENTRYWAY = "https://bsky.social/xrpc/"


def search_page(pds, headers, params, tries=5):
    """Una pagina di searchPosts come JSON grezzo; None dopo ripetuti errori."""
    for attempt in range(tries):
        try:
            r = requests.get(pds + "app.bsky.feed.searchPosts", params=params, headers=headers, timeout=30)
            if r.status_code == 200:
                return r.json()
            print(f"    HTTP {r.status_code}: {r.text[:200]}")
        except requests.RequestException as e:
            print(f"    errore di rete: {e}")
        time.sleep(2 ** attempt)
    return None


def extract_seed(p, topic, q, rank):
    """Metadati di un post trovato; None se e' una risposta o ha meno di MIN_REPLIES risposte."""
    rec = p.get("record", {})
    if rec.get("reply") is not None:          # solo post originali, non risposte
        return None
    if (p.get("replyCount") or 0) < MIN_REPLIES:
        return None
    return {
        "uri": p["uri"],
        "author_did": p["author"]["did"],
        "author_handle": p["author"]["handle"],
        "topic": topic,
        "query": q,
        "search_rank": rank,
        "reply_count": p.get("replyCount"),
        "like_count": p.get("likeCount"),
        "created_at": rec.get("createdAt"),
        "text": rec.get("text", ""),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--handle", required=True)
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--out", default="private/v2/seeds.json")
    args = ap.parse_args()

    with open(args.password_file) as f:
        password = f.read().strip()
    r = requests.post(ENTRYWAY + "com.atproto.server.createSession",
                      json={"identifier": args.handle, "password": password}, timeout=30)
    del password
    r.raise_for_status()
    session = r.json()
    pds = ENTRYWAY
    for svc in (session.get("didDoc") or {}).get("service", []):
        if svc.get("id") == "#atproto_pds":
            pds = svc["serviceEndpoint"].rstrip("/") + "/xrpc/"
    headers = {"Authorization": "Bearer " + session["accessJwt"],
               "atproto-proxy": "did:web:api.bsky.app#bsky_appview"}
    print(f"Login ok come {args.handle}")

    seeds, seen = [], set()
    for topic, queries in QUERIES.items():
        for q in queries:
            n_kept, cursor, pages, errors = 0, None, 0, 0
            while n_kept < CANDIDATES_PER_QUERY and pages < 30:
                params = {"q": q, "lang": "en", "sort": "top", "limit": 100,
                          "since": SINCE, "until": UNTIL}
                if cursor:
                    params["cursor"] = cursor
                res = search_page(pds, headers, params)
                if res is None:
                    errors += 1
                    print(f"  errore su '{q}' pagina {pages}")
                    break
                pages += 1
                for p in res.get("posts", []):
                    seed = extract_seed(p, topic, q, n_kept)
                    if seed is None or seed["uri"] in seen:
                        continue
                    seen.add(seed["uri"])
                    seeds.append(seed)
                    n_kept += 1
                    if n_kept >= CANDIDATES_PER_QUERY:
                        break
                cursor = res.get("cursor")
                if not cursor:
                    break
                time.sleep(PAGE_DELAY)
            print(f"[{topic:13s}] '{q}': {n_kept} semi ({pages} pagine)")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump({
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "since": SINCE, "until": UNTIL, "min_replies": MIN_REPLIES,
            "queries": QUERIES, "seeds": seeds,
        }, f, ensure_ascii=False, indent=1)
    print(f"Salvati {len(seeds)} semi in {args.out}")


if __name__ == "__main__":
    main()
