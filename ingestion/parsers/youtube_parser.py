import os
import sys
import re
from datetime import datetime
import html

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import ACCOUNT_PATHS

# ── CONFIGURATION ──────────────────────────────────────────

WATCH_REL_PATH  = "Takeout/YouTube and YouTube Music/history/watch-history.html"
SEARCH_REL_PATH = "Takeout/YouTube and YouTube Music/history/search-history.html"

# Matches one content cell: the 6-col body-1 div containing the entry text
_CELL_RE = re.compile(
    r'content-cell mdl-cell mdl-cell--6-col mdl-typography--body-1">(.*?)</div>',
    re.DOTALL,
)

# Date like "12 Apr 2023, 07:27:45 GMT+06:00" or "23 Feb 2023, 17:03:50 GMT+06:00"
_DATE_RE = re.compile(
    r'(\d{1,2}\s+\w+\s+\d{4}),\s*\d{2}:\d{2}:\d{2}\s+GMT'
)

_TAG_RE = re.compile(r'<[^>]+>')


# ── HELPERS ────────────────────────────────────────────────

def _read_html(filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        print(f"    Could not read {filepath}: {e}")
        return ""


def _parse_date(cell_text):
    m = _DATE_RE.search(cell_text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1).strip(), "%d %b %Y").strftime("%Y-%m-%d")
    except Exception:
        return None


def _strip_tags(text):
    return html.unescape(_TAG_RE.sub("", text)).strip()


def _first_link_text(cell_raw):
    m = re.search(r'<a[^>]*>(.*?)</a>', cell_raw, re.DOTALL)
    return _strip_tags(m.group(1)) if m else ""


def _second_link_text(cell_raw):
    links = re.findall(r'<a[^>]*>(.*?)</a>', cell_raw, re.DOTALL)
    return _strip_tags(links[1]) if len(links) >= 2 else ""


# ── PROCESSORS ─────────────────────────────────────────────

def process_watch_html(content, account_name):
    cells = _CELL_RE.findall(content)
    grouped = {}

    for cell in cells:
        if not (cell.startswith("Watched ") or cell.startswith("Watched\xa0")):
            continue

        date = _parse_date(cell)
        if not date:
            continue

        video_title = _first_link_text(cell)
        if not video_title:
            continue

        channel = _second_link_text(cell) or "Unknown Channel"
        grouped.setdefault(date, []).append(f"{channel}: {video_title}")

    chunks = []
    for date in sorted(grouped):
        lines = grouped[date]
        chunks.append({
            "text": f"YouTube watch history — {date} ({account_name})\n\n" + "\n".join(lines),
            "metadata": {
                "source": "youtube_watch",
                "account": account_name,
                "date": date,
                "item_count": len(lines),
                "priority": "normal",
                "modality": "text",
                "phase2": False,
            },
        })
    return chunks


def process_search_html(content, account_name):
    cells = _CELL_RE.findall(content)
    grouped = {}

    for cell in cells:
        if not cell.startswith("Searched for"):
            continue

        date = _parse_date(cell)
        if not date:
            continue

        query = _first_link_text(cell)
        if not query:
            continue

        grouped.setdefault(date, []).append(query)

    chunks = []
    for date in sorted(grouped):
        queries = grouped[date]
        chunks.append({
            "text": f"YouTube searches — {date} ({account_name})\n\n" + "\n".join(queries),
            "metadata": {
                "source": "youtube_search",
                "account": account_name,
                "date": date,
                "item_count": len(queries),
                "priority": "normal",
                "modality": "text",
                "phase2": False,
            },
        })
    return chunks


# ── MAIN PARSER ────────────────────────────────────────────

def parse_youtube_export():
    watch_chunks  = []
    search_chunks = []

    print("Scanning YouTube exports across all account paths...")

    for account_name, account_path in ACCOUNT_PATHS.items():
        watch_path  = os.path.join(account_path, WATCH_REL_PATH)
        search_path = os.path.join(account_path, SEARCH_REL_PATH)

        found_any = False

        if os.path.exists(watch_path):
            found_any = True
            print(f"  [{account_name}] Found watch history")
            content = _read_html(watch_path)
            watch_chunks.extend(process_watch_html(content, account_name))

        if os.path.exists(search_path):
            found_any = True
            print(f"  [{account_name}] Found search history")
            content = _read_html(search_path)
            search_chunks.extend(process_search_html(content, account_name))

        if not found_any:
            print(f"  [{account_name}] No YouTube Takeout history files found")

    chunks = watch_chunks + search_chunks

    print("\nDone!")
    print(f"Watch chunks:  {len(watch_chunks)}")
    print(f"Search chunks: {len(search_chunks)}")
    print(f"Total chunks:  {len(chunks)}")

    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_youtube_export()

    if chunks:
        print(f"\n── FIRST CHUNK PREVIEW ──")
        c = chunks[0]
        print(f"Source:  {c['metadata']['source']}")
        print(f"Account: {c['metadata']['account']}")
        print(f"Date:    {c['metadata']['date']}")
        print(f"Items:   {c['metadata']['item_count']}")
        print(f"Preview:\n{c['text'][:300]}...")
