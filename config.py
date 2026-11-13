import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
INDEX = DATA / "index"

EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
MIN_SIMILARITY = float(os.getenv("MIN_SIMILARITY", "0.45"))
RATE_DELAY = float(os.getenv("RATE_DELAY", "4.5"))
