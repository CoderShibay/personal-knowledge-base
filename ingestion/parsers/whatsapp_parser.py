import os
import sys
import re
from datetime import datetime

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import OTHER_PATHS, PRIORITY_PROJECTS

# ── CONFIGURATION ──────────────────────────────────────────

WHATSAPP_PATH = OTHER_PATHS["whatsapp"]


# ── HELPERS ────────────────────────────────────────────────

WHATSAPP_LINE_RE = re.compile(
    r"^\[(?P<date>[^,\]]+),\s*(?P<time>[^\]]+)\]\s*(?P<name>[^:]+):\s*(?P<message>.*)$"
)


def parse_whatsapp_date(date_str):
    """
    Parses WhatsApp export dates.
    Tries DD/MM/YYYY first, then US M/D/YY.
    """
    for fmt in ("%d/%m/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def process_whatsapp_file(filepath):
    """
    Reads one WhatsApp _chat.txt export file.
    Returns one chunk per chat with all messages grouped.
    """
    filename = os.path.basename(filepath)
    chat_name = filename[:-9] if filename.endswith("_chat.txt") else os.path.splitext(filename)[0]

    is_priority = any(p.lower() in chat_name.lower() for p in PRIORITY_PROJECTS)

    messages = []
    message_dates = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                match = WHATSAPP_LINE_RE.match(line)

                if not match:
                    continue

                date_obj = parse_whatsapp_date(match.group("date"))
                if date_obj is None:
                    continue

                message = match.group("message").strip()
                if message == "<Media omitted>":
                    message = "[media file]"

                name = match.group("name").strip()
                messages.append(f"[{date_obj.strftime('%Y-%m-%d')}] {name}: {message}")
                message_dates.append(date_obj)
    except Exception as e:
        print(f"    Could not read {filepath}: {e}")
        return None

    if not messages:
        return None

    start_date = min(message_dates).strftime("%Y-%m-%d")
    end_date = max(message_dates).strftime("%Y-%m-%d")
    date_range = f"{start_date} to {end_date}"

    chunk = {
        "text": f"WhatsApp chat: {chat_name}\nDate range: {date_range}\n\n" + "\n".join(messages),
        "metadata": {
            "source": "whatsapp",
            "chat_name": chat_name,
            "date": start_date,
            "date_range": date_range,
            "message_count": len(messages),
            "priority": "high" if is_priority else "normal",
            "modality": "text",
            "phase2": False,
        }
    }

    return chunk


# ── MAIN PARSER ────────────────────────────────────────────

def parse_whatsapp_export(whatsapp_path=WHATSAPP_PATH):
    """
    Walks through the entire WhatsApp export folder
    and processes every *_chat.txt file.
    """
    chunks = []

    if not os.path.exists(whatsapp_path):
        print(f"No WhatsApp export found at {whatsapp_path}")
        print("Place exported WhatsApp _chat.txt files in OTHER_PATHS['whatsapp']")
        return chunks

    print(f"Scanning WhatsApp export: {whatsapp_path}")

    chat_files = 0

    for root, dirs, files in os.walk(whatsapp_path):
        for filename in files:
            if not filename.endswith("_chat.txt"):
                continue

            filepath = os.path.join(root, filename)
            chunk = process_whatsapp_file(filepath)

            if chunk is None:
                continue

            chunks.append(chunk)
            chat_files += 1
            print(f"  Chat: {chunk['metadata']['chat_name']} ({chunk['metadata']['message_count']} messages)")

    print(f"\nDone!")
    print(f"Chats parsed:  {chat_files}")
    print(f"Total chunks:  {len(chunks)}")

    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_whatsapp_export()

    if chunks:
        print(f"\n── FIRST CHUNK PREVIEW ──")
        print(f"Chat:      {chunks[0]['metadata']['chat_name']}")
        print(f"Date:      {chunks[0]['metadata']['date']}")
        print(f"Priority:  {chunks[0]['metadata']['priority']}")
        print(f"Messages:  {chunks[0]['metadata']['message_count']}")
        print(f"Preview:\n{chunks[0]['text'][:300]}...")
