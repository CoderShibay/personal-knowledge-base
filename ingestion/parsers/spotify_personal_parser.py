import os
import sys
import json
import zipfile
from datetime import datetime

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import OTHER_PATHS

SPOTIFY_PATH         = OTHER_PATHS["spotify"]
SPOTIFY_PERSONAL_ZIP = os.path.join(SPOTIFY_PATH, "my_spotify_data_personal.zip")

_SOCIAL_CONNECT_FILE = "Spotify Technical Log Information/SocialConnectSessionCreated.json"
_ON_REPEAT_FILE      = "Spotify Technical Log Information/OnRepeatContents.json"


def _parse_utc(ts_str):
    try:
        return ts_str[:10]
    except Exception:
        return "unknown"


# ── MAIN PARSER ────────────────────────────────────────────

def parse_spotify_personal(zip_path=SPOTIFY_PERSONAL_ZIP):
    chunks = []

    if not os.path.exists(zip_path):
        print(f"No Spotify personal data zip found at {zip_path}")
        return chunks

    print(f"Scanning Spotify personal data: {zip_path}")

    try:
        z = zipfile.ZipFile(zip_path)
    except Exception as e:
        print(f"  Could not open zip: {e}")
        return chunks

    all_names = z.namelist()

    # ── Social Connect Sessions ─────────────────────────────
    if _SOCIAL_CONNECT_FILE in all_names:
        try:
            sessions = json.loads(z.read(_SOCIAL_CONNECT_FILE))
        except Exception:
            sessions = []

        if isinstance(sessions, list) and sessions:
            lines = []
            dates = []
            type_counts = {}

            for s in sessions:
                ts      = _parse_utc(s.get("timestamp_utc", ""))
                stype   = s.get("message_session_type", "unknown")
                platform = s.get("message_client_platform", "unknown")
                dates.append(ts)
                type_counts[stype] = type_counts.get(stype, 0) + 1
                lines.append(f"[{ts}] {stype} session on {platform}")

            type_summary = ", ".join(f"{k}: {v}" for k, v in sorted(type_counts.items()))
            start = min(dates)
            end   = max(dates)

            chunks.append({
                "text": f"Spotify social listening sessions — {len(sessions)} sessions "
                        f"({start} to {end})\n"
                        f"Types: {type_summary}\n\n"
                        + "\n".join(lines),
                "metadata": {
                    "source":        "spotify_social",
                    "date":          start,
                    "date_range":    f"{start} to {end}",
                    "session_count": len(sessions),
                    "priority":      "normal",
                    "modality":      "text",
                    "phase2":        False,
                },
            })
            print(f"  Social sessions: {len(sessions)}")

    # ── On Repeat Contents ──────────────────────────────────
    if _ON_REPEAT_FILE in all_names:
        try:
            on_repeat = json.loads(z.read(_ON_REPEAT_FILE))
        except Exception:
            on_repeat = []

        if isinstance(on_repeat, list) and on_repeat:
            lines = []
            dates = []

            for record in on_repeat:
                ts      = _parse_utc(record.get("timestamp_utc", ""))
                mix_id  = record.get("message_mix_id", "unknown")
                rtype   = record.get("message_type", "unknown")
                tracks  = record.get("message_contents", [])
                dates.append(ts)

                track_lines = "\n".join(f"  {t}" for t in tracks)
                lines.append(
                    f"[{ts}] On Repeat snapshot — mix {mix_id} ({rtype})\n"
                    f"{track_lines}"
                )

            start = min(dates)
            end   = max(dates)

            chunks.append({
                "text": f"Spotify On Repeat — {len(on_repeat)} snapshot(s) "
                        f"({start} to {end})\n"
                        "Note: track IDs are Spotify URIs, not resolved to names.\n\n"
                        + "\n\n".join(lines),
                "metadata": {
                    "source":         "spotify_on_repeat",
                    "date":           start,
                    "date_range":     f"{start} to {end}",
                    "snapshot_count": len(on_repeat),
                    "priority":       "normal",
                    "modality":       "text",
                    "phase2":         False,
                },
            })
            print(f"  On Repeat snapshots: {len(on_repeat)}")

    z.close()
    print(f"Spotify personal total chunks: {len(chunks)}")
    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_spotify_personal()
    print(f"\nTotal chunks: {len(chunks)}")
    for c in chunks:
        print(f"\n── {c['metadata']['source'].upper()} PREVIEW ──\n{c['text'][:400]}")
