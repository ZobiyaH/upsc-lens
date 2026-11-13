
import pymupdf
from pathlib import Path

files = [
    "2025_GS1.pdf",
    "2025_GS2.pdf"
]

for filename in files:
    path = Path("data/pyq_pdfs") / filename

    print("\n" + "=" * 70)
    print(filename)
    print("=" * 70)

    with pymupdf.open(path) as pdf:
        for page_number, page in enumerate(pdf):
            text = page.get_text("text", sort=True)

            print(f"\n--- PAGE {page_number + 1} ---\n")
            print(text[:7000])
