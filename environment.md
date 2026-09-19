# Conda Environment

Ambiente di riferimento: **`sna_env312`**, Python 3.12.6.
Eseguire i comandi dalla root del progetto.

## Creare l'ambiente

Da `environment.yml` (export completo, riproduce esattamente l'ambiente verificato):

```bash
conda env create -f environment.yml
conda activate sna_env312
```

In alternativa, con pip:

```bash
conda create -n sna_env312 python=3.12.6 -y
conda activate sna_env312
pip install -r requirements.txt
```

## Aggiornare un ambiente esistente

```bash
conda env update -n sna_env312 -f environment.yml --prune
conda activate sna_env312
```

## Usarlo nei notebook

```bash
python -m ipykernel install --user --name sna_env312 --display-name "sna_env312"
```

## Nota

`cdlib` deve essere almeno 0.4.1: la 0.4.0 non accetta `leiden(seed=...)`, che serve a
rendere riproducibile la partizione della Parte 3.
