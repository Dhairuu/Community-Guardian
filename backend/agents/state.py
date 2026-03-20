from typing import TypedDict
from backend.models import RawReport, ClassifiedReport, ActionableReport


class DigestState(TypedDict, total=False):
    city: str
    simple_mode: bool
    raw_reports: list[RawReport]
    pattern_matches: dict  # report_title -> list of ChromaDB matches
    classified_reports: list[ClassifiedReport]
    actionable_reports: list[ActionableReport]
    daily_tip: str
    is_fallback: bool
    news_stored_count: int  # number of articles stored in news_intelligence
    trending_threats: list[dict]  # trending threat categories
