# doltlite + SQLAlchemy: Getting Started

A getting-started demo of [doltlite](https://github.com/dolthub/doltlite)
with SQLAlchemy. doltlite is a fork of SQLite that adds Dolt's version
control: commits, branches, merges, diffs, and time-travel queries — all
through the SQLite file format and API.

This is a SQLite port of the
[dolt-sqlalchemy-getting-started](https://github.com/timsehn/dolt-sqlalchemy-getting-started)
demo
([blog](https://www.dolthub.com/blog/2023-07-12-sql-alchemy-getting-started/))
which targets the Dolt MySQL-compatible server. Because doltlite is a
drop-in SQLite replacement, this demo uses SQLAlchemy's standard
`sqlite` dialect — no custom driver required.

## What it shows

`demo.py` walks through, end to end:

1. Create three related tables (`employees`, `teams`, `employees_teams`)
   via SQLAlchemy's `MetaData.create_all`, then `dolt_commit` them.
2. Insert data, inspect `dolt_status` and `dolt_diff_employees`, commit.
3. Drop a table, then `dolt_reset --hard` to restore it.
4. Create a `modify_data` branch, change rows, commit.
5. Create a `modify_schema` branch from `main`, `ALTER TABLE … ADD COLUMN`,
   update via the SQLAlchemy ORM, commit.
6. Merge both feature branches back into `main`.

All version-control operations happen as plain SQL: `SELECT dolt_x(...)`
for procedures and `SELECT ... FROM dolt_log / dolt_status / dolt_branches
/ dolt_diff_<table>` for system tables, accessed through SQLAlchemy
reflection.

## Run it

```bash
pip install -r requirements.txt
python3 demo.py
```

That's it. The
[`doltlite`](https://github.com/dolthub/doltlite-python) package
bundles libdoltlite and handles loading it ahead of the system SQLite,
so SQLAlchemy's stock `sqlite` dialect transparently picks up Dolt
features.

You can set `DOLTLITE_DB` to control where the demo database is written
(default: `sqlalchemy_demo.db` in the current directory).

## Caveats

- The demo relies on Python's `sqlite3` module loading SQLite as a
  shared extension. Distro Python, Homebrew Python, pyenv-built Python,
  and Conda Python all work. **python-build-standalone** interpreters
  (the default for `uv python install`, `mise`, Rye) do **not** —
  their `_sqlite3` is statically built into the executable. If you use
  `uv`, point the venv at a supported Python explicitly:

  ```bash
  uv venv --python /opt/homebrew/bin/python3
  ```

- Importing `doltlite` re-execs the interpreter on macOS (and on Linux
  when `sqlite3` was already loaded) — so it has to be invoked from a
  script file, not `python -c "..."` or an interactive REPL. See the
  [doltlite-python README](https://github.com/dolthub/doltlite-python)
  for the workaround in those cases.

## Adaptations from the Dolt MySQL demo

| Dolt MySQL server                       | doltlite (SQLite)                                              |
| --------------------------------------- | -------------------------------------------------------------- |
| `mysql+mysqlconnector://...`            | `sqlite:///<path>`                                             |
| `CALL DOLT_COMMIT(...)`                 | `SELECT dolt_commit(...)`                                      |
| New engine per branch (`db/branch` URL) | One engine, `SELECT dolt_checkout('branch')` on the connection |
| `SHOW TABLES`                           | `SELECT name FROM sqlite_master WHERE …`                       |

To keep branch state coherent across the demo, the engine is built with
`StaticPool` so every SQLAlchemy `Session` / `Connection` reuses a
single underlying SQLite connection — doltlite stores the current branch
on the connection, not the file.

## License

Apache License 2.0. See [LICENSE](LICENSE).
