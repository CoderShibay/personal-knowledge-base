import os
import sys
from datetime import datetime, date as date_type

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import ACCOUNT_PATHS

# ── CONFIGURATION ──────────────────────────────────────────

CALENDAR_REL_DIRS = [
    os.path.join("Takeout", "Calendar"),
    os.path.join("Takeout", "Google Calendar"),
]


# ── HELPERS ────────────────────────────────────────────────

def read_text(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"    Could not read {filepath}: {e}")
        return ""


def unfold_ics_lines(raw_text):
    lines = raw_text.splitlines()
    unfolded = []

    for line in lines:
        if (line.startswith(" ") or line.startswith("\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)

    return unfolded


def extract_value(line):
    if ":" not in line:
        return ""
    return line.split(":", 1)[1].strip()


def parse_ics_datetime(value):
    if not value:
        return None

    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1]

    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            dt = datetime.strptime(cleaned, fmt)
            if fmt == "%Y%m%d":
                return dt.date()
            return dt
        except Exception:
            continue

    return None


def extract_cn_or_email(line):
    upper = line.upper()

    cn_index = upper.find("CN=")
    if cn_index != -1:
        start = cn_index + 3
        end = len(line)

        for sep in (";", ":"):
            sep_index = line.find(sep, start)
            if sep_index != -1:
                end = min(end, sep_index)

        cn = line[start:end].strip().strip('"')
        if cn:
            return cn

    value = extract_value(line)
    lower_value = value.lower()
    mailto_index = lower_value.find("mailto:")
    if mailto_index != -1:
        email = value[mailto_index + len("mailto:"):].strip()
        if email:
            return email

    return ""


def parse_events_from_ics(raw_text):
    lines = unfold_ics_lines(raw_text)
    events = []

    in_event = False
    event_lines = []

    for line in lines:
        stripped = line.strip()

        if stripped == "BEGIN:VEVENT":
            in_event = True
            event_lines = []
            continue

        if stripped == "END:VEVENT":
            if event_lines:
                event = parse_single_event(event_lines)
                if event:
                    events.append(event)
            in_event = False
            event_lines = []
            continue

        if in_event:
            event_lines.append(line)

    return events


def parse_single_event(event_lines):
    summary = ""
    description = ""
    organizer = ""
    attendees = []
    dtstart = None
    dtend = None

    for line in event_lines:
        if line.startswith("DTSTART"):
            dtstart = parse_ics_datetime(extract_value(line))
        elif line.startswith("DTEND"):
            dtend = parse_ics_datetime(extract_value(line))
        elif line.startswith("SUMMARY"):
            summary = extract_value(line)
        elif line.startswith("DESCRIPTION"):
            description = extract_value(line).replace("\\n", "\n")
        elif line.startswith("ORGANIZER"):
            organizer = extract_cn_or_email(line)
        elif line.startswith("ATTENDEE"):
            attendee = extract_cn_or_email(line)
            if attendee:
                attendees.append(attendee)

    summary = summary.strip()
    if not summary or not dtstart:
        return None

    deduped_attendees = []
    seen = set()
    for attendee in attendees:
        key = attendee.strip()
        if not key:
            continue
        lower_key = key.lower()
        if lower_key in seen:
            continue
        seen.add(lower_key)
        deduped_attendees.append(key)

    if isinstance(dtstart, datetime):
        event_date = dtstart.date()
    elif isinstance(dtstart, date_type):
        event_date = dtstart
    else:
        return None

    return {
        "date": event_date,
        "summary": summary,
        "description": description,
        "organizer": organizer,
        "attendees": deduped_attendees,
        "dtstart": dtstart,
        "dtend": dtend,
    }


def build_calendar_chunk(account_name, calendar_name, events):
    if not events:
        return None

    sorted_events = sorted(events, key=lambda e: (e["date"], e["summary"].lower()))

    earliest_date = sorted_events[0]["date"].isoformat()
    latest_date = sorted_events[-1]["date"].isoformat()

    lines = []
    for event in sorted_events:
        line = f"{event['date'].isoformat()}: {event['summary']}"
        if event["attendees"]:
            line += f" [with: {', '.join(event['attendees'])}]"
        lines.append(line)

    text = (
        f"Google Calendar — {calendar_name} ({account_name})\n"
        f"Date range: {earliest_date} to {latest_date}\n\n"
        + "\n".join(lines)
    )

    return {
        "text": text,
        "metadata": {
            "source": "google_calendar",
            "account": account_name,
            "calendar_name": calendar_name,
            "date": earliest_date,
            "date_range": f"{earliest_date} to {latest_date}",
            "event_count": len(sorted_events),
            "priority": "normal",
            "modality": "text",
            "phase2": False,
        },
    }


# ── MAIN PARSER ────────────────────────────────────────────

# Walks through all account paths and parses Google Calendar .ics exports.
def parse_calendar_export():
    chunks = []

    print("Scanning Calendar exports across all account paths...")

    for account_name, account_path in ACCOUNT_PATHS.items():
        calendar_dir = None
        for rel_dir in CALENDAR_REL_DIRS:
            candidate = os.path.join(account_path, rel_dir)
            if os.path.isdir(candidate):
                calendar_dir = candidate
                break

        if calendar_dir is None:
            print(f"  [{account_name}] No Calendar Takeout folder found")
            continue

        account_chunks = 0

        for root, _, files in os.walk(calendar_dir):
            for filename in files:
                if not filename.lower().endswith(".ics"):
                    continue

                filepath = os.path.join(root, filename)
                calendar_name = os.path.splitext(filename)[0]

                raw_text = read_text(filepath)
                if not raw_text:
                    continue

                events = parse_events_from_ics(raw_text)
                chunk = build_calendar_chunk(account_name, calendar_name, events)

                if chunk:
                    chunks.append(chunk)
                    account_chunks += 1

        if account_chunks:
            print(f"  [{account_name}] Parsed {account_chunks} calendar file(s)")
        else:
            print(f"  [{account_name}] No usable .ics files found")

    print("\nDone!")
    print(f"Total chunks: {len(chunks)}")

    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_calendar_export()
    print(f"\nTotal chunks found: {len(chunks)}")

    if chunks:
        print("\n── FIRST CHUNK PREVIEW ──")
        print(f"Preview:\n{chunks[0]['text'][:300]}...")
