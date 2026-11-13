
"""Gemini-powered UPSC article analysis with caching and retry handling."""

import hashlib
import json
import time
from functools import lru_cache

from config import CACHE, GEMINI_API_KEY, GEMINI_MODEL

PROMPT = """You are a UPSC mentor. Analyse the newspaper article below for Prelims and Mains.

SOURCE LABEL - give every item exactly one:
  "article" = stated in the ARTICLE; "notes" = stated in NOTES; "ai" = your own general knowledge.

RULES
- topic_id ONLY from CANDIDATE TOPICS.
- If the article is not useful for UPSC, set relevant=false.
- Prefer article and notes.
- Use "ai" for static background.
- Never invent recent events beyond the article.
- Return valid JSON only.

Return ONLY JSON:
{"relevant": bool, "topic_id": str, "relevance": "Prelims|Mains|Both", "confidence": "high|medium|low", "summary": str,
 "background": [{"text": str, "source": "article|notes|ai", "note_ids": [str]}],
 "prelims_pointer": [{"text": str, "source": "article|notes|ai"}],
 "mains_question": str,
 "mains_points": [{"text": str, "source": "article|notes|ai"}]}

ARTICLE
Headline: %(headline)s
%(text)s

CANDIDATE TOPICS
%(topics)s

NOTES
%(notes)s
"""


@lru_cache(maxsize=1)
def _client():
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


def _clean(out):
    if not isinstance(out, dict):
        raise ValueError("Gemini returned an invalid JSON object.")

    for key in ("background", "prelims_pointer", "mains_points"):
        items = out.get(key) or []
        cleaned = []

        for item in items:
            if not isinstance(item, dict) or not item.get("text"):
                continue

            cleaned_item = {
                "text": str(item["text"]),
                "source": (
                    item.get("source")
                    if item.get("source") in ("article", "notes", "ai")
                    else "ai"
                ),
            }

            if key == "background":
                cleaned_item["note_ids"] = item.get("note_ids", [])

            cleaned.append(cleaned_item)

        out[key] = cleaned

    return out


def analyse(article, topics, notes):
    """Returns (result_dict_or_None, from_cache)."""

    p = PROMPT % {
        "headline": article["headline"],
        "text": article["text"][:6000],
        "topics": "\n".join(
            f'{t["id"]}: {t["text"]}' for t in topics
        ),
        "notes": "\n".join(
            f'[{n["id"]}] {n["text"]}' for n in notes
        ) or "(none)",
    }

    CACHE.mkdir(parents=True, exist_ok=True)

    cache_file = CACHE / (
        hashlib.md5(p.encode("utf-8")).hexdigest() + ".json"
    )

    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8")), True
        except (json.JSONDecodeError, OSError):
            # Ignore a damaged cache file and regenerate it.
            pass

    client = _client()

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=p,
                config={
                    "response_mime_type": "application/json"
                },
            )

            if not response.text:
                raise ValueError("Gemini returned an empty response.")

            out = _clean(json.loads(response.text))

            if out.get("topic_id") not in {t["id"] for t in topics}:
                out["relevant"] = False
                out["confidence"] = "low"

            # Atomic write helps avoid incomplete cache files.
            temp_file = cache_file.with_suffix(".tmp")
            temp_file.write_text(
                json.dumps(out, ensure_ascii=False),
                encoding="utf-8",
            )
            temp_file.replace(cache_file)

            return out, False

        except Exception as e:
            print(f"LLM attempt {attempt + 1}/3 failed: {e}")

            if attempt < 2:
                time.sleep(2 ** (attempt + 1))

    return None, False
