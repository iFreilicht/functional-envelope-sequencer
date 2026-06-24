# Functional Envelope Sequencer — Claude Code guidance

## What this project is

**Functional Envelope Sequencer (FES)** is a novel sequencer module for the [VCV Rack](https://vcvrack.com/) virtual modular synthesizer. Instead of sequencing a loop of triggers that fire an external envelope generator, FES directly computes a looping envelope from its parameters as a pure mathematical function of time.

The key idea is that all envelope peaks — which humans perceive as rhythmic events — are locked to rhythmic intervals independently of attack and decay times. This lets a performer freely sweep attack, decay, and shape in real time without disturbing the rhythmic grid.

With a traditional trigger-based approach, increasing attack time shifts the peak later, requiring micro-timing compensation that is cumbersome or impossible on simple sequencers. FES eliminates this problem entirely.

## Goal

Implement FES as a VCV Rack plugin (C++). The mathematical core is being validated in Python first to catch bugs before C++ implementation begins.

# Non-Goals

The code in this repository is not consumed by any other party; all code consuming its APIs is in this very repository. This means that changes to its APIs and the code structure can be made quite liberally, as long as their coherent and don't break tests. Additionally, you do not need to put any thought into backwards-compatibility or being compatible with lower Python versions than what's specified in .python-version.

## Guidelines

This codebase is intended to be **correct** and **explicit**.

Linter warnings are to be taken serioously! If a rule is disabled on a single line via a comment, another comment must be added to explain why disabling this rule is the correct thing to do in that case.

You can never disable a rule globally (i.e. in pyproject.toml) without the user's explicit approval! Even if such a change was approved by the user, make sure you include it in the summary of your changes.

## Current status

- ✅ Core math implemented in Python (`src/simulations/simulations/envelope.py`)
- ✅ Visual validation done in Jupyter notebook (`src/notebooks/`)
- ✅ Comprehensive test suite covering all invariants, edge cases, and integration (`src/tests/`)
- 🔲 Bug-Free implementation in Python
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

## Running all checks and formatting

This should be done after finishing a task to ensure all tests, type-checks and linting-rules pass and that all formatting-rules are applied.

```bash
direnv exec . uv run check
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
