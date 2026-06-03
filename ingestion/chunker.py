import sys
import os
import re
import tiktoken

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import CHUNK_SIZE, CHUNK_OVERLAP

ENCODING = tiktoken.get_encoding("cl100k_base")


def _token_count(text):
    return len(ENCODING.encode(text or ""))


def _split_oversized_sentence(sentence):
    if _token_count(sentence) <= CHUNK_SIZE:
        return [sentence.strip()]

    parts = []
    words = re.findall(r"\S+\s*", sentence)
    current_words = []
    current_tokens = 0

    for word in words:
        word_tokens = _token_count(word)

        if word_tokens > CHUNK_SIZE:
            if current_words:
                parts.append("".join(current_words).strip())
                current_words = []
                current_tokens = 0

            raw_word = word.strip()
            if not raw_word:
                continue

            # Fallback: split a very long token-like word by character window.
            start = 0
            while start < len(raw_word):
                end = min(len(raw_word), start + CHUNK_SIZE * 4)
                piece = raw_word[start:end]

                while end < len(raw_word) and _token_count(piece) > CHUNK_SIZE:
                    end -= 1
                    piece = raw_word[start:end]

                if not piece:
                    end = min(len(raw_word), start + 1)
                    piece = raw_word[start:end]

                parts.append(piece.strip())
                start = end

            continue

        if current_tokens + word_tokens > CHUNK_SIZE and current_words:
            parts.append("".join(current_words).strip())
            current_words = [word]
            current_tokens = word_tokens
        else:
            current_words.append(word)
            current_tokens += word_tokens

    if current_words:
        parts.append("".join(current_words).strip())

    return [p for p in parts if p]


def _with_overlap(sentences):
    if CHUNK_OVERLAP <= 0 or not sentences:
        return []

    overlap = []
    tokens = 0

    for s in reversed(sentences):
        overlap.insert(0, s)
        tokens += _token_count(s)
        if tokens >= CHUNK_OVERLAP:
            break

    return overlap


def chunk(chunk_dict):
    """Split one parser chunk into token-limited sub-chunks. Returns a list of chunk dicts."""
    text = (chunk_dict or {}).get("text", "") or ""
    parent_metadata = dict((chunk_dict or {}).get("metadata", {}) or {})

    if _token_count(text) <= CHUNK_SIZE:
        return [{
            "text": text,
            "metadata": {
                **parent_metadata,
                "chunk_index": 0,
                "chunk_total": 1,
            }
        }]

    raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?\n])\s+", text) if s and s.strip()]

    sentences = []
    for s in raw_sentences:
        if _token_count(s) > CHUNK_SIZE:
            sentences.extend(_split_oversized_sentence(s))
        else:
            sentences.append(s)

    sub_texts = []
    buffer_sentences = []
    buffer_tokens = 0

    for sentence in sentences:
        sentence_tokens = _token_count(sentence)

        if buffer_sentences and buffer_tokens + sentence_tokens > CHUNK_SIZE:
            sub_texts.append(" ".join(buffer_sentences).strip())
            buffer_sentences = _with_overlap(buffer_sentences)
            buffer_tokens = _token_count(" ".join(buffer_sentences))

        buffer_sentences.append(sentence)
        buffer_tokens += sentence_tokens

        if buffer_tokens >= CHUNK_SIZE:
            sub_texts.append(" ".join(buffer_sentences).strip())
            buffer_sentences = _with_overlap(buffer_sentences)
            buffer_tokens = _token_count(" ".join(buffer_sentences))

    if buffer_sentences:
        remaining = " ".join(buffer_sentences).strip()
        if remaining:
            if not sub_texts or remaining != sub_texts[-1]:
                sub_texts.append(remaining)

    total = len(sub_texts)
    return [{
        "text": sub_text,
        "metadata": {
            **parent_metadata,
            "chunk_index": i,
            "chunk_total": total,
        }
    } for i, sub_text in enumerate(sub_texts)]


def chunk_many(chunk_list):
    """Run chunk() on a list of chunk dicts, return flat list of all sub-chunks."""
    result = []
    for c in chunk_list:
        result.extend(chunk(c))
    return result


if __name__ == "__main__":
    lorem_seed = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
        "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
        "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. "
        "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. "
        "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.\n"
    )

    lorem_5000 = (lorem_seed * ((5000 // len(lorem_seed)) + 1))[:5000]
    test_chunk = {
        "text": lorem_5000,
        "metadata": {
            "source": "test",
            "title": "Lorem Ipsum Test",
        }
    }

    chunks = chunk(test_chunk)

    print(f"Sub-chunks: {len(chunks)}")
    print("Tokens per sub-chunk:", [_token_count(c["text"]) for c in chunks])
    print("First sub-chunk metadata:", chunks[0]["metadata"] if chunks else {})
