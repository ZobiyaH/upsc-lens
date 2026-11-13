
from pathlib import Path
from urllib.parse import urljoin, urlparse
import re
import requests
from bs4 import BeautifulSoup

# --------------------------------------------------
# SOURCES
# --------------------------------------------------

VAJIRAM_URL = "https://vajiramandravi.com/upsc-previous-year-papers/"

DRISHTI_URL = (
    "https://www.drishtiias.com/free-downloads/"
    "prelims-previous-year-papers-1-gs-yearwise-downloads"
)

# Update when newer papers become available.
YEARS = list(range(2026, 2012, -1))

# --------------------------------------------------
# OUTPUT
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "pyq_pdfs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )
})


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def is_pdf_url(url):
    return ".pdf" in urlparse(url).path.lower()


def is_answer_key(text):
    text = text.lower()

    blocked = [
        "answer key",
        "answerkey",
        "ans key",
        "solutions",
        "solution pdf",
    ]

    return any(word in text for word in blocked)


def is_hindi_only(text):
    """
    Reject explicitly Hindi-labelled links.
    Bilingual PDFs are allowed because the importer
    extracts their English text.
    """

    text = text.lower()

    hindi_only_patterns = [
        r"\bhindi\s+medium\b",
        r"\bhindi\s+version\b",
        r"\bin\s+hindi\b",
        r"\bhindi\s+paper\b",
    ]

    english_indicators = [
        "english",
        "bilingual",
        "both languages",
    ]

    if any(word in text for word in english_indicators):
        return False

    return any(
        re.search(pattern, text)
        for pattern in hindi_only_patterns
    )


def download_pdf(url, filename, referer):
    destination = OUTPUT_DIR / filename

    if destination.exists() and destination.stat().st_size > 0:
        print(f"[EXISTS] {filename}")
        return True

    try:
        response = session.get(
            url,
            headers={"Referer": referer},
            timeout=60
        )

        response.raise_for_status()

        if not response.content.startswith(b"%PDF"):
            print(f"[NOT PDF] {filename}")
            return False

        destination.write_bytes(response.content)

        print(f"[DOWNLOADED] {filename}")
        return True

    except requests.RequestException as error:
        print(f"[FAILED] {filename}: {error}")
        return False


def fetch_page(url):
    try:
        response = session.get(url, timeout=45)
        response.raise_for_status()

        return BeautifulSoup(response.content, "html.parser")

    except requests.RequestException as error:
        print(f"\n[WEBSITE ERROR] {url}")
        print(error)
        return None


# --------------------------------------------------
# EXTRACT LINK INFORMATION
# --------------------------------------------------

def get_link_context(anchor):
    """
    Collect anchor text and nearby card/container text.
    """

    parts = [
        anchor.get_text(" ", strip=True),
        anchor.get("title", ""),
        anchor.get("href", ""),
    ]

    parent = anchor

    for _ in range(5):
        if parent is None:
            break

        parts.append(parent.get_text(" ", strip=True))
        parent = parent.parent

    return " ".join(parts)


def get_year(text):
    match = re.search(r"\b(20\d{2})\b", text)

    if match:
        year = int(match.group(1))

        if year in YEARS:
            return year

    return None


def get_paper_number(text):
    text = text.upper()

    # Reject CSAT / GS Paper II for Prelims.
    if "CSAT" in text:
        return None

    patterns = [
        r"GENERAL\s+STUDIES\s+PAPER\s*[-:]?\s*(I{1,3}|IV|[1-4])\b",
        r"GS\s*[-_]?\s*(I{1,3}|IV|[1-4])\b",
        r"PAPER\s*[-:]?\s*(I{1,3}|IV|[1-4])\b",
    ]

    roman = {
        "I": 1,
        "II": 2,
        "III": 3,
        "IV": 4,
    }

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            value = match.group(1)
            return roman.get(value, int(value) if value.isdigit() else None)

    return None


def get_stage(text):
    text = text.lower()

    prelim_words = [
        "prelims",
        "preliminary",
        "preliminary examination",
        "prelims paper",
    ]

    mains_words = [
        "mains",
        "main examination",
        "descriptive",
    ]

    if any(word in text for word in prelim_words):
        return "prelims"

    if any(word in text for word in mains_words):
        return "mains"

    return None


# --------------------------------------------------
# VAJIRAM DOWNLOAD
# --------------------------------------------------

def download_from_vajiram():
    print("\n========== VAJIRAM DOWNLOAD ==========")

    soup = fetch_page(VAJIRAM_URL)

    if soup is None:
        return

    detected = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        url = urljoin(VAJIRAM_URL, href)

        if not is_pdf_url(url):
            continue

        context = get_link_context(anchor)

        if is_answer_key(context):
            continue

        if is_hindi_only(context):
            continue

        year = get_year(context)
        paper = get_paper_number(context)
        stage = get_stage(context)

        if year is None or paper is None or stage is None:
            continue

        if stage == "prelims" and paper != 1:
            continue

        if stage == "mains" and paper not in (1, 2, 3, 4):
            continue

        if stage == "prelims":
            filename = f"{year}_GS1_prelims.pdf"
        else:
            filename = f"{year}_GS{paper}.pdf"

        key = (year, stage, paper)

        if key in detected:
            continue

        detected.add(key)

        download_pdf(url, filename, VAJIRAM_URL)

    print(f"\nVajiram papers identified: {len(detected)}")


# --------------------------------------------------
# DRISHTI SUPPLEMENTARY PRELIMS DOWNLOAD
# --------------------------------------------------

def download_from_drishti():
    print("\n========== DRISHTI SUPPLEMENTARY DOWNLOAD ==========")

    soup = fetch_page(DRISHTI_URL)

    if soup is None:
        print("Could not access Drishti. Continuing.")
        return

    downloaded = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        url = urljoin(DRISHTI_URL, href)

        if not is_pdf_url(url):
            continue

        context = get_link_context(anchor)

        if is_answer_key(context):
            continue

        if is_hindi_only(context):
            continue

        year = get_year(context)

        if year is None:
            continue

        # This page is used only for Prelims GS-I.
        if year in downloaded:
            continue

        filename = f"{year}_GS1_prelims.pdf"
        destination = OUTPUT_DIR / filename

        # Do not overwrite a paper already obtained from Vajiram.
        if destination.exists() and destination.stat().st_size > 0:
            continue

        success = download_pdf(url, filename, DRISHTI_URL)

        if success:
            downloaded.add(year)

    print(f"Additional Drishti papers downloaded: {len(downloaded)}")


# --------------------------------------------------
# SUMMARY
# --------------------------------------------------

def main():
    print("=" * 55)
    print("UPSC ENGLISH GS QUESTION PAPER DOWNLOADER")
    print("=" * 55)

    print(f"\nSaving PDFs to: {OUTPUT_DIR}")

    download_from_vajiram()
    download_from_drishti()

    print("\n" + "=" * 55)
    print("DOWNLOAD SUMMARY")
    print("=" * 55)

    files = sorted(OUTPUT_DIR.glob("*.pdf"))

    print(f"PDF files currently in folder: {len(files)}")

    for file in files:
        print(f"  {file.name}")

    print("\nNext step: python -m src.import_pyq")


if __name__ == "__main__":
    main()
