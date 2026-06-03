import hashlib

_seen = set()


def _text_hash(chunk_dict):
    return hashlib.md5(chunk_dict["text"].encode("utf-8")).hexdigest()


def is_duplicate(chunk_dict):
    """Return True if this chunk's text has already been seen this run."""
    return _text_hash(chunk_dict) in _seen


def mark_seen(chunk_dict):
    """Record this chunk's text hash so future duplicates are detected."""
    _seen.add(_text_hash(chunk_dict))


def reset():
    """Clear all seen hashes. Call at the start of each ingestion run."""
    _seen.clear()


if __name__ == "__main__":
    chunk_a = {"text": "Same text"}
    chunk_b_same_text = {"text": "Same text"}
    chunk_c_different_text = {"text": "Different text"}

    mark_seen(chunk_a)
    print(is_duplicate(chunk_a))
    print(is_duplicate(chunk_b_same_text))
    print(is_duplicate(chunk_c_different_text))
    reset()
    print(is_duplicate(chunk_a))
