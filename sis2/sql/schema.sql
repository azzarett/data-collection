CREATE TABLE IF NOT EXISTS chart_entries (
    kind TEXT NOT NULL CHECK (kind IN ('artist','recording')),
    period TEXT NOT NULL CHECK (period IN ('week','month')),
    start_utc TEXT NOT NULL,
    end_utc TEXT NOT NULL CHECK (end_utc > start_utc),
    rank INTEGER NOT NULL CHECK (rank BETWEEN 1 AND 100),
    artist_name TEXT NOT NULL CHECK (length(trim(artist_name)) > 0),
    track_name TEXT,
    mbid TEXT,
    entity_key TEXT NOT NULL,
    listens INTEGER NOT NULL CHECK (listens > 0),
    listens_per_day REAL NOT NULL CHECK (listens_per_day > 0),
    CHECK ((kind = 'artist' AND track_name IS NULL)
        OR (kind = 'recording' AND track_name IS NOT NULL AND length(trim(track_name)) > 0)),
    PRIMARY KEY (kind, period, start_utc, end_utc, rank)
) WITHOUT ROWID;
