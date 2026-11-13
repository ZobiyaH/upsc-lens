"""STEP 5: measure accuracy on your hand-labelled articles.   python -m src.evaluate
data/labeled_articles.json format:
[{"text": "article text...", "topic_id": "GS2_POL_06"}, {"text": "cricket match...", "topic_id": null}]"""
import json
from config import DATA
from src.search import topics


def main():
    data = json.load(open(DATA / "labeled_articles.json", encoding="utf-8"))
    if not data:
        return print("Add labelled articles to data/labeled_articles.json first.")
    runs = []
    for d in data:
        c = topics(d["text"], k=3)
        runs.append((d["topic_id"], [x["id"] for x in c], max(x["similarity"] for x in c)))
    pos = [r for r in runs if r[0]]
    print(f"Articles: {len(runs)} ({len(pos)} relevant)")
    print(f"Top-1 accuracy: {sum(r[1][0] == r[0] for r in pos) / max(len(pos), 1):.2%}")
    print(f"Top-3 accuracy: {sum(r[0] in r[1] for r in pos) / max(len(pos), 1):.2%}")
    print("\nthreshold  precision  recall  F1   (pick the best F1 for MIN_SIMILARITY)")
    for th in [x / 100 for x in range(30, 80, 5)]:
        tp = sum(1 for r in runs if r[0] and r[2] >= th)
        fp = sum(1 for r in runs if not r[0] and r[2] >= th)
        fn = sum(1 for r in runs if r[0] and r[2] < th)
        p, rc = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
        print(f"{th:.2f}       {p:.2f}       {rc:.2f}    {2 * p * rc / max(p + rc, 1e-9):.2f}")


if __name__ == "__main__":
    main()
