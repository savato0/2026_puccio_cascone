# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

Academic Social Network Analysis project (UNIPI). The pipeline collects discussion threads from Bluesky via the AT Protocol, builds a NetworkX graph of reply interactions, enriches edges with sentiment scores, and analyzes the resulting network. There is no application to "run" — work happens by executing scripts and notebooks in order.

## Environment

Two parallel ways to set up the same environment exist; pick one:

```bash
# Conda (authoritative; env name is sna_env, Python 3.13)
conda env create -f environment.yml
conda activate sna_env

# Or pip
pip install -r requirements.txt
```

There is no build, no lint, no test suite. Don't invent commands for these.

## Pipeline (must be run in order)

The scripts and notebooks form a strict producer/consumer chain via `.gexf` files. Each stage reads the previous stage's output:

1. **Collection** — `script1.py` (hashtag *or* author-feed mode, single-pass) or `script2.py` / `script2_v2.py` (snowball expansion from a seed query). `script2_v2.py` is the current version: supports multi-query (`SEARCH_QUERIES`), recursive thread traversal with `THREAD_DEPTH`, and aggregates multiple replies between the same pair into a single edge with a `comments_list` attribute and `weight` = count. Output: `dataset_*.gexf`.
2. **Sentiment enrichment** — `graph_sentiment_roberta.py` reads `dataset_snowball_aggregated.gexf`, runs `cardiffnlp/twitter-roberta-base-sentiment-latest` on every comment in each edge's `comments_list`, writes per-edge `sentiment_roberta` (mean of positive − negative probabilities, range −1..+1), and adds node centralities. Output: `dataset_roberta_final.gexf`. Uses Apple Silicon MPS if available.
3. **Analysis** — `network_analysis.ipynb` is the main analysis notebook (degree distribution, ER/BA baselines, etc.); `dataUnderstanding.ipynb` audits comment quality; `graph_visualization.ipynb` uses VADER + pyvis for interactive HTML output.

If you change the edge schema in stage 1, stage 2's `ast.literal_eval(data.get('comments_list', '[]'))` and the analysis notebooks will silently produce wrong results. Update consumers together.

## Important conventions

- **`.gexf` files live in `private/`** and are gitignored. Notebooks load from `private/dataset_*.gexf`; collection scripts write to the repo root. After running a collection script, move/copy the output into `private/` before running downstream stages, or update the path.
- **Bluesky credentials** are read from `my_password.txt` (gitignored, plain text, no trailing newline expected). The hardcoded `USERNAME` in each script is the project's account — don't change it casually. If the file is missing, every script crashes at import-time login.
- **Handles are normalized** by stripping `.bsky.social` in all collection scripts; re-append it when calling `search_posts(q='from:...')`. Stay consistent if you add new collection code.
- **`comments_list` is stored as a stringified Python list** (`str([...])`) because GEXF doesn't support list attributes — readers must `ast.literal_eval` it. Don't switch to JSON without updating every consumer.
- **Rate limiting**: all collection scripts sleep `DELAY` (1.5s) between thread fetches. Don't lower this without reason — the AT Protocol will start refusing.
- **`script_mio.py` and `script_v2_mio.py` are gitignored personal variants.** Don't treat them as canonical; `script1.py` / `script2_v2.py` are the shared versions.
- Code and comments are mixed Italian/English — match the surrounding style of the file you're editing.
