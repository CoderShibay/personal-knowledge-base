import os
import json
import csv
import re
import sys
from datetime import datetime
from collections import defaultdict

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import OTHER_PATHS, PRIORITY_PROJECTS

# ── CONFIGURATION ──────────────────────────────────────────

INSTAGRAM_PATH = OTHER_PATHS["instagram"]
FACEBOOK_PATH  = OTHER_PATHS["facebook"]
LINKEDIN_PATH  = OTHER_PATHS["linkedin"]

# Map content patterns to short descriptive tags
# Used when a message has no text but represents a real event
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


# ── ENCODING FIX ───────────────────────────────────────────

def _fix(s):
    """
    Meta exports store UTF-8 strings (emojis, non-ASCII) as latin-1 codepoints.
    Decode them back to proper UTF-8. Falls back to original on failure.
    """
    if not s:
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


# ── SHARED HELPERS ─────────────────────────────────────────

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


def _load_json(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"    Could not read {filepath}: {e}")
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


# ── META THREAD PARSER (Instagram DMs + Messenger) ─────────

def _find_message_dirs(base_path):
    """
    Walk base_path and return all .../messages/inbox and
    .../messages/message_requests directories at any depth.
    """
    found = []
    for root, dirs, files in os.walk(base_path):
        parent = os.path.basename(os.path.dirname(root))
        name   = os.path.basename(root)
        if parent == "messages" and name in ("inbox", "message_requests", "broadcast"):
            found.append(root)
    return found


def _format_share(share):
    """Format a share object into a readable string with full caption."""
    owner      = _fix(share.get("original_content_owner") or "")
    username   = _fix(share.get("profile_share_username")  or "")
    name       = _fix(share.get("profile_share_name")      or "")
    link       = share.get("link") or ""
    share_text = _fix(share.get("share_text") or "").strip()

    if username:
        # Profile share — someone shared an account
        label = f"[shared profile: @{username}" + (f" ({name})" if name else "") + "]"
        return label + (f" {link}" if link else "")

    parts = []
    if owner:
        parts.append(f"@{owner}")
    if link:
        parts.append(link)
    header = "[shared: " + " | ".join(parts) + "]" if parts else "[shared]"

    if share_text:
        return header + "\n    " + share_text  # full caption, no truncation

    return header


def _parse_message(msg):
    """
    Returns (formatted_line, date) for one message.
    Nothing is dropped — every event is represented.
    Attachment notifications → short tags ([photo], [video], etc.)
    Shared posts → full creator + link + complete caption.
    """
    raw_content = (msg.get("content") or "").strip()
    content     = _fix(raw_content)
    sender      = _fix(msg.get("sender_name") or "Unknown")
    date        = _ts_ms(msg.get("timestamp_ms", 0))
    share       = msg.get("share")

    # Share takes priority — always use it when present
    if share:
        content = _format_share(share)
        return f"[{date}] {sender}: {content}", date

    # No share — check if it is an attachment/event notification
    if not content:
        return f"[{date}] {sender}: [media]", date

    tag = _media_tag(content)
    if tag:
        return f"[{date}] {sender}: {tag}", date

    # Regular text message
    return f"[{date}] {sender}: {content}", date


def parse_meta_thread(source, thread_folder):
    thread_name_raw = os.path.basename(thread_folder)

    message_files = sorted(
        os.path.join(thread_folder, f)
        for f in os.listdir(thread_folder)
        if f.lower().startswith("message_") and f.lower().endswith(".json")
    )
    if not message_files:
        return None

    lines = []
    dates = []
    title = thread_name_raw  # fallback

    for message_file in message_files:
        data = _load_json(message_file)
        if not data:
            continue

        # Use the thread title from the JSON (first file wins)
        if title == thread_name_raw and data.get("title"):
            title = _fix(data["title"])

        messages = data.get("messages", [])
        if not isinstance(messages, list):
            continue

        for msg in messages:
            line, date = _parse_message(msg)
            if line:
                lines.append(line)
                dates.append(date)

    if not lines:
        return None

    return _build_chunk(source, title, lines, dates, len(lines))


