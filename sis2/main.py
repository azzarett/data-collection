"""Run the finite ListenBrainz pipeline and publish a verified result directory."""
import argparse
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from src.api_client import flatten
from src.cleaner import clean
from src.consumer import consume
from src.files import digest, read_json, write_json
from src.loader import load_twice
from src.producer import DEFAULT_BOOTSTRAP, DEFAULT_TOPIC, publish
from src.validator import validate, validation_demo


def run(snapshot_path, output, bootstrap, topic):
    # An incomplete run never replaces evidence from a successful one.
    if output.exists():
        raise FileExistsError(f"Choose an unused output path: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot = read_json(snapshot_path)
    records = flatten(snapshot)
    with TemporaryDirectory(prefix=".sis2-", dir=output.parent) as temporary:
        stage = Path(temporary) / "run"
        stage.mkdir()
        receipt = publish(records, bootstrap, topic)
        received = consume(receipt, bootstrap)
        if receipt["count"] != len(records) or digest(received) != digest(records):
            raise RuntimeError("Kafka round trip changed the batch")
        valid, rejected = validate(received)
        if valid.empty:
            raise ValueError("All received rows failed validation")
        processed, cleaning = clean(valid)
        database = load_twice(processed, stage / "charts.db")
        counts = {"collected": len(records), "published": receipt["count"],
                  "consumed": len(received), "valid": len(valid), "invalid": len(rejected),
                  "cleaned": len(processed), "stored": database["loads"][-1]["stored"]}
        if (counts["valid"] + counts["invalid"] != counts["consumed"]
                or counts["cleaned"] + cleaning["duplicates_removed"] != counts["valid"]
                or counts["cleaned"] != counts["stored"]):
            raise RuntimeError("Stage counts do not reconcile")

        from src.analysis import analyze
        analysis = analyze(stage / "charts.db", stage)
        if analysis["rows"] != counts["stored"]:
            raise RuntimeError("EDA row count differs from the verified database")
        write_json(stage / "receipt.json", receipt)
        write_json(stage / "quarantine.json", rejected)
        demo = validation_demo(received[int(valid.index[0])])
        write_json(stage / "invalid_examples.json", demo)
        evidence = {"snapshot_sha256": digest(snapshot), "messages_sha256": digest(received),
                    "counts": counts, "cleaning": cleaning, "database": database,
                    "analysis": analysis, "data_types": {c: str(t) for c, t in processed.dtypes.items()},
                    "schema_columns": processed.shape[1], "demo_rejected": len(demo)}
        write_json(stage / "verification.json", evidence)
        stage.rename(output)
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=Path("data/snapshot.json"))
    parser.add_argument("--out", type=Path, required=True, help="New directory for one snapshot")
    parser.add_argument("--bootstrap", default=DEFAULT_BOOTSTRAP)
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    args = parser.parse_args()
    # Keep Matplotlib's writable cache in the project, including for read-only home directories.
    os.environ.setdefault("MPLCONFIGDIR", str(Path(".work/matplotlib").resolve()))
    print(run(args.snapshot, args.out, args.bootstrap, args.topic))
