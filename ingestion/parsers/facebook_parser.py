import os
import json
import re
import sys
import zipfile
from datetime import datetime
from collections import defaultdict

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import OTHER_PATHS, PRIORITY_PROJECTS

FACEBOOK_PATH = OTHER_PATHS["facebook"]

_MEDIA_TAG_PATTERNS = [
    (re.compile(r"sent a? ?photo",          re.I), "[photo]"),
    (re.compile(r"sent a? ?video",          re.I), "[video]"),
    (re.compile(r"sent a? ?voice message",  re.I), "[voice note]"),
    (re.compile(r"sent a? ?reel",           re.I), "[reel]"),
    (re.compile(r"sent a? ?link",           re.I), "[link]"),
    (re.compile(r"sent a? ?sticker",        re.I), "[sticker]"),
    (re.compile(r"sent a? ?gif",            re.I), "[gif]"),
    (re.compile(r"sent an? attachment",     re.I), "[attachment]"),
    (re.compile(r"^liked a message$",       re.I), "[liked a message]"),
    (re.compile(r"^missed voice call$",     re.I), "[missed voice call]"),
    (re.compile(r"sent a disappearing",     re.I), "[disappearing message]"),
]


def _media_tag(content):
    for pattern, tag in _MEDIA_TAG_PATTERNS:
        if pattern.search(content):
            return tag
    return None


def _fix(s):
    if not s:
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _ts_ms(timestamp_ms):
    try:
        return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d")
    except Exception:
        return "unknown"


def _ts_unix(timestamp):
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
    except Exception:
        return "unknown"


def _load_json_from_zip(z, path):
    try:
        with z.open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"    Could not read {path}: {e}")
        return None


def _build_chunk(source, thread_name, lines, dates, message_count):
    is_priority = any(p.lower() in thread_name.lower() for p in PRIORITY_PROJECTS)
    start_date  = min(dates) if dates else "unknown"
    end_date    = max(dates) if dates else "unknown"
    date_range  = f"{start_date} to {end_date}"
    return {
        "text": f"{source.title()} thread: {thread_name}\n"
                f"Date range: {date_range}\n\n"
                + "\n".join(lines),
        "metadata": {
            "source":        source,
            "thread_name":   thread_name,
            "date":          start_date,
            "date_range":    date_range,
            "message_count": message_count,
            "priority":      "high" if is_priority else "normal",
            "modality":      "text",
            "phase2":        False,
        },
    }


def _format_share(share):
    owner      = _fix(share.get("original_content_owner") or "")
    username   = _fix(share.get("profile_share_username")  or "")
    name       = _fix(share.get("profile_share_name")      or "")
    link       = share.get("link") or ""
    share_text = _fix(share.get("share_text") or "").strip()

    if username:
        label = f"[shared profile: @{username}" + (f" ({name})" if name else "") + "]"
        return label + (f" {link}" if link else "")

    parts = []
    if owner:
        parts.append(f"@{owner}")
    if link:
        parts.append(link)
    header = "[shared: " + " | ".join(parts) + "]" if parts else "[shared]"

    if share_text:
        return header + "\n    " + share_text

    return header


def _parse_fb_message(msg):
    raw_sender  = _fix(msg.get("sender_name") or "")
    sender      = raw_sender if raw_sender.strip() else None
    date        = _ts_ms(msg.get("timestamp_ms", 0))
    raw_content = _fix((msg.get("content") or "").strip())
    share       = msg.get("share")
    reactions   = msg.get("reactions") or []

    if not sender:
        rxn_str = ""
        if reactions:
            rxn_str = " ".join(_fix(r.get("reaction") or "") for r in reactions if r.get("reaction"))
        tag = "[deleted message]" + (f"  [{rxn_str}]" if rxn_str else "")
        return f"[{date}] (deleted): {tag}", date

    if msg.get("is_unsent"):
        content = "[unsent message]"
    elif share:
        content = _format_share(share)
    elif raw_content:
        tag = _media_tag(raw_content)
        content = tag if tag else raw_content
    elif msg.get("photos"):
        content = "[photo]"
    elif msg.get("sticker"):
        content = "[sticker]"
    elif msg.get("audio_files"):
        content = "[voice note]"
    elif msg.get("videos"):
        content = "[video]"
    elif msg.get("gifs"):
        content = "[gif]"
    elif msg.get("files"):
        content = "[file]"
    elif msg.get("is_geoblocked_for_viewer"):
        content = "[geoblocked content]"
    elif sender == "Facebook user":
        content = "[message from deleted account]"
    else:
        content = "[media]"

    if reactions:
        rxn_str = " ".join(_fix(r.get("reaction") or "") for r in reactions if r.get("reaction"))
        if rxn_str:
            content += f"  [{rxn_str}]"

    return f"[{date}] {sender}: {content}", date


