# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Single-file Python CLI tool (`src/dropbox_to_gdrive.py`) that migrates files from Dropbox to Google Drive via their official APIs. No web server, database, or Docker involved.

### Python environment

- Python 3.12 with a virtualenv at `.venv`. Always activate with `source .venv/bin/activate` before running commands.
- `python3.12-venv` system package must be installed (not bundled by default on the VM image).

### Common dev commands

| Task | Command |
|---|---|
| Install deps | `source .venv/bin/activate && pip install -r requirements.txt` |
| Lint | `source .venv/bin/activate && ruff check src/` |
| Type check | `source .venv/bin/activate && mypy src/dropbox_to_gdrive.py --ignore-missing-imports` |
| Run CLI help | `source .venv/bin/activate && python -m src.dropbox_to_gdrive --help` |
| Run migration | `source .venv/bin/activate && python -m src.dropbox_to_gdrive <DROPBOX_TOKEN> <GOOGLE_CREDS_JSON> [--dropbox-path ...] [--drive-path ...]` |

### External credentials required for end-to-end run

The CLI requires a **Dropbox API token** and a **Google Service Account JSON key file** (with Drive API enabled). Without these, only `--help`, linting, type checking, and unit testing of internal logic are possible. See `README.md` for credential setup details.

### Gotchas

- There is no `src/__init__.py`; Python's implicit namespace packages allow `python -m src.dropbox_to_gdrive` to work from the repo root.
- The repo has no existing test suite. Dev tools (`ruff`, `pytest`, `mypy`) are installed into the venv but are not in `requirements.txt`.
