import os
import sys
import argparse
import traceback
from datetime import datetime

sys.path.append(os.path.expanduser("~/personal-kb"))

from ingestion.chunker import chunk_many
from ingestion.error_logger import log_error
from ingestion import checkpointer, deduplicator
from vectorstore.chroma_store import upsert_chunks, count

from ingestion.parsers.gmail_parser import parse_all_gmail_accounts
from ingestion.parsers.chatgpt_parser import parse_chatgpt_export
from ingestion.parsers.drive_parser import parse_all_drive_accounts
from ingestion.parsers.discord_parser import parse_discord_export
from ingestion.parsers.discord_server_parser import parse_all_servers
from ingestion.parsers.notion_parser import parse_notion_export
from ingestion.parsers.social_parser import parse_all_social
from ingestion.parsers.whatsapp_parser import parse_whatsapp_export
from ingestion.parsers.spotify_parser import parse_spotify_export
from ingestion.parsers.maps_parser import parse_maps_export
from ingestion.parsers.youtube_parser import parse_youtube_export
from ingestion.parsers.calendar_parser import parse_calendar_export
from ingestion.parsers.chrome_parser import parse_chrome_export
from ingestion.parsers.keep_parser import parse_keep_export
from ingestion.parsers.gemini_parser import parse_gemini_export


# ── PARSER REGISTRY ───────────────────────────────────────

PARSERS = [
    ("gmail",          parse_all_gmail_accounts),
    ("chatgpt",        parse_chatgpt_export),
    ("drive",          parse_all_drive_accounts),
    ("discord",        parse_discord_export),
    ("discord_server", parse_all_servers),
    ("notion",         parse_notion_export),
    ("social",         parse_all_social),
    ("whatsapp",       parse_whatsapp_export),
    ("spotify",        parse_spotify_export),
    ("maps",           parse_maps_export),
    ("youtube",        parse_youtube_export),
    ("calendar",       parse_calendar_export),
    ("chrome",         parse_chrome_export),
    ("keep",           parse_keep_export),
    ("gemini",         parse_gemini_export),
]


# ── PARSER RUNNER ─────────────────────────────────────────

def run_parser(name, parse_fn, collection_name, stats):
    key = f"parser:{name}"

    if checkpointer.is_processed(key):
        print(f"  [{name}] Skipping — already processed")
        stats["parsers_skipped"] += 1
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{name}] Starting... ({timestamp})")

    try:
        chunks = parse_fn()

        stats["chunks_parsed"] += len(chunks)

        text_chunks = [c for c in chunks if not c.get("metadata", {}).get("phase2", False)]
        stats["chunks_phase2_skipped"] += len(chunks) - len(text_chunks)

        sub_chunks = chunk_many(text_chunks)
        stats["chunks_after_chunking"] += len(sub_chunks)

        unique = []
        for c in sub_chunks:
            if deduplicator.is_duplicate(c):
                stats["chunks_deduped"] += 1
            else:
                deduplicator.mark_seen(c)
                unique.append(c)

        upsert_chunks(unique, collection_name=collection_name)
        stats["chunks_upserted"] += len(unique)

        checkpointer.mark_processed(key)
        stats["parsers_run"] += 1

        print(f"  [{name}] Done — {len(chunks)} parsed → {len(unique)} upserted")
    except Exception as e:
        log_error(name, f"parser:{name}", e)
        stats["parsers_failed"] += 1
        stats["errors"].append((name, str(e)))
        traceback.print_exc()


# ── ORCHESTRATOR ──────────────────────────────────────────

def run_ingestion(collection_name="personal_kb", reset=False, only=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("══════════════════════════════════════════")
    print(f"PKB Ingestion Run — {now}")
    print(f"Collection: {collection_name}")
    print("══════════════════════════════════════════")

    print("Loading embedding model into memory (M3 GPU via mps)...")
    print("Expect 10-20 seconds of memory pressure. Audio may stutter briefly.")
    from vectorstore.chroma_store import _get_embedding_fn
    _get_embedding_fn()
    print("Model ready. Memory pressure should normalise.\n")

    if reset:
        checkpointer.reset()
        print("Checkpoint cleared — running all parsers.")

    deduplicator.reset()

    stats = {
        "parsers_run": 0,
        "parsers_skipped": 0,
        "parsers_failed": 0,
        "chunks_parsed": 0,
        "chunks_after_chunking": 0,
        "chunks_phase2_skipped": 0,
        "chunks_deduped": 0,
        "chunks_upserted": 0,
        "errors": [],
    }

    selected_parsers = PARSERS
    if only:
        selected_parsers = [(name, fn) for name, fn in PARSERS if name == only]
        if not selected_parsers:
            print(f"Parser not found: {only}")
            return

    for name, fn in selected_parsers:
        run_parser(name, fn, collection_name, stats)

    print("\n══════════════════════════════════════════")
    print("INGESTION COMPLETE")
    print("══════════════════════════════════════════")
    print(f"Parsers run:       {stats['parsers_run']}")
    print(f"Parsers skipped:   {stats['parsers_skipped']}  (already checkpointed)")
    print(f"Parsers failed:    {stats['parsers_failed']}")
    print("")
    print(f"Chunks parsed:     {stats['chunks_parsed']}")
    print(f"After chunking:    {stats['chunks_after_chunking']}")
    print(f"Phase2 skipped:    {stats['chunks_phase2_skipped']}  (images/audio — processed in Phase 10)")
    print(f"Dedup removed:     {stats['chunks_deduped']}")
    print(f"Upserted:          {stats['chunks_upserted']}")
    print("")
    print(f"Total in DB:       {count(collection_name)}")
    print("")
    print("Errors:")
    if stats["errors"]:
        for parser_name, error_message in stats["errors"]:
            print(f"  - {parser_name}: {error_message}")
    else:
        print("  - None")
    print("══════════════════════════════════════════")


# ── CLI ENTRYPOINT ────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PKB ingestion pipeline")
    parser.add_argument("--collection", default="personal_kb", help="ChromaDB collection name")
    parser.add_argument("--reset", action="store_true", help="Clear checkpoint and re-process everything")
    parser.add_argument("--only", default=None, help="Run only one parser by name (e.g. --only gmail)")
    args = parser.parse_args()

    run_ingestion(collection_name=args.collection, reset=args.reset, only=args.only)
