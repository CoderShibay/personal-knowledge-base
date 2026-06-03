"""
PKB Data Status Check
=====================
Run this at the start of any session to see exactly what data is on the SSD,
what needs downloading, what needs extraction, and what is ready to ingest.

Usage:
    cd ~/personal-kb && source venv/bin/activate
    python3 tools/status_check.py
    python3 tools/status_check.py --zips    # also validate all zip files (slower)
"""

import os
import sys
import glob
import zipfile
import argparse
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import SSD_BASE, ACCOUNT_PATHS, OTHER_PATHS

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    from rich import box
    RICH = True
    console = Console(width=180)
except ImportError:
    RICH = False


# ── STATUS LEVELS ─────────────────────────────────────────────────────────────

READY      = "READY"      # key files present, parser can run now
PARTIAL    = "PARTIAL"    # some key files present but not all
ZIPPED     = "ZIPPED"     # zip(s) present but not extracted
CORRUPTED  = "CORRUPT"    # zip present but fails validation
MISSING    = "MISSING"    # no data at all


# ── ACCOUNT DATA DEFINITIONS ──────────────────────────────────────────────────
# For each data type extracted from a Google Takeout account,
# list the file paths (relative to the account folder) that indicate it's ready.
# Use glob patterns with * where needed.

ACCOUNT_DATA_TYPES = {
    "Mail": {
        "paths":    ["Takeout/Mail/All mail Including Spam and Trash.mbox"],
        "globs":    [],
    },
    "Cal": {
        "paths":    [],
        "globs":    ["Takeout/Calendar/*.ics"],
    },
    "Chrome": {
        "paths":    ["Takeout/Chrome/History.json"],
        "globs":    [],
    },
    "YT": {
        "paths":    ["Takeout/YouTube and YouTube Music/history/watch-history.html"],
        "globs":    [],
    },
    "Drive": {
        "paths":    ["Takeout/Drive"],
        "globs":    [],
    },
    "Maps": {
        "paths":    [],
        "globs":    [
            "Takeout/Location History (Timeline)/Records.json",
            "Takeout/Location History/Records.json",
        ],
    },
    "Keep": {
        "paths":    [],
        "globs":    ["Takeout/Keep/*.json"],
    },
    "Gem": {
        "paths":    ["Takeout/My Activity/Gemini Apps/MyActivity.html"],
        "globs":    [],
    },
}


# ── OTHER SOURCES ─────────────────────────────────────────────────────────────

