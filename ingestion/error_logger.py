import os
import sys
from datetime import datetime

sys.path.append(os.path.expanduser("~/personal-kb"))
from config.settings import SSD_BASE

LOG_PATH = os.path.join(SSD_BASE, "ingestion_errors.log")


def log_error(source, filepath, error):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    error_message = str(error)
    line = f"{timestamp} | {source} | {filepath} | {error_message}\n"

    try:
        log_dir = os.path.dirname(LOG_PATH)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)

        print(line, end="")
    except Exception:
        pass


if __name__ == "__main__":
    log_error("test_source", "/fake/path/file.json", ValueError("test error message"))
    print(f"Done — check log at {LOG_PATH}")
