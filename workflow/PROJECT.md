# PROJECT.md

## Identity
Project name: `doc2md`
Short description: Tiered PDF-to-Markdown converter with provenance, image handling, and benchmark support.

## Stack
Language: Python >= 3.11
Framework: Typer CLI, Pydantic v2 models
Styling: None
State management: Explicit `RunContext` and JSON disk cache
Data fetching: pdfplumber, optional Docling, optional Kelpie vision adapter
Testing: pytest, Ruff, mypy
Package manager: pip

## Commands
Install: `pip install -e ".[dev,hard,bench]"`
Build: `python -m build`
Type check: `mypy src`
Lint: `ruff check src tests`
Test: `pytest -q`
Convert: `doc2md convert INPUT --out OUTDIR`
Inspect: `doc2md inspect INPUT`

## File structure
Production code is under `src/doc2md/`. PDF extraction lives in
`src/doc2md/converters/pdf/`; pure rendering and models are kept separate from
the Docling and Kelpie adapters. Tests are under `tests/`, with generated
non-confidential PDFs under `tests/fixtures/synthetic/`.

## Conventions
Component style: Small pure functions at the core, thin I/O adapters at the edges.
File colocation: Tests remain under `tests/`, grouped by phase or subsystem.
Import paths: Package imports use `doc2md` or explicit relative imports inside the package.
API layer: `doc2md.api.convert()` and the Typer CLI are the public entry points.
Error handling: Isolate page and image failures, record warnings, and preserve strict mode semantics.
Env variables: Credentials and Kelpie settings come from environment variables; no secrets in files.

## Do not touch
- Confidential PDFs, reference Markdown, model responses, credentials, or token values.
- The read-only reference project outside this repository.
- PDF-specific branches, page-number checks, or copied reference output.

## Known constraints
- Docling artifacts must be locally provisioned for enterprise conversion.
- Tests must remain synthetic and offline by default.
- The fast path must preserve English and German characters and provenance.
