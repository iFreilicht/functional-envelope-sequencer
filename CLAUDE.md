# Functional Envelope Sequencer — Claude Code guidance

## What this project is

**Functional Envelope Sequencer (FES)** is a novel sequencer module for the [VCV Rack](https://vcvrack.com/) virtual modular synthesizer. Instead of sequencing a loop of triggers that fire an external envelope generator, FES directly computes a looping envelope from its parameters as a pure mathematical function of time.

The key idea is that all envelope peaks — which humans perceive as rhythmic events — are locked to rhythmic intervals independently of attack and decay times. This lets a performer freely sweep attack, decay, and shape in real time without disturbing the rhythmic grid.

With a traditional trigger-based approach, increasing attack time shifts the peak later, requiring micro-timing compensation that is cumbersome or impossible on simple sequencers. FES eliminates this problem entirely.

## Goal

Implement FES as a VCV Rack plugin (C++). The mathematical core is being validated in Python first to catch bugs before C++ implementation begins.

## Current status

- ✅ Core math implemented in Python (`src/simulations/simulations/envelope.py`)
- ✅ Visual validation done in Jupyter notebook (`src/notebooks/`)
- ✅ Comprehensive test suite covering all invariants, edge cases, and integration (`src/tests/`)
- 🔲 C++ implementation of the VCV Rack module (not started)

---

## Development environment

This project uses **Nix** for reproducible tooling (including `uv`, Python, the VCV Rack SDK, etc.).
All tools are available inside the Nix dev shell.

```bash
# Option 1: load the dev shell manually
nix develop

# Option 2: if direnv is installed, it loads the shell automatically
direnv allow   # one-time setup; after that it loads on cd

# Inside the dev shell run tools normally, e.g.
uv run pytest -v
```

To run any tool from *outside* the shell (e.g. from a Claude Code session):

```bash
direnv exec . <command>
# e.g.
direnv exec . uv run pytest -v
```

## Running the test suite

```bash
direnv exec . uv run pytest -v
```

The suite uses `pytest-randomly` for reproducible fuzzing. To replay a
specific seed shown in a failed run:

```bash
direnv exec . uv run pytest --randomly-seed=<seed>
```

To run in parallel (faster on large suites):

```bash
direnv exec . uv run pytest -n auto
```

## Project layout

| Path | Purpose |
|------|---------|
| `src/simulations/simulations/envelope.py` | Core mathematical implementation |
| `src/notebooks/` | Interactive Jupyter notebooks for visual validation |
| `src/tests/simulations/` | pytest suite (unit + integration) |
| `src/scripts/` | CLI entry points |
| `flake.nix` | Nix dev shell definition |
| `pyproject.toml` | Python project config, workspace members, pytest config |
