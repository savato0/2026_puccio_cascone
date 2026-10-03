"""Passo 6 del nuovo crawl: sentiment ed emozioni per commento.

Stesso modello della raccolta originale (cardiffnlp/twitter-roberta-base-sentiment-latest,
s = p_pos - p_neg) piu' il modello di emozioni. Il config.json del modello di emozioni sul hub ha
le etichette in ordine sbagliato: qui l'ordine e' corretto e verificato su frasi di controllo.

Input : private/v2/comments.csv, private/v2/posts_authors.jsonl, private/v2/dataset_snowball_aggregated.gexf
Output: private/v2/comments_scored.csv      (commenti della rete)
        private/v2/authors_scored.csv       (risposte in inglese dalla cronologia degli utenti)
        private/v2/dataset_roberta_final.gexf (rete con sentiment_roberta = media per arco)
"""
import argparse
import os

import networkx as nx
import numpy as np
import pandas as pd
import torch
from scipy.special import softmax
from transformers import AutoModelForSequenceClassification, AutoTokenizer

SENTIMENT_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"
EMOTION_MODEL = "cardiffnlp/twitter-roberta-base-emotion"
EMOTION_LABELS = ["anger", "joy", "optimism", "sadness"]   # ordine vero (il config.json e' sbagliato)
BATCH = 64
device = "mps" if torch.backends.mps.is_available() else "cpu"


def load(name):
    tok = AutoTokenizer.from_pretrained(name)
    return tok, AutoModelForSequenceClassification.from_pretrained(name).to(device).eval()


def predict(tok, model, texts):
    out = []
    with torch.no_grad():
        for i in range(0, len(texts), BATCH):
            enc = tok(texts[i:i + BATCH], return_tensors="pt", truncation=True, max_length=512, padding=True)
            enc = {k: v.to(device) for k, v in enc.items()}
            out.append(softmax(model(**enc).logits.float().cpu().numpy(), axis=1))
    return np.vstack(out) if out else np.empty((0, 3))


def score(df, sent, emo):
    texts = df.text.fillna("").astype(str).tolist()
    P = predict(*sent, texts)
    df["p_neg"], df["p_neu"], df["p_pos"] = P[:, 0], P[:, 1], P[:, 2]
    df["s"] = df.p_pos - df.p_neg
    df["label"] = np.array(["neg", "neu", "pos"])[P.argmax(1)]
    P = predict(*emo, texts)
    for k, lab in enumerate(EMOTION_LABELS):
        df[f"p_{lab}"] = P[:, k]
    df["emotion"] = np.array(EMOTION_LABELS)[P.argmax(1)]
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="private/v2")
    D = ap.parse_args().dir
    sent, emo = load(SENTIMENT_MODEL), load(EMOTION_MODEL)
    controls = ["I hate you, you are a disgusting idiot and I am furious.", "I am so happy today, what a wonderful day!",
                "Things will get better, keep going, we can do it!", "I feel hopeless and sad, everything is lost."]
    got = [EMOTION_LABELS[i] for i in predict(*emo, controls).argmax(1)]
    assert got == EMOTION_LABELS, f"Mappatura delle emozioni errata: {got}"
    print("Controllo etichette emozioni: OK")

    C = score(pd.read_csv(f"{D}/comments.csv"), sent, emo)
    C.to_csv(f"{D}/comments_scored.csv", index=False)
    print(f"Commenti della rete: {len(C):,}")

    if os.path.exists(f"{D}/posts_authors.jsonl"):
        A = pd.read_json(f"{D}/posts_authors.jsonl", lines=True).drop_duplicates("uri")
        A = A[A.text.fillna("").str.strip().str.len() >= 5]
        # Alla Parte 4 servono solo le risposte in inglese: le altre non vengono valutate
        en = A.langs.isna() | A.langs.astype(str).str.contains("'en'")
        A = A[A.is_reply & en]
        A = score(A, sent, emo)
        A.to_csv(f"{D}/authors_scored.csv", index=False)
        print(f"Post dalle cronologie: {len(A):,}")

    G = nx.read_gexf(f"{D}/dataset_snowball_aggregated.gexf")
    edge_mean = C.groupby(["source", "target"]).s.mean()
    nx.set_edge_attributes(G, {k: float(v) for k, v in edge_mean.items()}, "sentiment_roberta")
    nx.write_gexf(G, f"{D}/dataset_roberta_final.gexf")
    print(f"Salvato {D}/dataset_roberta_final.gexf")


if __name__ == "__main__":
    main()
