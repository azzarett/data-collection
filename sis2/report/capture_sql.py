"""Capture the SQLite CLI's actual verification output in a local browser."""
import argparse
import html
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def capture(run, target, chrome):
    queries = (ROOT / "sql/verify.sql").read_text()
    output = subprocess.run(
        ["sqlite3", "-readonly", "-header", "-column", str(run / "charts.db")],
        input=queries, capture_output=True, text=True, check=True,
    ).stdout
    page = """<!doctype html><meta charset="utf-8"><style>
    *{box-sizing:border-box}body{margin:0;background:#142a33;color:#edf7f6;padding:24px 30px}
    h1{font:600 22px system-ui;margin:0 0 13px;color:#a5ddd3}
    pre{font:16px/1.26 ui-monospace,monospace;margin:0;white-space:pre-wrap}
    </style><h1>SQLite verification</h1><pre>""" + html.escape(output) + "</pre>"
    with TemporaryDirectory() as directory:
        document = Path(directory) / "sql.html"
        document.write_text(page, encoding="utf-8")
        subprocess.run([chrome, "--headless", "--disable-gpu", "--disable-extensions",
                        "--disable-background-networking", "--hide-scrollbars",
                        "--user-data-dir=" + str(Path(directory) / "profile"),
                        "--window-size=1000,650", "--screenshot=" + str(target.resolve()),
                        document.as_uri()], check=True)
    if not target.exists():
        raise RuntimeError("Browser did not produce the SQL capture")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=Path("results"))
    parser.add_argument("--output", type=Path, default=Path("report/sql-check.png"))
    parser.add_argument("--chrome", required=True)
    args = parser.parse_args()
    capture(args.run, args.output, args.chrome)
