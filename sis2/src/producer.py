"""Publish JSON records to a single Kafka partition and save their receipt."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, TypedDict
from uuid import uuid4

from kafka import KafkaProducer
from kafka.errors import KafkaError

DEFAULT_BOOTSTRAP = "localhost:9092"
DEFAULT_TOPIC = "sis2-listenbrainz"
PARTITION = 0
RUN_HEADER = "sis2-run-id"
INDEX_HEADER = "sis2-record-index"


class Receipt(TypedDict):
    broker: str
    topic: str
    partition: int
    run_id: str
    count: int
    offsets: list[int]


def validate_topic(topic: object) -> str:
    if (
        not isinstance(topic, str)
        or not re.fullmatch(r"[a-zA-Z0-9._-]{1,249}", topic)
        or topic in {".", ".."}
    ):
        raise ValueError("Invalid Kafka topic name")
    return topic


def publish(
    records: list[dict[str, Any]],
    bootstrap: str = DEFAULT_BOOTSTRAP,
    topic: str = DEFAULT_TOPIC,
) -> Receipt:
    """Return broker-acknowledged offsets in the same order as the input."""
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError("Input must be a JSON array of objects")
    if not isinstance(bootstrap, str) or not bootstrap.strip():
        raise ValueError("Kafka bootstrap server is required")
    validate_topic(topic)

    payloads = [
        json.dumps(row, ensure_ascii=False, allow_nan=False).encode("utf-8")
        for row in records
    ]
    run_id = uuid4().hex
    receipt: Receipt = {
        "broker": bootstrap,
        "topic": topic,
        "partition": PARTITION,
        "run_id": run_id,
        "count": len(payloads),
        "offsets": [],
    }
    if not payloads:
        return receipt

    producer = KafkaProducer(
        bootstrap_servers=bootstrap,
        enable_idempotence=True,
        acks="all",
        api_version_auto_timeout_ms=5_000,
        max_block_ms=10_000,
        request_timeout_ms=10_000,
        delivery_timeout_ms=30_000,
    )
    try:
        futures = [
            producer.send(
                topic,
                value=payload,
                partition=PARTITION,
                headers=[
                    (RUN_HEADER, run_id.encode("ascii")),
                    (INDEX_HEADER, str(index).encode("ascii")),
                ],
            )
            for index, payload in enumerate(payloads)
        ]
        for future in futures:
            metadata = future.get(timeout=35)
            if metadata.topic != topic or metadata.partition != PARTITION:
                raise RuntimeError("Kafka acknowledged an unexpected topic or partition")
            receipt["offsets"].append(metadata.offset)
    finally:
        producer.close(timeout=5)

    offsets = receipt["offsets"]
    if offsets[0] < 0 or any(
        previous >= following for previous, following in zip(offsets, offsets[1:])
    ):
        raise RuntimeError("Kafka did not acknowledge strictly increasing offsets")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="JSON array of input records")
    parser.add_argument("--receipt", type=Path, required=True, help="Output receipt path")
    parser.add_argument("--bootstrap", default=DEFAULT_BOOTSTRAP, help="Kafka bootstrap server")
    parser.add_argument("--topic", default=DEFAULT_TOPIC, help="Kafka topic")
    args = parser.parse_args()
    try:
        records = json.loads(args.input.read_text(encoding="utf-8"))
        receipt = publish(records, bootstrap=args.bootstrap, topic=args.topic)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(f"Published {receipt['count']} messages to {receipt['topic']}, partition {PARTITION}")
    except (KafkaError, ValueError, TypeError, RuntimeError, OSError) as error:
        parser.exit(1, f"Kafka publish failed: {error}\n")


if __name__ == "__main__":
    main()
