import os
import json
import sys
import zipfile
from datetime import datetime

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import OTHER_PATHS, PRIORITY_PROJECTS

DISCORD_PATH         = OTHER_PATHS["discord"]
DISCORD_PERSONAL_ZIP = os.path.join(DISCORD_PATH, "personal", "package.zip")


def _parse_timestamp(ts):
    try:
        return ts[:10]
    except Exception:
        return "unknown"


# ── MAIN PARSER ────────────────────────────────────────────

def parse_discord_personal(zip_path=DISCORD_PERSONAL_ZIP):
    chunks = []

    if not os.path.exists(zip_path):
        print(f"No Discord personal export found at {zip_path}")
        return chunks

    print(f"Scanning Discord personal export: {zip_path}")

    try:
        z = zipfile.ZipFile(zip_path)
    except Exception as e:
        print(f"  Could not open zip: {e}")
        return chunks

    # Find all channel folders inside Messages/
    all_names    = z.namelist()
    channel_dirs = set()
    for name in all_names:
        parts = name.split("/")
        if len(parts) >= 3 and parts[0] == "Messages" and parts[1].startswith("c"):
            channel_dirs.add(parts[1])

    print(f"  Found {len(channel_dirs)} DM channel(s)")

    for channel_id in sorted(channel_dirs):
        msg_path = f"Messages/{channel_id}/messages.json"
        ch_path  = f"Messages/{channel_id}/channel.json"

        if msg_path not in all_names:
            continue

        # Read channel info
        channel_type = "DM"
        recipients   = []
        if ch_path in all_names:
            try:
                ch_data      = json.loads(z.read(ch_path))
                channel_type = ch_data.get("type", "DM")
                recipients   = ch_data.get("recipients", [])
            except Exception:
                pass

        # Read messages
        try:
            messages = json.loads(z.read(msg_path))
        except Exception as e:
            print(f"  Could not read {msg_path}: {e}")
            continue

        if not isinstance(messages, list) or not messages:
            continue

        lines = []
        dates = []

        for msg in messages:
            content     = (msg.get("Contents") or "").strip()
            timestamp   = msg.get("Timestamp", "")
            date        = _parse_timestamp(timestamp)
            attachments = (msg.get("Attachments") or "").strip()

            if not content and not attachments:
                continue

            line = f"[{date}] {content}"
            if attachments:
                line += f" [attachment: {attachments}]"

            lines.append(line)
            dates.append(date)

        if not lines:
            continue

        start_date = min(dates)
        end_date   = max(dates)
        date_range = f"{start_date} to {end_date}"

        # Use channel ID as name — personal export does not include display names
        channel_label = channel_id
        is_priority   = any(p.lower() in channel_id.lower() for p in PRIORITY_PROJECTS)

        recipient_note = ""
        if recipients:
            recipient_note = f"Recipients (IDs): {', '.join(str(r) for r in recipients)}\n"

        chunks.append({
            "text": f"Discord DM — channel {channel_label}\n"
                    f"{recipient_note}"
                    f"Type: {channel_type}\n"
                    f"Date range: {date_range}\n\n"
                    + "\n".join(lines),
            "metadata": {
                "source":        "discord_personal",
                "channel_id":    channel_id,
                "channel_type":  channel_type,
                "date":          start_date,
                "date_range":    date_range,
                "message_count": len(lines),
                "priority":      "high" if is_priority else "normal",
                "modality":      "text",
                "phase2":        False,
            },
        })

        label = " [PRIORITY]" if is_priority else ""
        print(f"  {channel_id} ({len(lines)} messages){label}")

    z.close()
    print(f"Discord personal total chunks: {len(chunks)}")
    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_discord_personal()
    print(f"\nTotal chunks: {len(chunks)}")
    if chunks:
        print(f"\n── FIRST CHUNK PREVIEW ──\n{chunks[0]['text'][:400]}")
