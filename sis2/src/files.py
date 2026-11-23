import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", dir=path.parent, encoding="utf-8", delete=False) as buffer:
        json.dump(value, buffer, ensure_ascii=False, indent=2, allow_nan=False)
        buffer.write("\n")
    Path(buffer.name).replace(path)


def digest(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()
