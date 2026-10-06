from pathlib import Path
from datetime import datetime
import shutil
import rich
from constant_details import BASE_DIR, LOG_FILES_DIR


def log_details(message):

    time = datetime.now()

    TEMP_LOG_FILE = Path(f"{time.strftime("%Y-%m-%d")}.tmp.log")

    TEMP_LOG_FILE_PATH = BASE_DIR / TEMP_LOG_FILE
    
    # Print to terminal using Rich
    rich.print(message)

    # Write to file
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with TEMP_LOG_FILE_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
        
        
def start_logging():
    LOG_FILES_DIR.mkdir(parents=True, exist_ok=True)
    empty_directory(LOG_FILES_DIR)
    

def complete_logging():
    
    time = datetime.now()

    LOG_FILES_DIR.mkdir(parents=True, exist_ok=True)

    TEMP_LOG_FILE = Path(f"{time.strftime("%Y-%m-%d")}.tmp.log")
    FINAL_LOG_FILE = Path(f"{time.strftime("%Y-%m-%d")}.log")

    TEMP_LOG_FILE_PATH = BASE_DIR / TEMP_LOG_FILE
    FINAL_LOG_FILE_PATH = LOG_FILES_DIR / FINAL_LOG_FILE
    
    with TEMP_LOG_FILE_PATH.open("r") as temp_file, \
        FINAL_LOG_FILE_PATH.open("a") as final_file:
        shutil.copyfileobj(temp_file, final_file)

    TEMP_LOG_FILE_PATH.unlink()
    

def empty_directory(path: Path):
    dir_path = Path(path)
    
    # Ensure the path exists and is a directory
    if not dir_path.is_dir():
        log_details(f"{dir_path} is not a valid directory.")
        return

    for item in dir_path.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()  # Delete file or symbolic link
            elif item.is_dir():
                shutil.rmtree(item)  # Delete folder and all its contents
        except Exception as e:
            log_details(f"Failed to delete {item}. Reason: {e}")