# ── MESSENGER ──────────────────────────────────────────────

def parse_messenger(facebook_path=FACEBOOK_PATH):
    chunks = []

    if not os.path.exists(facebook_path):
        print(f"No Facebook data found at {facebook_path}")
        return chunks

    print(f"Scanning Messenger (Facebook export): {facebook_path}")

    thread_files = defaultdict(list)
    zip_cache = {}

    for fname in sorted(os.listdir(facebook_path)):
        if not (fname.startswith("meta-") and fname.endswith(".zip")):
            continue
        fpath = os.path.join(facebook_path, fname)
        try:
            z = zipfile.ZipFile(fpath)
            zip_cache[fpath] = z
        except Exception as e:
            print(f"  Could not open {fname}: {e}")
            continue

        for n in z.namelist():
            if "/messages/" not in n or not n.endswith(".json"):
                continue
            basename = n.split("/")[-1]
            if not (basename.startswith("message_") and basename.endswith(".json")):
                continue
            parts = n.split("/")
            if len(parts) < 6:
                continue
            folder_cat = parts[-3] if len(parts) >= 7 else ""
            if folder_cat not in ("inbox", "message_requests", "archived_threads",
                                  "e2ee_cutover", "filtered_threads"):
                continue
            thread_id = parts[-2]
            try:
                msg_num = int(basename[8:-5])
            except ValueError:
                msg_num = 0
            thread_files[thread_id].append((fpath, n, msg_num))

    print(f"  Found {len(thread_files)} threads across {len(zip_cache)} zips")

    for thread_id, file_list in thread_files.items():
        file_list.sort(key=lambda x: -x[2])

        lines = []
        dates = []
        title = thread_id
        participant_count = 0

        for zip_path, json_path, _ in file_list:
            z    = zip_cache[zip_path]
            data = _load_json_from_zip(z, json_path)
            if not data:
                continue

            if title == thread_id and data.get("title"):
                title = _fix(data["title"])

            if not participant_count:
                participant_count = len(data.get("participants") or [])

            for msg in reversed(data.get("messages") or []):
                line, date = _parse_fb_message(msg)
                if line:
                    lines.append(line)
                    dates.append(date)

        if not lines:
            continue

        chunk = _build_chunk("messenger", title, lines, dates, len(lines))
        chunk["metadata"]["participant_count"] = participant_count
        chunks.append(chunk)

        label = " [PRIORITY]" if chunk["metadata"]["priority"] == "high" else ""
        print(f"  {title} ({len(lines)} messages){label}")

    for z in zip_cache.values():
        z.close()

    print(f"Messenger chunks: {len(chunks)}")
    return chunks


# ── REACTIONS ──────────────────────────────────────────────