OTHER_SOURCES = {
    "chatgpt": {
        "label":        "ChatGPT",
        "path_key":     "chatgpt",
        "ready_paths":  [],
        "ready_globs":  ["conversations.json"],
        "zip_globs":    ["*.zip"],
        "notes":        "Re-download from ChatGPT Settings > Data Controls > Export Data",
        "how_to_get":   "Manual: chatgpt.com > Settings > Data Controls > Export",
    },
    "spotify": {
        "label":        "Spotify",
        "path_key":     "spotify",
        "ready_paths":  [],
        "ready_globs":  ["**/Streaming_History_Audio_*.json"],
        "zip_globs":    ["*.zip"],
        "notes":        "Extended Streaming History",
        "how_to_get":   "Manual: spotify.com > Account > Privacy Settings > Download your data",
    },
    "instagram": {
        "label":        "Instagram",
        "path_key":     "instagram",
        "ready_paths":  [],
        "ready_globs":  ["**/messages/inbox/*/message_1.json"],
        "zip_globs":    ["*.zip"],
        "notes":        "Meta export (messages/inbox)",
        "how_to_get":   "Manual: instagram.com > Settings > Account > Download your information",
    },
    "facebook": {
        "label":        "Facebook/Messenger",
        "path_key":     "facebook",
        "ready_paths":  [],
        "ready_globs":  ["**/messages/inbox/*/message_1.json"],
        "zip_globs":    ["*.zip"],
        "notes":        "16 outer zips contain nested facebook_XXXXXX.zip",
        "how_to_get":   "Manual: facebook.com > Settings > Your Facebook information > Download your information",
    },
    "discord": {
        "label":        "Discord (Personal)",
        "path_key":     "discord",
        "ready_paths":  [],
        "ready_globs":  ["**/messages/*/messages.json"],
        "zip_globs":    ["package/*.zip", "*.zip"],
        "notes":        "Personal DM export (7-30 days after request)",
        "how_to_get":   "Manual: Discord Settings > Privacy & Safety > Request all of my Data",
    },
    "discord_servers": {
        "label":        "Discord (Servers)",
        "path_key":     "discord",
        "ready_paths":  [],
        "ready_globs":  ["servers/**/*.json"],
        "zip_globs":    [],
        "notes":        "DiscordChatExporter CLI exports per server",
        "how_to_get":   "CLI: DiscordChatExporter -- needs user token + channel IDs",
    },
    "linkedin": {
        "label":        "LinkedIn",
        "path_key":     "linkedin",
        "ready_paths":  ["messages.csv"],
        "ready_globs":  [],
        "zip_globs":    ["*.zip"],
        "notes":        "Needs messages.csv",
        "how_to_get":   "Manual: linkedin.com > Settings > Data Privacy > Get a copy of your data",
    },
    "whatsapp": {
        "label":        "WhatsApp",
        "path_key":     "whatsapp",
        "ready_paths":  [],
        "ready_globs":  ["*_chat.txt"],
        "zip_globs":    [],
        "notes":        "Per-chat export -- one file per conversation",
        "how_to_get":   "Manual (per chat): WhatsApp > Open chat > ... > Export Chat (without media)",
    },
    "notion": {
        "label":        "Notion",
        "path_key":     "notion",
        "ready_paths":  [],
        "ready_globs":  ["**/*.md", "**/*.csv"],
        "zip_globs":    ["*.zip"],
        "notes":        "Markdown + CSV export",
        "how_to_get":   "Manual: Notion Settings > Export all workspace content > Markdown & CSV",
    },
    "android": {
        "label":        "Android",
        "path_key":     "android",
        "ready_paths":  [],
        "ready_globs":  ["**/*"],
        "zip_globs":    ["*.zip"],
        "notes":        "No defined export yet",
        "how_to_get":   "ADB backup or Google Takeout (Android Device Configuration)",
    },
    "windows_laptop": {
        "label":        "Windows Laptop",
        "path_key":     "windows_laptop",
        "ready_paths":  [],
        "ready_globs":  ["**/*"],
        "zip_globs":    ["*.zip"],
        "notes":        "No data imported yet",
        "how_to_get":   "Manual: copy files from Windows laptop via USB or network",
    },
}


# ── HELPERS ───────────────────────────────────────────────────────────────────

def human_size(path):
    """Return human-readable size of a file or directory."""
    try:
        if os.path.isfile(path):
            b = os.path.getsize(path)
        elif os.path.isdir(path):
            b = sum(
                os.path.getsize(os.path.join(root, f))
                for root, _, files in os.walk(path)
                for f in files
            )
        else:
            return "—"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} PB"
    except Exception:
        return "?"


def check_zip_valid(zip_path):
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            return len(z.namelist()) > 0
    except Exception:
        return False


def find_zips(folder, pattern="*.zip"):
    """Find all real (non-._) zip files in folder (non-recursive)."""
    if not os.path.exists(folder):
        return []
    results = []
    for f in os.listdir(folder):
        if f.endswith(".zip") and not f.startswith("._"):
            results.append(os.path.join(folder, f))
    return sorted(results)


def key_files_present(folder, paths, globs):
    """Check if any of the key files/patterns exist under folder."""
    for p in paths:
        if os.path.exists(os.path.join(folder, p)):
            return True
    for g in globs:
        if glob.glob(os.path.join(folder, g), recursive=True):
            return True
    return False


def count_key_files(folder, paths, globs):
    found = 0
    for p in paths:
        if os.path.exists(os.path.join(folder, p)):
            found += 1
    for g in globs:
        hits = glob.glob(os.path.join(folder, g), recursive=True)
        if hits:
            found += 1
    return found


def folder_item_count(folder):
    """Count non-hidden files in a folder (non-recursive)."""
    if not os.path.exists(folder):
        return 0
    return sum(1 for f in os.listdir(folder) if not f.startswith("."))


# ── ACCOUNT STATUS ────────────────────────────────────────────────────────────

def _takeout_is_extracted(account_path):
    """True if a Takeout/ folder exists with >=5 subdirectories."""
    takeout = os.path.join(account_path, "Takeout")
    if not os.path.isdir(takeout):
        return False
    try:
        return len(os.listdir(takeout)) >= 5
    except Exception:
        return False


