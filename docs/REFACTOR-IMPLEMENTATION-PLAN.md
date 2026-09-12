# Paperkit Full Refactor Implementation Plan

**Goal:** Reduce the application to focused modules with explicit dependencies while preserving the current CLI, registry format, cache format, and offline behavior.

**Architecture:** `cli -> services -> domain`, with HTTP, translation, registry, cache, and image files behind infrastructure objects. `fetch_papers.py` remains a three-line compatibility entry point only.

**Tech Stack:** Python standard library, `unittest`, GitHub Actions.

## Tasks

1. Extract pure domain code into `paperkit/domain/` and move HTML parsing/rendering there. Add direct domain tests with no global patching.
2. Extract `HttpClient`, arXiv API access, translation backends, registry/cache stores, and image localization into `paperkit/infra/`. Each object receives settings and paths explicitly.
3. Extract download and bilingual workflows into `paperkit/services/`. Services accept domain objects and infrastructure interfaces; no service reads module globals.
4. Move argument parsing and command dispatch into `paperkit/cli/`. The legacy script delegates only to `paperkit.cli.main`.
5. Convert existing tests to service/domain tests and retain a small compatibility suite for `fetch_papers`.
6. Add `test_layering.py`, `pyproject.toml`, and a CI workflow enforcing import direction and the test command.
7. Delete duplicate implementations from `core.py`, run the complete suite, CLI smoke tests, and `git diff --check`.