def parse_facebook_reactions(facebook_path=FACEBOOK_PATH):
    chunks = []

    if not os.path.exists(facebook_path):
        return chunks

    print(f"Scanning Facebook reactions: {facebook_path}")

    _EMOJI = {
        "LIKE": "👍", "LOVE": "❤️", "HAHA": "😂", "WOW": "😮",
        "SORRY": "😢", "ANGER": "😡", "NONE": "·", "DOROTHY": "🌈",
    }

    by_month = defaultdict(lambda: defaultdict(int))
    total = 0

    for fname in sorted(os.listdir(facebook_path)):
        if not (fname.startswith("meta-") and fname.endswith(".zip")):
            continue
        fpath = os.path.join(facebook_path, fname)
        try:
            z = zipfile.ZipFile(fpath)
        except Exception:
            continue

        for n in z.namelist():
            if "likes_and_reactions_" not in n or not n.endswith(".json"):
                continue
            data = _load_json_from_zip(z, n)
            if not isinstance(data, list):
                continue
            for item in data:
                ts = item.get("timestamp", 0)
                if not ts or ts < 1000000:
                    continue
                month = _ts_unix(ts)[:7]
                for d in item.get("data") or []:
                    rxn = ((d.get("reaction") or {}).get("reaction") or "LIKE").strip()
                    if rxn:
                        by_month[month][rxn] += 1
                        total += 1
        z.close()

    for month in sorted(by_month):
        rxn_counts  = by_month[month]
        month_total = sum(rxn_counts.values())
        lines = []
        for rxn, count in sorted(rxn_counts.items(), key=lambda x: -x[1]):
            emoji = _EMOJI.get(rxn, rxn)
            lines.append(f"  {emoji} {rxn}: {count}")
        chunks.append({
            "text": f"Facebook reactions — {month} ({month_total} total)\n" + "\n".join(lines),
            "metadata": {
                "source":         "facebook_reactions",
                "date":           f"{month}-01",
                "date_range":     month,
                "reaction_count": month_total,
                "priority":       "normal",
                "modality":       "text",
                "phase2":         False,
            },
        })

    print(f"  Facebook reactions: {total} total, {len(chunks)} monthly chunks")
    return chunks


# ── COMMENTS ───────────────────────────────────────────────

def parse_facebook_comments(facebook_path=FACEBOOK_PATH):
    chunks = []

    if not os.path.exists(facebook_path):
        return chunks

    print(f"Scanning Facebook comments: {facebook_path}")

    all_comments = []
    seen_keys    = set()

    for fname in sorted(os.listdir(facebook_path)):
        if not (fname.startswith("meta-") and fname.endswith(".zip")):
            continue
        fpath = os.path.join(facebook_path, fname)
        try:
            z = zipfile.ZipFile(fpath)
        except Exception:
            continue

        for n in z.namelist():
            if not n.endswith(".json"):
                continue

            if n.endswith("comments_and_reactions/comments.json"):
                data = _load_json_from_zip(z, n)
                if not isinstance(data, dict):
                    continue
                for item in (data.get("comments_v2") or []):
                    ts = item.get("timestamp", 0)
                    if not ts or ts < 1000000:
                        continue
                    date = _ts_unix(ts)
                    for d in (item.get("data") or []):
                        cmt  = d.get("comment") or {}
                        text = _fix((cmt.get("comment") or "")).strip()
                        if text:
                            key = (date, text[:60])
                            if key not in seen_keys:
                                seen_keys.add(key)
                                all_comments.append((date, text))

            elif n.endswith("comments_and_reactions/your_comment_edits.json"):
                data = _load_json_from_zip(z, n)
                if not isinstance(data, list):
                    continue
                for item in data:
                    ts = item.get("timestamp", 0)
                    if not ts or ts < 1000000:
                        continue
                    date = _ts_unix(ts)
                    lv   = item.get("label_values") or []
                    text = _fix(next(
                        (x.get("value", "") for x in lv if x.get("label") == "Text"), ""
                    )).strip()
                    if text:
                        key = (date, text[:60])
                        if key not in seen_keys:
                            seen_keys.add(key)
                            all_comments.append((date, text))
        z.close()

    if not all_comments:
        print("  No Facebook comments found")
        return chunks

    all_comments.sort(key=lambda x: x[0])
    lines = [f"[{date}] {text}" for date, text in all_comments]
    dates = [c[0] for c in all_comments]

    chunks.append({
        "text": f"Facebook comments — {len(all_comments)} total\n\n" + "\n".join(lines),
        "metadata": {
            "source":        "facebook_comments",
            "date":          min(dates),
            "date_range":    f"{min(dates)} to {max(dates)}",
            "comment_count": len(all_comments),
            "priority":      "normal",
            "modality":      "text",
            "phase2":        False,
        },
    })

    print(f"  Facebook comments: {len(all_comments)}")
    return chunks


