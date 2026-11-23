# Data dictionary

One database row represents a source chart position in a particular ListenBrainz sitewide statistics window. One Kafka message carries the nine fields in the received schema. Every time in the project uses UTC.

## Source archive

`data/snapshot.json` contains format `version` and four `pages`. Each page records `kind`, the query `params`, resolved `url`, `retrieved_utc`, and the complete `response` JSON. The source `payload` contains the row array under `artists` or `recordings`, the returned `count`, `offset`, `range`, `from_ts`, `to_ts`, and `last_updated`. The API's `total_artist_count` or `total_recording_count` describes the full chart population. The collector takes its leading positions. Original release, artist-credit and cover-art metadata remain in the archive where supplied.

## Received schema

| Field | JSON type | Source or derivation | Validation and meaning |
|---|---|---|---|
| kind | string | Endpoint | `artist` or `recording`. |
| period | string | Requested range, checked against payload | `week` or `month`. |
| rank | integer | Source array index + 1 | Position 1–100. Ties retain API order. |
| artist_name | string | Row's artist_name | Nonblank artist credit. |
| track_name | string or null | Row's track_name | Nonblank for a recording. Null for an artist position. |
| mbid | string or null | artist_mbid or recording_mbid | Optional MusicBrainz identifier, checked for UUID syntax when supplied. An empty string means missing. |
| listens | integer | Row's listen_count | Positive count for the chart position across the whole window. |
| from_ts | integer | Parent payload | Start of the observation window, Unix seconds. |
| to_ts | integer | Parent payload | Later boundary, Unix seconds. Duration is to_ts minus from_ts. |

Message headers `sis2-run-id` and `sis2-record-index` identify the run and the message's zero-based position. `receipt.json` adds the bootstrap server, topic, partition number, count and ordered broker offsets. It contains no API credentials.

## SQLite table

| Column | SQLite type | Definition |
|---|---|---|
| kind, period | TEXT | Source categories. Both participate in the primary key. |
| start_utc, end_utc | TEXT | UTC bounds in YYYY-MM-DDTHH:MM:SSZ form. Both participate in the primary key. |
| rank | INTEGER | Source position and final part of the primary key. |
| artist_name | TEXT | Required display credit after Unicode NFC and whitespace normalization. |
| track_name | TEXT, nullable | Normalized recording title. Null on artist rows. |
| mbid | TEXT, nullable | Lowercase UUID. Missing IDs retain SQL NULL. |
| entity_key | TEXT | `mbid:` and the identifier, or `name:` and a JSON array of the case-folded artist and title. Matching also uses kind. |
| listens | INTEGER | Validated number of listens for this entry. |
| listens_per_day | REAL | NumPy division of listens by (to_ts − from_ts) / 86,400. |

A display name can occur both with and without an MBID. Such rows can receive different keys. Different recordings with identical normalized fallback names can coincide. The reported counts of distinct entities are estimates under this key. Recordings with the same reliable MBID can appear several times within the same chart.

## Analysis and verification fields

- `window_days` is elapsed UTC days. `chart_share` is an entry's listens divided by the sum for the same kind and period.
- `top_10_share` sums the shares of retained positions at ranks 1–10. `distinct_artist_names` counts display credits, while `distinct_entities` counts comparison keys.
- `rank_comparison.csv` contains the best weekly and monthly ranks per kind and key. `rank_change = month - week`. Positive values indicate a better weekly position. Missing ranks stay empty.
- `jaccard` divides shared keys by the number of distinct keys in the union. Median absolute rank change uses only shared keys.
- `weekly_recording_filter.csv` includes weekly recording ranks 1–20 whose daily rate is at or above the weekly recording median.
- `numeric_summary.csv` includes count, mean, sample standard deviation, extrema and quartiles. `categorical_summary.csv` includes non-null and distinct counts, one deterministic mode, its frequency and the number of tied modes.
- `verification.json` stores stage counts, ordered content hashes, missing-value counts, both load results, SQL result sets and EDA metrics. `quarantine.json` records zero-based input indexes, original data and failed checks. `invalid_examples.json` follows the same structure with a case description for each isolated invalid copy.
