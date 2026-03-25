import os
import sys
import csv
from datetime import datetime

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import OTHER_PATHS, PRIORITY_PROJECTS

# ── CONFIGURATION ──────────────────────────────────────────

NOTION_PATH = OTHER_PATHS["notion"]


# ── HELPERS ────────────────────────────────────────────────

def read_markdown(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"    Could not read {filepath}: {e}")
        return ""


def read_csv(filepath):
    try:
        rows = []
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_text = " | ".join(
                    f"{k}: {v}"
                    for k, v in row.items()
                    if v and v.strip()
                )
                if row_text:
                    rows.append(row_text)
        return "\n".join(rows)
    except Exception as e:
        print(f"    Could not read {filepath}: {e}")
        return ""


# ── FILE PROCESSOR ─────────────────────────────────────────

def process_notion_file(filepath):
    """
    Reads one Notion export file.
    Handles both .md pages and .csv databases.
    """
    filename = os.path.basename(filepath)
    ext      = os.path.splitext(filename)[1].lower()

    # get the page title from filename
    # Notion adds a unique ID at the end like "Page Title abc123.md"
    # we strip that out to get the clean title
    title = os.path.splitext(filename)[0]
    if len(title) > 32 and title[-32:].replace("-", "").isalnum():
        title = title[:-33].strip()

    mod_time = os.path.getmtime(filepath)
    date     = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d")

    is_priority = any(p.lower() in title.lower() for p in PRIORITY_PROJECTS)

    if ext == ".md":
        text = read_markdown(filepath)
        file_type = "notion_page"
    elif ext == ".csv":
        text = read_csv(filepath)
        file_type = "notion_database"
    else:
        return None

    if not text:
        return None

    chunk = {
        "text": f"Notion page: {title}\nDate: {date}\n\n{text}",
        "metadata": {
            "source":    "notion",
            "title":     title,
            "file_type": file_type,
            "date":      date,
            "file_path": filepath,
            "priority":  "high" if is_priority else "normal",
            "phase2":    False,
        }
    }

    return chunk


# ── MAIN PARSER ────────────────────────────────────────────

def parse_notion_export(notion_path=NOTION_PATH):
    """
    Walks through the entire Notion export folder
    and processes every .md and .csv file.
    """
    chunks = []

    if not os.path.exists(notion_path):
        print(f"No Notion export found at {notion_path}")
        print("Export from Notion: Settings → Export all workspace content")
        return chunks

    print(f"Scanning Notion export: {notion_path}")

    pages     = 0
    databases = 0

    for root, dirs, files in os.walk(notion_path):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()

            if ext not in [".md", ".csv"]:
                continue

            filepath = os.path.join(root, filename)
            chunk    = process_notion_file(filepath)

            if chunk is None:
                continue

            chunks.append(chunk)

            if chunk["metadata"]["file_type"] == "notion_page":
                pages += 1
                print(f"  Page:     {chunk['metadata']['title']}")
            else:
                databases += 1
                print(f"  Database: {chunk['metadata']['title']}")

    print(f"\nDone!")
    print(f"Pages parsed:     {pages}")
    print(f"Databases parsed: {databases}")
    print(f"Total chunks:     {len(chunks)}")

    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_notion_export()

    if chunks:
        print(f"\n── FIRST CHUNK PREVIEW ──")
        print(f"Title:    {chunks[0]['metadata']['title']}")
        print(f"Type:     {chunks[0]['metadata']['file_type']}")
        print(f"Priority: {chunks[0]['metadata']['priority']}")
        print(f"Preview:\n{chunks[0]['text'][:300]}...")