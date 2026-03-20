"""
ChromaDB vector store with two collections:
  1. threat_patterns — 25 static known threat patterns (seeded from JSON)
  2. news_intelligence — live news articles enriched with metadata (built over time)

Supports metadata-filtered semantic search, trend detection, and credibility scoring.
"""

import chromadb
import json
import os
import logging
from datetime import datetime, timedelta
from backend.config import settings

log = logging.getLogger("pipeline.chromadb")

_client = None
_threat_collection = None
_news_collection = None


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return _client



def get_collection():
    """Get the threat_patterns collection (backwards-compatible name)."""
    global _threat_collection
    if _threat_collection is None:
        client = _get_client()
        _threat_collection = client.get_or_create_collection(
            name="threat_patterns", metadata={"hnsw:space": "cosine"}
        )
        if _threat_collection.count() == 0:
            _seed_patterns()
    return _threat_collection


def _seed_patterns():
    data_path = os.path.join(settings.DATA_DIR, "threat_patterns.json")
    with open(data_path, encoding="utf-8") as f:
        patterns = json.load(f)

    ids = [p["id"] for p in patterns]
    documents = [f"{p['pattern_name']}: {p['description']}" for p in patterns]
    metadatas = [
        {
            "category": p["category"],
            "severity": p["severity"],
            "affected_cities": json.dumps(p["affected_cities"]),
            "recommended_action": p["recommended_action"],
            "helpline": p.get("helpline", ""),
            "pattern_name": p["pattern_name"],
        }
        for p in patterns
    ]

    _threat_collection.add(ids=ids, documents=documents, metadatas=metadatas)
    log.info("Seeded %d threat patterns into ChromaDB", len(patterns))


def search_similar_threats(query_text: str, city: str = None, n_results: int = 3,
                          min_similarity: float = 0.50) -> list[dict]:
    """Search threat_patterns collection for known threat matches."""
    collection = get_collection()

    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    log.info("    ChromaDB query: \"%s\"", query_text[:80])
    matches = []
    for i in range(len(results["ids"][0])):
        distance = results["distances"][0][i]
        similarity = round(1 - distance, 2)
        metadata = results["metadatas"][0][i]
        pattern_name = metadata.get("pattern_name", "?")

        if similarity < min_similarity:
            log.info("      [REJECTED] %.0f%% — %s (below %.0f%% threshold)",
                     similarity * 100, pattern_name, min_similarity * 100)
            continue

        if city:
            affected = metadata.get("affected_cities", "[]")
            if city not in affected and "All" not in affected:
                log.info("      [SKIPPED]  %.0f%% — %s (city %s not in %s)",
                         similarity * 100, pattern_name, city, affected)
                continue

        log.info("      [MATCHED]  %.0f%% — %s",
                 similarity * 100, pattern_name)
        matches.append(
            {
                "id": results["ids"][0][i],
                "pattern": results["documents"][0][i],
                "metadata": metadata,
                "similarity": similarity,
            }
        )
    return matches


def add_threat_pattern(pattern_id: str, document: str, metadata: dict):
    collection = get_collection()
    collection.add(ids=[pattern_id], documents=[document], metadatas=[metadata])


def get_news_collection():
    """Get or create the news_intelligence collection for storing enriched news."""
    global _news_collection
    if _news_collection is None:
        client = _get_client()
        _news_collection = client.get_or_create_collection(
            name="news_intelligence", metadata={"hnsw:space": "cosine"}
        )
    return _news_collection


def store_news_article(article_id: str, title: str, content: str, metadata: dict):
    """Store a news article in the news_intelligence collection with rich metadata."""
    collection = get_news_collection()

    try:
        existing = collection.get(ids=[article_id])
        if existing and existing["ids"]:
            return False  # Already exists
    except Exception:
        pass

    clean_metadata = {}
    for k, v in metadata.items():
        if isinstance(v, (str, int, float, bool)):
            clean_metadata[k] = v
        elif isinstance(v, list):
            clean_metadata[k] = json.dumps(v)
        elif v is None:
            clean_metadata[k] = ""
        else:
            clean_metadata[k] = str(v)

    document = f"{title}: {content[:500]}"
    collection.add(ids=[article_id], documents=[document], metadatas=[clean_metadata])
    return True


def search_news_intelligence(query_text: str, city: str = None,
                             category: str = None, n_results: int = 5,
                             min_similarity: float = 0.40) -> list[dict]:
    """Semantic search over stored news articles with optional metadata filters."""
    collection = get_news_collection()

    if collection.count() == 0:
        return []

    where_filter = None
    conditions = []
    if city:
        conditions.append({"city": city})
    if category:
        conditions.append({"category": category})
    if len(conditions) == 1:
        where_filter = conditions[0]
    elif len(conditions) > 1:
        where_filter = {"$and": conditions}

    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=min(n_results, collection.count()),
            where=where_filter if where_filter else None,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        log.warning("  Filtered query failed (%s), retrying without filters", str(e)[:60])
        results = collection.query(
            query_texts=[query_text],
            n_results=min(n_results, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

    matches = []
    for i in range(len(results["ids"][0])):
        distance = results["distances"][0][i]
        similarity = round(1 - distance, 2)
        if similarity < min_similarity:
            continue
        matches.append({
            "id": results["ids"][0][i],
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "similarity": similarity,
        })

    return matches


def get_trending_threats(days: int = 7, min_count: int = 2) -> list[dict]:
    """Detect trending threat categories from recent news intelligence."""
    collection = get_news_collection()
    if collection.count() == 0:
        return []

    # Get all recent articles
    try:
        all_docs = collection.get(
            include=["metadatas"],
            limit=100,
        )
    except Exception:
        return []


    category_counts = {}
    city_counts = {}
    category_articles = {}

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    for metadata in all_docs.get("metadatas", []):
        pub_date = metadata.get("published_at", "")
        if pub_date and pub_date < cutoff:
            continue

        cat = metadata.get("category", "UNKNOWN")
        city = metadata.get("city", "Unknown")

        category_counts[cat] = category_counts.get(cat, 0) + 1
        city_counts[city] = city_counts.get(city, 0) + 1

        if cat not in category_articles:
            category_articles[cat] = []
        category_articles[cat].append(metadata.get("title", "Unknown"))

    trends = []
    for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        if count >= min_count:
            trends.append({
                "category": cat,
                "count": count,
                "sample_titles": category_articles.get(cat, [])[:3],
            })

    return trends


def get_news_intelligence_stats() -> dict:
    """Get stats about the news intelligence collection."""
    collection = get_news_collection()
    return {
        "total_articles": collection.count(),
        "collection_name": "news_intelligence",
    }
