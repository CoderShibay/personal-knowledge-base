import os
import sys
import json
from datetime import datetime

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import OTHER_PATHS

# ── CONFIGURATION ──────────────────────────────────────────

SPOTIFY_PATH = OTHER_PATHS["spotify"]

# Extended Streaming History uses "Streaming_History_Audio_YYYY.json"
# Basic export used "StreamingHistory_music_N.json" — that format is no longer exported
_AUDIO_PREFIX = "Streaming_History_Audio_"


# ── HELPERS ────────────────────────────────────────────────

def ms_to_mmss(ms):
    total_seconds = int(ms // 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def _parse_entry(row):
    # Extended format fields
    ts         = (row.get("ts") or "").strip()
    artist     = (row.get("master_metadata_album_artist_name") or "").strip()
    track      = (row.get("master_metadata_track_name") or "").strip()
    ms_played  = row.get("ms_played", 0)

    # Skip podcasts, audiobooks, and missing track metadata
    if not ts or not artist or not track:
        return None

    try:
        ms_played = int(ms_played or 0)
    except Exception:
        return None

    if ms_played < 30000:
        return None

    # ts is ISO: "2022-06-12T02:58:01Z"
    date = ts[:10]

    return {"date": date, "artist": artist, "track": track, "ms_played": ms_played}


def _read_json(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"    Could not read {filepath}: {e}")
        return []


# ── MAIN PARSER ────────────────────────────────────────────

def parse_spotify_export(spotify_path=SPOTIFY_PATH):
    chunks = []

    if not os.path.exists(spotify_path):
        print(f"No Spotify export found at {spotify_path}")
        return chunks

    print(f"Scanning Spotify export: {spotify_path}")

    daily = {}
    files_parsed = 0

    for root, dirs, files in os.walk(spotify_path):
        for filename in sorted(files):
            if not (filename.startswith(_AUDIO_PREFIX) and filename.endswith(".json")):
                continue

            filepath = os.path.join(root, filename)
            rows = _read_json(filepath)
            kept = 0

            for row in rows:
                entry = _parse_entry(row)
                if entry is None:
                    continue
                daily.setdefault(entry["date"], []).append(entry)
                kept += 1

            files_parsed += 1
            print(f"  {filename}: {kept} kept / {len(rows)} total")

    if files_parsed == 0:
        print("  No Streaming_History_Audio_*.json files found — zip may not be extracted yet")

    for date in sorted(daily):
        day_entries = daily[date]
        lines = []
        total_ms = 0

        for entry in day_entries:
            lines.append(f"{entry['artist']} - {entry['track']} ({ms_to_mmss(entry['ms_played'])})")
            total_ms += entry["ms_played"]

        chunks.append({
            "text": f"Spotify listening — {date}\n\n" + "\n".join(lines),
            "metadata": {
                "source": "spotify",
                "date": date,
                "track_count": len(day_entries),
                "total_minutes": int(total_ms // 60000),
                "priority": "normal",
                "modality": "text",
                "phase2": False,
            },
        })

    print(f"\nDone!")
    print(f"Files parsed:  {files_parsed}")
    print(f"Total days:    {len(chunks)}")
    print(f"Total chunks:  {len(chunks)}")
    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_spotify_export()

    total_tracks = sum(c["metadata"]["track_count"] for c in chunks)
    print(f"\nTotal days:   {len(chunks)}")
    print(f"Total tracks: {total_tracks}")

    if chunks:
        print(f"\n── FIRST CHUNK PREVIEW ──")
        print(f"Date:    {chunks[0]['metadata']['date']}")
        print(f"Preview:\n{chunks[0]['text'][:300]}...")
