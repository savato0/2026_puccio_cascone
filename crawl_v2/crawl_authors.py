"""Passo 3 del nuovo crawl: cronologia recente degli utenti (API pubblica, nessun login).

Per ogni utente che ha ricevuto almeno una risposta nei thread, e per un campione casuale degli
altri, scarica con getAuthorFeed i post e le risposte scritti di recente, fino a MAX_REPLIES
risposte. Questi testi servono SOLO a stimare il sentiment scritto di ogni utente: non entrano
nella rete, cosi' la centralita' non dipende da come si stima il sentiment.

Output: private/v2/posts_authors.jsonl (una riga per post) e private/v2/authors_done.txt
(utente, stato, risposte trovate: per riprendere dopo un'interruzione).

Uso: python crawl_v2/crawl_authors.py [--sample-others 1000]
"""
import argparse
import json
import os
import random

from api import STATS, get

MAX_REPLIES = 50
MAX_PAGES = 5


def users_to_fetch(threads_file, sample_others, seed=42):
    in_from = {}
    everyone = set()
    with open(threads_file) as f:
        for line in f:
            r = json.loads(line)
            everyone.add(r["author_did"])
            t = r["parent_author_did"]
            if t and t != r["author_did"]:
                in_from.setdefault(t, set()).add(r["author_did"])
    central = sorted(in_from)
    others = sorted(everyone - set(central))
    random.Random(seed).shuffle(others)
    return central, others[:sample_others]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", default="private/v2/posts_threads.jsonl")
    ap.add_argument("--out", default="private/v2/posts_authors.jsonl")
    ap.add_argument("--done", default="private/v2/authors_done.txt")
    ap.add_argument("--sample-others", type=int, default=1000)
    args = ap.parse_args()

    central, others = users_to_fetch(args.threads, args.sample_others)
    group = {d: "in_degree>=1" for d in central} | {d: "random_other" for d in others}
    done = {l.split("\t")[0] for l in open(args.done) if l.strip()} if os.path.exists(args.done) else set()
    todo = [d for d in central + others if d not in done]
    print(f"Utenti con almeno una risposta ricevuta: {len(central)}; campione degli altri: {len(others)}; "
          f"gia' fatti: {len(done)}; da fare: {len(todo)}")

    with open(args.out, "a") as f, open(args.done, "a") as fd:
        for i, did in enumerate(todo, 1):
            cursor, n_replies, pages, status = None, 0, 0, "ok"
            while n_replies < MAX_REPLIES and pages < MAX_PAGES:
                params = {"actor": did, "filter": "posts_with_replies", "limit": 100}
                if cursor:
                    params["cursor"] = cursor
                data = get("app.bsky.feed.getAuthorFeed", **params)
                pages += 1
                if data is None:
                    status = "unavailable"   # account cancellato, sospeso o privato
                    break
                for item in data.get("feed", []):
                    p = item["post"]
                    if p["author"]["did"] != did or item.get("reason"):
                        continue  # repost di altri
                    rec = p.get("record", {})
                    reply = rec.get("reply")
                    f.write(json.dumps({
                        "author_did": did,
                        "group": group[did],
                        "uri": p["uri"],
                        "text": rec.get("text", ""),
                        "created_at": rec.get("createdAt"),
                        "langs": rec.get("langs"),
                        "is_reply": reply is not None,
                        "parent_author_did": reply["parent"]["uri"].split("/")[2] if reply else None,
                        "like_count": p.get("likeCount", 0),
                        "reply_count": p.get("replyCount", 0),
                    }, ensure_ascii=False) + "\n")
                    n_replies += reply is not None
                cursor = data.get("cursor")
                if not cursor:
                    break
            fd.write(f"{did}\t{status}\t{n_replies}\n")
            f.flush(); fd.flush()
            if i % 100 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} utenti, richieste {STATS['requests']}, errori {STATS['errors']}")
    print("Fatto.", STATS)


if __name__ == "__main__":
    main()
