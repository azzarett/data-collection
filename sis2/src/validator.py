"""Validate each received JSON row before coercion; keep every failed check."""
from uuid import UUID

import pandas as pd
import pandera.pandas as pa


def text(value):
    return isinstance(value, str) and bool(value.strip())


def positive_integer(value):
    return type(value) is int and 0 < value <= 2**63 - 1


def chart_position(value):
    return type(value) is int and 1 <= value <= 100


def timestamp(value):
    # ListenBrainz stores Unix seconds. Upper bound also fits pandas datetime64[ns].
    return type(value) is int and 0 <= value <= 9_214_646_400


def optional_uuid(value):
    if value is None or value == "":
        return True
    try:
        return isinstance(value, str) and str(UUID(value)) == value.lower()
    except ValueError:
        return False


def check(rule):
    return pa.Check(rule, element_wise=True, name=rule.__name__, ignore_na=False)


SCHEMA = pa.DataFrameSchema({
    "kind": pa.Column(object, pa.Check.isin(["artist", "recording"])),
    "period": pa.Column(object, pa.Check.isin(["week", "month"])),
    "rank": pa.Column(object, check(chart_position)),
    "artist_name": pa.Column(object, check(text)),
    "track_name": pa.Column(object, nullable=True),
    "mbid": pa.Column(object, check(optional_uuid), nullable=True),
    "listens": pa.Column(object, check(positive_integer)),
    "from_ts": pa.Column(object, check(timestamp)),
    "to_ts": pa.Column(object, check(timestamp)),
})


def check_track(row):
    if row["kind"] == "recording":
        return text(row["track_name"])
    return row["track_name"] is None


def check_window(row):
    return (timestamp(row["from_ts"]) and timestamp(row["to_ts"])
            and row["from_ts"] < row["to_ts"])


SCHEMA.checks = [check(check_track), check(check_window)]


def validate(records):
    # Object dtype preserves JSON integer vs float, even beside a null or bad value.
    frame = pd.DataFrame(records, columns=list(SCHEMA.columns), dtype=object)
    errors = {}
    try:
        SCHEMA.validate(frame, lazy=True)
    except pa.errors.SchemaErrors as exc:
        for failure in exc.failure_cases.to_dict("records"):
            index = failure["index"]
            if pd.isna(index):
                raise ValueError(f"Batch schema error: {failure['check']}") from exc
            column = failure["column"]
            # Pandera reports each column of a failed row-level check.
            rule = failure["check"]
            message = rule if rule in {"check_window", "check_track"} else f"{column}: {rule}"
            errors.setdefault(int(index), set()).add(message)
    invalid = [{"index": i, "record": records[i], "errors": sorted(messages)}
               for i, messages in sorted(errors.items())]
    return frame.drop(index=list(errors)), invalid


def validation_demo(example):
    """Exercise isolated corrupt copies; none enters the production consumer batch."""
    tests = [
        ("negative listens", {"listens": -1}),
        ("unknown period", {"period": "day"}),
        ("reversed window", {"to_ts": example["from_ts"] - 1}),
        ("missing title", {"kind": "recording", "track_name": None}),
    ]
    rows = [dict(example, **changes) for _, changes in tests]
    valid, errors = validate(rows)
    if not valid.empty or len(errors) != len(rows):
        raise RuntimeError("An intentionally invalid row escaped validation")
    return [dict(error, case=tests[error["index"]][0]) for error in errors]
