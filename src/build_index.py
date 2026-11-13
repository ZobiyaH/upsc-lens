"""Embed syllabus + PYQs + notes and save them. Notes are cached per file, so reruns are fast.
python -m src.build_index"""
import csv, hashlib
import numpy as np
from config import DATA, INDEX
from src.store import embed, save


def chunk(text, size=250, overlap=40):
    w = text.split()
    return [" ".join(w[i:i + size]) for i in range(0, len(w), size - overlap) if len(w[i:i + size]) > 30]


def load_syllabus():
    """data/syllabus.txt lines:  ID | Stage | Paper | Subject | Topic | keywords.  Lines starting with # are skipped."""
    out = []
    for line in open(DATA / "syllabus.txt", encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        i, stage, paper, subj, topic, kw = [x.strip() for x in line.split("|")]
        out.append({"id": i, "stage": stage, "paper": paper, "subject": subj, "topic": topic,
                    "keywords": [k.strip() for k in kw.split(",")]})
    return out


def main():
    (INDEX / "cache").mkdir(parents=True, exist_ok=True)
    syl = load_syllabus()
    docs = [f'{s["topic"]}. Keywords: {", ".join(s["keywords"])}' for s in syl]
    save("syllabus", [s["id"] for s in syl], docs,
         [{"stage": s["stage"], "paper": s["paper"], "subject": s["subject"]} for s in syl], embed(docs))
    print("syllabus topics:", len(syl))

    rows = list(csv.DictReader(open(DATA / "pyq.csv", encoding="utf-8")))
    qs = [r["question"] for r in rows]
    save("pyq", [f"pyq_{i}" for i in range(len(rows))], qs,
         [{"year": r["year"], "paper": r["paper"], "topic_id": r["topic_id"]} for r in rows], embed(qs) if qs else [])
    print("PYQs:", len(rows))

    ids, docs, metas, vecs = [], [], [], []
    files = sorted((DATA / "notes").glob("*.txt"))
    for n, f in enumerate(files, 1):
        st = f.stat()
        cf = INDEX / "cache" / (hashlib.md5(f"{f.name}{st.st_size}{st.st_mtime_ns}".encode()).hexdigest() + ".npz")
        if cf.exists():
            z = np.load(cf); chunks, v = z["chunks"].tolist(), z["v"]
        else:
            chunks = chunk(f.read_text(encoding="utf-8", errors="ignore"))
            if not chunks:
                continue
            print(f"embedding [{n}/{len(files)}] {f.name} ({len(chunks)} chunks)")
            v = embed(chunks); np.savez(cf, chunks=np.array(chunks), v=v)
        ids += [f"{f.stem}_{i}" for i in range(len(chunks))]; docs += chunks
        metas += [{"source": f.stem}] * len(chunks); vecs.append(v)
    save("notes", ids, docs, metas, np.vstack(vecs) if vecs else [])
    print("note chunks:", len(ids))


if __name__ == "__main__":
    main()
