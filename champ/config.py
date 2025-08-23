import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDyTuUsLjdW1reNFVTQd0YT4mf1sE81ZsY")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")

SQLSERVER_DSN = os.getenv("SQLSERVER_DSN", "")
TENANT_KEY = os.getenv("TENANT_KEY", "user_id")
DB_MAX_ROWS = int(os.getenv("DB_MAX_ROWS", "1000"))
