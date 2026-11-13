"""One command:  python start.py"""
import sys, threading, webbrowser
from config import GEMINI_API_KEY, INDEX

if not GEMINI_API_KEY:
    sys.exit("Copy .env.example to .env and paste your free Gemini key first.")
if not (INDEX / "syllabus.json").exists():
    print("First run: building the index (downloads a small embedding model once)...")
    from src.build_index import main
    main()
import uvicorn
threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:8000")).start()
uvicorn.run("server:app", host="127.0.0.1", port=8000, log_level="warning")