def _parse_message_dirs(source, message_dirs):
    chunks = []
    for msg_dir in message_dirs:
        thread_folders = [
            os.path.join(msg_dir, d)
            for d in os.listdir(msg_dir)
            if os.path.isdir(os.path.join(msg_dir, d))
        ]
        for thread_folder in thread_folders:
            chunk = parse_meta_thread(source, thread_folder)
            if chunk is None:
                continue
            chunks.append(chunk)
            label = " [PRIORITY]" if chunk["metadata"]["priority"] == "high" else ""
            print(f"  {chunk['metadata']['thread_name']} "
                  f"({chunk['metadata']['message_count']} messages){label}")
    return chunks


# ── INSTAGRAM-SPECIFIC PARSERS ──────────────────────────────

def _find_instagram_dir(instagram_path):
    """Return the instagram-USER-DATE directory inside the Meta export."""
    for root, dirs, files in os.walk(instagram_path):
        for d in dirs:
            if d.startswith("instagram-"):
                return os.path.join(root, d)
    return None


def parse_instagram_comments(instagram_dir):
    """Parse post and reels comments written by the user."""
    comments_dir = os.path.join(instagram_dir, "your_instagram_activity", "comments")
    if not os.path.isdir(comments_dir):
        return []

    all_comments = []

    # post_comments_1.json — list of {string_map_data: {Comment, Media Owner, Time}}
    post_file = os.path.join(comments_dir, "post_comments_1.json")
    if os.path.exists(post_file):
        data = _load_json(post_file) or []
        if isinstance(data, list):
            for item in data:
                smd = item.get("string_map_data", {})
                text  = _fix((smd.get("Comment") or {}).get("value") or "").strip()
                owner = _fix((smd.get("Media Owner") or {}).get("value") or "").strip()
                ts    = (smd.get("Time") or {}).get("timestamp", 0)
                date  = _ts_unix(ts)
                if text:
                    all_comments.append((date, owner, text))

    # reels_comments.json — {comments_reels_comments: [...]}
    reels_file = os.path.join(comments_dir, "reels_comments.json")
    if os.path.exists(reels_file):
        data = _load_json(reels_file) or {}
        for item in data.get("comments_reels_comments", []):
            smd   = item.get("string_map_data", {})
            text  = _fix((smd.get("Comment") or {}).get("value") or "").strip()
            owner = _fix((smd.get("Media Owner") or {}).get("value") or "").strip()
            ts    = (smd.get("Time") or {}).get("timestamp", 0)
            date  = _ts_unix(ts)
            if text:
                all_comments.append((date, owner, text))

    if not all_comments:
        return []

    all_comments.sort(key=lambda x: x[0])
    lines = [
        f"[{date}] On @{owner}'s post: {text}" if owner else f"[{date}] {text}"
        for date, owner, text in all_comments
    ]
    dates = [c[0] for c in all_comments]

    print(f"  Comments: {len(all_comments)}")
    return [{
        "text": f"Instagram comments — {len(all_comments)} total\n\n" + "\n".join(lines),
        "metadata": {
            "source":        "instagram_comments",
            "date":          min(dates),
            "date_range":    f"{min(dates)} to {max(dates)}",
            "comment_count": len(all_comments),
            "priority":      "normal",
            "modality":      "text",
            "phase2":        False,
        },
    }]