def _has_large_unextracted_zips(account_path, threshold_mb=500):
    """True if any zip in the account folder is larger than threshold_mb."""
    for z in find_zips(account_path):
        try:
            if os.path.getsize(z) > threshold_mb * 1024 * 1024:
                return True
        except OSError:
            pass
    return False


def check_account_data_type(account_path, dtype_def):
    """
    Returns (status, detail_string) for one data type in one account.
    """
    paths = dtype_def["paths"]
    globs = dtype_def["globs"]

    # Key files already extracted and present
    if key_files_present(account_path, paths, globs):
        return READY, ""

    zips = find_zips(account_path)

    # If Takeout/ is already extracted (>=5 subdirs), the account was processed.
    # Missing data types mean that data was not included in the export,
    # UNLESS there are large additional zips (>500MB) still waiting.
    if _takeout_is_extracted(account_path):
        if zips and _has_large_unextracted_zips(account_path):
            return ZIPPED, f"{len(zips)} zip(s) (incl. large unextracted)"
        return MISSING, "not in export"

    # No Takeout/ — check for zips to extract
    if zips:
        return ZIPPED, f"{len(zips)} zip(s)"

    return MISSING, ""


def check_all_accounts(validate_zips=False):
    """
    Returns dict: account_name -> {dtype_name -> (status, detail)}
    """
    results = {}
    for account, account_path in ACCOUNT_PATHS.items():
        results[account] = {}
        for dtype_name, dtype_def in ACCOUNT_DATA_TYPES.items():
            status, detail = check_account_data_type(account_path, dtype_def)
            results[account][dtype_name] = (status, detail)

        # Zip validity pass (optional, slower)
        if validate_zips:
            zips = find_zips(account_path)
            for z in zips:
                if not check_zip_valid(z):
                    # Mark all ZIPPED entries as CORRUPTED
                    for dtype_name in results[account]:
                        if results[account][dtype_name][0] == ZIPPED:
                            results[account][dtype_name] = (CORRUPTED, os.path.basename(z))
                    break  # one corrupted zip flags the whole account

    return results


# ── OTHER SOURCE STATUS ───────────────────────────────────────────────────────

def check_other_source(source_key, source_def, validate_zips=False):
    """
    Returns (status, size_str, notes_str, zip_count, zip_valid_count)
    """
    path_key = source_def["path_key"]

    # Resolve path — could be in ACCOUNT_PATHS or OTHER_PATHS
    folder = OTHER_PATHS.get(path_key) or ACCOUNT_PATHS.get(path_key, "")

    if not folder or not os.path.exists(folder):
        return MISSING, "—", source_def["notes"], 0, 0

    # Check if key files exist
    ready_paths = source_def["ready_paths"]
    ready_globs = source_def["ready_globs"]

    if key_files_present(folder, ready_paths, ready_globs):
        size = human_size(folder)
        return READY, size, source_def["notes"], 0, 0

    # Check for zips
    zip_globs = source_def.get("zip_globs", [])
    all_zips = []
    for zg in zip_globs:
        all_zips.extend(glob.glob(os.path.join(folder, zg), recursive=True))
    all_zips = [z for z in all_zips if not os.path.basename(z).startswith("._")]

    if all_zips:
        size = human_size(folder)
        if validate_zips:
            valid = sum(1 for z in all_zips if check_zip_valid(z))
            invalid = len(all_zips) - valid
            if invalid > 0:
                return CORRUPTED, size, f"{invalid} invalid zip(s)", len(all_zips), valid
        return ZIPPED, size, source_def["notes"], len(all_zips), len(all_zips)

    # Folder exists but empty-ish
    if folder_item_count(folder) == 0:
        return MISSING, "—", source_def["notes"], 0, 0

    return MISSING, "—", source_def["notes"], 0, 0


# ── FORMATTING ────────────────────────────────────────────────────────────────

STATUS_COLORS = {
    READY:     "green",
    PARTIAL:   "yellow",
    ZIPPED:    "cyan",
    CORRUPTED: "red",
    MISSING:   "dim",
}

STATUS_SYMBOLS = {
    READY:     "READY",
    PARTIAL:   "PART ",
    ZIPPED:    "ZIP  ",
    CORRUPTED: "CORRUPT",
    MISSING:   "  --  ",
}


