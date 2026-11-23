# Music Listening Trends on ListenBrainz

SIS 2 · Data Collection & Preparation · Temirkhan Adilet and Bertayev Azat

The project compares the public sitewide artist and recording charts for October 2026 and the week starting 9 November 2026. The archived run contains four top-100 lists. The first-ranked BTS entry accounts for 24.9% of listens in the captured weekly artist list and 8.9% in the monthly list. The same display name also occurs at lower positions. The recording at rank one in both windows is *SWIM* by BTS.

[Project report](report/project_report.pdf) · [Data dictionary](docs/data_dictionary.md) · [Oral defense guide](docs/defense.md)

## Reproduce the submitted run

Use Python 3.11, Docker with Compose v2, and an available local port 9092. The commands below use a POSIX shell. Run them from the repository root, then keep the working directory at `sis2`. The SQLite CLI is optional for interactive SQL. Python includes the SQLite driver used by the pipeline.

```sh
cd sis2
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
docker compose up -d --wait
docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic sis2-listenbrainz --partitions 1 --replication-factor 1
python main.py --out .work/replay
```

This command replays the submitted API responses through a real Apache Kafka broker. Kafka runs in single-node KRaft mode. The broker also supports topic auto-creation with the same one-partition configuration. `main.py` accepts `--snapshot`, `--bootstrap`, and `--topic`. Supply a new output directory on each run. For example, use `.work/replay-2` for a second run. Each run already executes the database load twice.

| Stage | Archived result |
|---|---:|
| API chart positions | 400 |
| Broker-acknowledged messages | 400 |
| Messages decoded by the consumer | 400 |
| Valid / invalid production rows | 400 / 0 |
| Clean / stored rows | 400 / 400 |
| Rows inserted on first / second load | 400 / 0 |
| Deliberate test records rejected separately | 4 / 4 |

### Verify the replay

```sh
python -m unittest discover -s tests -v
python -m pip check
docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic sis2-listenbrainz
cmp results/verification.json .work/replay/verification.json
diff -qr results/analysis .work/replay/analysis
sqlite3 -readonly -header -column .work/replay/charts.db < sql/verify.sql
```

The submitted snapshot passes eight regression tests. The two file comparison commands exit successfully with empty output for an equivalent replay. Receipt IDs and offsets change with each publication. SQLite reports 100 positions per chart, zero duplicate positions, and an integrity result of `ok`. Both loads produce the ordered-row SHA-256 `c9be4747e868dd9739b4bbfacf0b99663db01798b7dd3a7f0cddebeb6158bd24`. The verification file also contains all five SQL statements and their results for environments without the SQLite CLI.

### Collect fresh data

The live collector needs outbound HTTPS and uses public statistics endpoints. No token or account configuration is required. This command performs collection, preserves the source responses, and writes the flattened input for inspection.

```sh
python -m src.api_client --live --count 100 --snapshot .work/live.json --records .work/live-rows.json
python main.py --snapshot .work/live.json --out .work/live-run
```

The API base is `https://api.listenbrainz.org/1/stats/sitewide`. The collector requests `/artists` and `/recordings` with `range=week` and `range=month`, `offset=0` and the requested count. Choose 50–100 positions for each of the four lists. Capture times, full URLs, time bounds, and original JSON fields are retained before flattening. The API can publish different time windows on a later date. To protect the origin of a result, the collector requires an unused path for a live snapshot. [ListenBrainz statistics API](https://listenbrainz.readthedocs.io/en/latest/users/api/statistics.html)

### Demonstrate the producer and consumer separately

These commands constitute a separate transport demonstration. The full runner above calls the same two Python functions before validating the received batch.

```sh
python -m src.api_client --snapshot data/snapshot.json --records .work/input.json
python -m src.producer --input .work/input.json --receipt .work/manual-receipt.json --bootstrap localhost:9092 --topic sis2-listenbrainz
python -m src.consumer --receipt .work/manual-receipt.json --output .work/received.json --timeout 30
python -c "import json; from pathlib import Path; read=lambda p: json.loads(Path(p).read_text()); assert read('.work/input.json') == read('.work/received.json'); print('All ordered records match')"
```

Each row becomes UTF-8 JSON. The producer requests acknowledgements from all in-sync replicas, attaches run and sequence headers, and saves the offsets returned by Kafka. The consumer seeks to the first acknowledged offset on partition 0, checks headers and offsets, and stops after the last expected row. Old topic contents or concurrent batches have their own offsets. If topic data have expired, publish a new batch and use its receipt.

## Pipeline and output files

| Stage | Implementation | Evidence |
|---|---|---|
| API | `src/api_client.py` | `data/snapshot.json` holds four original payloads with request metadata. |
| Transport | `compose.yaml`, `src/producer.py`, `src/consumer.py` | `results/receipt.json` lists every acknowledged offset. Ordered content equality is checked before validation. |
| Validation | `src/validator.py` | `results/quarantine.json` lists production failures. `results/invalid_examples.json` records four failing fixtures with rule names. |
| Preparation | `src/cleaner.py` | `results/verification.json` records missing fields, name fallbacks, text changes, data types and duplicate counts. |
| Storage | `src/loader.py`, `sql/schema.sql`, `sql/verify.sql` | `results/charts.db` is the final SQLite database. Load counts, sorted-row hashes and verification queries are in the run evidence. |
| EDA | `src/analysis.py` | `results/analysis/` contains numeric and categorical summaries, grouped chart statistics, filtered weekly recordings and a rank pivot. `results/figures/` holds three PNGs. |
| Report | `report/build_report.py` | `report/project_report.pdf` combines the archived evidence, figures, source details, SQL screenshot and conclusions. |

`main.py` stages a run in a temporary directory and publishes it after validation, database checks and EDA succeed. A failed send can leave acknowledged messages on the broker. A retry uses a new run ID. The loader checks the complete database against its intended snapshot and rolls back conflicting data. A separate run directory keeps previous evidence available.

SQL uniquely identifies a row by chart type, period, time bounds and source rank. The same recording can occupy multiple ranks with different release metadata. For cross-window comparisons the pivot uses its best rank per period. Daily averages divide counts by the actual duration of each window. Percentages use the sum of listens for retained positions in the same chart. Chart and identifier limitations are discussed in the report.

## Rebuild the PDF

```sh
python report/build_report.py
```

The builder targets the submitted `results/` and includes its checked-in SQL screenshot. To recapture that screenshot from the database, first run the command below with a local Chrome or Chromium executable. It requires the SQLite CLI. The data pipeline and normal PDF rebuild use the existing capture.

```sh
python report/capture_sql.py --chrome chromium
python report/build_report.py
```

## Troubleshooting and shutdown

- **Broker unavailable.** Run `docker compose ps` and `docker compose logs --tail 40 kafka`. Wait for healthy status. The published port must be available and the client runs on the host.
- **HTTP 204, timeout or short response.** The collector stops before publishing a partial snapshot. Use the archived snapshot to reproduce the report. For a new capture, retry once all four charts are available.
- **Validation failure.** Inspect the original row and failed rule in the quarantine file. The isolated test records never enter the analysis. Conflicting versions of one chart slot fail explicitly.
- **Output exists.** Choose an unused run directory. To stop the classroom broker and preserve its container, use `docker compose stop`. Start it again with `docker compose up -d --wait`.
