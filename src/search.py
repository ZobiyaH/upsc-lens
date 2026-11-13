"""Hybrid retrieval: embeddings (meaning) + BM25 (exact words), merged by rank."""
import re
from functools import lru_cache
from rank_bm25 import BM25Okapi
from src.store import coll, embed


def _tok(t):
    return re.findall(r"[a-z0-9]+", t.lower())


@lru_cache(maxsize=1)
def _bm25():
    return BM25Okapi([_tok(d) for d in coll("syllabus").docs])


def topics(text, k=5):
    c = coll("syllabus")
    q = embed([text[:2000]])[0]
    vec = c.query(q, 10)
    sims = {c.ids[i]: s for i, s in vec}
    sc = _bm25().get_scores(_tok(text))
    bm_ids = [c.ids[i] for i in sorted(range(len(c.ids)), key=lambda i: -sc[i])[:10]]
    fused = {}
    for ranking in ([c.ids[i] for i, _ in vec], bm_ids):
        for rank, i in enumerate(ranking):
            fused[i] = fused.get(i, 0) + 1 / (60 + rank)
    text_of = dict(zip(c.ids, c.docs))
    return [{"id": i, "text": text_of[i], "similarity": sims.get(i, 0.0)}
            for i in sorted(fused, key=fused.get, reverse=True)[:k]]


def _simple(name, text, k, min_sim=0.0):
    c = coll(name)
    q = embed([text[:2000]])[0]
    return [{"id": c.ids[i], "text": c.docs[i], "meta": c.metas[i], "similarity": s}
            for i, s in c.query(q, k) if s >= min_sim]


def pyqs(text, k=3):
    return _simple("pyq", text, k, 0.5)


def notes(text, k=3):
    return _simple("notes", text, k, 0.4)
