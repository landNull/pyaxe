# pyaxe

Python Swiss army knife for Python code. Syntax, pattern, style, dependency, and safety checks with safe local healing. Auto-scans the tree. Emits JSON for LLMs and a one-line spoken summary for voice assistants.

Pyaxe is the Python counterpart to posaxe. It deliberately mirrors posaxe’s CLI, modes, output formats, and philosophy so the two tools remain interchangeable for wrappers, skills, and LLM pipelines.

## Relationship to posaxe

posaxe is a pure POSIX shell tool for shell scripts:

- Auto-scan for shell scripts
- Syntax / pattern / dialect / dependency checks
- Safe local healing
- Optional external tools (shellcheck, shfmt, shellharden, shellspec)
- Human, `--json`, and `--speak` output
- `intent` mode for voice mapping

pyaxe does the same things for Python, written in Python so it can use native AST analysis and the modern Python tooling ecosystem (especially ruff).

## Design principles

- Same CLI surface as posaxe wherever possible
- Same JSON schema and SPEAK: line format
- Prefer ruff as the primary optional tool (fast, all-in-one lint + format + fix)
- Fall back gracefully when tools are missing
- Safe healing only by default
- Portable enough to drop into scripts, CI, or voice skills
- No forced coupling with posaxe — each tool stays in its natural language

## Usage

```sh
pyaxe                   # auto-scan . and check every Python file
pyaxe scan              # list Python files
pyaxe check [FILE...]   # check files, or auto-scan if none
pyaxe heal [FILE...]    # safe fixes, then check
pyaxe --json check      # one JSON object per finding
pyaxe --speak check     # SPEAK: summary line
pyaxe intent "phrase"   # map speech to a mode
```

## Output

Human mode prints labeled blocks (same structure as posaxe):

```
ERROR
LAYER: lint
FILE: lib/foo.py
WHAT: ...
WHY: ...
FIX: ...
```

`--json` emits (same schema as posaxe):

```json
{"kind":"error","file":"...","what":"...","why":"...","fix":"..."}
{"kind":"summary","failed":0,"passed_hint":"ok"}
```

`--speak` produces a single line starting with `SPEAK:` for voice assistants.

## Optional tools

Preferred: ruff (lint + format + fix in one fast tool).

Others when present on PATH: black, isort, mypy, pyflakes, bandit, etc.

Detect presence and use what is available; degrade gracefully.

## Layers / checks (suggested)

- Syntax (Python parser / AST)
- Style and patterns (ruff or equivalent)
- Imports and dependencies
- Common safety / best-practice issues
- Safe automatic fixes via heal mode

## Installation

```bash
pip install -e .
# or
pipx install .
```

## Voice

A minimal OVOS skill stub can be created by adapting the posaxe skill (replace the binary name and spoken prompts). Intents: check, heal, scan. Forward JSON lines on the bus and speak the SPEAK: line.

## Goal

A lightweight, consistent Swiss army knife for Python that feels like posaxe, speaks the same language to LLMs and voice systems, and is built in the language that best fits the job.
