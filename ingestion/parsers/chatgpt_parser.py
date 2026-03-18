import json
import os
from datetime import datetime

CHATGPT_DATA_PATH = os.path.expanduser("~/personal-kb/data/chatgpt/conversations.json")

PRIORITY_PROJECTS = ["Side Projects and Life"]

SKIP_EXTENSIONS = [
    ".mkv", ".mp4", ".avi", ".mov", ".torrent",
    ".iso", ".zip", ".rar", ".exe", ".dmg"
]

def parse_chatgpt_export(filepath=CHATGPT_DATA_PATH):
    with open(filepath, "r", encoding="utf-8") as f:
        conversations = json.load(f)

    print(f"Found {len(conversations)} conversations in ChatGPT export")

    chunks = []

    for convo in conversations:
        title = convo.get("title", "Untitled")
        raw_time = convo.get("create_time", 0)
        date = datetime.fromtimestamp(raw_time).strftime("%Y-%m-%d") if raw_time else "unknown"
        is_priority = any(p.lower() in title.lower() for p in PRIORITY_PROJECTS)

        messages_dict = convo.get("mapping", {})
        conversation_text = []

        for node in messages_dict.values():
            message = node.get("message")
            if not message:
                continue

            role = message.get("author", {}).get("role", "")
            content = message.get("content", {})
            parts = content.get("parts", [])

            if role not in ["user", "assistant"]:
                continue

            text = " ".join(str(p) for p in parts if isinstance(p, str))
            text = text.strip()

            if not text:
                continue

            label = "You" if role == "user" else "ChatGPT"
            conversation_text.append(f"{label}: {text}")

        if not conversation_text:
            continue

        full_text = "\n".join(conversation_text)

        chunk = {
            "text": full_text,
            "metadata": {
                "source": "chatgpt",
                "title": title,
                "date": date,
                "priority": "high" if is_priority else "normal",
                "char_count": len(full_text)
            }
        }

        chunks.append(chunk)

        priority_label = "PRIORITY" if is_priority else ""
        print(f"  Parsed: '{title}' ({date}) {priority_label}")

    print(f"\nDone! {len(chunks)} conversations parsed.")
    print(f"Priority conversations: {sum(1 for c in chunks if c['metadata']['priority'] == 'high')}")

    return chunks

if __name__ == "__main__":
    chunks = parse_chatgpt_export()

    if chunks:
        print("\n── PREVIEW OF FIRST CHUNK ──")
        print(f"Title: {chunks[0]['metadata']['title']}")
        print(f"Date: {chunks[0]['metadata']['date']}")
        print(f"Priority: {chunks[0]['metadata']['priority']}")
        print(f"Text preview: {chunks[0]['text'][:300]}...")
