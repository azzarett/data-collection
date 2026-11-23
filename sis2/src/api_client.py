"""Collect or replay the original ListenBrainz sitewide chart responses."""
import argparse
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .files import read_json, write_json

BASE = "https://api.listenbrainz.org/1/stats/sitewide"
CHARTS = {"artist": "artists", "recording": "recordings"}
PERIODS = ("week", "month")


def collect(count=100):
    if not 50 <= count <= 100:
        raise ValueError("Choose 50 to 100 entries per chart (four charts).")
    pages = []
    retries = Retry(total=3, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504))
    with requests.Session() as session:
        session.headers["User-Agent"] = "SIS2-ListenBrainz-Statistics/1.0 (educational project)"
        session.mount("https://", HTTPAdapter(max_retries=retries))
        for kind, endpoint in CHARTS.items():
            for period in PERIODS:
                params = {"range": period, "count": count, "offset": 0}
                response = session.get(f"{BASE}/{endpoint}", params=params, timeout=(8, 30))
                response.raise_for_status()
                if response.status_code == 204:
                    raise ValueError(f"Statistics unavailable for {endpoint} / {period}")
                pages.append({"kind": kind, "params": params, "url": response.url,
                              "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                              "response": response.json()})
    snapshot = {"version": 1, "pages": pages}
    flatten(snapshot)
    return snapshot


def flatten(snapshot):
    rows = []
    charts = set()
    if snapshot["version"] != 1:
        raise ValueError("Unsupported snapshot version")
    for page in snapshot["pages"]:
        kind, params = page["kind"], page["params"]
        period = params["range"]
        payload = page["response"]["payload"]
        items = payload[CHARTS[kind]]
        if (kind, period) in charts or payload["range"] != period or payload["offset"] != 0:
            raise ValueError("Repeated chart or unexpected request metadata")
        charts.add((kind, period))
        if payload["count"] != len(items) or len(items) != params["count"]:
            raise ValueError(f"Incomplete response for {kind} / {period}")
        for rank, item in enumerate(items, 1):
            rows.append({"kind": kind, "period": period, "rank": rank,
                         "artist_name": item.get("artist_name"), "track_name": item.get("track_name"),
                         "mbid": item.get("artist_mbid" if kind == "artist" else "recording_mbid"),
                         "listens": item.get("listen_count"), "from_ts": payload["from_ts"],
                         "to_ts": payload["to_ts"]})
    if charts != {(k, p) for k in CHARTS for p in PERIODS} or len(rows) < 200:
        raise ValueError("Need all four charts and at least 200 API rows")
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--live", action="store_true", help="Write a new snapshot at an unused path")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--records", type=Path, required=True)
    args = parser.parse_args()
    if args.live:
        if args.snapshot.exists():
            parser.error("Choose an unused path for a fresh snapshot")
        write_json(args.snapshot, collect(args.count))
    records = flatten(read_json(args.snapshot))
    write_json(args.records, records)
    print(f"API chart rows: {len(records)}")
