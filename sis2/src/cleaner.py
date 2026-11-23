"""Prepare validated chart positions for relational storage."""
import json
import re
import unicodedata

import numpy as np
import pandas as pd

KEY = ["kind", "period", "start_utc", "end_utc", "rank"]
COLUMNS = KEY + ["artist_name", "track_name", "mbid", "entity_key", "listens", "listens_per_day"]


def normalize(value):
    if value is None:
        return None
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def identity(row):
    if row.mbid:
        return "mbid:" + row.mbid
    names = [row.artist_name.casefold(), (row.track_name or "").casefold()]
    return "name:" + json.dumps(names, ensure_ascii=False, separators=(",", ":"))


def clean(valid):
    frame = valid.copy()
    for name in ["artist_name", "track_name"]:
        frame[name] = frame[name].map(normalize)
    frame["mbid"] = frame.mbid.map(lambda value: value.lower() if value else None)
    for name in ["listens", "rank", "from_ts", "to_ts"]:
        frame[name] = pd.to_numeric(frame[name]).astype("int64")
    for source, name in [("from_ts", "start_utc"), ("to_ts", "end_utc")]:
        frame[name] = pd.to_datetime(frame[source], unit="s", utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    frame["entity_key"] = [identity(row) for row in frame.itertuples()]
    days = (frame.to_ts - frame.from_ts) / 86_400
    frame["listens_per_day"] = np.divide(frame.listens.to_numpy(), days.to_numpy())
    clean_rows = frame[COLUMNS].drop_duplicates().reset_index(drop=True)
    if clean_rows.duplicated(KEY).any():
        raise ValueError("Conflicting observations for the same chart position")
    return clean_rows, {"duplicates_removed": len(frame) - len(clean_rows),
                        "name_fallback_rows": int(clean_rows.mbid.isna().sum()),
                        "normalized_text_cells": int(sum(
                            (valid[col].fillna("") != frame[col].fillna("")).sum()
                            for col in ["artist_name", "track_name"])),
                        "missing_before": {k: int(v) for k, v in valid.isna().sum().items()}}
