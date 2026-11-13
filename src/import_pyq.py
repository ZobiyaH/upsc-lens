
import csv
import re
import unicodedata
from pathlib import Path

import pymupdf

from config import DATA
from src.search import topics


# ==================================================
# PATHS AND CSV SETTINGS
# ==================================================

PDF_DIR = DATA / "pyq_pdfs"
CSV_PATH = DATA / "pyq.csv"
SYLLABUS_INDEX = DATA / "index" / "syllabus.json"

CSV_FIELDS = [
    "year",
    "paper",
    "stage",
    "topic_id",
    "question",
]

VALID_PRELIMS_PAPERS = {"GS1"}
VALID_MAINS_PAPERS = {"GS1", "GS2", "GS3", "GS4"}


# ==================================================
# TEXT NORMALIZATION
# ==================================================

def normalize_question(text):
    text = unicodedata.normalize("NFKC", text)

    # Remove Hindi/Devanagari characters.
    text = re.sub(
        r"[\u0900-\u097F\uA8E0-\uA8FF]+",
        " ",
        text
    )

    # Remove common PDF footer information.
    text = re.sub(
        r"SLPM[-\w/]*.*",
        " ",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\b(?:P\.T\.O\.|CONTINUED ON NEXT PAGE)\b",
        " ",
        text,
        flags=re.IGNORECASE
    )

    # Preserve line breaks for question detection.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_for_duplicate(text):
    text = normalize_question(text).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


# ==================================================
# ANSWER KEY DETECTION
# ==================================================

def is_answer_key(text):
    """
    Prevent answer keys and solution documents
    from entering the question database.
    """

    head = text[:8000].upper()

    indicators = [
        "ANSWER KEY",
        "ANSWER KEYS",
        "SOLUTION & EXPLANATION",
        "SOLUTION AND EXPLANATION",
        "WITH EXPLANATION",
        "OFFICIAL ANSWERS",
    ]

    for indicator in indicators:
        if indicator in head:
            return True

    # Detect answer tables containing Set-A, Set-B, etc.
    # alongside many answer entries such as 1.(a).
    has_sets = bool(
        re.search(r"SET[- ]?A", head)
        and re.search(r"SET[- ]?B", head)
    )

    answer_entries = re.findall(
        r"\b\d{1,3}\.\s*\([a-d](?:/[a-d])?\)",
        head,
        flags=re.IGNORECASE
    )

    if has_sets and len(answer_entries) >= 10:
        return True

    return False


# ==================================================
# METADATA DETECTION
# ==================================================

def detect_metadata(file_path, text):
    """
    Supported filenames:

    2024_GS1_prelims.pdf
    2024_GS1.pdf
    2024_GS2.pdf
    2024_GS3.pdf
    2024_GS4.pdf
    """

    if is_answer_key(text):
        return None

    filename = file_path.stem.lower()

    match = re.fullmatch(
        r"(20\d{2})_gs([1-4])(?:_(prelims|mains))?",
        filename
    )

    if match:
        year = match.group(1)
        paper_number = int(match.group(2))
        stage_name = match.group(3)

        if stage_name == "prelims":
            stage = "Prelims"
        else:
            stage = "Mains"

        paper = f"GS{paper_number}"

        if stage == "Prelims" and paper not in VALID_PRELIMS_PAPERS:
            return None

        if stage == "Mains" and paper not in VALID_MAINS_PAPERS:
            return None

        return year, paper, stage

    # Fallback for differently named files.
    head = text[:4000].upper()

    year_match = re.search(r"\b(20\d{2})\b", head)

    if not year_match:
        return None

    year = year_match.group(1)

    if "CSAT" in head:
        return None

    paper_match = re.search(
        r"(?:GENERAL\s+STUDIES|GS)\s*"
        r"(?:PAPER)?\s*[-:]?\s*(IV|III|II|I|[1-4])\b",
        head
    )

    if not paper_match:
        return None

    value = paper_match.group(1)

    roman = {
        "I": 1,
        "II": 2,
        "III": 3,
        "IV": 4,
    }

    paper_number = (
        roman[value]
        if value in roman
        else int(value)
    )

    paper = f"GS{paper_number}"

    if "PRELIMINARY" in head or "PRELIMS" in head:
        stage = "Prelims"
    else:
        stage = "Mains"

    if stage == "Prelims" and paper not in VALID_PRELIMS_PAPERS:
        return None

    return year, paper, stage


