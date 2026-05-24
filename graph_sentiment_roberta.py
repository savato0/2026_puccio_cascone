import networkx as nx
import numpy as np
import ast
import torch
from scipy.special import softmax
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns

# --- CONFIGURAZIONE ---
INPUT_FILE = "dataset_snowball_aggregated.gexf"
OUTPUT_FILE = "dataset_roberta_final.gexf"
MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"

# Device: Apple Silicon GPU (MPS) se disponibile, altrimenti CPU
device = "mps" if torch.backends.mps.is_available() else "cpu"
print(f"Utilizzo del dispositivo: {device.upper()}")

# --- CARICAMENTO GRAFO ---
G = nx.read_gexf(INPUT_FILE)
print(f"Grafo caricato! Nodi: {G.number_of_nodes()}, Archi: {G.number_of_edges()}")

# --- CARICAMENTO MODELLO ---
print(f"Caricamento modello {MODEL_NAME}...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
model.to(device)
print("Modello caricato e pronto.")

# --- FUNZIONE DI ANALISI ---
def analyze_comments_list(comments_list):
    """
    Prende una lista di commenti, analizza ognuno con RoBERTa
    e restituisce il sentiment medio della relazione (-1 a 1).
    """
    if not comments_list:
        return 0.0

    scores_accumulated = []
    for text in comments_list:
        try:
            encoded_input = tokenizer(text, return_tensors='pt', truncation=True, max_length=512)
            encoded_input = {k: v.to(device) for k, v in encoded_input.items()}

            with torch.no_grad():
                output = model(**encoded_input)

            # Output: [Prob_Negativo, Prob_Neutro, Prob_Positivo]
            scores = softmax(output.logits.detach().cpu().numpy()[0])
            # Punteggio unico: Positivo - Negativo
            compound_score = scores[2] - scores[0]
            scores_accumulated.append(compound_score)
        except Exception:
            continue

    if not scores_accumulated:
        return 0.0
    return float(np.mean(scores_accumulated))

# --- ANALISI SENTIMENT SU TUTTI GLI ARCHI ---
print("Inizio analisi semantica con RoBERTa...")

edge_updates = {}
sentiment_values = []

for u, v, data in tqdm(G.edges(data=True), desc="Analisi Relazioni"):
    comments_str = data.get('comments_list', "[]")
    try:
        real_list = ast.literal_eval(comments_str)
    except Exception:
        real_list = []

    avg_sentiment = analyze_comments_list(real_list)
    edge_updates[(u, v)] = avg_sentiment
    sentiment_values.append(avg_sentiment)

nx.set_edge_attributes(G, edge_updates, 'sentiment_roberta')
print("Analisi completata.")

# --- VISUALIZZAZIONE DISTRIBUZIONE ---
plt.figure(figsize=(10, 6))
sns.histplot(sentiment_values, bins=30, kde=True, color='purple')
plt.title(f"Distribuzione del Sentiment (RoBERTa)\nMedia su {len(sentiment_values)} relazioni")
plt.xlabel("Sentiment Medio (-1: Ostile | 0: Neutro | +1: Supportivo)")
plt.ylabel("Numero di Relazioni")
plt.axvline(0, color='black', linestyle='--', alpha=0.5)
plt.savefig("sentiment_distribution.png", dpi=150, bbox_inches='tight')
plt.show()

print(f"Sentiment Medio Totale: {np.mean(sentiment_values):.4f}")
print(f"Relazioni Molto Negative (<-0.5): {sum(1 for x in sentiment_values if x < -0.5)}")
print(f"Relazioni Molto Positive (>0.5): {sum(1 for x in sentiment_values if x > 0.5)}")

# --- METRICHE DI RETE E SALVATAGGIO ---
print("Calcolo metriche di rete...")
nx.set_node_attributes(G, nx.degree_centrality(G), 'centrality_degree')
nx.set_node_attributes(G, nx.betweenness_centrality(G), 'centrality_betweenness')

nx.write_gexf(G, OUTPUT_FILE)
print(f"File salvato: {OUTPUT_FILE}")