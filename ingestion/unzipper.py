import os
import zipfile
import sys
sys.path.append(os.path.expanduser("~/personal-kb"))

from config.settings import ACCOUNT_PATHS, OTHER_PATHS

# ── CONFIGURATION ──────────────────────────────────────────

ALL_FOLDERS = {**ACCOUNT_PATHS, **OTHER_PATHS}


# ── EXTRACTOR ──────────────────────────────────────────────

def extract_zip(zip_path, destination_folder):
    """
    Extracts everything from a zip into the same folder it lives in.
    No filtering — everything gets extracted.
    We review and clean up unwanted files later.
    """
    extracted = 0
    failed    = 0

    with zipfile.ZipFile(zip_path, 'r') as zf:
        all_files = zf.namelist()
        print(f"    Found {len(all_files)} files inside zip")

        for file_path in all_files:

            if not os.path.basename(file_path):
                continue

            try:
                zf.extract(file_path, destination_folder)
                extracted += 1

                if extracted % 500 == 0:
                    print(f"    Extracted {extracted} files so far...")

            except Exception as e:
                print(f"    Could not extract {os.path.basename(file_path)}: {e}")
                failed += 1

    return extracted, failed


# ── ZIP FINDER ─────────────────────────────────────────────

def find_zips_in_folder(folder_path):
    """
    Walks through a folder and finds all zip files inside it.
    Includes zips inside subfolders too.
    """
    zip_files = []

    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".zip"):
                zip_files.append(os.path.join(root, file))

    return zip_files


# ── MAIN ───────────────────────────────────────────────────

def unzip_all():
    """
    Goes through every account folder on the SSD,
    finds all zip files inside them,
    and extracts them right there in place.
    """
    total_zips = 0

    for account_name, account_path in ALL_FOLDERS.items():

        if not os.path.exists(account_path):
            continue

        zip_files = find_zips_in_folder(account_path)

        if not zip_files:
            print(f"{account_name}: no zip files found, skipping")
            continue

        print(f"\n{account_name}: found {len(zip_files)} zip file(s)")

        for zip_path in zip_files:
            zip_filename = os.path.basename(zip_path)
            destination  = os.path.dirname(zip_path)

            print(f"  Extracting: {zip_filename}")
            print(f"  Into:       {destination}")

            extracted, failed = extract_zip(zip_path, destination)

            print(f"  Extracted: {extracted} files")
            if failed:
                print(f"  Failed:    {failed} files")

            total_zips += 1

    if total_zips == 0:
        print("\nNo zip files found in any account folder.")
        print("Make sure your zip files are inside the SSD account folders.")
    else:
        print(f"\nAll done! Processed {total_zips} zip file(s).")


# ── RUN ────────────────────────────────────────────────────

if __name__ == "__main__":
    unzip_all()