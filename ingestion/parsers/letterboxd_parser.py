import os
import csv
import sys
from datetime import datetime
from collections import defaultdict

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import OTHER_PATHS

LETTERBOXD_PATH = OTHER_PATHS["letterboxd"]


def _read_csv(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        print(f"    Could not read {filepath}: {e}")
        return []


def _parse_date(s):
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
    except Exception:
        return s.strip()[:10] if s else "unknown"


# ── WATCHED ────────────────────────────────────────────────

def _parse_watched(letterboxd_path):
    filepath = os.path.join(letterboxd_path, "watched.csv")
    rows     = _read_csv(filepath)
    if not rows:
        return []

    by_year = defaultdict(list)
    for row in rows:
        date  = _parse_date(row.get("Date", ""))
        name  = (row.get("Name") or "").strip()
        year  = (row.get("Year") or "").strip()
        if not name:
            continue
        label = f"{name} ({year})" if year else name
        by_year[date[:4]].append((date, label))

    chunks = []
    for yr in sorted(by_year):
        films      = sorted(by_year[yr], key=lambda x: x[0])
        dates      = [f[0] for f in films]
        lines      = [f"[{d}] {title}" for d, title in films]
        chunks.append({
            "text": f"Letterboxd — films watched in {yr} ({len(films)} films)\n\n"
                    + "\n".join(lines),
            "metadata": {
                "source":      "letterboxd_watched",
                "account":     "sma_purno",
                "date":        min(dates),
                "date_range":  f"{min(dates)} to {max(dates)}",
                "film_count":  len(films),
                "priority":    "normal",
                "modality":    "text",
                "phase2":      False,
            },
        })

    total = sum(len(v) for v in by_year.values())
    print(f"  Watched: {total} films across {len(by_year)} years, {len(chunks)} chunks")
    return chunks


# ── RATINGS ────────────────────────────────────────────────

def _parse_ratings(letterboxd_path):
    filepath = os.path.join(letterboxd_path, "ratings.csv")
    rows     = _read_csv(filepath)
    if not rows:
        return []

    by_rating = defaultdict(list)
    dates     = []
    for row in rows:
        date   = _parse_date(row.get("Date", ""))
        name   = (row.get("Name") or "").strip()
        year   = (row.get("Year") or "").strip()
        rating = (row.get("Rating") or "").strip()
        if not name or not rating:
            continue
        label  = f"{name} ({year})" if year else name
        by_rating[rating].append(label)
        dates.append(date)

    if not dates:
        return []

    lines = []
    for rating in sorted(by_rating.keys(), key=lambda x: -float(x) if x else 0):
        films = by_rating[rating]
        stars = int(float(rating)) if rating else 0
        lines.append(f"\n★ {rating}/5 ({len(films)} films):")
        lines.extend(f"  {f}" for f in sorted(films))

    chunks = [{
        "text": f"Letterboxd ratings — {len(rows)} films rated "
                f"({min(dates)} to {max(dates)})\n"
                + "\n".join(lines),
        "metadata": {
            "source":     "letterboxd_ratings",
            "account":    "sma_purno",
            "date":       min(dates),
            "date_range": f"{min(dates)} to {max(dates)}",
            "film_count": len(rows),
            "priority":   "normal",
            "modality":   "text",
            "phase2":     False,
        },
    }]

    print(f"  Ratings: {len(rows)} films rated")
    return chunks


# ── DIARY ──────────────────────────────────────────────────

def _parse_diary(letterboxd_path):
    filepath = os.path.join(letterboxd_path, "diary.csv")
    rows     = _read_csv(filepath)
    if not rows:
        return []

    by_month = defaultdict(list)
    for row in rows:
        date         = _parse_date(row.get("Date", ""))
        watched_date = _parse_date(row.get("Watched Date", "")) or date
        name         = (row.get("Name") or "").strip()
        year         = (row.get("Year") or "").strip()
        rating       = (row.get("Rating") or "").strip()
        rewatch      = (row.get("Rewatch") or "").strip().lower() == "yes"
        tags         = (row.get("Tags") or "").strip()
        if not name:
            continue
        month = watched_date[:7] if watched_date != "unknown" else date[:7]
        label = f"{name} ({year})" if year else name
        parts = [label]
        if rating:
            parts.append(f"★{rating}")
        if rewatch:
            parts.append("rewatch")
        if tags:
            parts.append(f"[{tags}]")
        by_month[month].append((watched_date, " — ".join(parts)))

    chunks = []
    all_dates = []
    for month in sorted(by_month):
        entries    = sorted(by_month[month], key=lambda x: x[0])
        month_dates = [e[0] for e in entries]
        all_dates.extend(month_dates)
        lines      = [f"[{d}] {title}" for d, title in entries]
        chunks.append({
            "text": f"Letterboxd diary — {month} ({len(entries)} entries)\n\n"
                    + "\n".join(lines),
            "metadata": {
                "source":      "letterboxd_diary",
                "account":     "sma_purno",
                "date":        min(month_dates),
                "date_range":  month,
                "entry_count": len(entries),
                "priority":    "normal",
                "modality":    "text",
                "phase2":      False,
            },
        })

    print(f"  Diary: {len(rows)} entries across {len(by_month)} months, {len(chunks)} chunks")
    return chunks


# ── WATCHLIST ──────────────────────────────────────────────

def _parse_watchlist(letterboxd_path):
    filepath = os.path.join(letterboxd_path, "watchlist.csv")
    rows     = _read_csv(filepath)
    if not rows:
        return []

    films = []
    dates = []
    for row in rows:
        date  = _parse_date(row.get("Date", ""))
        name  = (row.get("Name") or "").strip()
        year  = (row.get("Year") or "").strip()
        if not name:
            continue
        label = f"{name} ({year})" if year else name
        films.append((date, label))
        dates.append(date)

    if not films:
        return []

    films.sort(key=lambda x: x[0])
    lines = [f"[{d}] {title}" for d, title in films]

    chunks = [{
        "text": f"Letterboxd watchlist — {len(films)} films "
                f"(added {min(dates)} to {max(dates)})\n\n"
                + "\n".join(lines),
        "metadata": {
            "source":     "letterboxd_watchlist",
            "account":    "sma_purno",
            "date":       min(dates),
            "date_range": f"{min(dates)} to {max(dates)}",
            "film_count": len(films),
            "priority":   "normal",
            "modality":   "text",
            "phase2":     False,
        },
    }]

    print(f"  Watchlist: {len(films)} films")
    return chunks


# ── MAIN PARSER ────────────────────────────────────────────

def parse_letterboxd(letterboxd_path=LETTERBOXD_PATH):
    chunks = []

    if not os.path.exists(letterboxd_path):
        print(f"No Letterboxd data found at {letterboxd_path}")
        return chunks

    print(f"Scanning Letterboxd: {letterboxd_path}")

    chunks.extend(_parse_watched(letterboxd_path))
    chunks.extend(_parse_ratings(letterboxd_path))
    chunks.extend(_parse_diary(letterboxd_path))
    chunks.extend(_parse_watchlist(letterboxd_path))

    print(f"Letterboxd total chunks: {len(chunks)}")
    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_letterboxd()
    print(f"\nTotal chunks: {len(chunks)}")
    by_source = {}
    for c in chunks:
        s = c["metadata"]["source"]
        by_source[s] = by_source.get(s, 0) + 1
    for s, n in sorted(by_source.items()):
        print(f"  {s}: {n}")
    if chunks:
        print(f"\n── FIRST CHUNK PREVIEW ──\n{chunks[0]['text'][:400]}")
