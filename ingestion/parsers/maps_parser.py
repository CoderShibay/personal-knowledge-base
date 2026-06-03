import os
import sys
import ijson
from datetime import datetime

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import ACCOUNT_PATHS

# ── CONFIGURATION ──────────────────────────────────────────

ACCOUNTS = ACCOUNT_PATHS

RECORDS_RELATIVE_PATHS = [
    os.path.join("Takeout", "Location History (Timeline)", "Records.json"),
    os.path.join("Takeout", "Location History", "Records.json"),
    "Records.json",
]


# ── HELPERS ────────────────────────────────────────────────

def find_records_file(account_path):
    for rel_path in RECORDS_RELATIVE_PATHS:
        records_path = os.path.join(account_path, rel_path)
        if os.path.exists(records_path):
            return records_path
    return None


def parse_timestamp_to_date(timestamp):
    try:
        dt = datetime.fromisoformat(timestamp.rstrip("Z"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


# ── FILE PROCESSOR ─────────────────────────────────────────

def process_records_file(records_path, account_name="unknown"):
    chunks = []
    daily = {}
    processed_points = 0

    try:
        with open(records_path, "rb") as f:
            for location in ijson.items(f, "locations.item"):
                processed_points += 1
                if processed_points % 100_000 == 0:
                    print(f"    Streamed {processed_points:,} points...")

                timestamp = location.get("timestamp")
                lat_e7 = location.get("latitudeE7")
                lng_e7 = location.get("longitudeE7")

                if timestamp is None or lat_e7 is None or lng_e7 is None:
                    continue

                date = parse_timestamp_to_date(timestamp)
                if date is None:
                    continue

                try:
                    lat = float(lat_e7) / 1e7
                    lng = float(lng_e7) / 1e7
                except Exception:
                    continue

                if date not in daily:
                    daily[date] = {"point_count": 0, "lat_min": lat, "lat_max": lat, "lng_min": lng, "lng_max": lng}

                day = daily[date]
                day["point_count"] += 1
                day["lat_min"] = min(day["lat_min"], lat)
                day["lat_max"] = max(day["lat_max"], lat)
                day["lng_min"] = min(day["lng_min"], lng)
                day["lng_max"] = max(day["lng_max"], lng)

    except Exception as e:
        print(f"    Could not read {records_path}: {e}")
        return chunks

    if not daily:
        return chunks

    print(f"  Streamed {processed_points:,} points → {len(daily)} days")

    for date, day in daily.items():
        text = (
            f"Location history — {date}\n\n"
            f"Recorded {day['point_count']} location points.\n"
            f"Approximate area: lat {day['lat_min']:.2f} to {day['lat_max']:.2f}, "
            f"lng {day['lng_min']:.2f} to {day['lng_max']:.2f}"
        )

        chunk = {
            "text": text,
            "metadata": {
                "source": "google_maps",
                "account": account_name,
                "date": date,
                "point_count": int(day["point_count"]),
                "lat_min": float(day["lat_min"]),
                "lat_max": float(day["lat_max"]),
                "lng_min": float(day["lng_min"]),
                "lng_max": float(day["lng_max"]),
                "priority": "normal",
                "modality": "text",
                "phase2": False,
            }
        }

        chunks.append(chunk)

    return chunks


# ── MAIN PARSER ────────────────────────────────────────────

def parse_maps_export():
    """
    Walks all account paths and parses Google Maps location history exports.
    """
    all_chunks = []

    for account_name, account_path in ACCOUNTS.items():
        print(f"\nProcessing Maps export for: {account_name}")

        records_path = find_records_file(account_path)

        if records_path is None:
            print(f"  No Maps Records.json found in {account_path}")
            continue

        print(f"  Found: {records_path}")

        chunks = process_records_file(records_path, account_name)
        all_chunks.extend(chunks)
        print(f"  Daily chunks: {len(chunks)}")

    all_chunks.sort(key=lambda c: c["metadata"]["date"])

    print(f"\nDone! Total Maps chunks: {len(all_chunks)}")
    return all_chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_maps_export()

    if chunks:
        print(f"\n── FIRST CHUNK PREVIEW ──")
        print(f"Date:       {chunks[0]['metadata']['date']}")
        print(f"Points:     {chunks[0]['metadata']['point_count']}")
        print(f"Area:       lat {chunks[0]['metadata']['lat_min']:.2f} to {chunks[0]['metadata']['lat_max']:.2f}, "
              f"lng {chunks[0]['metadata']['lng_min']:.2f} to {chunks[0]['metadata']['lng_max']:.2f}")
        print(f"Preview:\n{chunks[0]['text']}")
