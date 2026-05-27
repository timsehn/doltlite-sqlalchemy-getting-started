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
drop-in SQLite replacement, the example uses SQLAlchemy's standard
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

## Setup

### 1. Build (or install) doltlite

You need a `libdoltlite.dylib` (macOS) or `libdoltlite.so` (Linux). See
the [doltlite README](https://github.com/dolthub/doltlite#readme) for
build instructions. The shared library lands at the repository root
after `make`.

### 2. Install Python deps

```bash
pip install -r requirements.txt
```

### 3. Use a compatible Python interpreter

The demo relies on the standard `sqlite3` module loading SQLite as a
**shared extension**. The following work:

- Distro / system Python (Linux)
- Homebrew Python (macOS / Linux)
- pyenv-built Python
- Conda Python

The following do **not** work because their `_sqlite3` is statically
linked into the interpreter:

- python-build-standalone interpreters (this is the default for `uv
  python install`, `mise`, and Rye)

If you use `uv`, point the environment at one of the supported Pythons
explicitly:

```bash
uv venv --python /opt/homebrew/bin/python3   # or /usr/bin/python3, etc.
```

### 4. Run

```bash
DOLTLITE_LIB=/abs/path/to/libdoltlite.dylib python3 demo.py   # macOS
DOLTLITE_LIB=/abs/path/to/libdoltlite.so    python3 demo.py   # Linux
```

The first invocation re-execs the interpreter with the right loader
environment, so you should not need to set `DYLD_INSERT_LIBRARIES` or
`LD_PRELOAD` yourself.

You can also set `DOLTLITE_DB` to control where the demo database file
is written (default: `sqlalchemy_demo.db` in the current directory).

## How the preload works

doltlite implements the SQLite C API — its `sqlite3_*` symbols replace
the stock SQLite's. Python's `sqlite3` module dispatches through those
symbols at runtime, so any Python program that uses `sqlite3` (including
SQLAlchemy) automatically sees Dolt features (`dolt_commit`,
`dolt_branch`, `dolt_log`, etc.) once libdoltlite is loaded ahead of the
system libsqlite3.

### Linux

`LD_PRELOAD=libdoltlite.so` ahead of `python3` puts libdoltlite first in
the symbol resolution order. The demo's bootstrap sets this for you and
re-execs.

### macOS

macOS uses a two-level namespace: `_sqlite3.so` is linked to a specific
`libsqlite3.dylib` path (e.g.,
`/opt/homebrew/opt/sqlite/lib/libsqlite3.dylib`), so plain
`DYLD_INSERT_LIBRARIES` or `ctypes.CDLL` won't redirect symbol lookups.

The demo handles this by:

1. Detecting the libsqlite3 path that the active Python's `_sqlite3` is
   linked against (via `otool -L`).
2. Copying `libdoltlite.dylib` to a temp file named `libsqlite3.dylib`.
3. Rewriting its `install_name` (`LC_ID_DYLIB`) to that detected path
   with `install_name_tool -id`.
4. Re-execing with `DYLD_INSERT_LIBRARIES` pointing at the shim, which
   the two-level namespace then accepts as a substitute.

The shim is cached under `$TMPDIR` per (lib path, mtime, install_name)
so subsequent runs reuse it.

## Adaptations from the Dolt MySQL demo

| Dolt MySQL server                      | doltlite (SQLite)                              |
| -------------------------------------- | ---------------------------------------------- |
| `mysql+mysqlconnector://...`           | `sqlite:///<path>`                             |
| `CALL DOLT_COMMIT(...)`                | `SELECT dolt_commit(...)`                      |
| New engine per branch (`db/branch` URL) | One engine, `SELECT dolt_checkout('branch')` on the connection |
| `SHOW TABLES`                          | `SELECT name FROM sqlite_master WHERE …`       |

To keep branch state coherent across the demo, the engine is built with
`StaticPool` so every SQLAlchemy `Session` / `Connection` reuses a
single underlying SQLite connection — doltlite stores the current branch
on the connection, not the file.

## License

Apache License 2.0. See [LICENSE](LICENSE).
