import os
import sys
import hashlib

import chromadb
from chromadb import EmbeddingFunction, Documents, Embeddings
from sentence_transformers import SentenceTransformer

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import CHROMA_DB_PATH, EMBEDDING_MODEL


# ── EMBEDDING FUNCTION ────────────────────────────────────

class BGE_EmbeddingFunction(EmbeddingFunction):
    def __init__(self):
        print(f"Loading embedding model {EMBEDDING_MODEL} onto M3 GPU (mps)...")
        self._model = SentenceTransformer(EMBEDDING_MODEL, device="mps")
        print("Model ready.")

    def __call__(self, input: Documents) -> Embeddings:
        vectors = self._model.encode(
            list(input),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()


# ── MODULE STATE ──────────────────────────────────────────

_client = None
_embedding_fn = None


# ── INTERNAL HELPERS ──────────────────────────────────────

def _get_client():
    global _client
    if _client is None:
        try:
            os.makedirs(CHROMA_DB_PATH, exist_ok=True)
            _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        except Exception as e:
            raise RuntimeError(f"Failed to initialise ChromaDB client at '{CHROMA_DB_PATH}': {e}") from e
    return _client


def _get_embedding_fn():
    global _embedding_fn
    if _embedding_fn is None:
        try:
            _embedding_fn = BGE_EmbeddingFunction()
        except Exception as e:
            raise RuntimeError(f"Failed to load embedding model '{EMBEDDING_MODEL}': {e}") from e
    return _embedding_fn


def _chunk_id(chunk):
    chunk_data = chunk if isinstance(chunk, dict) else {}
    metadata = chunk_data.get("metadata", {}) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    source = metadata.get("source", "")
    date = metadata.get("date", "")
    chunk_index = metadata.get("chunk_index", 0)
    text_prefix = (chunk_data.get("text", "") or "")[:120]
    raw = f"{source}-{date}-{chunk_index}-{text_prefix}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _clean_metadata(metadata):
    cleaned = {}
    metadata_dict = metadata if isinstance(metadata, dict) else {}
    for k, v in metadata_dict.items():
        if v is None:
            cleaned[k] = ""
        elif isinstance(v, (str, int, float, bool)):
            cleaned[k] = v
        else:
            cleaned[k] = str(v)
    return cleaned


def _is_missing_collection_error(error):
    msg = str(error).lower()
    return "does not exist" in msg or "not found" in msg or "no collection" in msg


# ── PUBLIC API ────────────────────────────────────────────

def get_or_create_collection(name="personal_kb"):
    # Return a ChromaDB collection wired to the local embedding function.
    try:
        client = _get_client()
        return client.get_or_create_collection(
            name=name,
            embedding_function=_get_embedding_fn(),
        )
    except Exception as e:
        raise RuntimeError(f"Failed to get or create collection '{name}': {e}") from e


def upsert_chunks(chunks, collection_name="personal_kb", batch_size=25):
    # Upsert chunk dicts into ChromaDB in memory-safe batches.
    if not chunks:
        print(f"Done. 0 chunks upserted to '{collection_name}'.")
        return

    valid_chunks = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        text = (chunk.get("text", "") or "")
        if (text or "").strip():
            valid_chunks.append(chunk)

    if not valid_chunks:
        print(f"Done. 0 chunks upserted to '{collection_name}'.")
        return

    if not isinstance(batch_size, int) or batch_size <= 0:
        batch_size = 100

    collection = get_or_create_collection(collection_name)
    total_batches = (len(valid_chunks) + batch_size - 1) // batch_size

    for i in range(0, len(valid_chunks), batch_size):
        batch = valid_chunks[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        print(f"  Upserting batch {batch_num}/{total_batches} ({len(batch)} chunks)...")

        ids = [_chunk_id(chunk) for chunk in batch]
        documents = [chunk.get("text", "") or "" for chunk in batch]
        metadatas = [_clean_metadata(chunk.get("metadata", {})) for chunk in batch]

        try:
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        except Exception as e:
            raise RuntimeError(f"Failed upserting batch {batch_num}/{total_batches}: {e}") from e

    print(f"Done. {len(valid_chunks)} chunks upserted to '{collection_name}'.")


def query(text, n_results=10, filters=None, collection_name="personal_kb"):
    # Query the collection and return normalized result rows.
    if not (text or "").strip():
        return []

    collection = get_or_create_collection(collection_name)
    total_docs = collection.count()

    if total_docs <= 0:
        return []

    max_results = min(int(n_results), int(total_docs))
    if max_results <= 0:
        return []

    query_args = {
        "query_texts": [text],
        "n_results": max_results,
    }
    if filters is not None:
        query_args["where"] = filters

    try:
        raw = collection.query(**query_args)
    except Exception as e:
        raise RuntimeError(f"Failed query on collection '{collection_name}': {e}") from e

    documents = (raw.get("documents") or [[]])[0]
    metadatas = (raw.get("metadatas") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]

    results = []
    for i, doc_text in enumerate(documents):
        metadata = metadatas[i] if i < len(metadatas) and isinstance(metadatas[i], dict) else {}
        distance = distances[i] if i < len(distances) else None
        results.append({
            "text": doc_text,
            "metadata": metadata,
            "distance": float(distance) if distance is not None else 0.0,
        })

    return results


def count(collection_name="personal_kb"):
    # Return total number of chunks in a collection.
    try:
        client = _get_client()
        collection = client.get_collection(name=collection_name)
        return int(collection.count())
    except Exception as e:
        if _is_missing_collection_error(e):
            return 0
        raise


def delete_collection(name):
    # Delete a collection by name.
    try:
        client = _get_client()
        client.delete_collection(name=name)
        print(f"Collection '{name}' deleted.")
    except Exception as e:
        if _is_missing_collection_error(e):
            print(f"Collection '{name}' does not exist.")
            return
        raise RuntimeError(f"Failed to delete collection '{name}': {e}") from e


# ── SELF TEST ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=== chroma_store self-test ===")

    TEST_COLLECTION = "test_phase4"

    # Clean up any previous test run
    try:
        delete_collection(TEST_COLLECTION)
    except Exception:
        pass

    # Insert 5 test chunks
    test_chunks = [
        {"text": "I went to the hospital for a routine checkup in January 2024.", "metadata": {"source": "gmail", "date": "2024-01-10", "priority": "normal", "modality": "text", "phase2": False, "chunk_index": 0, "chunk_total": 1}},
        {"text": "Working on the Android DICOM viewer — added segmentation overlay.", "metadata": {"source": "chatgpt", "date": "2024-02-14", "priority": "high", "modality": "text", "phase2": False, "chunk_index": 0, "chunk_total": 1}},
        {"text": "Listened to Radiohead — OK Computer for three hours straight.", "metadata": {"source": "spotify", "date": "2024-03-05", "priority": "normal", "modality": "text", "phase2": False, "chunk_index": 0, "chunk_total": 1}},
        {"text": "Flight to Dhaka booked for April, transit via Dubai.", "metadata": {"source": "gmail", "date": "2024-03-20", "priority": "normal", "modality": "text", "phase2": False, "chunk_index": 0, "chunk_total": 1}},
        {"text": "Finished reading the ChromaDB documentation on metadata filtering.", "metadata": {"source": "chrome_history", "date": "2024-04-01", "priority": "normal", "modality": "text", "phase2": False, "chunk_index": 0, "chunk_total": 1}},
    ]

    print(f"\nInserting {len(test_chunks)} test chunks...")
    upsert_chunks(test_chunks, collection_name=TEST_COLLECTION)

    print(f"\nTotal in collection: {count(TEST_COLLECTION)}")

    print("\nQuery: 'medical checkup'")
    results = query("medical checkup", n_results=2, collection_name=TEST_COLLECTION)
    for r in results:
        print(f"  [{r['metadata']['source']}] {r['text'][:80]}  (distance: {r['distance']:.4f})")

    print("\nQuery: 'travel plans'")
    results = query("travel plans", n_results=2, collection_name=TEST_COLLECTION)
    for r in results:
        print(f"  [{r['metadata']['source']}] {r['text'][:80]}  (distance: {r['distance']:.4f})")

    print("\nQuery with filter: source=gmail")
    results = query("anything", n_results=5, filters={"source": "gmail"}, collection_name=TEST_COLLECTION)
    for r in results:
        print(f"  [{r['metadata']['source']}] {r['text'][:80]}")

    # Clean up
    delete_collection(TEST_COLLECTION)
    print("\nTest collection deleted. Self-test complete.")
