import httpx
import json
import os
from backend.config import settings
from backend.models import RawReport
from backend.services.news_fetcher import _detect_city

SUBREDDIT_CITY_MAP = {
    "bangalore": "Bengaluru",
    "delhi": "Delhi",
    "mumbai": "Mumbai",
    "hyderabad": "Hyderabad",
    "chennai": "Chennai",
    "india": None,
    "scams": None,
}


async def fetch_reddit(city: str = None) -> list[RawReport]:
    if settings.DATA_MODE == "synthetic":
        return _load_synthetic(city)
    return await _fetch_live(city)


def _load_synthetic(city: str = None) -> list[RawReport]:
    data_path = os.path.join(settings.DATA_DIR, "reddit_posts.json")
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)

    reports = []
    for child in data["data"]["children"]:
        post = child["data"]
        subreddit = post["subreddit"].lower()
        detected_city = SUBREDDIT_CITY_MAP.get(subreddit)

        if not detected_city:
            text = post["title"] + " " + post.get("selftext", "")
            detected_city = _detect_city(text)

        if city and detected_city != city:
            continue

        reports.append(
            RawReport(
                source="reddit",
                title=post["title"],
                content=post.get("selftext", ""),
                url=f"https://reddit.com{post['permalink']}",
                published_at=str(post.get("created_utc", "")),
                city=detected_city or "Unknown",
                metadata={
                    "subreddit": post["subreddit"],
                    "score": post.get("score", 0),
                    "num_comments": post.get("num_comments", 0),
                },
            )
        )
    return reports


async def _fetch_live(city: str = None) -> list[RawReport]:
    token = await _get_reddit_token()
    if not token:
        return []

    if city:
        subreddits = [k for k, v in SUBREDDIT_CITY_MAP.items() if v == city or v is None]
    else:
        subreddits = list(SUBREDDIT_CITY_MAP.keys())

    all_reports = []
    async with httpx.AsyncClient() as client:
        for sub in subreddits:
            try:
                resp = await client.get(
                    f"https://oauth.reddit.com/r/{sub}/new.json",
                    params={"limit": 10},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "User-Agent": "CommunityGuardian/1.0",
                    },
                    timeout=10.0,
                )
                if resp.status_code != 200:
                    continue

                data = resp.json()
                for child in data.get("data", {}).get("children", []):
                    post = child["data"]
                    detected_city = SUBREDDIT_CITY_MAP.get(sub)
                    if not detected_city:
                        text = post.get("title", "") + " " + post.get("selftext", "")
                        detected_city = _detect_city(text)

                    all_reports.append(
                        RawReport(
                            source="reddit",
                            title=post.get("title", ""),
                            content=post.get("selftext", ""),
                            url=f"https://reddit.com{post.get('permalink', '')}",
                            published_at=str(post.get("created_utc", "")),
                            city=detected_city or city or "Unknown",
                            metadata={
                                "subreddit": sub,
                                "score": post.get("score", 0),
                                "num_comments": post.get("num_comments", 0),
                            },
                        )
                    )
            except Exception:
                continue

    return all_reports


async def _get_reddit_token() -> str | None:
    if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_CLIENT_SECRET:
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://www.reddit.com/api/v1/access_token",
                data={"grant_type": "client_credentials"},
                auth=(settings.REDDIT_CLIENT_ID, settings.REDDIT_CLIENT_SECRET),
                headers={"User-Agent": "CommunityGuardian/1.0"},
                timeout=10.0,
            )
            data = resp.json()
            return data.get("access_token")
    except Exception:
        return None
