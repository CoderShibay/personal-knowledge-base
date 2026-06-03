import os
import sys
import json
from datetime import datetime, timedelta

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import ACCOUNT_PATHS

# ── CONFIGURATION ──────────────────────────────────────────

CHROME_REL_PATH = "Takeout/Chrome/History.json"
# Takeout JSON uses Unix microseconds (since 1970), NOT Windows FILETIME (since 1601)
_UNIX_EPOCH = datetime(1970, 1, 1)


# ── HELPERS ────────────────────────────────────────────────

def read_json(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"    Could not read {filepath}: {e}")
        return {}


def extract_date(time_usec):
    try:
        dt = _UNIX_EPOCH + timedelta(microseconds=int(time_usec))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def should_skip_url(url):
    return (
        url.startswith("chrome://")
        or url.startswith("chrome-extension://")
        or url.startswith("about:")
    )


def process_history_entries(entries, account_name):
    grouped = {}

    for entry in entries:
        title = (entry.get("title") or "").strip()
        if not title:
            continue

        transition = (entry.get("page_transition_qualifier") or entry.get("page_transition") or "").strip()
        if transition == "RELOAD":
            continue

        url = (entry.get("url") or "").strip()
        if not url or should_skip_url(url):
            continue

        date = extract_date(entry.get("time_usec"))
        if not date:
            continue

        if date not in grouped:
            grouped[date] = []

        if title:
            grouped[date].append(f"{title}: {url}")
        else:
            grouped[date].append(url)

    chunks = []

    for date in sorted(grouped.keys()):
        lines = grouped[date]
        chunk = {
            "text": f"Chrome history — {date} ({account_name})\n\n" + "\n".join(lines),
            "metadata": {
                "source": "chrome_history",
                "account": account_name,
                "date": date,
                "item_count": len(lines),
                "priority": "normal",
                "modality": "text",
                "phase2": False,
            }
        }
        chunks.append(chunk)

    return chunks


# ── MAIN PARSER ────────────────────────────────────────────

def parse_chrome_export():
    # Walk all account paths and parse Chrome history from Google Takeout.
    chunks = []

    print("Scanning Chrome exports across all account paths...")

    for account_name, account_path in ACCOUNT_PATHS.items():
        history_path = os.path.join(account_path, CHROME_REL_PATH)

        if not os.path.exists(history_path):
            print(f"  [{account_name}] No Chrome Takeout history file found")
            continue

        print(f"  [{account_name}] Found Chrome history")

        data = read_json(history_path)
        entries = data.get("Browser History") or []

        if not isinstance(entries, list):
            print(f"    Invalid Browser History format in {history_path}")
            continue

        chunks.extend(process_history_entries(entries, account_name))

    chunks = sorted(chunks, key=lambda c: (c["metadata"]["date"], c["metadata"]["account"]))

    print("\nDone!")
    print(f"Total chunks: {len(chunks)}")

    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_chrome_export()
    total_visits = sum(chunk["metadata"].get("item_count", 0) for chunk in chunks)

    print(f"Total visits: {total_visits}")

    if chunks:
        print(f"\n── FIRST CHUNK PREVIEW ──")
        print(f"Account: {chunks[0]['metadata']['account']}")
        print(f"Date:    {chunks[0]['metadata']['date']}")
        print(f"Items:   {chunks[0]['metadata']['item_count']}")
        print(f"Preview:\n{chunks[0]['text'][:300]}...")
