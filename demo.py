#!/usr/bin/env python3
"""
doltlite + SQLAlchemy Getting Started

Demonstrates Dolt version control features (commits, branches, merges,
diffs, schema changes) through SQLAlchemy against a doltlite database.

Adapted from https://github.com/timsehn/dolt-sqlalchemy-getting-started
which targets the Dolt MySQL-compatible server. doltlite is a drop-in
SQLite replacement, so we use SQLAlchemy's standard `sqlite` dialect and
call dolt_* operations as SQL functions / virtual tables.

Usage:
    pip install -r requirements.txt
    python3 demo.py
"""
import doltlite  # bootstraps libdoltlite into the active sqlite3 module
import datetime
import os
from pprint import pprint

from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
)
from sqlalchemy.pool import StaticPool


DB_PATH = os.environ.get("DOLTLITE_DB", "sqlalchemy_demo.db")


def _build_engine():
    """One engine, one connection (StaticPool).

    Dolt's MySQL server exposes each branch as a separate database, so the
    blog version creates a fresh engine per branch. With doltlite the branch
    state lives on the SQLite connection — so we share a single connection
    across the whole demo and switch branches by calling dolt_checkout().
    """
    return create_engine(
        f"sqlite:///{DB_PATH}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


_engine = _build_engine()


def main():
    _start_fresh()

    engine = dolt_checkout("main")
    print_active_branch(engine)

    setup_database(engine)
    print_tables(engine)

    dolt_commit(engine, "Tim <tim@dolthub.com>", "Created tables")
    print_commit_log(engine)

    insert_data(engine)
    print_summary_table(engine)

    print_status(engine)
    print_diff(engine, "employees")

    dolt_commit(engine,
                "Aaron <aaron@dolthub.com>",
                "Inserted data into tables")
    print_commit_log(engine)

    # Show off dolt_reset --hard
    drop_table(engine, "employees_teams")
    print_status(engine)
    print_tables(engine)
    dolt_reset_hard(engine, None)
    print_status(engine)
    print_tables(engine)

    # Branch + modify data
    dolt_create_branch(engine, "modify_data")
    engine = dolt_checkout("modify_data")
    modify_data(engine)
    print_status(engine)
    print_diff(engine, "employees")
    print_diff(engine, "employees_teams")
    print_summary_table(engine)
    dolt_commit(engine,
                "Brian <brian@dolthub.com>",
                "Modified data on branch")
    print_commit_log(engine)

    # Back to main for a fresh branch with a schema change
    engine = dolt_checkout("main")
    dolt_create_branch(engine, "modify_schema")
    engine = dolt_checkout("modify_schema")
    print_active_branch(engine)
    modify_schema(engine)
    print_status(engine)
    print_diff(engine, "employees")
    print_summary_table(engine)
    dolt_commit(engine,
                "Tim <tim@dolthub.com>",
                "Modified schema on branch")
    print_commit_log(engine)

    # Merge both feature branches into main
    engine = dolt_checkout("main")
    print_active_branch(engine)
    print_commit_log(engine)
    print_summary_table(engine)
    dolt_merge(engine, "modify_data")
    print_summary_table(engine)
    print_commit_log(engine)
    dolt_merge(engine, "modify_schema")
    print_commit_log(engine)
    print_summary_table(engine)


def _start_fresh():
    """Remove any prior demo DB so the script is re-runnable."""
    for suffix in ("", "-wal", "-shm", "-journal"):
        p = DB_PATH + suffix
        if os.path.exists(p):
            os.remove(p)


def setup_database(engine):
    metadata_obj = MetaData()

    Table(
        "employees",
        metadata_obj,
        Column("id", Integer, primary_key=True, autoincrement=False),
        Column("last_name", String(255)),
        Column("first_name", String(255)),
    )
    Table(
        "teams",
        metadata_obj,
        Column("id", Integer, primary_key=True, autoincrement=False),
        Column("name", String(255)),
    )
    Table(
        "employees_teams",
        metadata_obj,
        Column("employee_id", ForeignKey("employees.id"),
               primary_key=True, autoincrement=False),
        Column("team_id", ForeignKey("teams.id"),
               primary_key=True, autoincrement=False),
    )

    metadata_obj.create_all(engine)


def load_tables(engine):
    metadata_obj = MetaData()
    employees = Table("employees", metadata_obj, autoload_with=engine)
    teams = Table("teams", metadata_obj, autoload_with=engine)
    employees_teams = Table("employees_teams",
                            metadata_obj,
                            autoload_with=engine)
    return employees, teams, employees_teams


def insert_data(engine):
    employees, teams, employees_teams = load_tables(engine)

    with engine.connect() as conn:
        conn.execute(insert(employees).values([
            {"id": 0, "last_name": "Sehn",       "first_name": "Tim"},
            {"id": 1, "last_name": "Hendriks",   "first_name": "Brian"},
            {"id": 2, "last_name": "Son",        "first_name": "Aaron"},
            {"id": 3, "last_name": "Fitzgerald", "first_name": "Brian"},
        ]))
        conn.execute(insert(teams).values([
            {"id": 0, "name": "Engineering"},
            {"id": 1, "name": "Sales"},
        ]))
        conn.execute(insert(employees_teams).values([
            {"employee_id": 0, "team_id": 0},
            {"employee_id": 1, "team_id": 0},
            {"employee_id": 2, "team_id": 0},
            {"employee_id": 0, "team_id": 1},
            {"employee_id": 3, "team_id": 1},
        ]))
        conn.commit()


def modify_data(engine):
    employees, _, employees_teams = load_tables(engine)

    with engine.connect() as conn:
        conn.execute(update(employees)
                     .where(employees.c.first_name == "Tim")
                     .values(first_name="Timothy"))
        conn.execute(insert(employees).values([
            {"id": 4, "last_name": "Wilkins", "first_name": "Daylon"},
        ]))
        conn.execute(insert(employees_teams).values([
            {"employee_id": 4, "team_id": 0},
        ]))
        conn.execute(delete(employees_teams)
                     .where(employees_teams.c.employee_id == 0)
                     .where(employees_teams.c.team_id == 1))
        conn.commit()


def modify_schema(engine):
    # SQLAlchemy has no portable ALTER ADD COLUMN, so use raw SQL.
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE employees ADD COLUMN start_date DATE"))
        conn.commit()

    class Base(DeclarativeBase):
        pass

    class Employee(Base):
        __tablename__ = "employees"
        id: Mapped[int] = mapped_column(primary_key=True)
        last_name: Mapped[str] = mapped_column(String(255))
        first_name: Mapped[str] = mapped_column(String(255))
        start_date: Mapped[Date] = mapped_column(Date)

        def __repr__(self) -> str:
            return (
                f"Employee(id={self.id!r}, "
                f"last_name={self.last_name!r}, "
                f"first_name={self.first_name!r}, "
                f"start_date={self.start_date!r})"
            )

    with Session(engine) as session:
        tim = session.get(Employee, 0)
        tim.start_date = datetime.date(2018, 8, 6)

        bheni = session.get(Employee, 1)
        bheni.start_date = datetime.date(2018, 8, 6)

        aaron = session.get(Employee, 2)
        aaron.start_date = datetime.date(2018, 8, 6)

        fitz = session.execute(
            select(Employee).filter_by(last_name="Fitzgerald")
        ).scalar_one()
        fitz.start_date = datetime.date(2021, 4, 19)

        session.commit()


def drop_table(engine, name):
    employees, teams, employees_teams = load_tables(engine)
    by_name = {
        "employees": employees,
        "teams": teams,
        "employees_teams": employees_teams,
    }
    tbl = by_name.get(name)
    if tbl is None:
        print(f"{name}: Not found")
        return
    tbl.drop(engine)


def dolt_commit(engine, author, message):
    """In doltlite the Dolt operations are SQL functions: SELECT dolt_x(...).

    The Dolt MySQL server exposes them as procedures (CALL DOLT_X(...)),
    which is the only material syntactic difference for this demo.
    """
    with engine.connect() as conn:
        conn.execute(text("SELECT dolt_add('-A')"))
        row = conn.execute(
            text("SELECT dolt_commit('--skip-empty', "
                 "'--author', :author, '-m', :msg)"),
            {"author": author, "msg": message},
        ).fetchone()
        commit = row[0] if row else None
        if commit:
            print(f"Created commit: {commit}")


def dolt_reset_hard(engine, commit):
    if commit:
        sql = text("SELECT dolt_reset('--hard', :c)")
        params = {"c": commit}
        print(f"Resetting to commit: {commit}")
    else:
        sql = text("SELECT dolt_reset('--hard')")
        params = {}
        print("Resetting to HEAD")
    with engine.connect() as conn:
        conn.execute(sql, params)
        conn.commit()


def dolt_create_branch(engine, branch):
    metadata_obj = MetaData()
    dolt_branches = Table("dolt_branches", metadata_obj, autoload_with=engine)
    with engine.connect() as conn:
        existing = conn.execute(
            select(dolt_branches.c.name).where(dolt_branches.c.name == branch)
        ).fetchall()
        if existing:
            print(f"Branch exists: {branch}")
            return
        conn.execute(text("SELECT dolt_branch(:b)"), {"b": branch})
        print(f"Created branch: {branch}")


def dolt_checkout(branch):
    with _engine.connect() as conn:
        conn.execute(text("SELECT dolt_checkout(:b)"), {"b": branch})
    print(f"Using branch: {branch}")
    return _engine


def dolt_merge(engine, branch):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT dolt_merge(:b)"), {"b": branch}
        ).fetchone()
    print(f"Merge complete: {branch}")
    if row:
        print(f"\tResult: {row[0]}")