# ==================================================
# PDF TEXT EXTRACTION
# ==================================================

def extract_pdf_text(file_path):
    pages = []

    try:
        with pymupdf.open(file_path) as pdf:

            for page in pdf:
                page_text = page.get_text(
                    "text",
                    sort=True
                )

                if page_text.strip():
                    pages.append(page_text)

    except Exception as error:
        print(f"[PDF ERROR] {file_path.name}: {error}")
        return ""

    return "\n".join(pages)


# ==================================================
# QUESTION MARKER DETECTION
# ==================================================

# Examples:
#
# 1.
# 2
# 10.
# Q1.
# Question 2.
#
STANDALONE_NUMBER = re.compile(
    r"^\s*(?:Q(?:uestion)?\s*)?(\d{1,3})\s*[.)]?\s*$",
    re.IGNORECASE
)

# Examples:
#
# 1. With reference to...
# Q2. Discuss...
#
INLINE_NUMBER = re.compile(
    r"^\s*(?:Q(?:uestion)?\s*)?(\d{1,3})[.)]\s+(.+?)\s*$",
    re.IGNORECASE
)


def find_question_markers(text, stage):
    """
    Find question numbers while preserving their positions.

    Supports both standalone question numbers and
    question numbers followed by text.
    """

    markers = []

    max_number = 100 if stage == "Prelims" else 30

    position = 0
    last_number = 0

    for line in text.splitlines(keepends=True):

        clean_line = line.strip()

        standalone = STANDALONE_NUMBER.fullmatch(clean_line)
        inline = INLINE_NUMBER.match(clean_line)

        number = None
        question_start = None

        if standalone:
            number = int(standalone.group(1))
            question_start = position + len(line)

        elif inline:
            number = int(inline.group(1))

            # Start after the number and punctuation.
            content = inline.group(2)
            content_position = line.find(content)

            question_start = position + content_position

        if number is not None:

            if (
                1 <= number <= max_number
                and number > last_number
            ):
                markers.append({
                    "number": number,
                    "start": question_start,
                })

                last_number = number

        position += len(line)

    return markers


# ==================================================
# QUESTION CLEANING
# ==================================================

def clean_question(text):
    text = normalize_question(text)

    # Remove common bilingual instructions.
    text = re.sub(
        r"\(?\s*Answer\s+in\s+\d+\s*words?\s*\)?",
        " ",
        text,
        flags=re.IGNORECASE
    )

    # Remove marks printed at the end of questions.
    text = re.sub(
        r"\s+\b(?:10|15|20)\s*$",
        "",
        text
    )

    # Remove leftover standalone numbering.
    text = re.sub(
        r"^\s*\d{1,3}[.)]?\s*",
        "",
        text
    )

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def is_valid_question(question):
    """
    Reject page fragments, marks and very short text.
    """

    if len(question) < 40:
        return False

    words = re.findall(
        r"\b[A-Za-z]{2,}\b",
        question
    )

    if len(words) < 6:
        return False

    return True


# ==================================================
# QUESTION EXTRACTION
# ==================================================

def extract_questions(text, stage):
    """
    Extract numbered questions from a PDF.

    Supports:

    1.
    Question text...

    2
    Question text...

    3. Question text...

    Also handles the case where question 1 has
    no visible number but question 2 is present.
    """

    text = normalize_question(text)

    markers = find_question_markers(text, stage)

    if not markers:
        return []

    questions_found = []

    # Some PDFs have no visible number before question 1.
    # Example: GS-II 2025 starts with question text,
    # followed by a standalone "2".
    if markers[0]["number"] > 1:

        prefix = text[:markers[0]["start"]]

        prefix_question = clean_question(prefix)

        if is_valid_question(prefix_question):

            questions_found.append({
                "number": 1,
                "question": prefix_question,
            })

    for index, marker in enumerate(markers):

        start = marker["start"]

        if index + 1 < len(markers):
            end = markers[index + 1]["start"]
        else:
            end = len(text)

        raw_question = text[start:end]

        question = clean_question(raw_question)

        if not is_valid_question(question):
            continue

        questions_found.append({
            "number": marker["number"],
            "question": question,
        })

    return questions_found


# ==================================================
# TOPIC CLASSIFICATION
# ==================================================

