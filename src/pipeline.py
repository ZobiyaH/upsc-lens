"""parse -> filter -> retrieve -> LLM. Results are streamed through on_result as soon as each is ready."""
import time
from config import MIN_SIMILARITY, RATE_DELAY
from src.llm import analyse
from src.search import notes, pyqs, topics


def process(articles, on_progress=None, on_result=None):
    results = []
    for i, a in enumerate(articles):
        q = a["headline"] + ". " + a["text"][:1500]
        cand = topics(q)
        sim = max(c["similarity"] for c in cand)
        if sim >= MIN_SIMILARITY:                                   # cheap relevance filter
            out, cached = analyse(a, cand, notes(q))
            if out and out.get("relevant"):
                r = {**a, **out, "idx": i, "similarity": round(sim, 3), "pyqs": pyqs(q), "candidates": cand}
                results.append(r)
                if on_result:
                    on_result(r)
            if not cached:
                time.sleep(RATE_DELAY)                              # free-tier pacing
        if on_progress:
            on_progress(i + 1, len(articles))
    return results
