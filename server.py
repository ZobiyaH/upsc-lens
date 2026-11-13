
"""Fast web server (FastAPI). Starts quickly; models load in the background."""

import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from src.pdf_parser import parse, render
from src.pipeline import process


app = FastAPI()

# In-memory storage for analysis jobs.
JOBS = {}


# --------------------------------------------------
# STARTUP: Warm up the embedding model in background
# --------------------------------------------------

@app.on_event("startup")
def warm():

    def w():
        try:
            from src.store import embed

            embed(["warm up"])
            print("[STARTUP] Embedding model warmed up.")

        except Exception as e:
            print(f"[STARTUP] Warm-up failed: {e}")

    threading.Thread(
        target=w,
        daemon=True
    ).start()


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.get("/")
def home():

    html_path = Path(__file__).resolve().parent / "static" / "index.html"

    if not html_path.exists():
        raise HTTPException(
            status_code=404,
            detail="static/index.html not found"
        )

    return FileResponse(html_path)


# --------------------------------------------------
# START PDF ANALYSIS
# --------------------------------------------------

@app.post("/api/analyse")
async def analyse(
    file: UploadFile = File(...),
    pages: int = Form(0)
):

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF file."
        )

    pdf = await file.read()

    if not pdf:
        raise HTTPException(
            status_code=400,
            detail="Uploaded PDF is empty."
        )

    jid = uuid.uuid4().hex[:8]

    job = JOBS[jid] = {
        "status": "parsing",
        "done": 0,
        "total": 0,
        "results": [],
        "pdf": pdf,
        "articles": [],
        "error": None
    }

    def run():

        try:
            print(f"[JOB {jid}] Starting PDF parsing...")

            articles = parse(pdf, pages or None)

            job["articles"] = articles
            job["total"] = len(articles)
            job["status"] = "analysing"

            print(
                f"[JOB {jid}] Found {len(articles)} articles."
            )

            def update_progress(done, total):
                job["done"] = done

            def add_result(result):
                job["results"].append(result)

            process(
                articles,
                on_progress=update_progress,
                on_result=add_result
            )

            job["status"] = "done"

            print(
                f"[JOB {jid}] Analysis completed. "
                f"{len(job['results'])} relevant articles found."
            )

        except Exception as e:

            job["status"] = "error"
            job["error"] = str(e)

            print(f"[JOB {jid}] ERROR: {e}")

    threading.Thread(
        target=run,
        daemon=True
    ).start()

    return {"job": jid}


# --------------------------------------------------
# GET ANALYSIS PROGRESS AND RESULTS
# --------------------------------------------------

@app.get("/api/job/{jid}")
def job_status(jid: str):

    j = JOBS.get(jid)

    if not j:
        raise HTTPException(
            status_code=404,
            detail="Analysis job not found."
        )

    return {
        "status": j["status"],
        "done": j["done"],
        "total": j["total"],
        "error": j["error"],
        "results": list(j["results"])
    }


# --------------------------------------------------
# GET ORIGINAL NEWSPAPER PAGE WITH ARTICLE HIGHLIGHT
# --------------------------------------------------

@app.get("/api/image/{jid}/{idx}")
def image(jid: str, idx: int):

    print(
        f"[IMAGE] Request received: job={jid}, article_index={idx}"
    )

    # Check whether the job exists.
    j = JOBS.get(jid)

    if not j:
        print(f"[IMAGE] Job not found: {jid}")

        raise HTTPException(
            status_code=404,
            detail="Analysis job not found."
        )

    # Validate article index.
    articles = j.get("articles", [])

    if idx < 0 or idx >= len(articles):
        print(
            f"[IMAGE] Invalid article index: {idx}. "
            f"Available articles: {len(articles)}"
        )

        raise HTTPException(
            status_code=404,
            detail="Article index not found."
        )

    try:

        # IMPORTANT:
        # idx is the original article index from the parser.
        # Do not replace it with the filtered results position.

        art = articles[idx]

        print(
            f"[IMAGE] Rendering page {art['page']} "
            f"for article index {idx}"
        )

        # Render the original newspaper page with the
        # selected article highlighted.
        image_bytes = render(
            j["pdf"],
            art["page"],
            articles,
            active=art
        )

        if not image_bytes:
            raise ValueError("PDF renderer returned empty image data.")

        print(
            f"[IMAGE] Successfully rendered article {idx}"
        )

        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={
                "Cache-Control": "no-store"
            }
        )

    except HTTPException:
        raise

    except Exception as e:

        print(
            f"[IMAGE] Rendering failed for "
            f"job={jid}, index={idx}: {e}"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Could not render newspaper page: {str(e)}"
        )