def get_topic_id(question):
    # Avoid calling topics() when the syllabus index
    # has not yet been created.
    if not SYLLABUS_INDEX.exists():
        return "unclassified"

    try:
        results = topics(question, k=1)

        if results:
            return results[0].get("id", "unclassified")

    except Exception as error:
        print(f"[TOPIC WARNING] {error}")

    return "unclassified"


# ==================================================
# CSV HELPERS
# ==================================================

def load_existing_questions():
    existing = set()

    if not CSV_PATH.exists():
        return existing

    with open(
        CSV_PATH,
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            question = row.get("question", "")

            if not question:
                continue

            key = (
                row.get("year", ""),
                row.get("paper", ""),
                row.get("stage", ""),
                normalize_for_duplicate(question)
            )

            existing.add(key)

    return existing


def ensure_csv_exists():
    CSV_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0:

        with open(
            CSV_PATH,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=CSV_FIELDS
            )

            writer.writeheader()


def save_questions(rows):
    if not rows:
        return

    ensure_csv_exists()

    with open(
        CSV_PATH,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=CSV_FIELDS
        )

        writer.writerows(rows)


# ==================================================
# MAIN IMPORTER
# ==================================================

def main():

    print("=" * 65)
    print("UPSC ENGLISH GS QUESTION PAPER IMPORTER")
    print("=" * 65)

    print(f"\nPDF folder: {PDF_DIR}")
    print(f"CSV output: {CSV_PATH}")

    if not PDF_DIR.exists():
        print("\n[ERROR] PDF folder does not exist.")
        return

    pdf_files = sorted(PDF_DIR.glob("*.pdf"))

    if not pdf_files:
        print("\nNo PDF files found.")
        return

    if not SYLLABUS_INDEX.exists():
        print(
            "\n[INFO] Syllabus index not found. "
            "Questions will be tagged as unclassified."
        )

    existing = load_existing_questions()

    new_rows = []

    skipped_answer_keys = 0
    skipped_scanned = 0
    skipped_invalid = 0

    for file_path in pdf_files:

        print(f"\nProcessing: {file_path.name}")

        text = extract_pdf_text(file_path)

        if not text.strip():
            print("  [SKIPPED] No readable text. OCR may be required.")
            skipped_scanned += 1
            continue

        if is_answer_key(text):
            print("  [SKIPPED] Answer key / solution document detected.")
            skipped_answer_keys += 1
            continue

        metadata = detect_metadata(file_path, text)

        if metadata is None:
            print("  [SKIPPED] Could not identify a valid GS paper.")
            skipped_invalid += 1
            continue

        year, paper, stage = metadata

        if stage == "Prelims" and paper != "GS1":
            print("  [SKIPPED] Prelims GS-II / CSAT is excluded.")
            skipped_invalid += 1
            continue

        extracted = extract_questions(text, stage)

        if not extracted:
            print("  [WARNING] No numbered questions detected.")
            skipped_invalid += 1
            continue

        added = 0
        duplicates = 0

        for item in extracted:

            question = item["question"]

            key = (
                year,
                paper,
                stage,
                normalize_for_duplicate(question)
            )

            if key in existing:
                duplicates += 1
                continue

            topic_id = get_topic_id(question)

            row = {
                "year": year,
                "paper": paper,
                "stage": stage,
                "topic_id": topic_id,
                "question": question,
            }

            new_rows.append(row)

            existing.add(key)
            added += 1

        print(f"  Year: {year}")
        print(f"  Paper: {paper}")
        print(f"  Stage: {stage}")
        print(f"  Questions detected: {len(extracted)}")
        print(f"  Duplicates skipped: {duplicates}")
        print(f"  New questions added: {added}")

    save_questions(new_rows)

    print("\n" + "=" * 65)
    print("IMPORT SUMMARY")
    print("=" * 65)

    print(f"PDF files found: {len(pdf_files)}")
    print(f"New questions imported: {len(new_rows)}")
    print(f"Answer keys skipped: {skipped_answer_keys}")
    print(f"Scanned PDFs skipped: {skipped_scanned}")
    print(f"Other PDFs skipped: {skipped_invalid}")

    print(f"\nCSV location: {CSV_PATH}")

    print("\nNEXT STEPS:")
    print("1. Inspect data/pyq.csv.")
    print("2. Check question text for extraction errors.")
    print("3. Build the syllabus index before topic classification.")
    print("4. Add OCR support for scanned PDFs.")


if __name__ == "__main__":
    main()
