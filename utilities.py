from pathlib import Path
from datetime import datetime
import shutil
import rich
from constant_details import BASE_DIR, LOG_FILES_DIR, TEMP_LOG_FILES_DIR


def log_details(message):

    time = datetime.now()

    TEMP_LOG_FILE = Path(f"{time.strftime("%Y-%m-%d")}.tmp.log")

    TEMP_LOG_FILE_PATH = BASE_DIR / TEMP_LOG_FILES_DIR / TEMP_LOG_FILE
    
    # Print to terminal using Rich
    rich.print(message)

    # Write to file
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with TEMP_LOG_FILE_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
        
        
def start_logging():
    time = datetime.now()
    
    LOG_FILES_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_LOG_FILES_DIR.mkdir(parents=True, exist_ok=True)
    
    TODAYS_LOG_FILE = Path(f"{time.strftime("%Y-%m-%d")}.log")
    TODAYS_LOG_FILE_PATH = LOG_FILES_DIR / TODAYS_LOG_FILE
    
    TODAYS_TEMP_LOG_FILE = Path(f"{time.strftime("%Y-%m-%d")}.tmp.log")
    TODAYS_TEMP_LOG_FILE_PATH = TEMP_LOG_FILES_DIR / TODAYS_TEMP_LOG_FILE
    
    empty_directory(LOG_FILES_DIR, preserve_file=TODAYS_LOG_FILE_PATH)
    empty_directory(TEMP_LOG_FILES_DIR, preserve_file=TODAYS_TEMP_LOG_FILE_PATH)
    

def complete_logging():
    try:
        
        time = datetime.now()

        LOG_FILES_DIR.mkdir(parents=True, exist_ok=True)

        TEMP_LOG_FILE = Path(f"{time.strftime("%Y-%m-%d")}.tmp.log")
        FINAL_LOG_FILE = Path(f"{time.strftime("%Y-%m-%d")}.log")

        TEMP_LOG_FILE_PATH = TEMP_LOG_FILES_DIR / TEMP_LOG_FILE
        FINAL_LOG_FILE_PATH = LOG_FILES_DIR / FINAL_LOG_FILE
        
        log_details(f"Removing {TEMP_LOG_FILE_PATH}")
        
        with TEMP_LOG_FILE_PATH.open("rb") as temp_file, \
            FINAL_LOG_FILE_PATH.open("ab") as final_file:
            shutil.copyfileobj(temp_file, final_file)
            
        TEMP_LOG_FILE_PATH.unlink()

    except Exception as e:
        log_details(
            f"Some exception occurred while copying tmp.log file to log file: "
            f"{type(e).__name__}: {e}"
        )
    
    
def empty_directory(path: Path, preserve_file: Path | None = None):
    dir_path = Path(path)

    # Ensure the path exists and is a directory
    if not dir_path.is_dir():
        log_details(f"{dir_path} is not a valid directory.")
        return

    # Resolve the excluded file path, if provided
    excluded_path = (
        Path(preserve_file).resolve()
        if preserve_file is not None
        else None
    )

    for item in dir_path.iterdir():
        try:
            # Skip the file specified by preserve_file
            if excluded_path is not None and item.resolve() == excluded_path:
                continue

            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

        except Exception as e:
            log_details(f"Failed to delete {item}. Reason: {e}")