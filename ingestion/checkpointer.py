import os
import sys
import json
import hashlib

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import SSD_BASE


CHECKPOINT_PATH = os.path.join(SSD_BASE, "checkpoint.json")


def _file_hash(filepath):
    base = filepath
    if os.path.exists(filepath):
        try:
            size = os.path.getsize(filepath)
            base = f"{filepath}:{size}"
        except OSError:
            base = filepath

    digest = hashlib.md5()
    digest.update(base.encode("utf-8"))
    return digest.hexdigest()


def _load():
    if not os.path.exists(CHECKPOINT_PATH):
        return set()

    try:
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return set()

    if not isinstance(data, list):
        return set()

    return {item for item in data if isinstance(item, str)}


def _save():
    parent = os.path.dirname(CHECKPOINT_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(_processed), f)


_processed = _load()


def is_processed(filepath):
    # Return True if this file has already been ingested.
    return _file_hash(filepath) in _processed


def mark_processed(filepath):
    # Record this file as done and persist to disk immediately.
    _processed.add(_file_hash(filepath))
    _save()


def reset():
    # Clear all checkpoint state (wipe the JSON file and in-memory set).
    _processed.clear()
    _save()


if __name__ == "__main__":
    mark_processed("/fake/path/a.json")
    mark_processed("/fake/path/b.json")
    print(is_processed("/fake/path/a.json"))
    print(is_processed("/fake/path/c.json"))
    reset()
    print(is_processed("/fake/path/a.json"))
