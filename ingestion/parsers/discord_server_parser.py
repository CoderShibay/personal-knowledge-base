import os
import json
import sys
from datetime import datetime

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import OTHER_PATHS, PRIORITY_PROJECTS

# ── CONFIGURATION ──────────────────────────────────────────
# Put your DiscordChatExporter exports inside this folder
# one subfolder per server

DISCORD_SERVERS_PATH = os.path.join(OTHER_PATHS["discord"], "servers")


# ── HELPERS ────────────────────────────────────────────────

def parse_timestamp(ts):
    try:
        return ts[:10]
    except:
        return "unknown"


def load_json(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  Could not read {filepath}: {e}")
        return None


# ── CHANNEL PARSER ─────────────────────────────────────────

def parse_server_channel(json_path, server_name):
    """
    Parses one channel export from DiscordChatExporter.
    Contains messages from ALL users not just you.
    """
    data = load_json(json_path)
    if not data:
        return None

    # DiscordChatExporter wraps everything in a root object
    channel_info = data.get("channel", {})
    channel_name = channel_info.get("name", os.path.basename(json_path))
    messages     = data.get("messages", [])

    if not messages:
        return None

    conversation_lines = []
    dates = []

    for msg in messages:
        content   = msg.get("content", "").strip()
        timestamp = msg.get("timestamp", "")
        date      = parse_timestamp(timestamp)
        author    = msg.get("author", {})
        username  = author.get("name", "Unknown")

        if not content:
            # check if it's an attachment only message
            attachments = msg.get("attachments", [])
            if attachments:
                names = [a.get("fileName", "file") for a in attachments]
                content = f"[attachments: {', '.join(names)}]"
            else:
                continue

        # include reactions if any — interesting signal
        reactions = msg.get("reactions", [])
        reaction_text = ""
        if reactions:
            reaction_text = " " + " ".join(
                f"{r.get('emoji', {}).get('name', '')}x{r.get('count', 0)}"
                for r in reactions
            )

        conversation_lines.append(
            f"[{date}] {username}: {content}{reaction_text}"
        )
        dates.append(date)

    if not conversation_lines:
        return None

    full_text  = "\n".join(conversation_lines)
    date_range = f"{min(dates)} to {max(dates)}" if dates else "unknown"

    is_priority = any(
        p.lower() in channel_name.lower() or
        p.lower() in server_name.lower()
        for p in PRIORITY_PROJECTS
    )

    chunk = {
        "text": f"Discord server: {server_name}\n"
                f"Channel: #{channel_name}\n"
                f"Date range: {date_range}\n\n"
                f"{full_text}",
        "metadata": {
            "source":        "discord_server",
            "server_name":   server_name,
            "channel_name":  channel_name,
            "date_range":    date_range,
            "message_count": len(conversation_lines),
            "priority":      "high" if is_priority else "normal",
            "phase2":        False,
        }
    }

    return chunk


# ── SERVER PARSER ──────────────────────────────────────────

def parse_server(server_folder):
    """
    Parses all channels inside one server folder.
    """
    chunks      = []
    server_name = os.path.basename(server_folder)

    print(f"  Server: {server_name}")

    # find all json files in the server folder
    json_files = [
        os.path.join(server_folder, f)
        for f in os.listdir(server_folder)
        if f.endswith(".json")
    ]

    if not json_files:
        print(f"    No channel exports found")
        return chunks

    for json_path in json_files:
        chunk = parse_server_channel(json_path, server_name)

        if chunk is None:
            continue

        chunks.append(chunk)
        print(f"    Parsed: #{chunk['metadata']['channel_name']} "
              f"({chunk['metadata']['message_count']} messages)")

    return chunks


# ── MAIN PARSER ────────────────────────────────────────────

def parse_all_servers(servers_path=DISCORD_SERVERS_PATH):
    """
    Walks through all server folders and parses every channel.
    """
    all_chunks = []

    if not os.path.exists(servers_path):
        print(f"No Discord servers folder found at {servers_path}")
        print(f"Please export your servers using DiscordChatExporter")
        print(f"and place them in: {servers_path}")
        return all_chunks

    server_folders = [
        os.path.join(servers_path, d)
        for d in os.listdir(servers_path)
        if os.path.isdir(os.path.join(servers_path, d))
    ]

    if not server_folders:
        print(f"No server folders found in {servers_path}")
        return all_chunks

    print(f"Found {len(server_folders)} server(s)\n")

    for server_folder in server_folders:
        chunks = parse_server(server_folder)
        all_chunks.extend(chunks)
        print(f"  Total chunks from this server: {len(chunks)}\n")

    print(f"Done! Total server chunks: {len(all_chunks)}")
    return all_chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_all_servers()

    if chunks:
        print(f"\n── FIRST CHUNK PREVIEW ──")
        print(f"Server:   {chunks[0]['metadata']['server_name']}")
        print(f"Channel:  {chunks[0]['metadata']['channel_name']}")
        print(f"Messages: {chunks[0]['metadata']['message_count']}")
        print(f"Preview:\n{chunks[0]['text'][:300]}...")