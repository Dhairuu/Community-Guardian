"""
ReAct agent tools for the Community Guardian chat agent.

Tools:
  1. search_news — Fetch latest safety news from newsdata.io for a city
  2. search_threat_db — Semantic search over ChromaDB (patterns + news intelligence)
  3. get_trending_threats — Detect trending threat categories from stored news
  4. verify_credibility — Score source credibility based on newsdata.io metadata
  5. extract_keywords — Extract safety-relevant keywords from text (LLM or fallback)
  6. get_safety_checklist — Get actionable safety checklist for a threat category
"""

import asyncio
import hashlib
import json
import logging
from langchain_core.tools import tool

from backend.config import settings, SAFETY_KEYWORDS
from backend.services.vector_store import (
    search_similar_threats,
    search_news_intelligence,
    store_news_article,
    get_trending_threats as _get_trending,
    get_news_intelligence_stats,
)
from backend.services.news_fetcher import fetch_news, _detect_city
from backend.database import get_reports
from backend.fallback.templates import get_fallback_checklist
from backend.models import Category

log = logging.getLogger("pipeline.tools")


def _run_async(coro):
    """Run async function from sync context."""
    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


@tool
def search_news(query: str, city: str = "India") -> str:
    """Search for latest Indian safety and crime news. Use this when the user asks about
    recent incidents, current threats, or news in a specific city. Returns news articles
    with source credibility info."""
    log.info("  TOOL: search_news(query='%s', city='%s')", query[:60], city)

    articles = _run_async(fetch_news(city, query=query))

    if not articles:
        return json.dumps({"articles": [], "message": f"No news articles found for '{query}'."})


    from backend.services.news_fetcher import _extract_keywords
    keywords = _extract_keywords(query)
    log.info("    Scoring %d articles against keywords: %s", len(articles), keywords)

    scored = []
    for article in articles:
        text = f"{article.title} {article.content}".lower()
        hits = sum(1 for kw in keywords if kw in text)
        scored.append((hits, article))

    scored.sort(key=lambda x: x[0], reverse=True)

    relevant = [(h, a) for h, a in scored if h > 0]
    top = relevant[:5] if relevant else scored[:3]

    stored_count = 0
    for hits, article in top:
        if hits == 0:
            continue  # Skip articles with no keyword relevance
        article_id = hashlib.md5(article.title.encode()).hexdigest()[:16]
        was_new = store_news_article(
            article_id=article_id,
            title=article.title,
            content=article.content[:500],
            metadata={
                "title": article.title,
                "city": article.city or city,
                "source": article.source,
                "news_source": article.metadata.get("news_source", "Unknown"),
                "source_priority": article.metadata.get("source_priority", 999999),
                "published_at": article.published_at or "",
                "keywords": json.dumps(article.metadata.get("api_keywords", [])),
                "category": json.dumps(article.metadata.get("category", [])),
                "url": article.url or "",
                "origin": "chat_search",
            },
        )
        if was_new:
            stored_count += 1

    result = []
    for _, article in top:
        result.append({
            "title": article.title,
            "content": article.content[:300],
            "source": article.metadata.get("news_source", article.source),
            "source_priority": article.metadata.get("source_priority", "N/A"),
            "city": article.city,
            "published_at": article.published_at,
            "url": article.url,
        })

    log.info("    → Found %d relevant articles, stored %d new in ChromaDB", len(result), stored_count)
    return json.dumps({"articles": result, "stored_new": stored_count})


@tool
def search_threat_db(query: str, city: str = None) -> str:
    """Search the threat intelligence database for known threat patterns and past news.
    Use this to check if a threat has been seen before or to find similar incidents.
    Searches both static threat patterns and stored news intelligence."""
    log.info("  TOOL: search_threat_db(query='%s', city=%s)", query[:60], city)

    # Search static threat patterns
    pattern_matches = search_similar_threats(query, city, n_results=3, min_similarity=0.45)

    # Search news intelligence
    news_matches = search_news_intelligence(query, city=city, n_results=5, min_similarity=0.35)

    results = {
        "known_patterns": [
            {
                "pattern_name": m["metadata"]["pattern_name"],
                "description": m["pattern"],
                "category": m["metadata"].get("category", "Unknown"),
                "severity": m["metadata"].get("severity", "Unknown"),
                "similarity": m["similarity"],
                "recommended_action": m["metadata"].get("recommended_action", ""),
                "helpline": m["metadata"].get("helpline", ""),
            }
            for m in pattern_matches
        ],
        "past_news": [
            {
                "title": m["metadata"].get("title", m["document"][:80]),
                "source": m["metadata"].get("news_source", "Unknown"),
                "city": m["metadata"].get("city", "Unknown"),
                "similarity": m["similarity"],
                "published_at": m["metadata"].get("published_at", ""),
            }
            for m in news_matches
        ],
    }

    log.info("    → %d pattern matches, %d news matches",
             len(results["known_patterns"]), len(results["past_news"]))
    return json.dumps(results)


