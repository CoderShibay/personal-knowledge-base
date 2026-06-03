import os
import sys
import json

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import OTHER_PATHS

# ── CONFIGURATION ──────────────────────────────────────────

SPOTIFY_PATH = OTHER_PATHS["spotify"]

# Extended Streaming History filenames
_HISTORY_PREFIX = "Streaming_History_"


# ── HELPERS ────────────────────────────────────────────────

def ms_to_mmss(ms):
    total_seconds = int(ms // 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def _parse_entry(row):
    ts        = (row.get("ts") or "").strip()
    artist    = (row.get("master_metadata_album_artist_name") or "").strip()
    track     = (row.get("master_metadata_track_name") or "").strip()
    album     = (row.get("master_metadata_album_album_name") or "").strip()
    ms_played = row.get("ms_played", 0)
    skipped   = bool(row.get("skipped", False))

    # Drop podcasts, audiobooks, and entries with no track metadata
    if not ts or not artist or not track:
        return None

    try:
        ms_played = int(ms_played or 0)
    except Exception:
        return None

    # Drop plays under 30 seconds — these are accidental taps or buffering
    if ms_played < 30000:
        return None

    return {
        "date":     ts[:10],
        "artist":   artist,
        "track":    track,
        "album":    album,
        "ms":       ms_played,
        "skipped":  skipped,
    }


def _read_json(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"    Could not read {filepath}: {e}")
        return []


def _format_line(entry):
    """Format one track as a single line for the chunk text."""
    time_str = ms_to_mmss(entry["ms"])
    album_part = f" / {entry['album']}" if entry["album"] else ""
    skip_tag = " [skip]" if entry["skipped"] else ""
    return f"{entry['artist']} - {entry['track']}{album_part} ({time_str}){skip_tag}"


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
            if not (filename.startswith(_HISTORY_PREFIX) and filename.endswith(".json")):
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
        print("  No Streaming_History_*.json files found — zip may not be extracted yet")

    for date in sorted(daily):
        day_entries = daily[date]
        total_ms    = sum(e["ms"] for e in day_entries)
        total_min   = int(total_ms // 60000)
        skip_count  = sum(1 for e in day_entries if e["skipped"])

        lines = [_format_line(e) for e in day_entries]

        header = f"Spotify listening — {date} ({len(day_entries)} tracks, {total_min} min"
        if skip_count:
            header += f", {skip_count} skipped"
        header += ")"

        chunks.append({
            "text": header + "\n\n" + "\n".join(lines),
            "metadata": {
                "source":        "spotify",
                "date":          date,
                "track_count":   len(day_entries),
                "total_minutes": total_min,
                "skip_count":    skip_count,
                "priority":      "normal",
                "modality":      "text",
                "phase2":        False,
            },
        })

    print(f"\nDone!")
    print(f"Files parsed:  {files_parsed}")
    print(f"Total days:    {len(chunks)}")
    print(f"Total tracks:  {sum(c['metadata']['track_count'] for c in chunks)}")
    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_spotify_export()

    total_tracks = sum(c["metadata"]["track_count"] for c in chunks)
    total_skips  = sum(c["metadata"]["skip_count"]  for c in chunks)
    print(f"\nTotal days:    {len(chunks)}")
    print(f"Total tracks:  {total_tracks}")
    print(f"Total skipped: {total_skips}")

    if chunks:
        print(f"\n── FIRST CHUNK PREVIEW ──")
        print(chunks[0]["text"][:400])
        print()
        print(f"── LARGEST DAY ──")
        biggest = max(chunks, key=lambda c: c["metadata"]["track_count"])
        print(biggest["text"][:400])
