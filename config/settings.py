import os

SSD_BASE       = "/Volumes/SSD1/personal-kb-data"
CHROMA_DB_PATH = f"{SSD_BASE}/chroma_db"

ACCOUNT_PATHS = {
    "purno230":       f"{SSD_BASE}/purno230",
    "ciai":           f"{SSD_BASE}/ciai",
    "alisyed_office": f"{SSD_BASE}/alisyed_office",
    "purnoli230":     f"{SSD_BASE}/purnoli230",
    "purno240":       f"{SSD_BASE}/purno240",
    "uni_aiub":       f"{SSD_BASE}/uni_aiub",
}

OTHER_PATHS = {
    "chatgpt":        f"{SSD_BASE}/chatgpt",
    "discord":        f"{SSD_BASE}/discord",
    "instagram":      f"{SSD_BASE}/instagram",
    "messenger":      f"{SSD_BASE}/messenger",
    "whatsapp":       f"{SSD_BASE}/whatsapp",
    "linkedin":       f"{SSD_BASE}/linkedin",
    "spotify":        f"{SSD_BASE}/spotify",
    "notion":         f"{SSD_BASE}/notion",
    "android":        f"{SSD_BASE}/android",
    "windows_laptop": f"{SSD_BASE}/windows_laptop",
}

PRIORITY_PROJECTS = [
    "Side Projects and Life",
]

IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"]
ZIP_EXTENSIONS   = [".zip", ".rar", ".tar", ".gz"]
SKIP_EXTENSIONS  = [".torrent"]

LARGE_VIDEO_THRESHOLD_MB = 500

EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE      = 1000
CHUNK_OVERLAP   = 100

LLM_MODEL = "claude-sonnet-4-20250514"

# language settings
PRIMARY_LANGUAGES   = ["en", "bn"]
WHISPER_LANGUAGE    = "bn"  # for Bangla audio transcription