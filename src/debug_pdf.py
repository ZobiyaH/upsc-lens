"""SEE how the parser split a page.   python -m src.debug_pdf paper.pdf 1 2 3
Writes debug_page<N>.png with every article boxed in its own colour. If headlines are missed, lower HEAD_RATIO;
if junk is picked up, raise it. Edit src/pdf_parser.py, rerun, compare."""
import sys
from src.pdf_parser import parse, render

pdf, pages = sys.argv[1], [int(x) for x in sys.argv[2:]] or [1]
arts = parse(pdf)
for p in pages:
    on = [a for a in arts if a["page"] == p]
    open(f"debug_page{p}.png", "wb").write(render(pdf, p, on))
    print(f"page {p}: {len(on)} articles")
    for i, a in enumerate(on):
        print(f"  #{i} {a['headline'][:70]} ({len(a['text'].split())} words, {len(a['rects'])} columns)")
