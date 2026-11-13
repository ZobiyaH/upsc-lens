"""Newspaper PDF -> articles, each with PER-COLUMN highlight rectangles (so an L-shaped article doesn't cover its neighbours).
How it works:
 1. Read text blocks with font size. Headline = block much bigger than the page's body text (merged if it wraps over 2 blocks).
 2. Body blocks go to the nearest headline ABOVE them that overlaps them horizontally.
 3. Captions (small text), 'Continued on...' and 'Also read' lines are dropped.
 4. Text is read column by column; one rectangle is kept per column.
Tune HEAD_RATIO / MIN_WORDS, and use  python -m src.debug_pdf paper.pdf 3  to SEE the result."""
import re, statistics
import fitz  # PyMuPDF

HEAD_RATIO = 1.35   # headline font >= this x body font (lower it if headlines are missed)
MIN_WORDS = 50      # drop articles shorter than this
COL_TOL = 14        # points: x positions closer than this are the same column
PALETTE = [(0.9, 0.1, 0.1), (0.1, 0.5, 0.9), (0.1, 0.7, 0.3), (0.9, 0.5, 0.0), (0.6, 0.2, 0.8), (0.0, 0.7, 0.7)]
JUNK = re.compile(r"(?i)^\W*(continued on|also read|read more|advertisement|sponsored)")


def _blocks(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        spans = [s for l in b["lines"] for s in l["spans"] if s["text"].strip()]
        if not spans:
            continue
        text = " ".join(" ".join(s["text"] for s in l["spans"]).strip() for l in b["lines"])
        text = re.sub(r"([a-z])- ([a-z])", r"\1\2", re.sub(r"\s+", " ", text).strip())   # re-join hyphenated words
        chars = sum(len(s["text"]) for s in spans)
        size = sum(s["size"] * len(s["text"]) for s in spans) / chars                  # average, not max (ignores drop caps)
        out.append({"bbox": tuple(b["bbox"]), "text": text, "size": size, "chars": chars})
    return out


def _union(bs):
    return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))


def _xov(a, b):
    """Fraction of b's width that lies inside a's horizontal span."""
    return (min(a[2], b[2]) - max(a[0], b[0])) / max(b[2] - b[0], 1)


def _is_head(b, body, page_h):
    t = b["text"]
    if b["size"] < body * HEAD_RATIO or not 2 <= len(t.split()) <= 30 or len(t) < 12:
        return False
    if sum(c.isalpha() for c in t) / len(t) < 0.6 or b["bbox"][2] - b["bbox"][0] < 40 or JUNK.match(t):
        return False
    if b["bbox"][1] < 0.09 * page_h and re.search(r"(?i)the hindu|indian express|e-?paper", t):   # masthead
        return False
    return True


def _merge_heads(heads):
    out = []
    for h in sorted(heads, key=lambda b: (b["bbox"][1], b["bbox"][0])):
        p = out[-1] if out else None
        if (p and abs(p["size"] - h["size"]) < 0.1 * p["size"] and 0 <= h["bbox"][1] - p["bbox"][3] < p["size"] * 1.2
                and _xov(p["bbox"], h["bbox"]) > 0.5):
            p["text"] += " " + h["text"]; p["bbox"] = _union([p["bbox"], h["bbox"]])
        else:
            out.append(dict(h))
    return out


def _page_articles(n, rect, blocks, body):
    hb = [b for b in blocks if _is_head(b, body, rect.height)]
    ids = {id(b) for b in hb}
    heads = _merge_heads(hb)
    text_blocks = [b for b in blocks if id(b) not in ids and b["chars"] >= 25 and not JUNK.match(b["text"])
                   and not (b["size"] < body * 0.88 and b["chars"] < 250)]          # captions / credits
    anchors = []
    for x in sorted({round(b["bbox"][0]) for b in text_blocks}):
        if not anchors or x - anchors[-1] > COL_TOL:
            anchors.append(x)
    col = lambda b: max([i for i, a in enumerate(anchors) if a <= b["bbox"][0] + COL_TOL] or [0])
    parts = {id(h): [] for h in heads}
    for b in text_blocks:
        above = [h for h in heads if h["bbox"][3] <= b["bbox"][1] + 3 and _xov(h["bbox"], b["bbox"]) > 0.5]
        if above:
            parts[id(max(above, key=lambda h: h["bbox"][3]))].append(b)
    arts = []
    for h in heads:
        cols = {}
        for b in parts[id(h)]:
            cols.setdefault(col(b), []).append(b)
        ordered = [b for c in sorted(cols) for b in sorted(cols[c], key=lambda b: b["bbox"][1])]
        text = " ".join(b["text"] for b in ordered)
        if len(text.split()) < MIN_WORDS:
            continue
        rects = [_union([b["bbox"] for b in cols[c]]) for c in sorted(cols)]
        arts.append({"page": n, "headline": h["text"], "text": text, "head": list(h["bbox"]),
                     "rects": [list(r) for r in rects], "bbox": list(_union([h["bbox"]] + rects))})
    return arts


def parse(pdf, max_pages=None):
    doc = fitz.open(stream=pdf, filetype="pdf") if isinstance(pdf, (bytes, bytearray)) else fitz.open(pdf)
    pages = []
    for n, page in enumerate(doc, 1):
        if max_pages and n > max_pages:
            break
        pages.append((n, page.rect, _blocks(page)))
    allsz = [b["size"] for _, _, bl in pages for b in bl if b["chars"] > 200]
    doc_body = statistics.median(allsz) if allsz else 9
    arts = []
    for n, rect, bl in pages:
        sz = [b["size"] for b in bl if b["chars"] > 200]
        arts += _page_articles(n, rect, bl, statistics.median(sz) if len(sz) >= 3 else doc_body)
    return arts


def render(pdf, page_no, arts, active=None, zoom=1.4):
    """PNG of one page. active=article -> only that article is highlighted. active=None -> debug view of all."""
    doc = fitz.open(stream=pdf, filetype="pdf") if isinstance(pdf, (bytes, bytearray)) else fitz.open(pdf)
    page = doc[page_no - 1]
    for i, a in enumerate(arts):
        if active is not None and a is not active:
            continue
        col = (0.9, 0.1, 0.1) if active is not None else PALETTE[i % len(PALETTE)]
        for r in a["rects"]:
            page.draw_rect(fitz.Rect(*r), color=col, fill=col, fill_opacity=0.15, width=1.2)
        page.draw_rect(fitz.Rect(*a["head"]), color=col, fill=col, fill_opacity=0.3, width=2)
        if active is None:
            page.insert_text((a["head"][0] + 2, max(a["head"][1] - 3, 10)), f"#{i} {a['headline'][:40]}", fontsize=8, color=col)
    return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).tobytes("png")
