# Conda Environment

Run these commands from the project root.

## Create the environment

```bash
conda env create -f environment.yml
conda activate sna_env
```

## Update an existing environment

```bash
conda env update -n sna_env -f environment.yml --prune
conda activate sna_env
```

## Use it in notebooks

```bash
python -m ipykernel install --user --name sna_env --display-name "Python (sna_env)"
```