@tool
def get_trending_threats(city: str = None) -> str:
    """Get currently trending threat categories based on recent news intelligence.
    Use this to understand what types of threats are most active right now."""
    log.info("  TOOL: get_trending_threats(city=%s)", city)

    trends = _get_trending(days=7, min_count=1)

    db_reports = get_reports(city=city, signal="SIGNAL")
    db_categories = {}
    for r in db_reports[:20]:
        cat = r.get("category", "UNKNOWN")
        db_categories[cat] = db_categories.get(cat, 0) + 1

    stats = get_news_intelligence_stats()

    result = {
        "chromadb_trends": trends,
        "classified_report_trends": [
            {"category": cat, "count": count}
            for cat, count in sorted(db_categories.items(), key=lambda x: x[1], reverse=True)
        ],
        "news_db_size": stats["total_articles"],
    }

    log.info("    → %d category trends, %d classified categories",
             len(trends), len(db_categories))
    return json.dumps(result)


@tool
def verify_credibility(source_name: str, source_priority: int = 999999) -> str:
    """Verify the credibility of a news source. Lower source_priority number means
    more trusted (e.g., NDTV=4836, Times of India=1242). Use this to assess
    whether a piece of news is from a reliable outlet."""
    log.info("  TOOL: verify_credibility(source='%s', priority=%d)", source_name, source_priority)

    if source_priority <= 5000:
        tier = "HIGH"
        description = "Major national outlet — highly trusted"
    elif source_priority <= 20000:
        tier = "MEDIUM"
        description = "Regional or specialized outlet — generally reliable"
    elif source_priority <= 100000:
        tier = "LOW"
        description = "Smaller outlet — verify with additional sources"
    else:
        tier = "UNKNOWN"
        description = "Source priority unknown — treat with caution"

    result = {
        "source": source_name,
        "source_priority": source_priority,
        "credibility_tier": tier,
        "description": description,
        "recommendation": (
            "This source can be cited directly." if tier == "HIGH"
            else "Cross-reference with a major outlet before citing." if tier in ("MEDIUM", "LOW")
            else "Look for corroboration from established news sources."
        ),
    }

    log.info("    → %s credibility: %s", source_name, tier)
    return json.dumps(result)


@tool
def extract_keywords(text: str) -> str:
    """Extract safety-relevant keywords from text. Use this when a news article
    has null/missing keywords and you need to categorize it. Returns matched
    safety keywords and detected threat category."""
    log.info("  TOOL: extract_keywords(text='%s')", text[:60])

    text_lower = text.lower()

    matched_keywords = [kw for kw in SAFETY_KEYWORDS if kw in text_lower]

    from backend.fallback.keyword_rules import CATEGORY_KEYWORDS
    category_scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            category_scores[cat.value] = score

    best_category = max(category_scores, key=category_scores.get) if category_scores else "UNKNOWN"

    detected_city = _detect_city(text)

    result = {
        "safety_keywords": matched_keywords,
        "detected_category": best_category,
        "detected_city": detected_city,
        "keyword_count": len(matched_keywords),
    }

    log.info("    → %d keywords found, category=%s, city=%s",
             len(matched_keywords), best_category, detected_city)
    return json.dumps(result)


@tool
def get_safety_checklist(category: str) -> str:
    """Get a safety action checklist for a specific threat category.
    Categories: PHISHING, SCAM, BREACH, PHYSICAL. Returns step-by-step
    actions and relevant Indian helpline numbers."""
    log.info("  TOOL: get_safety_checklist(category='%s')", category)

    try:
        cat = Category(category.upper())
    except ValueError:
        cat = Category.SCAM 

    checklist_data = get_fallback_checklist(cat)

    result = {
        "category": cat.value,
        "checklist": checklist_data["checklist"],
        "simple_action": checklist_data["simple_checklist"],
        "helpline": checklist_data["helpline"],
        "general_helplines": {
            "emergency": "112",
            "cyber_crime": "1930",
            "women_helpline": "181",
            "police": "100",
            "cyber_portal": "cybercrime.gov.in",
        },
    }

    log.info("    → Returned %d-step checklist for %s", len(result["checklist"]), cat.value)
    return json.dumps(result)


ALL_TOOLS = [
    search_news,
    search_threat_db,
    get_trending_threats,
    verify_credibility,
    extract_keywords,
    get_safety_checklist,
]