# ── POSTS ──────────────────────────────────────────────────

def parse_facebook_posts(facebook_path=FACEBOOK_PATH):
    chunks = []

    if not os.path.exists(facebook_path):
        return chunks

    print(f"Scanning Facebook posts: {facebook_path}")

    all_posts  = []
    seen_texts = set()

    for fname in sorted(os.listdir(facebook_path)):
        if not (fname.startswith("meta-") and fname.endswith(".zip")):
            continue
        fpath = os.path.join(facebook_path, fname)
        try:
            z = zipfile.ZipFile(fpath)
        except Exception:
            continue

        for n in z.namelist():
            if not n.endswith(".json"):
                continue
            basename = n.split("/")[-1]

            if "your_posts__check_ins" in basename or "posts_on_other_pages" in basename:
                data = _load_json_from_zip(z, n)
                if not isinstance(data, list):
                    continue
                for item in data:
                    ts = item.get("timestamp", 0)
                    if not ts or ts < 1000000:
                        continue
                    date = _ts_unix(ts)
                    lv   = item.get("label_values") or []
                    msg  = _fix(next(
                        (x.get("value", "") for x in lv if x.get("label") == "Message"), ""
                    )).strip()
                    if msg:
                        key = (date, msg[:80])
                        if key not in seen_texts:
                            seen_texts.add(key)
                            all_posts.append((date, msg))

            elif basename == "group_posts_and_comments.json":
                data = _load_json_from_zip(z, n)
                if not isinstance(data, dict):
                    continue
                for item in (data.get("group_posts_v2") or []):
                    ts = item.get("timestamp", 0)
                    if not ts or ts < 1000000:
                        continue
                    date = _ts_unix(ts)
                    for d in (item.get("data") or []):
                        text = _fix((d.get("post") or "")).strip()
                        if text:
                            key = (date, text[:80])
                            if key not in seen_texts:
                                seen_texts.add(key)
                                all_posts.append((date, text))
        z.close()

    if not all_posts:
        print("  No Facebook posts with text found")
        return chunks

    all_posts.sort(key=lambda x: x[0])

    by_year = defaultdict(list)
    for date, text in all_posts:
        by_year[date[:4]].append((date, text))

    for year in sorted(by_year):
        year_posts = by_year[year]
        lines      = [f"[{date}] {text}" for date, text in year_posts]
        dates      = [p[0] for p in year_posts]
        chunks.append({
            "text": f"Facebook posts — {year} ({len(year_posts)} posts)\n\n" + "\n".join(lines),
            "metadata": {
                "source":     "facebook_posts",
                "date":       min(dates),
                "date_range": f"{min(dates)} to {max(dates)}",
                "post_count": len(year_posts),
                "priority":   "normal",
                "modality":   "text",
                "phase2":     False,
            },
        })

    print(f"  Facebook posts: {len(all_posts)} with text, {len(chunks)} yearly chunks")
    return chunks


# ── MAIN ENTRY POINT ───────────────────────────────────────

def parse_facebook(facebook_path=FACEBOOK_PATH):
    chunks = []
    chunks.extend(parse_messenger(facebook_path))
    chunks.extend(parse_facebook_reactions(facebook_path))
    chunks.extend(parse_facebook_comments(facebook_path))
    chunks.extend(parse_facebook_posts(facebook_path))
    print(f"\nFacebook total chunks: {len(chunks)}")
    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    if target == "messenger":
        chunks = parse_messenger()
    elif target == "reactions":
        chunks = parse_facebook_reactions()
    elif target == "comments":
        chunks = parse_facebook_comments()
    elif target == "posts":
        chunks = parse_facebook_posts()
    else:
        chunks = parse_facebook()

    print(f"\nTotal chunks: {len(chunks)}")
    by_source = {}
    for c in chunks:
        s = c["metadata"]["source"]
        by_source[s] = by_source.get(s, 0) + 1
    for s, n in sorted(by_source.items()):
        print(f"  {s}: {n}")
