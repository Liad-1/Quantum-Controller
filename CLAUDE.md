# CLAUDE.md

## Conventions

- Shared configuration constants go in `src/globals.py`.
- Import with the `src.` prefix, for example `from src.microscope import MicroScope`.
- Group tests into `Test*` classes under `test/`.
- Create tests for each new function.
- Add type hints to every new function.
- Keep commits small and focused.
- Change one file at a time.
- Add logging along as you see fit