def parse_instagram_saves(instagram_dir):
    """Parse saved posts — grouped by creator, one chunk per creator with >=3 saves."""
    saved_file = os.path.join(
        instagram_dir, "your_instagram_activity", "saved", "saved_posts.json"
    )
    if not os.path.exists(saved_file):
        return []

    data = _load_json(saved_file) or {}
    items = data.get("saved_saved_media", [])
    if not items:
        return []

    # Group by creator (title field = username)
    by_creator = defaultdict(list)
    for item in items:
        creator = _fix((item.get("title") or "")).strip() or "unknown"
        ts      = (item.get("string_map_data") or {})
        ts      = (ts.get("Saved on") or {}).get("timestamp", 0)
        date    = _ts_unix(ts)
        href    = ((item.get("string_map_data") or {}).get("Saved on") or {}).get("href", "")
        by_creator[creator].append((date, href))

    chunks = []

    # One chunk per creator with >= 3 saves
    frequent = {c: saves for c, saves in by_creator.items() if len(saves) >= 3}
    long_tail = {c: saves for c, saves in by_creator.items() if len(saves) < 3}

    for creator, saves in sorted(frequent.items(), key=lambda x: -len(x[1])):
        saves_sorted = sorted(saves, key=lambda x: x[0])
        dates        = [s[0] for s in saves_sorted]
        lines        = [f"[{d}] {href}" if href else f"[{d}]" for d, href in saves_sorted]
        chunks.append({
            "text": f"Instagram saves — @{creator} ({len(saves)} saves, "
                    f"{dates[0]} to {dates[-1]})\n\n" + "\n".join(lines),
            "metadata": {
                "source":     "instagram_saves",
                "creator":    creator,
                "date":       dates[0],
                "date_range": f"{dates[0]} to {dates[-1]}",
                "save_count": len(saves),
                "priority":   "normal",
                "modality":   "text",
                "phase2":     False,
            },
        })

    # One summary chunk for the long tail
    if long_tail:
        tail_lines = [f"@{c}: {len(s)} save(s)" for c, s in sorted(long_tail.items())]
        chunks.append({
            "text": f"Instagram saves — {len(long_tail)} other creators (1-2 saves each)\n\n"
                    + "\n".join(tail_lines),
            "metadata": {
                "source":     "instagram_saves",
                "creator":    "various",
                "date":       "unknown",
                "date_range": "unknown",
                "save_count": sum(len(s) for s in long_tail.values()),
                "priority":   "normal",
                "modality":   "text",
                "phase2":     False,
            },
        })

    total_saves = sum(len(s) for s in by_creator.values())
    print(f"  Saves: {total_saves} saves, {len(by_creator)} creators, {len(chunks)} chunks")
    return chunks


def _extract_like_owner(entry):
    """Extract creator username from liked_posts.json entry."""
    for item in entry.get("label_values", []):
        if item.get("title") == "Owner":
            for d in item.get("dict", []):
                for subitem in d.get("dict", []):
                    if subitem.get("label") == "Username":
                        return (subitem.get("value") or "").strip()
    return ""


def parse_instagram_likes(instagram_dir):
    """Parse liked posts — one chunk per month showing top creators."""
    liked_file = os.path.join(
        instagram_dir, "your_instagram_activity", "likes", "liked_posts.json"
    )
    if not os.path.exists(liked_file):
        return []

    data = _load_json(liked_file) or []
    if not isinstance(data, list) or not data:
        return []

    # Group by YYYY-MM
    by_month = defaultdict(lambda: defaultdict(int))  # month -> creator -> count

    for entry in data:
        ts      = entry.get("timestamp", 0)
        date    = _ts_unix(ts)
        month   = date[:7]  # YYYY-MM
        creator = _extract_like_owner(entry) or "unknown"
        by_month[month][creator] += 1

    chunks = []

    for month in sorted(by_month):
        creator_counts = by_month[month]
        total          = sum(creator_counts.values())
        top            = sorted(creator_counts.items(), key=lambda x: -x[1])[:10]

        top_lines = [f"  @{c}: {n}" for c, n in top]
        others    = total - sum(n for _, n in top)
        if others > 0:
            top_lines.append(f"  (+ {others} likes from other creators)")

        chunks.append({
            "text": f"Instagram likes — {month} ({total} likes)\n\n"
                    + "\n".join(top_lines),
            "metadata": {
                "source":     "instagram_likes",
                "date":       f"{month}-01",
                "date_range": month,
                "like_count": total,
                "priority":   "normal",
                "modality":   "text",
                "phase2":     False,
            },
        })

    total_likes = sum(sum(c.values()) for c in by_month.values())
    print(f"  Likes: {total_likes} likes across {len(by_month)} months, {len(chunks)} chunks")
    return chunks


# ── SOURCE PARSERS ─────────────────────────────────────────

def parse_instagram(instagram_path=INSTAGRAM_PATH):
    chunks = []

    if not os.path.exists(instagram_path):
        print(f"No Instagram data found at {instagram_path}")
        return chunks

    print(f"Scanning Instagram: {instagram_path}")

    instagram_dir = _find_instagram_dir(instagram_path)

    # DMs — inbox + message_requests
    message_dirs = _find_message_dirs(instagram_path)
    if not message_dirs:
        print(f"  No message dirs found — zip may not be extracted yet")
    else:
        print(f"  Found {len(message_dirs)} message dir(s) (inbox + requests)")
        chunks.extend(_parse_message_dirs("instagram", message_dirs))

    # Activity data — only if instagram dir found
    if instagram_dir:
        chunks.extend(parse_instagram_comments(instagram_dir))
        chunks.extend(parse_instagram_saves(instagram_dir))
        chunks.extend(parse_instagram_likes(instagram_dir))
    else:
        print("  Instagram user dir not found — skipping activity data")

    print(f"Instagram total chunks: {len(chunks)}")
    return chunks


