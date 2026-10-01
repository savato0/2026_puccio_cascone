"""Passo 1 del nuovo crawl: ricerca dei post seme per parola chiave.

E' l'unico passo che richiede il login (searchPosts non e' disponibile sull'API pubblica).
Salva SOLO i metadati dei post trovati in private/v2/seeds.json; nessuna credenziale viene salvata.

Uso (dalla root del worktree):
    python crawl_v2/seed_search.py --handle TUO_HANDLE.bsky.social --password-file PERCORSO/my_password.txt
"""
import argparse
import json
import os
import time
from datetime import datetime, timezone

from atproto import Client

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--handle", required=True)
    ap.add_argument("--password-file", required=True)
    ap.add_argument("--out", default="private/v2/seeds.json")
    args = ap.parse_args()

    with open(args.password_file) as f:
        password = f.read().strip()
    client = Client()
    client.login(args.handle, password)
    del password
    print(f"Login ok come {args.handle}")

    seeds, seen = [], set()
    for topic, queries in QUERIES.items():
        for q in queries:
            n_kept, cursor, pages = 0, None, 0
            while n_kept < CANDIDATES_PER_QUERY and pages < 30:
                params = {"q": q, "lang": "en", "sort": "top", "limit": 100,
                          "since": SINCE, "until": UNTIL}
                if cursor:
                    params["cursor"] = cursor
                try:
                    res = client.app.bsky.feed.search_posts(params=params)
                except Exception as e:
                    print(f"  errore su '{q}' pagina {pages}: {e}")
                    break
                pages += 1
                for rank, p in enumerate(res.posts):
                    rec = p.record
                    if getattr(rec, "reply", None) is not None:   # solo post originali, non risposte
                        continue
                    if (p.reply_count or 0) < MIN_REPLIES or p.uri in seen:
                        continue
                    seen.add(p.uri)
                    seeds.append({
                        "uri": p.uri,
                        "author_did": p.author.did,
                        "author_handle": p.author.handle,
                        "topic": topic,
                        "query": q,
                        "search_rank": n_kept,
                        "reply_count": p.reply_count,
                        "like_count": p.like_count,
                        "created_at": getattr(rec, "created_at", None),
                        "text": getattr(rec, "text", ""),
                    })
                    n_kept += 1
                    if n_kept >= CANDIDATES_PER_QUERY:
                        break
                cursor = res.cursor
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
