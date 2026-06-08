import os
import csv
import sys
from datetime import datetime

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import OTHER_PATHS, PRIORITY_PROJECTS

LINKEDIN_PATH = OTHER_PATHS["linkedin"]


def _build_chunk(thread_name, lines, dates, message_count):
    is_priority = any(p.lower() in thread_name.lower() for p in PRIORITY_PROJECTS)
    start_date  = min(dates) if dates else "unknown"
    end_date    = max(dates) if dates else "unknown"
    date_range  = f"{start_date} to {end_date}"
    return {
        "text": f"LinkedIn thread: {thread_name}\n"
                f"Date range: {date_range}\n\n"
                + "\n".join(lines),
        "metadata": {
            "source":        "linkedin",
            "thread_name":   thread_name,
            "date":          start_date,
            "date_range":    date_range,
            "message_count": message_count,
            "priority":      "high" if is_priority else "normal",
            "modality":      "text",
            "phase2":        False,
        },
    }


# ── MAIN PARSER ────────────────────────────────────────────

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
                convo_id    = (row.get("CONVERSATION ID") or "").strip()
                content     = (row.get("CONTENT") or "").strip()
                thread_name = (row.get("CONVERSATION TITLE") or "Untitled").strip()
                sender      = (row.get("FROM") or "Unknown").strip()
                raw_date    = (row.get("DATE") or "").strip()

                if not convo_id or not content:
                    continue

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
        chunk = _build_chunk(convo["thread_name"], convo["lines"], convo["dates"], len(convo["lines"]))
        chunks.append(chunk)
        label = " [PRIORITY]" if chunk["metadata"]["priority"] == "high" else ""
        print(f"  {chunk['metadata']['thread_name']} ({chunk['metadata']['message_count']} messages){label}")

    print(f"LinkedIn chunks: {len(chunks)}")
    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_linkedin()
    print(f"\nTotal chunks: {len(chunks)}")
    if chunks:
        print(f"\n── FIRST CHUNK PREVIEW ──\n{chunks[0]['text'][:400]}")