def colored(text, color):
    if not RICH:
        return text
    colors = {
        "green": "\033[92m", "yellow": "\033[93m", "cyan": "\033[96m",
        "red": "\033[91m", "dim": "\033[2m", "reset": "\033[0m",
    }
    return f"{colors.get(color,'')}{text}{colors['reset']}"


def fmt_status(status, detail=""):
    sym = STATUS_SYMBOLS.get(status, status)
    col = STATUS_COLORS.get(status, "")
    label = sym if not detail else f"{sym} ({detail})"
    return colored(label, col)


# ── ACTION ITEMS ──────────────────────────────────────────────────────────────

def build_actions(account_results, other_results):
    actions = []

    # Account actions
    for account, dtype_results in account_results.items():
        statuses = [s for s, _ in dtype_results.values()]

        # Anything that's CORRUPTED
        corrupted = [d for d, (s, _) in dtype_results.items() if s == CORRUPTED]
        if corrupted:
            actions.append(("HIGH", f"RE-DOWNLOAD ZIP: {account} — corrupted zip detected"))

        # Has zips not extracted
        zipped = [d for d, (s, _) in dtype_results.items() if s == ZIPPED]
        if zipped:
            account_path = ACCOUNT_PATHS[account]
            zips = find_zips(account_path)
            total_mb = sum(os.path.getsize(z) for z in zips if os.path.exists(z)) // (1024*1024)
            # Only flag if not already fully extracted
            if not (_takeout_is_extracted(account_path) and not _has_large_unextracted_zips(account_path)):
                actions.append(("MED", f"EXTRACT ZIPS: {account} ({total_mb} MB across {len(zips)} zip(s))"))

        # Totally missing
        missing = [d for d, (s, _) in dtype_results.items() if s == MISSING]
        all_missing = all(s == MISSING for s, _ in dtype_results.values())
        if all_missing:
            actions.append(("HIGH", f"DOWNLOAD TAKEOUT: {account} — no data on SSD at all"))

    # Other source actions
    for key, (status, size, notes, zip_count, zip_valid) in other_results.items():
        src = OTHER_SOURCES[key]
        label = src["label"]
        how = src["how_to_get"]

        if status == CORRUPTED:
            actions.append(("HIGH", f"RE-DOWNLOAD: {label} — corrupted zip | {how}"))
        elif status == ZIPPED:
            actions.append(("MED", f"EXTRACT ZIPS: {label} ({size}, {zip_count} zip(s))"))
        elif status == MISSING:
            priority = "LOW" if key in ("android", "windows_laptop") else "MED"
            actions.append((priority, f"DOWNLOAD: {label} | {how}"))

    # Sort: HIGH first, then MED, then LOW
    order = {"HIGH": 0, "MED": 1, "LOW": 2}
    actions.sort(key=lambda x: order.get(x[0], 3))
    return actions


# ── PRINT FUNCTIONS ───────────────────────────────────────────────────────────

def print_account_table(account_results):
    dtype_names = list(ACCOUNT_DATA_TYPES.keys())

    if RICH:
        table = Table(title="Google Takeout Accounts", box=box.SIMPLE_HEAVY, show_lines=False)
        table.add_column("Account", style="bold", min_width=14)
        for d in dtype_names:
            table.add_column(d, justify="center", min_width=8)

        for account, dtype_results in account_results.items():
            row = [account]
            for dtype in dtype_names:
                status, detail = dtype_results[dtype]
                sym = STATUS_SYMBOLS[status]
                color = STATUS_COLORS[status]
                row.append(Text(sym, style=color))
            table.add_row(*row)
        console.print(table)
    else:
        header = f"{'Account':<16}" + "".join(f"{d:<10}" for d in dtype_names)
        print(header)
        print("-" * len(header))
        for account, dtype_results in account_results.items():
            row = f"{account:<16}"
            for dtype in dtype_names:
                status, _ = dtype_results[dtype]
                row += f"{STATUS_SYMBOLS[status]:<10}"
            print(row)