def print_commit_log(engine):
    metadata_obj = MetaData()
    print("Commit Log:")
    dolt_log = Table("dolt_log", metadata_obj, autoload_with=engine)
    stmt = (
        select(dolt_log.c.commit_hash,
               dolt_log.c.committer,
               dolt_log.c.message)
        .order_by(dolt_log.c.date.desc())
    )
    with engine.connect() as conn:
        for row in conn.execute(stmt):
            commit_hash, committer, message = row
            print(f"\t{commit_hash}: {message} by {committer}")


def print_status(engine):
    metadata_obj = MetaData()
    dolt_status = Table("dolt_status", metadata_obj, autoload_with=engine)
    print("Status")
    stmt = select(dolt_status.c.table_name, dolt_status.c.status)
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
    if rows:
        for table_name, status in rows:
            print(f"\t{table_name}: {status}")
    else:
        print("\tNo tables modified")


def print_active_branch(engine):
    with engine.connect() as conn:
        row = conn.execute(text("SELECT active_branch()")).fetchone()
    print(f"Active branch: {row[0]}")


def print_diff(engine, table):
    metadata_obj = MetaData()
    print(f"Diffing table: {table}")
    dolt_diff = Table(f"dolt_diff_{table}",
                      metadata_obj,
                      autoload_with=engine)
    stmt = select(dolt_diff).where(dolt_diff.c.to_commit == "WORKING")
    with engine.connect() as conn:
        for row in conn.execute(stmt):
            pprint(row._asdict())


def print_tables(engine):
    # SQLite equivalent of MySQL's "SHOW TABLES", filtering out the
    # sqlite_* internals and the dolt_* virtual tables.
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE 'dolt_%' "
            "ORDER BY name"
        ))
        print("Tables in database:")
        for (name,) in rows:
            print(f"\t{name}")


def print_summary_table(engine):
    employees, teams, employees_teams = load_tables(engine)
    print("Team Summary")

    columns = tuple(c.key for c in employees.c if c.key != "id")

    stmt = (
        select(teams.c.name, employees.c[columns])
        .select_from(employees)
        .join(employees_teams,
              employees.c.id == employees_teams.c.employee_id)
        .join(teams,
              teams.c.id == employees_teams.c.team_id)
        .order_by(teams.c.name.asc())
    )
    with engine.connect() as conn:
        for row in conn.execute(stmt):
            team_name = row[0]
            last_name = row[1]
            first_name = row[2]
            start_date = ""
            if len(row) > 3 and row[3]:
                start_date = (
                    row[3].strftime("%Y-%m-%d")
                    if hasattr(row[3], "strftime") else str(row[3])
                )
            print(f"\t{team_name}: {first_name} {last_name} {start_date}")


if __name__ == "__main__":
    main()
