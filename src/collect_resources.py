"""Download PUBLIC resources listed in data/sources.txt and convert them to text notes; also converts your own files.
   python -m src.collect_resources      then      python -m src.build_index
Line formats in data/sources.txt:
   name | URL                                  one PDF or web page  -> data/notes/name.txt
   crawl:name | page URL | regex [| pyq]       every PDF linked on that page whose link text/URL matches the regex (max 25)
                                               (add | pyq to save the raw PDFs into data/pyq_pdfs/ instead)
Your own files (PDF/TXT/MD) placed in data/my_files/ are converted too."""
import re, time
from html.parser import HTMLParser
from urllib.parse import urljoin
import pymupdf as fitz
import requests
from config import DATA

UA = {"User-Agent": "Mozilla/5.0 (personal study tool)"}


def get(url):
    try:
        r = requests.get(url, headers=UA, timeout=90)
    except requests.exceptions.SSLError:             # some government sites have broken certificates (public data only)
        r = requests.get(url, headers=UA, timeout=90, verify=False)
    r.raise_for_status()
    return r


class _Html(HTMLParser):
    SKIP = ("script", "style", "nav", "footer", "header")

    def __init__(self):
        super().__init__(); self.lines, self.skip, self.buf, self.links, self._href, self._atext = [], 0, "", [], None, ""

    def handle_starttag(self, t, a):
        if t in self.SKIP: self.skip += 1
        if t == "a": self._href, self._atext = dict(a).get("href"), ""

    def handle_endtag(self, t):
        if t in self.SKIP and self.skip: self.skip -= 1
        if t == "a" and self._href:
            self.links.append((self._href, re.sub(r"\s+", " ", self.buf[-150:] + " " + self._atext)))
            self._href = None

    def handle_data(self, d):
        self.buf += " " + d
        if self._href is not None: self._atext += " " + d
        if not self.skip and d.strip(): self.lines.append(d.strip())


def html_text(html):
    p = _Html(); p.feed(html)
    return "\n".join(l for l in p.lines if len(l.split()) >= 5)          # drop menu items, keep sentences


def pdf_text(data):
    return "\n".join(p.get_text() for p in fitz.open(stream=data, filetype="pdf"))


def save_note(name, text):
    (DATA / "notes" / f"{re.sub(r'[^A-Za-z0-9_.-]+', '_', name)[:80]}.txt").write_text(text, encoding="utf-8")
    print(f"OK   {name}: {len(text):,} characters")


def one(name, url):
    r = get(url)
    is_pdf = url.lower().split("?")[0].endswith(".pdf") or "pdf" in r.headers.get("content-type", "")
    save_note(name, pdf_text(r.content) if is_pdf else html_text(r.text))


def crawl(name, page, pattern, dest):
    r = get(page); p = _Html(); p.feed(r.text)
    hits = [(urljoin(page, h), ctx) for h, ctx in p.links if h.lower().split("?")[0].endswith(".pdf") and re.search(pattern, ctx + " " + h)]
    print(f"{name}: {len(hits)} matching PDFs on the page")
    for k, (u, _) in enumerate(hits[:25], 1):
        try:
            data = get(u).content
            if dest == "pyq":
                (DATA / "pyq_pdfs" / f"{name}_{k}.pdf").write_bytes(data); print(f"OK   saved {name}_{k}.pdf")
            else:
                save_note(f"{name}_{k}", pdf_text(data))
        except Exception as e:
            print(f"FAIL {u}: {e}")
        time.sleep(2)


def main():
    for line in open(DATA / "sources.txt", encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [x.strip() for x in line.split(" | ")]
        try:
            if parts[0].startswith("crawl:"):
                crawl(parts[0][6:], parts[1], parts[2], parts[3] if len(parts) > 3 else "notes")
            else:
                one(parts[0], parts[1])
        except Exception as e:
            print(f"FAIL {parts[0]}: {e}  (fix or remove this line; the rest continues)")
        time.sleep(2)
    for f in (DATA / "my_files").glob("*"):                                   # your own legitimately obtained notes
        try:
            if f.suffix.lower() == ".pdf": save_note("my_" + f.stem, pdf_text(f.read_bytes()))
            elif f.suffix.lower() in (".txt", ".md"): save_note("my_" + f.stem, f.read_text(encoding="utf-8", errors="ignore"))
        except Exception as e:
            print(f"FAIL {f.name}: {e}")


if __name__ == "__main__":
    main()
