"""Passo 5 del nuovo crawl: dalla tabella dei post alla rete.

Stesse regole della raccolta originale (script_v3.py): un nodo per utente, un arco diretto
u -> v per ogni risposta di u a un post di v, risposte a se stessi escluse, risposte sotto i 5
caratteri escluse, handle senza il suffisso '.bsky.social'. Il grafo ha gli stessi attributi del
vecchio dataset (comments_list, weight), cosi' i notebook delle Parti 1-3 lo leggono senza modifiche.

In piu' rispetto alla raccolta originale:
- una tabella con una riga per commento (private/v2/comments.csv), dato primario della Parte 4;
- attributi dei nodi: did, ondata (0 = autore di un post seme), tema prevalente, follower.

Output: private/v2/comments.csv, private/v2/dataset_snowball_aggregated.gexf
"""
import argparse
import json
from collections import Counter, defaultdict

import networkx as nx
import pandas as pd

MIN_REPLY_CHARS = 5


def short(handle):
    return handle.replace(".bsky.social", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", default="private/v2/posts_threads.jsonl")
    ap.add_argument("--profiles", default="private/v2/profiles.csv")
    ap.add_argument("--comments-out", default="private/v2/comments.csv")
    ap.add_argument("--gexf-out", default="private/v2/dataset_snowball_aggregated.gexf")
    args = ap.parse_args()

    posts = pd.read_json(args.threads, lines=True).drop_duplicates("uri")
    did2handle = dict(zip(posts.author_did, posts.author_handle))
    print(f"Post: {len(posts):,} (semi {posts.is_seed.sum()}, thread troncati {posts[posts.is_seed].truncated.sum()} "
          f"radici / {posts.truncated.sum()} nodi con risposte mancanti)")

    r = posts[~posts.is_seed & posts.parent_author_did.notna()].copy()
    n0 = len(r)
    r = r[r.parent_author_did.isin(did2handle)]                      # parent visibile nel thread
    n_parent = len(r)
    r = r[r.author_did != r.parent_author_did]                       # niente risposte a se stessi
    n_self = len(r)
    r = r[r.text.fillna("").str.strip().str.len() >= MIN_REPLY_CHARS]
    print(f"Risposte: {n0:,}; con parent visibile {n_parent:,}; senza autorisposte {n_self:,}; "
          f">= {MIN_REPLY_CHARS} caratteri {len(r):,}")

    r["source"] = r.author_did.map(did2handle).map(short)
    r["target"] = r.parent_author_did.map(did2handle).map(short)
    comments = r[["uri", "source", "target", "author_did", "parent_author_did", "text", "created_at",
                  "langs", "depth", "like_count", "topic", "query", "seed_uri"]]
    comments.to_csv(args.comments_out, index=False)

    G = nx.DiGraph()
    for (u, v), g in comments.groupby(["source", "target"]):
        G.add_edge(u, v, comments_list=str(g.text.tolist()), weight=len(g))

    # attributi dei nodi
    handle2did = {short(h): d for d, h in did2handle.items()}
    seed_authors = set(posts[posts.is_seed].author_did)
    topic_of = defaultdict(Counter)
    for d, t in zip(posts.author_did, posts.topic):
        topic_of[d][t] += 1
    try:
        prof = pd.read_csv(args.profiles).set_index("did")
    except FileNotFoundError:
        prof = pd.DataFrame(columns=["followers", "follows", "posts"])
    for n in G.nodes():
        d = handle2did[n]
        G.nodes[n]["did"] = d
        G.nodes[n]["wave"] = 0 if d in seed_authors else 1
        G.nodes[n]["topic"] = topic_of[d].most_common(1)[0][0]
        if d in prof.index and pd.notna(prof.loc[d, "followers"]):
            G.nodes[n]["followers"] = int(prof.loc[d, "followers"])
            G.nodes[n]["follows"] = int(prof.loc[d, "follows"])

    nx.write_gexf(G, args.gexf_out)
    und = G.to_undirected()
    gcc = max(nx.connected_components(und), key=len)
    print(f"Rete: {G.number_of_nodes():,} nodi, {G.number_of_edges():,} archi diretti, "
          f"{und.number_of_edges():,} non orientati; GCC {len(gcc):,} nodi")
    print("Nodi per tema:", dict(Counter(nx.get_node_attributes(G, 'topic').values())))
    print(f"Salvati {args.comments_out} e {args.gexf_out}")


if __name__ == "__main__":
    main()
