import os
import sys
import re
import html
from datetime import datetime

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import ACCOUNT_PATHS

# ── CONFIGURATION ──────────────────────────────────────────

GEMINI_REL_PATH = "Takeout/My Activity/Gemini Apps/MyActivity.html"

# One content cell per entry in the HTML activity log
_CELL_RE = re.compile(
    r'content-cell mdl-cell mdl-cell--6-col mdl-typography--body-1">(.*?)</div>',
    re.DOTALL,
)

# "Mar 18, 2026" or "Dec 2, 2025"
_DATE_RE = re.compile(
    r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4})'
)

_TAG_RE = re.compile(r'<[^>]+>')

# Gemini tool JSON blobs start with {"contentMetadata": — strip from there
_JSON_NOISE_RE = re.compile(r'\s*\{&quot;contentMetadata.*', re.DOTALL)


# ── HELPERS ────────────────────────────────────────────────

def _read_html(filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        print(f"    Could not read {filepath}: {e}")
        return ""


def _strip_tags(text):
    return _TAG_RE.sub("", text).strip()


def _parse_date(cell_text):
    m = _DATE_RE.search(cell_text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1).strip(), "%b %d, %Y").strftime("%Y-%m-%d")
    except Exception:
        return None


def _extract_prompt(cell_raw):
    # Strip everything from the first <br> onward — that's date + response
    before_br = cell_raw.split("<br>")[0]
    # Remove "Prompted\xa0" prefix (with possible &nbsp; variants)
    text = _strip_tags(before_br)
    text = html.unescape(text)
    # Remove leading "Prompted" word (with regular or non-breaking space)
    text = re.sub(r'^Prompted[\s\xa0]+', '', text, flags=re.IGNORECASE).strip()
    return text


def _extract_canvas_title(cell_raw):
    text = _strip_tags(cell_raw)
    text = html.unescape(text)
    # "Created Gemini Canvas titled\xa0<title>http://..."
    m = re.search(r'titled[\s\xa0]+(.+?)(?:http|$)', text)
    if m:
        return m.group(1).strip()
    return ""


# ── PROCESSOR ──────────────────────────────────────────────

def process_gemini_html(content, account_name):
    cells = _CELL_RE.findall(content)
    grouped = {}

    for cell in cells:
        if cell.startswith("Prompted"):
            date = _parse_date(cell)
            if not date:
                continue
            prompt = _extract_prompt(cell)
            if not prompt:
                continue
            grouped.setdefault(date, []).append(f"Q: {prompt}")

        elif cell.startswith("Created"):
            date = _parse_date(cell)
            if not date:
                continue
            title = _extract_canvas_title(cell)
            if title:
                grouped.setdefault(date, []).append(f"Created: {title}")

    chunks = []
    for date in sorted(grouped):
        lines = grouped[date]
        chunks.append({
            "text": f"Gemini activity — {date} ({account_name})\n\n" + "\n".join(lines),
            "metadata": {
                "source": "gemini",
                "account": account_name,
                "date": date,
                "item_count": len(lines),
                "priority": "normal",
                "modality": "text",
                "phase2": False,
            },
        })

    return chunks


# ── MAIN PARSER ────────────────────────────────────────────

def parse_gemini_export():
    chunks = []

    for account_name, account_path in ACCOUNT_PATHS.items():
        html_path = os.path.join(account_path, GEMINI_REL_PATH)

        if not os.path.exists(html_path):
            print(f"  [{account_name}] No Gemini activity file found")
            continue

        print(f"  [{account_name}] Found Gemini activity log")
        content = _read_html(html_path)
        account_chunks = process_gemini_html(content, account_name)
        chunks.extend(account_chunks)

        total_prompts = sum(c["metadata"]["item_count"] for c in account_chunks)
        print(f"    {len(account_chunks)} days, {total_prompts} prompts/entries")

    print(f"\nDone!")
    print(f"Total chunks: {len(chunks)}")
    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_gemini_export()

    if chunks:
        print(f"\n── FIRST CHUNK PREVIEW ──")
        c = chunks[0]
        print(f"Account: {c['metadata']['account']}")
        print(f"Date:    {c['metadata']['date']}")
        print(f"Items:   {c['metadata']['item_count']}")
        print(f"Preview:\n{c['text'][:400]}")
