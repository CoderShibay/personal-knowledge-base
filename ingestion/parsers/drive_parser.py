import os
import sys
from datetime import datetime

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import ACCOUNT_PATHS, PRIORITY_PROJECTS, IMAGE_EXTENSIONS, ZIP_EXTENSIONS

try:
    import fitz
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("PyMuPDF not installed - PDF support disabled")

try:
    from docx import Document
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False
    print("python-docx not installed - Word doc support disabled")

try:
    import openpyxl
    XLSX_SUPPORT = True
except ImportError:
    XLSX_SUPPORT = False
    print("openpyxl not installed - Excel support disabled")

# ── CONFIGURATION ──────────────────────────────────────────

ACCOUNTS = ACCOUNT_PATHS

# files we tag as pointers for phase 2 processing
PHASE2_EXTENSIONS = {
    "image": IMAGE_EXTENSIONS,
    "zip":   ZIP_EXTENSIONS,
    "audio": [".mp3", ".wav", ".m4a", ".flac", ".ogg"],
    "video": [".mp4", ".mkv", ".avi", ".mov", ".wmv"],
}


# ── FILE TYPE DETECTOR ─────────────────────────────────────

def get_file_type(filename):
    """
    Returns what kind of file this is so we know how to handle it.
    Either process it now or create a pointer for phase 2.
    """
    ext = os.path.splitext(filename)[1].lower()

    for phase2_type, extensions in PHASE2_EXTENSIONS.items():
        if ext in extensions:
            return f"phase2_{phase2_type}"

    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "docx"
    if ext in [".xlsx", ".xls"]:
        return "excel"
    if ext in [".txt", ".md", ".csv"]:
        return "text"
    if ext in [".pptx", ".ppt"]:
        return "slides"
    if ext in [".json"]:
        return "json"

    return "unknown"


# ── TEXT EXTRACTORS ────────────────────────────────────────

def extract_pdf(filepath):
    if not PDF_SUPPORT:
        return ""
    try:
        doc = fitz.open(filepath)
        text = ""
        for page in doc:
            text += page.get_text()
        return text.strip()
    except Exception as e:
        print(f"    Could not read PDF {os.path.basename(filepath)}: {e}")
        return ""


def extract_docx(filepath):
    if not DOCX_SUPPORT:
        return ""
    try:
        doc = Document(filepath)
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    except Exception as e:
        print(f"    Could not read Word doc {os.path.basename(filepath)}: {e}")
        return ""


def extract_excel(filepath):
    if not XLSX_SUPPORT:
        return ""
    try:
        wb = openpyxl.load_workbook(filepath, read_only=True)
        text = ""
        for sheet in wb.worksheets:
            text += f"\n[Sheet: {sheet.title}]\n"
            for row in sheet.iter_rows(values_only=True):
                row_text = " | ".join(str(c) for c in row if c is not None)
                if row_text.strip():
                    text += row_text + "\n"
        return text.strip()
    except Exception as e:
        print(f"    Could not read Excel {os.path.basename(filepath)}: {e}")
        return ""


def extract_text_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except Exception as e:
        print(f"    Could not read text file {os.path.basename(filepath)}: {e}")
        return ""


# ── MAIN FILE PROCESSOR ────────────────────────────────────

def process_file(filepath, account_name):
    """
    Takes one file and returns a chunk ready for ChromaDB.
    Text files get full content extracted now.
    Images, videos, audio get a pointer for phase 2.
    """
    filename  = os.path.basename(filepath)
    file_type = get_file_type(filename)
    ext       = os.path.splitext(filename)[1].lower()
    file_size = os.path.getsize(filepath)

    # get file modification date as proxy for creation date
    mod_time = os.path.getmtime(filepath)
    date     = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d")

    # check if this is a priority file
    is_priority = any(p.lower() in filepath.lower() for p in PRIORITY_PROJECTS)

    # base metadata every chunk gets
    metadata = {
        "source":      "google_drive",
        "account":     account_name,
        "filename":    filename,
        "file_type":   file_type,
        "extension":   ext,
        "date":        date,
        "file_size":   file_size,
        "file_path":   filepath,
        "priority":    "high" if is_priority else "normal",
        "phase2":      False,
    }

    # phase 2 files — create pointer, process content later
    if file_type.startswith("phase2_"):
        modality = file_type.replace("phase2_", "")
        metadata["phase2"]   = True
        metadata["modality"] = modality

        chunk = {
            "text": f"[{modality.upper()} FILE: {filename}] "
                    f"Located at {filepath}. "
                    f"Date: {date}. "
                    f"Size: {file_size / (1024*1024):.1f}MB. "
                    f"Will be processed in phase 2.",
            "metadata": metadata
        }
        return chunk

    # extract text based on file type
    if file_type == "pdf":
        text = extract_pdf(filepath)
    elif file_type == "docx":
        text = extract_docx(filepath)
    elif file_type == "excel":
        text = extract_excel(filepath)
    elif file_type == "text":
        text = extract_text_file(filepath)
    else:
        return None

    if not text:
        return None

    chunk = {
        "text":     text,
        "metadata": metadata
    }

    return chunk


# ── MAIN PARSER ────────────────────────────────────────────

def parse_drive_account(account_name, account_path):
    """
    Walks through one account's Drive folder and processes every file.
    """
    chunks = []

    # Google Drive files live inside Takeout/Drive/
    drive_path = os.path.join(account_path, "Takeout", "Drive")

    if not os.path.exists(drive_path):
        # also try without Takeout subfolder
        drive_path = os.path.join(account_path, "Drive")

    if not os.path.exists(drive_path):
        print(f"  No Drive folder found in {account_path}")
        return chunks

    print(f"  Scanning: {drive_path}")

    processed = 0
    pointers  = 0
    skipped   = 0

    for root, dirs, files in os.walk(drive_path):
        for filename in files:
            filepath  = os.path.join(root, filename)

            chunk = process_file(filepath, account_name)

            if chunk is None:
                skipped += 1
                continue

            if chunk["metadata"]["phase2"]:
                pointers += 1
            else:
                processed += 1

            chunks.append(chunk)

    print(f"  Processed: {processed} files")
    print(f"  Pointers:  {pointers} files (phase 2)")
    print(f"  Skipped:   {skipped} files (unknown format)")

    return chunks


def parse_all_drive_accounts():
    all_chunks = []

    for account_name, account_path in ACCOUNTS.items():
        print(f"\nProcessing Drive for: {account_name}")
        chunks = parse_drive_account(account_name, account_path)
        all_chunks.extend(chunks)
        print(f"  Total chunks: {len(chunks)}")

    print(f"\nDone! Total Drive chunks: {len(all_chunks)}")
    return all_chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_all_drive_accounts()

    if chunks:
        text_chunks    = [c for c in chunks if not c["metadata"]["phase2"]]
        pointer_chunks = [c for c in chunks if c["metadata"]["phase2"]]

        print(f"\n── SUMMARY ──")
        print(f"Text chunks ready now:     {len(text_chunks)}")
        print(f"Phase 2 pointers created:  {len(pointer_chunks)}")

        if text_chunks:
            print(f"\n── FIRST TEXT CHUNK ──")
            print(f"File:     {text_chunks[0]['metadata']['filename']}")
            print(f"Account:  {text_chunks[0]['metadata']['account']}")
            print(f"Preview:  {text_chunks[0]['text'][:300]}...")