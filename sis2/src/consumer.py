"""Consume and verify the JSON records named in a Kafka publish receipt."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from time import monotonic
from typing import Any

from kafka import KafkaConsumer, TopicPartition
from kafka.errors import KafkaError

from .producer import INDEX_HEADER, PARTITION, RUN_HEADER, Receipt, validate_topic


def consume(
    receipt: Receipt, bootstrap: str | None = None, *, timeout: float = 30
) -> list[dict[str, Any]]:
    """Read and verify the receipt's offsets before the polling deadline."""
    if not isinstance(receipt, dict):
        raise ValueError("Kafka receipt must be a JSON object")
    topic = validate_topic(receipt.get("topic"))
    broker = receipt.get("broker") if bootstrap is None else bootstrap
    if not isinstance(broker, str) or not broker.strip():
        raise ValueError("Kafka bootstrap server is required")
    partition = receipt.get("partition")
    if type(partition) is not int or partition != PARTITION:
        raise ValueError("Kafka receipt must identify partition 0")
    run_id = receipt.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise ValueError("Kafka receipt has an invalid run ID")
    count = receipt.get("count")
    offsets = receipt.get("offsets")
    if (
        type(count) is not int
        or not isinstance(offsets, list)
        or count != len(offsets)
        or any(type(offset) is not int or offset < 0 for offset in offsets)
        or any(previous >= following for previous, following in zip(offsets, offsets[1:]))
    ):
        raise ValueError("Kafka receipt must list one increasing offset per record")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Kafka consume timeout must be positive and finite")
    if not offsets:
        return []

    assigned = TopicPartition(topic, PARTITION)
    consumer = KafkaConsumer(
        bootstrap_servers=broker,
        group_id=None,
        enable_auto_commit=False,
        auto_offset_reset="none",
        api_version_auto_timeout_ms=5_000,
    )
    received = []
    expected_run = run_id.encode("ascii")
    try:
        consumer.assign([assigned])
        consumer.seek(assigned, offsets[0])
        deadline = monotonic() + timeout
        while len(received) < count:
            remaining_ms = min(1000, int((deadline - monotonic()) * 1000))
            if remaining_ms <= 0:
                raise TimeoutError(
                    f"Read {len(received)} of {count} Kafka records for run {run_id}"
                )
            for message in consumer.poll(timeout_ms=remaining_ms).get(assigned, []):
                index = len(received)
                expected_offset = offsets[index]
                if message.offset < expected_offset:
                    continue
                if message.offset > expected_offset:
                    raise RuntimeError(f"Kafka skipped expected offset {expected_offset}")
                headers = dict(message.headers)
                if (
                    headers.get(RUN_HEADER) != expected_run
                    or headers.get(INDEX_HEADER) != str(index).encode("ascii")
                ):
                    raise RuntimeError(
                        f"Kafka record at offset {expected_offset} does not match the receipt"
                    )
                record = json.loads(message.value)
                if not isinstance(record, dict):
                    raise ValueError(f"Kafka record at offset {expected_offset} is not a JSON object")
                received.append(record)
                if len(received) == count:
                    break
    finally:
        consumer.close()
    return received


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True, help="Producer receipt path")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON path")
    parser.add_argument("--bootstrap", help="Override the Kafka bootstrap server in the receipt")
    parser.add_argument("--timeout", type=float, default=30, help="Polling deadline in seconds")
    args = parser.parse_args()
    try:
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        records = consume(receipt, bootstrap=args.bootstrap, timeout=args.timeout)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        print(f"Consumed {len(records)} messages for run {receipt['run_id']}")
    except (KafkaError, ValueError, TypeError, RuntimeError, OSError) as error:
        parser.exit(1, f"Kafka consume failed: {error}\n")


if __name__ == "__main__":
    main()