def parse_messenger(facebook_path=FACEBOOK_PATH):
    chunks = []

    if not os.path.exists(facebook_path):
        print(f"No Facebook/Messenger data found at {facebook_path}")
        return chunks

    print(f"Scanning Messenger (Facebook export): {facebook_path}")

    message_dirs = _find_message_dirs(facebook_path)

    if not message_dirs:
        print(f"  No messages/inbox found — zips may not be extracted yet")
        return chunks

    print(f"  Found {len(message_dirs)} message dir(s)")
    chunks = _parse_message_dirs("messenger", message_dirs)

    print(f"Messenger chunks: {len(chunks)}")
    return chunks


def parse_linkedin(linkedin_path=LINKEDIN_PATH):
    chunks = []

    csv_path = os.path.join(linkedin_path, "messages.csv")
    if not os.path.exists(csv_path):
        print(f"No LinkedIn messages.csv found at {csv_path}")
        return chunks

    print(f"Scanning LinkedIn messages: {csv_path}")

    conversations = {}

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                convo_id    = (row.get("CONVERSATION ID") or "").strip()
                content     = (row.get("CONTENT") or "").strip()
                thread_name = (row.get("CONVERSATION TITLE") or "Untitled").strip()
                sender      = (row.get("FROM") or "Unknown").strip()
                raw_date    = (row.get("DATE") or "").strip()

                if not convo_id or not content:
                    continue

                try:
                    date = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).strftime("%Y-%m-%d")
                except Exception:
                    date = raw_date[:10] if len(raw_date) >= 10 else "unknown"

                if convo_id not in conversations:
                    conversations[convo_id] = {"thread_name": thread_name, "lines": [], "dates": []}

                conversations[convo_id]["lines"].append(f"[{date}] {sender}: {content}")
                conversations[convo_id]["dates"].append(date)
    except Exception as e:
        print(f"Could not parse LinkedIn CSV: {e}")
        return chunks

    for convo in conversations.values():
        if not convo["lines"]:
            continue
        chunk = _build_chunk("linkedin", convo["thread_name"], convo["lines"], convo["dates"], len(convo["lines"]))
        chunks.append(chunk)
        label = " [PRIORITY]" if chunk["metadata"]["priority"] == "high" else ""
        print(f"  {chunk['metadata']['thread_name']} ({chunk['metadata']['message_count']} messages){label}")

    print(f"LinkedIn chunks: {len(chunks)}")
    return chunks


# ── MAIN ───────────────────────────────────────────────────

def parse_all_social():
    chunks = []
    chunks.extend(parse_instagram())
    chunks.extend(parse_messenger())
    chunks.extend(parse_linkedin())
    print(f"\nDone! Total social chunks: {len(chunks)}")
    return chunks


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = parse_instagram()

    print(f"\nTotal chunks: {len(chunks)}")

    by_source = {}
    for c in chunks:
        s = c["metadata"]["source"]
        by_source[s] = by_source.get(s, 0) + 1
    for s, n in sorted(by_source.items()):
        print(f"  {s}: {n}")

    if chunks:
        # Find first DM chunk for preview
        dm = next((c for c in chunks if c["metadata"]["source"] == "instagram"), None)
        if dm:
            print(f"\n── DM PREVIEW ──")
            print(dm["text"][:400])

        # Find a likes chunk
        like = next((c for c in chunks if c["metadata"]["source"] == "instagram_likes"), None)
        if like:
            print(f"\n── LIKES PREVIEW ──")
            print(like["text"][:400])

        # Find a saves chunk
        save = next((c for c in chunks if c["metadata"]["source"] == "instagram_saves"), None)
        if save:
            print(f"\n── SAVES PREVIEW ──")
            print(save["text"][:400])
