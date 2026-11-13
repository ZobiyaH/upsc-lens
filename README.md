# UPSC News Mapper (all GS papers, Prelims + Mains)

Newspaper PDF -> articles -> syllabus topic -> background, Prelims pointers, Mains question, similar past questions.
Every point is labelled Newspaper (green) / Your notes (blue) / AI knowledge (orange, verify it).

## Setup (once, a few minutes)
1. Python 3.10+.  `python -m venv venv`, activate it (Windows `venv\Scripts\activate`, Mac/Linux `source venv/bin/activate`)
2. `pip install -r requirements.txt`   (light: no PyTorch, no database, no Streamlit)
3. Copy `.env.example` to `.env`, paste your free Gemini key, check GEMINI_MODEL.

## Run
`python start.py` -> opens http://127.0.0.1:8000 in about 2 seconds. Upload a PDF, click Analyse. Results appear one by one.
First run downloads a small embedding model once (about 130 MB).

## Collect resources (public sources, automatic)
- `python -m src.collect_resources` : reads `data/sources.txt` (Constitution, Economic Survey, Budget, UPSC papers, anything you add) and converts to notes.
- `python -m src.fetch_pib`          : saves the latest PIB press releases. Run it daily.
- `python -m src.import_pyq`         : turns UPSC question-paper PDFs in `data/pyq_pdfs/` into `data/pyq.csv`. Then CHECK the CSV.
- Your own notes: drop PDF/TXT/MD files into `data/my_files/` (collect_resources converts them). Only use files you are allowed to keep, for personal study.
- Then ALWAYS: `python -m src.build_index` (notes are cached per file, so reruns are fast).

## Make highlights accurate
`python -m src.debug_pdf paper.pdf 1 2 3` writes `debug_page1.png` ... showing every detected article in its own colour with its headline.
Missed headlines -> lower HEAD_RATIO in `src/pdf_parser.py`. Junk picked up -> raise it. Short items dropped -> lower MIN_WORDS.

## Other files
`data/syllabus.txt` (edit freely, # disables a line) | `src/evaluate.py` (accuracy on `data/labeled_articles.json`) | `src/llm.py` (the prompt)

## Limits
- Articles that continue on another page are not joined. Heavily graphic layouts and scans may split badly.
- Orange items come from the model's memory; verify them. CSAT is not included.
- Check the Gemini model name and free limits yourself; they change.
