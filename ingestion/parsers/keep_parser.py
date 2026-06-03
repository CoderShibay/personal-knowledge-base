import os
import sys
import json
from datetime import datetime

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import ACCOUNT_PATHS

# ── CONFIGURATION ──────────────────────────────────────────

KEEP_REL_PATH = "Takeout/Keep"


# ── HELPERS ────────────────────────────────────────────────

def _ts_to_date(usec):
    try:
        return datetime.fromtimestamp(int(usec) / 1_000_000).strftime("%Y-%m-%d")
    except Exception:
        return None


def _note_to_text(note):
    parts = []

    title = (note.get("title") or "").strip()
    if title:
        parts.append(title)

    text = (note.get("textContent") or "").strip()
    if text:
        parts.append(text)

    list_items = note.get("listContent") or []
    if list_items:
        lines = []
        for item in list_items:
            t = (item.get("text") or "").strip()
            if not t:
                continue
            checked = item.get("isChecked", False)
            prefix = "[x]" if checked else "[ ]"
            lines.append(f"{prefix} {t}")
        if lines:
            parts.append("\n".join(lines))

    return "\n\n".join(parts)


# ── MAIN PARSER ────────────────────────────────────────────

def parse_keep_export():
    chunks = []

    for account_name, account_path in ACCOUNT_PATHS.items():
        keep_path = os.path.join(account_path, KEEP_REL_PATH)

        if not os.path.exists(keep_path):
            print(f"  [{account_name}] No Keep folder found")
            continue

        json_files = [
            f for f in os.listdir(keep_path)
            if f.endswith(".json") and not f.startswith("._")
        ]

        if not json_files:
            print(f"  [{account_name}] Keep folder exists but no JSON files")
            continue

        print(f"  [{account_name}] Found {len(json_files)} Keep note(s)")
        account_chunks = 0

        for filename in sorted(json_files):
            filepath = os.path.join(keep_path, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    note = json.load(f)
            except Exception as e:
                print(f"    Could not read {filename}: {e}")
                continue

            if note.get("isTrashed", False):
                continue

            text = _note_to_text(note)
            if not text:
                continue

            ts = note.get("userEditedTimestampUsec") or note.get("createdTimestampUsec")
            date = _ts_to_date(ts) if ts else None

            chunks.append({
                "text": f"Google Keep note ({account_name})\n\n{text}",
                "metadata": {
                    "source": "keep",
                    "account": account_name,
                    "date": date or "unknown",
                    "is_pinned": note.get("isPinned", False),
                    "is_archived": note.get("isArchived", False),
                    "priority": "normal",
                    "modality": "text",
                    "phase2": False,
                    "file_path": filepath,
                },
            })
            account_chunks += 1

        print(f"    {account_chunks} note(s) with text content")

    print(f"\nDone!")
    print(f"Total chunks: {len(chunks)}")
    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_keep_export()

    if chunks:
        print(f"\n── FIRST CHUNK PREVIEW ──")
        c = chunks[0]
        print(f"Account: {c['metadata']['account']}")
        print(f"Date:    {c['metadata']['date']}")
        print(f"Preview:\n{c['text'][:400]}")
