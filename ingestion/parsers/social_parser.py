import os
import json
import csv
import sys
from datetime import datetime

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import OTHER_PATHS, PRIORITY_PROJECTS

# ── CONFIGURATION ──────────────────────────────────────────

INSTAGRAM_PATH = OTHER_PATHS["instagram"]
FACEBOOK_PATH  = OTHER_PATHS["facebook"]
LINKEDIN_PATH  = OTHER_PATHS["linkedin"]


# ── HELPERS ────────────────────────────────────────────────

def parse_timestamp_ms(timestamp_ms):
    try:
        return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d")
    except Exception:
        return "unknown"


def load_json(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"    Could not read {filepath}: {e}")
        return None


def build_chunk(source, thread_name, lines, dates, message_count):
    is_priority = any(p.lower() in thread_name.lower() for p in PRIORITY_PROJECTS)
    start_date = min(dates) if dates else "unknown"
    end_date   = max(dates) if dates else "unknown"
    date_range = f"{start_date} to {end_date}"

    return {
        "text": f"{source.title()} thread: {thread_name}\n"
                f"Date range: {date_range}\n\n"
                + "\n".join(lines),
        "metadata": {
            "source": source,
            "thread_name": thread_name,
            "date": start_date,
            "date_range": date_range,
            "message_count": message_count,
            "priority": "high" if is_priority else "normal",
            "modality": "text",
            "phase2": False,
        },
    }


def parse_meta_thread(source, thread_folder):
    thread_name = os.path.basename(thread_folder)

    message_files = sorted(
        os.path.join(thread_folder, f)
        for f in os.listdir(thread_folder)
        if f.lower().startswith("message_") and f.lower().endswith(".json")
    )

    if not message_files:
        return None

    lines = []
    dates = []

    for message_file in message_files:
        data = load_json(message_file)
        if not data:
            continue

        messages = data.get("messages", [])
        if not isinstance(messages, list):
            continue

        for msg in messages:
            content = (msg.get("content") or "").strip()
            if not content:
                continue

            sender = msg.get("sender_name", "Unknown")
            date   = parse_timestamp_ms(msg.get("timestamp_ms", 0))
            lines.append(f"[{date}] {sender}: {content}")
            dates.append(date)

    if not lines:
        return None

    return build_chunk(source, thread_name, lines, dates, len(lines))


def _find_inbox_dirs(base_path):
    """Walk base_path and return all .../messages/inbox directories found at any depth."""
    found = []
    for root, dirs, files in os.walk(base_path):
        if os.path.basename(root) == "inbox" and os.path.basename(os.path.dirname(root)) == "messages":
            found.append(root)
    return found


def _parse_inbox_dirs(source, inbox_dirs):
    chunks = []
    for inbox_path in inbox_dirs:
        thread_folders = [
            os.path.join(inbox_path, d)
            for d in os.listdir(inbox_path)
            if os.path.isdir(os.path.join(inbox_path, d))
        ]
        for thread_folder in thread_folders:
            chunk = parse_meta_thread(source, thread_folder)
            if chunk is None:
                continue
            chunks.append(chunk)
            priority_label = " [PRIORITY]" if chunk["metadata"]["priority"] == "high" else ""
            print(f"  {chunk['metadata']['thread_name']} "
                  f"({chunk['metadata']['message_count']} messages){priority_label}")
    return chunks


# ── SOURCE PARSERS ─────────────────────────────────────────

def parse_instagram(instagram_path=INSTAGRAM_PATH):
    chunks = []

    if not os.path.exists(instagram_path):
        print(f"No Instagram data found at {instagram_path}")
        return chunks

    print(f"Scanning Instagram: {instagram_path}")

    # Meta export nests data under meta-DATE/instagram-USER/your_instagram_activity/messages/inbox/
    inbox_dirs = _find_inbox_dirs(instagram_path)

    if not inbox_dirs:
        print(f"  No messages/inbox found — zip may not be extracted yet")
        return chunks

    print(f"  Found {len(inbox_dirs)} inbox folder(s)")
    chunks = _parse_inbox_dirs("instagram", inbox_dirs)

    print(f"Instagram chunks: {len(chunks)}")
    return chunks


def parse_messenger(facebook_path=FACEBOOK_PATH):
    chunks = []

    if not os.path.exists(facebook_path):
        print(f"No Facebook/Messenger data found at {facebook_path}")
        return chunks

    print(f"Scanning Messenger (Facebook export): {facebook_path}")

    # Meta export nests data under meta-DATE/facebook-USER/your_facebook_activity/messages/inbox/
    inbox_dirs = _find_inbox_dirs(facebook_path)

    if not inbox_dirs:
        print(f"  No messages/inbox found — zips may not be extracted yet")
        return chunks

    print(f"  Found {len(inbox_dirs)} inbox folder(s)")
    chunks = _parse_inbox_dirs("messenger", inbox_dirs)

    print(f"Messenger chunks: {len(chunks)}")
    return chunks


def parse_linkedin(linkedin_path=LINKEDIN_PATH):
    chunks = []

    csv_path = os.path.join(linkedin_path, "messages.csv")
    if not os.path.exists(csv_path):
        print(f"No LinkedIn messages.csv found at {csv_path}")
        return chunks

    print(f"Scanning LinkedIn messages: {csv_path}")

    conversations = {}

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                convo_id = (row.get("CONVERSATION ID") or "").strip()
                if not convo_id:
                    continue

                content = (row.get("CONTENT") or "").strip()
                if not content:
                    continue

                thread_name = (row.get("CONVERSATION TITLE") or "Untitled").strip()
                sender = (row.get("FROM") or "Unknown").strip()
                raw_date = (row.get("DATE") or "").strip()

                try:
                    date = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).strftime("%Y-%m-%d")
                except Exception:
                    date = raw_date[:10] if len(raw_date) >= 10 else "unknown"

                if convo_id not in conversations:
                    conversations[convo_id] = {"thread_name": thread_name, "lines": [], "dates": []}

                conversations[convo_id]["lines"].append(f"[{date}] {sender}: {content}")
                conversations[convo_id]["dates"].append(date)
    except Exception as e:
        print(f"Could not parse LinkedIn CSV: {e}")
        return chunks

    for convo in conversations.values():
        if not convo["lines"]:
            continue
        chunk = build_chunk("linkedin", convo["thread_name"], convo["lines"], convo["dates"], len(convo["lines"]))
        chunks.append(chunk)
        priority_label = " [PRIORITY]" if chunk["metadata"]["priority"] == "high" else ""
        print(f"  {chunk['metadata']['thread_name']} ({chunk['metadata']['message_count']} messages){priority_label}")

    print(f"LinkedIn chunks: {len(chunks)}")
    return chunks


# ── MAIN PARSER ────────────────────────────────────────────

def parse_all_social():
    chunks = []
    chunks.extend(parse_instagram())
    chunks.extend(parse_messenger())
    chunks.extend(parse_linkedin())

    print(f"\nDone! Total social chunks: {len(chunks)}")
    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_all_social()

    print(f"\nTotal chunks: {len(chunks)}")

    if chunks:
        print(f"\n── FIRST CHUNK PREVIEW ──")
        print(f"Source:   {chunks[0]['metadata']['source']}")
        print(f"Thread:   {chunks[0]['metadata']['thread_name']}")
        print(f"Messages: {chunks[0]['metadata']['message_count']}")
        print(f"Priority: {chunks[0]['metadata']['priority']}")
        print(f"Preview:\n{chunks[0]['text'][:300]}...")
