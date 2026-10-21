# Configuration

Runtime paths and the UCI source schema mapping are centralized in `src/config.py` to keep the starter implementation small and importable. Environment-specific credentials are supplied via `DATABASE_URL` in the current PowerShell session, not in source control. `.env.example` is a template only; this repository intentionally does not load a committed `.env` file or persist private database secrets.
