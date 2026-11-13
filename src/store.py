"""Tiny vector store: fastembed (fast ONNX embeddings, no PyTorch) + numpy files. No database needed."""
import json
from functools import lru_cache
import numpy as np
from config import EMBED_MODEL, INDEX


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding      # imported lazily so the app starts instantly
    return TextEmbedding(EMBED_MODEL)


def embed(texts):
    v = np.array(list(_model().embed(list(texts))), dtype="float32")
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)   # unit length: dot product = cosine


def save(name, ids, docs, metas, vecs):
    INDEX.mkdir(parents=True, exist_ok=True)
    np.save(INDEX / f"{name}.npy", np.asarray(vecs, dtype="float32") if len(ids) else np.zeros((0, 1), "float32"))
    (INDEX / f"{name}.json").write_text(json.dumps({"ids": ids, "docs": docs, "metas": metas}), encoding="utf-8")


class Coll:
    def __init__(self, name):
        d = json.loads((INDEX / f"{name}.json").read_text(encoding="utf-8"))
        self.ids, self.docs, self.metas = d["ids"], d["docs"], d["metas"]
        self.vecs = np.load(INDEX / f"{name}.npy")

    def query(self, qvec, k):
        if not self.ids:
            return []
        sc = self.vecs @ qvec
        return [(int(i), float(sc[i])) for i in np.argsort(-sc)[:k]]


@lru_cache(maxsize=None)
def coll(name):
    return Coll(name)
