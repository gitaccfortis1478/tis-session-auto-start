from enum import Enum
from pathlib import Path

BASE_DIR = Path(__file__).parent

# SESSIONS_URL = "https://tis-mentor.onrender.com/sessions"
SESSIONS_URL = "https://tis-mentor.vercel.app/sessions"

SELENIUM_PROFILE = r"C:\Users\thein\TIS Mentor Additional Chrome Profile\selenium_chrome"

SESSION_LOAD_TIMEOUT = 10

UPCOMING_SCHEDULES_DIR = "upcoming_schedules"

PYTHON_EXE = Path(r"C:\Users\thein\AppData\Local\Programs\Python\Python313\python.exe")

TODAYS_SCHEDULE_SCRIPT = BASE_DIR / "todays_schedule.py"

SESSION_STARTER_SCRIPT = BASE_DIR / "session_starter.py"

SESSION_ENDER_SCRIPT = BASE_DIR / "session_ender.py"

LOG_FILES_DIR = BASE_DIR / "log_files"

SESSION_STARTER_ARGUMENT_NAME = "--prev-session-id-for-message"

SESSION_ENDER_ARGUMENT_NAME = "--session-id-for-message"

class CSSClassName(str, Enum):
    SESSION_CARD_CONTAINER = ".session-card-container"
    SESSION_CARD_DATE_BLOCK = ".session-card-date-block"

