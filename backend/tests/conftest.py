import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")
os.environ.setdefault("REACT_APP_BACKEND_URL", "http://localhost:8001")
