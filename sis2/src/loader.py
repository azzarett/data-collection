"""Load one snapshot transactionally and compare every stored field twice."""
import sqlite3
from pathlib import Path

from .cleaner import COLUMNS, KEY
from .files import digest

SQL = Path(__file__).resolve().parents[1] / "sql"


def load_twice(frame, db_path):
    columns = ", ".join(COLUMNS)
    keys = ", ".join(KEY)
    marks = ", ".join("?" for _ in COLUMNS)
    rows = list(frame.sort_values(KEY).itertuples(index=False, name=None))
    expected = digest(rows)
    checks = []
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.executescript((SQL / "schema.sql").read_text())
        for _ in range(2):
            with db:
                db.execute("BEGIN IMMEDIATE")
                before = db.total_changes
                db.executemany(f"INSERT INTO chart_entries ({columns}) VALUES ({marks}) "
                               f"ON CONFLICT ({keys}) DO NOTHING", rows)
                stored = db.execute(f"SELECT {columns} FROM chart_entries ORDER BY {keys}").fetchall()
                observed = digest(stored)
                if observed != expected:
                    raise ValueError("Database differs from this snapshot. Use a new output directory.")
                checks.append({"inserted": db.total_changes - before, "stored": len(stored),
                               "sha256": observed})
        queries = []
        for sql in (SQL / "verify.sql").read_text().split(";"):
            if sql.strip():
                cursor = db.execute(sql)
                queries.append({"sql": sql.strip(), "columns": [col[0] for col in cursor.description],
                                "rows": cursor.fetchall()})
    if checks[1]["inserted"] or queries[-1]["rows"] != [("ok",)]:
        raise RuntimeError("Database verification failed")
    return {"loads": checks, "queries": queries}
