"""Save the latest PIB press releases (official government feed) as notes. Run daily:  python -m src.fetch_pib
Then:  python -m src.build_index"""
import re, time
import xml.etree.ElementTree as ET
from config import DATA
from src.collect_resources import get, html_text

FEED = "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"     # all ministries, English


def main():
    items = ET.fromstring(get(FEED).content).iter("item")
    new = 0
    for it in items:
        title, link = (it.findtext("title") or "").strip(), (it.findtext("link") or "").strip()
        m = re.search(r"PRID=(\d+)", link)
        f = DATA / "notes" / f"pib_{m.group(1)}.txt" if m else None
        if not f or f.exists():
            continue
        try:
            f.write_text(title + "\n" + html_text(get(link).text), encoding="utf-8"); new += 1
        except Exception as e:
            print("skip", link, e)
        time.sleep(1)
    print("new PIB releases saved:", new)


if __name__ == "__main__":
    main()
