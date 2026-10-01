"""Passo 4 del nuovo crawl: profili degli utenti (API pubblica, nessun login).

Per ogni autore presente nei thread scarica follower, seguiti, numero di post e data di creazione
dell'account con getProfiles, a gruppi di 25. Il numero di follower e' una misura di importanza
esterna al campione, indipendente da come e' stato fatto il crawl.

Output: private/v2/profiles.csv
"""
import argparse
import csv
import json

from api import STATS, get


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", default="private/v2/posts_threads.jsonl")
    ap.add_argument("--out", default="private/v2/profiles.csv")
    args = ap.parse_args()

    dids = sorted({json.loads(l)["author_did"] for l in open(args.threads)})
    print(f"Profili da scaricare: {len(dids)}")
    fields = ["did", "handle", "followers", "follows", "posts", "account_created_at"]
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i in range(0, len(dids), 25):
            data = get("app.bsky.actor.getProfiles", actors=dids[i:i + 25])
            for p in (data or {}).get("profiles", []):
                w.writerow({"did": p["did"], "handle": p["handle"],
                            "followers": p.get("followersCount"), "follows": p.get("followsCount"),
                            "posts": p.get("postsCount"), "account_created_at": p.get("createdAt")})
            if (i // 25) % 40 == 0:
                print(f"  {i}/{len(dids)}  richieste {STATS['requests']}")
    print("Fatto.", STATS)


if __name__ == "__main__":
    main()
