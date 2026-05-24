import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
DATA_PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
DB_PATH = os.path.join(DATA_PROCESSED_DIR, "edupulse.db")
DB_URL = f"sqlite:///{DB_PATH}"

os.makedirs(DATA_PROCESSED_DIR, exist_ok=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.1-8b-instant"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

CSV_FILES = {
    "students": "students_2023_24.csv",
    "enrollments": "program_enrollments.csv",
    "attendance": "attendance_log.csv",
    "assessments": "assessment_scores.csv",
    "grants": "grants_outcomes.csv",
    "staff": "staff_roster.csv",
}
