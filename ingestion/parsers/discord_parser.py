import os
import json
import sys
from datetime import datetime

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import OTHER_PATHS, PRIORITY_PROJECTS

# ── CONFIGURATION ──────────────────────────────────────────

DISCORD_PATH = OTHER_PATHS["discord"]


# ── HELPERS ────────────────────────────────────────────────

def parse_timestamp(ts):
    """
    Converts Discord timestamp to a readable date.
    Discord uses ISO 8601 format like "2023-08-14T10:23:45.123000+00:00"
    """
    try:
        return ts[:10]
    except:
        return "unknown"


def load_json(filepath):
    """Safely loads a JSON file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  Could not read {filepath}: {e}")
        return None


# ── CHANNEL PARSER ─────────────────────────────────────────

def parse_channel(channel_folder):
    """
    Parses one channel or DM folder.
    Returns a chunk with all messages grouped together.
    """
    channel_json  = os.path.join(channel_folder, "channel.json")
    messages_json = os.path.join(channel_folder, "messages.json")

    if not os.path.exists(messages_json):
        return None

    # load channel info
    channel_info = load_json(channel_json) or {}
    channel_name = channel_info.get("name", "Unknown Channel")
    channel_type = channel_info.get("type", "unknown")
    guild        = channel_info.get("guild", {})
    server_name  = guild.get("name", "Direct Message") if guild else "Direct Message"

    # load messages
    messages_data = load_json(messages_json)
    if not messages_data:
        return None

    # messages.json is a list of message objects
    if not isinstance(messages_data, list):
        return None

    if len(messages_data) == 0:
        return None

    # build conversation text
    conversation_lines = []
    dates = []

    for msg in messages_data:
        content   = msg.get("Contents", "").strip()
        timestamp = msg.get("Timestamp", "")
        date      = parse_timestamp(timestamp)

        if not content:
            continue

        # check for attachments
        attachments = msg.get("Attachments", "")
        if attachments:
            content += f" [attachment: {attachments}]"

        conversation_lines.append(f"[{date}] You: {content}")
        dates.append(date)

    if not conversation_lines:
        return None

    full_text = "\n".join(conversation_lines)
    date_range = f"{min(dates)} to {max(dates)}" if dates else "unknown"

    # check if priority
    is_priority = any(
        p.lower() in channel_name.lower() or
        p.lower() in server_name.lower()
        for p in PRIORITY_PROJECTS
    )

    chunk = {
        "text": f"Discord channel: {channel_name}\n"
                f"Server: {server_name}\n"
                f"Date range: {date_range}\n\n"
                f"{full_text}",
        "metadata": {
            "source":       "discord",
            "channel_name": channel_name,
            "server_name":  server_name,
            "channel_type": channel_type,
            "date_range":   date_range,
            "message_count":len(conversation_lines),
            "priority":     "high" if is_priority else "normal",
            "phase2":       False,
        }
    }

    return chunk


# ── MAIN PARSER ────────────────────────────────────────────

def parse_discord_export(discord_path=DISCORD_PATH):
    """
    Walks through the Discord export and parses every channel and DM.
    """
    chunks = []

    # Discord messages live in a messages/ subfolder
    messages_path = os.path.join(discord_path, "package", "messages")

    if not os.path.exists(messages_path):
        # try without package subfolder
        messages_path = os.path.join(discord_path, "messages")

    if not os.path.exists(messages_path):
        print(f"No Discord messages folder found in {discord_path}")
        return chunks

    print(f"Scanning Discord messages: {messages_path}")

    # each subfolder is one channel or DM
    channel_folders = [
        os.path.join(messages_path, d)
        for d in os.listdir(messages_path)
        if os.path.isdir(os.path.join(messages_path, d))
    ]

    print(f"Found {len(channel_folders)} channels/DMs")

    for channel_folder in channel_folders:
        chunk = parse_channel(channel_folder)

        if chunk is None:
            continue

        chunks.append(chunk)
        priority_label = "PRIORITY" if chunk["metadata"]["priority"] == "high" else ""
        print(f"  Parsed: {chunk['metadata']['server_name']} / "
              f"{chunk['metadata']['channel_name']} "
              f"({chunk['metadata']['message_count']} messages) {priority_label}")

    print(f"\nDone! Total Discord chunks: {len(chunks)}")
    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_discord_export()

    if chunks:
        print(f"\n── FIRST CHUNK PREVIEW ──")
        print(f"Server:   {chunks[0]['metadata']['server_name']}")
        print(f"Channel:  {chunks[0]['metadata']['channel_name']}")
        print(f"Messages: {chunks[0]['metadata']['message_count']}")
        print(f"Preview:\n{chunks[0]['text'][:300]}...")