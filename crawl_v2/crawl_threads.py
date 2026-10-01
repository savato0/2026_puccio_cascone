"""Passo 2 del nuovo crawl: thread interi dei post seme (API pubblica, nessun login).

Per ogni seme scarica l'albero completo con getPostThread e salva OGNI post (seme compreso) come
una riga di private/v2/posts_threads.jsonl. Il lavoro riprende da dove si era fermato: i semi gia'
presenti nel file vengono saltati.

Campi salvati per post: uri, autore (did, handle), testo, data, lingue, parent e root (uri e
autore), profondita' nel thread, conteggi di like/repost/reply, tema e query del seme, e il flag
'truncated' se l'API ha restituito meno risposte di quelle dichiarate.

Uso: python crawl_v2/crawl_threads.py [--seeds private/v2/seeds.json] [--per-query 40]
"""
import argparse
import json
import os
from collections import defaultdict

from api import STATS, get

DEPTH = 1000  # massimo consentito: thread interi


def walk(node, seed, depth, out, did_to_handle):
    """Visita ricorsiva dell'albero restituito da getPostThread."""
    if node.get("$type") != "app.bsky.feed.defs#threadViewPost":
        return 0  # post cancellato o bloccato
    p = node["post"]
    rec = p.get("record", {})
    did_to_handle[p["author"]["did"]] = p["author"]["handle"]
    replies = node.get("replies") or []
    reply = rec.get("reply")
    row = {
        "uri": p["uri"],
        "author_did": p["author"]["did"],
        "author_handle": p["author"]["handle"],
        "text": rec.get("text", ""),
        "created_at": rec.get("createdAt"),
        "langs": rec.get("langs"),
        "parent_uri": reply["parent"]["uri"] if reply else None,
        "parent_author_did": reply["parent"]["uri"].split("/")[2] if reply else None,
        "root_uri": reply["root"]["uri"] if reply else p["uri"],
        "root_author_did": reply["root"]["uri"].split("/")[2] if reply else p["author"]["did"],
        "depth": depth,
        "like_count": p.get("likeCount", 0),
        "repost_count": p.get("repostCount", 0),
        "reply_count": p.get("replyCount", 0),
        "truncated": (p.get("replyCount", 0) or 0) > len(replies),
        "is_seed": depth == 0,
        "seed_uri": seed["uri"],
        "topic": seed["topic"],
        "query": seed["query"],
    }
    out.append(row)
    n = 1
    for child in replies:
        n += walk(child, seed, depth + 1, out, did_to_handle)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="private/v2/seeds.json")
    ap.add_argument("--out", default="private/v2/posts_threads.jsonl")
    ap.add_argument("--per-query", type=int, default=40,
                    help="numero di semi per query, presi in ordine di rilevanza")
    args = ap.parse_args()

    seeds = json.load(open(args.seeds))["seeds"]
    by_query = defaultdict(list)
    for s in seeds:
        by_query[s["query"]].append(s)
    chosen = [s for q in by_query for s in sorted(by_query[q], key=lambda s: s["search_rank"])[:args.per_query]]

    done = set()
    if os.path.exists(args.out):
        with open(args.out) as f:
            for line in f:
                done.add(json.loads(line)["seed_uri"])
    todo = [s for s in chosen if s["uri"] not in done]
    print(f"Semi scelti: {len(chosen)} ({args.per_query} per query); gia' fatti: {len(done)}; da fare: {len(todo)}")

    did_to_handle = {}
    total = 0
    with open(args.out, "a") as f:
        for i, seed in enumerate(todo, 1):
            data = get("app.bsky.feed.getPostThread", uri=seed["uri"], depth=DEPTH, parentHeight=0)
            if not data:
                continue
            rows = []
            walk(data["thread"], seed, 0, rows, did_to_handle)
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            total += len(rows)
            if i % 20 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} thread, {total} post, richieste {STATS['requests']}, errori {STATS['errors']}")
    print("Fatto.", STATS)


if __name__ == "__main__":
    main()
