# versione con profondita = 3 e aggregazione dei commenti in un unico arco (lista di commenti per ogni coppia di utenti)
# Supporto multi-query abilitato
import time
import networkx as nx
from atproto import Client
from tqdm import tqdm
from collections import defaultdict # Fondamentale per le liste di commenti

# --- CONFIGURAZIONE ---
USERNAME = 'atlasover.bsky.social'
with open('my_password.txt', 'r') as f:
    PASSWORD = f.read().strip()

# Query Iniziali (Supporta una lista di parole chiave)
SEARCH_QUERIES = ['venezuela', 'tennis']

# LIMITI
INITIAL_POSTS_LIMIT = 3   
USER_POSTS_LIMIT = 3      
DELAY = 1.5               
MIN_REPLIES = 5           
MIN_REPLY_CHARS = 5       
THREAD_DEPTH = 3          # <--- Nuova profondità richiesta (1 = solo dirette, 3 = conversazioni)

# --- LOGIN ---
client = Client()
client.login(USERNAME, PASSWORD)
print(f"✅ Loggato come {USERNAME}")

# --- STRUTTURA DATI GLOBALE PER AGGREGAZIONE ---
# Chiave: (source_handle, target_handle)
# Valore: [lista di testi dei commenti]
global_interactions = defaultdict(list)
# Per tenere traccia dei nodi e statistiche (followers/posts) se servisse in futuro
global_users_info = {}

# --- FUNZIONI DI SUPPORTO ---
def extract_text_content(post_record):
    full_text = []
    if hasattr(post_record, 'text') and post_record.text:
        full_text.append(post_record.text)
    return " ".join(full_text)

def process_replies_recursive(replies, parent_handle):
    """
    Funzione ricorsiva che scende nell'albero dei commenti.
    - replies: la lista delle risposte a un certo livello
    - parent_handle: l'autore del livello superiore (a cui queste risposte sono dirette)
    """
    if not replies:
        return

    for reply_view in replies:
        # Controllo che sia un post valido (non cancellato/bloccato)
        if not hasattr(reply_view, 'post'):
            continue
            
        post_data = reply_view.post
        source_handle = post_data.author.handle.replace('.bsky.social', '')
        
        # 1. NO SELF LOOPS (L'utente risponde a se stesso)
        if source_handle == parent_handle:
            if hasattr(reply_view, 'replies') and reply_view.replies:
                process_replies_recursive(reply_view.replies, source_handle)
            continue

        # 2. Estrazione Testo
        reply_text = ""
        if hasattr(post_data, 'record'):
            reply_text = extract_text_content(post_data.record)
        
        # Filtro lunghezza minima
        if len(reply_text.strip()) >= MIN_REPLY_CHARS:
            # 3. AGGREGAZIONE GLOBALE
            global_interactions[(source_handle, parent_handle)].append(reply_text)
            
            if source_handle not in global_users_info:
                global_users_info[source_handle] = {'type': 'commenter'}

        # 4. RICORSIONE (Scendiamo al livello successivo)
        if hasattr(reply_view, 'replies') and reply_view.replies:
            process_replies_recursive(reply_view.replies, source_handle)

def process_single_thread(post_uri):
    """Scarica un thread e avvia la ricorsione"""
    try:
        thread_data = client.get_post_thread(uri=post_uri, depth=THREAD_DEPTH)
    except Exception:
        return set()

    if not hasattr(thread_data.thread, 'post'): return set()
    
    original_post = thread_data.thread.post
    root_handle = original_post.author.handle.replace('.bsky.social', '')
    
    if not hasattr(thread_data.thread, 'replies') or not thread_data.thread.replies:
        return set()

    process_replies_recursive(thread_data.thread.replies, root_handle)
    return set()

# --- MAIN LOOP ---
if __name__ == "__main__":
    users_processed = set()
    
    # --- FASE 1: Ricerca per ogni parola chiave ---
    for query in SEARCH_QUERIES:
        print(f"🚀 FASE 1: Ricerca iniziale per '{query}' (Depth={THREAD_DEPTH})...")
        
        try:
            search_res = client.app.bsky.feed.search_posts(
                params={'q': query, 'limit': INITIAL_POSTS_LIMIT, 'sort': 'top', 'lang': 'en'}
            )
            
            print(f"   Trovati {len(search_res.posts)} post seme per '{query}'. Analisi thread...")

            for post in tqdm(search_res.posts):
                process_single_thread(post.uri)
                time.sleep(DELAY)
                
        except Exception as e:
            print(f"⚠️ Errore durante la ricerca di '{query}': {e}")
            continue

    # Calcoliamo chi espandere basandoci sulla mappa globale aggregata
    current_commenters = set([src for (src, tgt) in global_interactions.keys()])
    
    print(f"\n📊 Fine Fase 1. Interazioni uniche (Archi): {len(global_interactions)}")
    print(f"👥 Utenti attivi scoperti in totale: {len(current_commenters)}")
    
    # Filtriamo chi espandere
    users_to_expand = list(current_commenters)[:100] # Limite di sicurezza
    
    print(f"🚀 FASE 2: Espansione a Valanga su {len(users_to_expand)} utenti...")
    
    for user_handle in tqdm(users_to_expand):
        if user_handle in users_processed: continue
        
        try:
            full_handle = user_handle if '.' in user_handle else f"{user_handle}.bsky.social"
            user_search = client.app.bsky.feed.search_posts(
                params={'q': f'from:{full_handle}', 'limit': USER_POSTS_LIMIT, 'sort': 'top'}
            )
            
            if not user_search.posts: continue

            for user_post in user_search.posts:
                process_single_thread(user_post.uri)
                time.sleep(DELAY)
            
            users_processed.add(user_handle)
                
        except Exception:
            continue

    # --- COSTRUZIONE GRAFO E SALVATAGGIO ---
    print(f"\n✅ RACCOLTA COMPLETATA!")
    
    G = nx.DiGraph()
    count_edges = 0
    for (source, target), text_list in global_interactions.items():
        G.add_edge(source, target, 
                   comments_list=str(text_list), 
                   weight=len(text_list))
        count_edges += 1

    print(f"   Totale Archi (Relazioni uniche): {count_edges}")
    print(f"   Totale Nodi: {G.number_of_nodes()}")

    nx.write_gexf(G, "dataset_snowball_aggregated.gexf")
    print("💾 File 'dataset_snowball_aggregated.gexf' salvato.")