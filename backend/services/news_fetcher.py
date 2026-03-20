"""
News fetcher with dual mode: newsdata.io (live) or synthetic JSON (tests).
Live mode fetches Indian crime/safety news, filters by safety relevance,
and enriches articles with city detection and keyword extraction.
"""

import httpx
import json
import os
import logging
from backend.config import settings, SAFETY_KEYWORDS
from backend.models import RawReport

log = logging.getLogger("pipeline.news")

CITY_KEYWORDS = {
    "Bengaluru": ["bengaluru", "bangalore", "karnataka", "koramangala", "whitefield", "indiranagar", "hsr layout", "electronic city"],
    "Delhi": ["delhi", "ncr", "new delhi", "noida", "gurgaon", "dwarka", "connaught place", "south delhi"],
    "Mumbai": ["mumbai", "bombay", "maharashtra", "thane", "andheri", "bandra", "juhu", "borivali"],
    "Hyderabad": ["hyderabad", "telangana", "secunderabad"],
    "Chennai": ["chennai", "tamil nadu", "madras"],
}

SAFETY_QUERY_TERMS = [
    "scam", "fraud", "cyber crime", "phishing", "theft", "robbery",
    "data breach", "hack", "ransomware", "identity theft", "murder",
    "kidnapping", "attack", "safety", "arrest", "police",
]