def print_other_table(other_results):
    if RICH:
        table = Table(title="Other Sources", box=box.SIMPLE_HEAVY, show_lines=False)
        table.add_column("Source", style="bold", min_width=22)
        table.add_column("Status", min_width=9)
        table.add_column("Size", min_width=8)
        table.add_column("Notes")

        for key, (status, size, notes, zip_count, _) in other_results.items():
            label = OTHER_SOURCES[key]["label"]
            sym = STATUS_SYMBOLS[status]
            color = STATUS_COLORS[status]
            zip_note = f"{zip_count} zip(s)" if zip_count else ""
            note_text = f"{notes} {zip_note}".strip()
            table.add_row(label, Text(sym, style=color), size, note_text)
        console.print(table)
    else:
        print(f"{'Source':<24} {'Status':<10} {'Size':<10} Notes")
        print("-" * 80)
        for key, (status, size, notes, zip_count, _) in other_results.items():
            label = OTHER_SOURCES[key]["label"]
            sym = STATUS_SYMBOLS[status]
            zip_note = f"({zip_count} zips)" if zip_count else ""
            print(f"{label:<24} {sym:<10} {size:<10} {notes} {zip_note}")


def print_actions(actions):
    priority_colors = {"HIGH": "red", "MED": "yellow", "LOW": "dim"}
    if RICH:
        console.print("\n[bold]Action Items[/bold]")
        for i, (priority, msg) in enumerate(actions, 1):
            color = priority_colors.get(priority, "white")
            console.print(f"  [{color}][{priority}][/{color}] {i}. {msg}")
    else:
        print("\nACTION ITEMS")
        print("-" * 60)
        for i, (priority, msg) in enumerate(actions, 1):
            print(f"  [{priority}] {i}. {msg}")


def print_summary(account_results, other_results):
    total_ready   = sum(1 for dr in account_results.values() for s, _ in dr.values() if s == READY)
    total_zipped  = sum(1 for dr in account_results.values() for s, _ in dr.values() if s == ZIPPED)
    total_corrupt = sum(1 for dr in account_results.values() for s, _ in dr.values() if s == CORRUPTED)
    total_missing = sum(1 for dr in account_results.values() for s, _ in dr.values() if s == MISSING)

    other_ready   = sum(1 for s, *_ in other_results.values() if s == READY)
    other_zipped  = sum(1 for s, *_ in other_results.values() if s == ZIPPED)
    other_missing = sum(1 for s, *_ in other_results.values() if s == MISSING)

    if RICH:
        console.print(f"\n[bold]Summary[/bold]")
        console.print(f"  Account data types — [green]READY: {total_ready}[/green]  [cyan]ZIPPED: {total_zipped}[/cyan]  [red]CORRUPT: {total_corrupt}[/red]  [dim]MISSING: {total_missing}[/dim]")
        console.print(f"  Other sources      — [green]READY: {other_ready}[/green]  [cyan]ZIPPED: {other_zipped}[/cyan]  [dim]MISSING: {other_missing}[/dim]")
    else:
        print(f"\nSUMMARY")
        print(f"  Account data types — READY:{total_ready}  ZIPPED:{total_zipped}  CORRUPT:{total_corrupt}  MISSING:{total_missing}")
        print(f"  Other sources      — READY:{other_ready}  ZIPPED:{other_zipped}  MISSING:{other_missing}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PKB Data Status Check")
    parser.add_argument("--zips", action="store_true",
                        help="Validate all zip files (slower — opens each zip)")
    args = parser.parse_args()

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    if RICH:
        console.print(f"\n[bold white]PKB Data Status — {now}[/bold white]")
        console.print(f"[dim]SSD: {SSD_BASE}[/dim]\n")
    else:
        print(f"\nPKB Data Status — {now}")
        print(f"SSD: {SSD_BASE}\n")

    if args.zips and RICH:
        console.print("[dim]Validating zip files — this may take a moment...[/dim]\n")

    # Account grid
    account_results = check_all_accounts(validate_zips=args.zips)
    print_account_table(account_results)

    if RICH:
        console.print()

    # Other sources
    other_results = {}
    for key, src_def in OTHER_SOURCES.items():
        other_results[key] = check_other_source(key, src_def, validate_zips=args.zips)
    print_other_table(other_results)

    # Actions
    actions = build_actions(account_results, other_results)
    print_actions(actions)

    # Summary
    print_summary(account_results, other_results)

    if RICH:
        console.print(f"\n[dim]Tip: run with --zips to validate zip integrity[/dim]\n")
    else:
        print("\nTip: run with --zips to validate zip integrity\n")


if __name__ == "__main__":
    main()
