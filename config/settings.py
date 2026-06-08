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
    "chatgpt":        f"{SSD_BASE}/chatgpt_ciai",
    "discord":        f"{SSD_BASE}/discord",
    "instagram":      f"{SSD_BASE}/instagram",
    "messenger":      f"{SSD_BASE}/messenger",
    "facebook":       f"{SSD_BASE}/facebook",
    "whatsapp":       f"{SSD_BASE}/whatsapp",
    "linkedin":       f"{SSD_BASE}/linkedin",
    "spotify":        f"{SSD_BASE}/spotify",
    "letterboxd":     f"{SSD_BASE}/letterboxd-sma_purno-2025-08-30-10-56-utc",
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

EMBEDDING_MODEL = "BAAI/bge-m3"  # local, multilingual, 8192 token limit, Bangla-native
CHUNK_SIZE      = 512             # tiktoken cl100k_base tokens; well within bge-m3's 8192 limit
CHUNK_OVERLAP   = 50              # ~10% overlap between consecutive chunks

LLM_MODEL = "llama3.2"  # local Ollama model

# language settings
PRIMARY_LANGUAGES   = ["en", "bn"]
WHISPER_LANGUAGE    = "bn"  # for Bangla audio transcription