STOPWORDS = {
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "they",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "about", "above", "after",
    "before", "between", "but", "by", "for", "from", "if", "in", "into",
    "of", "on", "or", "out", "over", "so", "than", "that", "then", "there",
    "this", "to", "too", "under", "up", "very", "what", "when", "where",
    "which", "while", "who", "why", "with", "and", "not", "no", "any",
    "some", "just", "how", "here", "all", "also", "am", "at", "as",
    "heard", "going", "near", "around", "tell", "know", "think", "said",
    "please", "help", "want", "need", "like", "get", "got", "make",
    "recently", "recent", "latest", "new", "last", "today", "happening",
    # Generic adjectives/words that pollute news search queries
    "bad", "good", "big", "many", "much", "more", "most", "real", "really",
    "lot", "lots", "thing", "things", "news", "case", "cases", "people",
    "someone", "something", "anything", "everyone", "update", "updates",
    "information", "info", "details", "regarding", "related", "report",
    "reports", "read", "saw", "seen", "come", "came", "look", "looking",
}


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from a natural language query.
    Strips stopwords and short words (< 3 chars), returns content keywords."""
    words = text.lower().split()
    # Remove punctuation from each word
    cleaned = []
    for w in words:
        w = w.strip(".,?!\"'()[]{}:;")
        if w and len(w) > 2 and w not in STOPWORDS:
            cleaned.append(w)
    return cleaned


def _detect_city(text: str) -> str | None:
    """Detect Indian city from text content."""
    text_lower = text.lower()
    for city, keywords in CITY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return city
    return None


def _is_safety_relevant(title: str, description: str, keywords: list | None) -> bool:
    """Check if an article is relevant to community safety (not entertainment/sports)."""
    text = f"{title} {description}".lower()
    hits = sum(1 for kw in SAFETY_KEYWORDS if kw in text)
    if hits > 0:
        return True
    if keywords:
        kw_text = " ".join(keywords).lower()
        return any(sk in kw_text for sk in SAFETY_KEYWORDS)
    return False


async def fetch_news(city: str = None, query: str = None) -> list[RawReport]:
    """Fetch news articles — synthetic or live from newsdata.io.

    Args:
        city: Filter by Indian city name
        query: User's search query — passed to newsdata.io `q` param for targeted results
    """
    if settings.DATA_MODE == "synthetic":
        return _load_synthetic(city)
    return await _fetch_live(city, query=query)


def _load_synthetic(city: str = None) -> list[RawReport]:
    """Load synthetic news from JSON file (used in tests and demo mode)."""
    data_path = os.path.join(settings.DATA_DIR, "news_feed.json")
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)

    reports = []
    for article in data["articles"]:
        text = article["title"] + " " + article.get("content", "")
        detected_city = _detect_city(text)

        if city and detected_city != city:
            continue

        reports.append(
            RawReport(
                source="newsapi",
                title=article["title"],
                content=article.get("content") or article.get("description", ""),
                url=article.get("url"),
                published_at=article.get("publishedAt"),
                city=detected_city or "Unknown",
                metadata={"news_source": article["source"]["name"]},
            )
        )
    return reports


async def _fetch_live(city: str = None, query: str = None) -> list[RawReport]:
    """Fetch live news from newsdata.io API (free tier: 200 credits/day).

    Args:
        city: Filter results by Indian city
        query: User's search terms — combined with safety keywords for the `q` param.
               If None, uses generic safety keywords only.
    """
    if not settings.NEWSDATA_API_KEY:
        log.warning("NEWSDATA_API_KEY not set — falling back to synthetic data")
        return _load_synthetic(city)

    keywords = _extract_keywords(query) if query else []

    city_aliases = []
    if city:
        city_aliases = [city.lower()]
        for c, kws in CITY_KEYWORDS.items():
            if c == city:
                city_aliases = kws[:2]
                break

    if keywords:
        log.info("  Extracted keywords from user query: %s", keywords)
        queries_to_try = []

        if city_aliases:
            city_q = " OR ".join(city_aliases[:2])
            kw_q = " OR ".join(keywords)
            queries_to_try.append(f"({kw_q}) {city_aliases[0]}")

        queries_to_try.append(" OR ".join(keywords))

        if city_aliases:
            queries_to_try.append(f"({' OR '.join(SAFETY_QUERY_TERMS[:5])}) {city_aliases[0]}")

        queries_to_try.append(" OR ".join(SAFETY_QUERY_TERMS[:8]))
    else:
        queries_to_try = []
        if city_aliases:
            queries_to_try.append(f"({' OR '.join(SAFETY_QUERY_TERMS[:6])}) ({' OR '.join(city_aliases[:2])})")

        queries_to_try.append(" OR ".join(SAFETY_QUERY_TERMS[:8]))

    log.info("  Fetching from newsdata.io (category=crime)...")
    log.info("  City: %s → aliases: %s", city, city_aliases)

    for attempt, q in enumerate(queries_to_try):
        log.info("  Attempt %d — API q param: \"%s\"", attempt + 1, q[:100])

        params = {
            "apikey": settings.NEWSDATA_API_KEY,
            "country": "in",
            "language": "en",
            "category": "crime",
            "q": q,
            "removeduplicate": 1,
            "size": 10,
        }

        try:
            reports = await _execute_newsdata_request(params, city, user_keywords=keywords if query else None)
            if reports:
                return reports
            log.info("  Attempt %d returned 0 usable articles, trying next query...", attempt + 1)
        except Exception as e:
            log.warning("  Attempt %d failed: %s", attempt + 1, str(e)[:100])

    log.info("  All newsdata.io queries returned 0 results — supplementing with synthetic data")
    return _load_synthetic(city)


async def _execute_newsdata_request(params: dict, city: str = None,
                                     user_keywords: list[str] = None) -> list[RawReport]:
    """Execute a single newsdata.io API request and parse results."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                settings.NEWSDATA_BASE_URL,
                params=params,
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "success":
            log.warning("  newsdata.io returned status=%s: %s",
                        data.get("status"), data.get("results", {}).get("message", ""))
            return []

        results = data.get("results", [])
        log.info("  newsdata.io returned %d articles (totalResults=%s)",
                 len(results), data.get("totalResults", "?"))

        if not results:
            return []

        reports = []
        for article in results:
            title = article.get("title", "")
            description = article.get("description") or ""
            raw_content = article.get("content") or ""
            if "ONLY AVAILABLE IN PAID PLANS" in raw_content or not raw_content.strip():
                content = description
            else:
                content = raw_content
            api_keywords = article.get("keywords") or []

            if not user_keywords:
                if not _is_safety_relevant(title, description, api_keywords):
                    log.info("    [FILTERED] Not safety-relevant: %s", title[:60])
                    continue

            full_text = f"{title} {description} {content}"
            detected_city = _detect_city(full_text)

           
            if city and detected_city and detected_city != city:
                log.info("    [SKIPPED] City mismatch (%s != %s): %s",
                         detected_city, city, title[:60])
                continue

            source_name = article.get("source_name") or article.get("source_id") or "Unknown"
            source_priority = article.get("source_priority", 999999)

            reports.append(
                RawReport(
                    source="newsdata",
                    title=title,
                    content=content[:1000],
                    url=article.get("link"),
                    published_at=article.get("pubDate"),
                    city=detected_city or city or "India",
                    metadata={
                        "news_source": source_name,
                        "source_priority": source_priority,
                        "api_keywords": api_keywords,
                        "image_url": article.get("image_url"),
                        "creator": article.get("creator"),
                        "country": article.get("country", []),
                        "category": article.get("category", []),
                        "sentiment": article.get("sentiment"),
                        "ai_tag": article.get("ai_tag"),
                    },
                )
            )
            log.info("    [ACCEPTED] [priority=%d] %s — %s",
                     source_priority, source_name, title[:60])

        log.info("  Final: %d safety-relevant articles after filtering", len(reports))
        return reports

    except httpx.HTTPStatusError as e:
        log.warning("  newsdata.io HTTP error %d: %s", e.response.status_code, str(e)[:100])
        return []
    except Exception as e:
        log.warning("  newsdata.io request failed: %s", str(e)[:100])
        return []
