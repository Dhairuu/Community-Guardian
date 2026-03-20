import json
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from backend.config import settings
from backend.llm_provider import get_llm, get_provider_name, reset_provider
from backend.models import (
    RawReport, ClassifiedReport, ActionableReport,
    Category, Severity, SignalType,
)
from backend.services.news_fetcher import fetch_news
from backend.services.vector_store import search_similar_threats, store_news_article
from backend.fallback.keyword_rules import classify_by_keywords
from backend.fallback.templates import get_fallback_checklist, get_fallback_daily_tip
from backend.database import save_report, save_daily_tip, get_daily_tip
from backend.agents.state import DigestState

import asyncio
import hashlib
import re
from datetime import datetime

log = logging.getLogger("pipeline")


def _sanitize_text(text: str) -> str:
    """Remove non-Latin script characters (e.g., Chinese from qwen2.5 leaking)."""
    return re.sub(r'[^\x00-\x7F\u00C0-\u024F\u20B9₹\u0900-\u097F]', '', text).strip()


BATCH_CLASSIFIER_PROMPT = """You are a safety intelligence analyst for Indian communities.
Classify EACH report below as SIGNAL (real safety concern) or NOISE (irrelevant/entertainment/venting).

For SIGNAL reports, assign:
- category: PHISHING | SCAM | BREACH | PHYSICAL
- severity: LOW | MEDIUM | HIGH | CRITICAL

Classification rules:
- PHISHING: Fake websites, credential theft, fake emails/SMS with malicious links
- SCAM: Financial fraud, UPI scams, lottery/prize scams, impersonation
- BREACH: Data leaks, hacking, ransomware, exposed databases
- PHYSICAL: Robbery, theft, accidents, physical safety threats
- NOISE: Entertainment, sports, food, weather (unless severe), ads, tech events

Severity rules:
- CRITICAL: Active ongoing threat, immediate risk to many
- HIGH: Confirmed threat, multiple victims, widespread
- MEDIUM: Reported incident, moderate risk
- LOW: Advisory, old incident, limited scope

{reports_block}

Respond ONLY with a JSON array, one object per report in the same order:
[{{"id": 1, "signal": "SIGNAL or NOISE", "category": "PHISHING|SCAM|BREACH|PHYSICAL|NOISE", "severity": "LOW|MEDIUM|HIGH|CRITICAL", "confidence": 0.0 to 1.0, "reasoning": "one sentence"}}, ...]"""


BATCH_RESPONDER_PROMPT = """You are a community safety advisor. Your tone is CALM, CLEAR, and EMPOWERING.
Never use alarmist language. Focus on what people CAN DO.

For EACH safety report below, generate:
1. A 3-step action checklist (specific, practical)
2. A single simplified action for elderly users (plain language, no jargon, one sentence)
3. A relevant Indian helpline number

{reports_block}

Respond ONLY with a JSON array, one object per report in the same order:
[{{"id": 1, "checklist": ["step 1", "step 2", "step 3"], "simple_checklist": "one simple sentence", "helpline": "helpline with number"}}, ...]"""


DAILY_TIP_PROMPT = """You are a cybersecurity advisor for Indian communities.
Based on these recent threat trends, generate ONE practical daily security tip.

Recent threats in {city}:
{threat_summaries}

The tip should be:
- Specific and actionable (not generic)
- Calm, friendly language
- 2-3 sentences maximum
- Relevant to current threats
- In English only (no other languages or scripts)

Respond with ONLY the tip text in English."""


def _get_llm(temperature=0.1):
    return get_llm(temperature=temperature)



def fetch_data_node(state: DigestState) -> dict:
    city = state["city"]
    log.info("=" * 60)
    log.info("NODE: fetch_data  |  city=%s  |  data_mode=%s", city, settings.DATA_MODE)
    log.info("=" * 60)

    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            news = pool.submit(asyncio.run, fetch_news(city)).result()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            news = loop.run_until_complete(fetch_news(city))
        finally:
            loop.close()

    log.info("  Fetched %d news articles", len(news))
    for i, r in enumerate(news):
        log.info("  [%d] %-8s | %s", i + 1, r.source, r.title[:70])

    return {"raw_reports": news}



def pattern_lookup_node(state: DigestState) -> dict:
    raw_reports = state.get("raw_reports", [])
    city = state["city"]
    pattern_matches = {}

    log.info("=" * 60)
    log.info("NODE: pattern_lookup  |  Querying ChromaDB for %d reports", len(raw_reports))
    log.info("=" * 60)

    for report in raw_reports:
        query = f"{report.title} {report.content}"
        matches = search_similar_threats(query, city)
        if matches:
            pattern_matches[report.title] = matches
            best = matches[0]
            log.info("  MATCH: \"%s\"", report.title[:50])
            log.info("    → Pattern: %s  (similarity: %.2f)",
                     best["metadata"]["pattern_name"], best["similarity"])
        else:
            log.info("  NO MATCH: \"%s\"", report.title[:50])

    log.info("  Summary: %d/%d reports matched known threat patterns",
             len(pattern_matches), len(raw_reports))

    return {"pattern_matches": pattern_matches}



def classify_node(state: DigestState) -> dict:
    raw_reports = state.get("raw_reports", [])
    pattern_matches = state.get("pattern_matches", {})
    classified = []
    is_fallback = False

    log.info("=" * 60)
    log.info("NODE: classify  |  Agent 1 (Classifier)  |  %d reports to classify", len(raw_reports))
    log.info("  LLM provider: %s  |  Model: %s",
             get_provider_name(), settings.LLM_MODEL if get_provider_name() == "gemini" else settings.OLLAMA_MODEL)
    log.info("=" * 60)

    similar_patterns = {}
    for raw in raw_reports:
        matches = pattern_matches.get(raw.title, [])
        if matches:
            similar_patterns[raw.title] = matches[0]["metadata"]["pattern_name"]

    llm_results = None
    try:
        # Build batch prompt
        report_lines = []
        for idx, raw in enumerate(raw_reports):
            matches = pattern_matches.get(raw.title, [])
            ctx = ""
            if matches:
                best = matches[0]
                ctx = f" [KNOWN PATTERN: {best['metadata']['pattern_name']}, similarity={best['similarity']}]"
            report_lines.append(
                f"Report {idx + 1}:{ctx}\n"
                f"  Title: {raw.title}\n"
                f"  Content: {raw.content[:200]}\n"
                f"  Source: {raw.source}\n"
                f"  City: {raw.city or 'Unknown'}"
            )
        reports_block = "\n\n".join(report_lines)

        log.info("  Sending SINGLE batched LLM call for all %d reports...", len(raw_reports))
        llm = _get_llm()
        if llm is None:
            raise ValueError("No LLM available")
        prompt = ChatPromptTemplate.from_template(BATCH_CLASSIFIER_PROMPT)
        chain = prompt | llm | JsonOutputParser()
        llm_results = chain.invoke({"reports_block": reports_block})

        if not isinstance(llm_results, list) or len(llm_results) != len(raw_reports):
            log.warning("  LLM returned %s items (expected %d) — falling back",
                        len(llm_results) if isinstance(llm_results, list) else "non-list",
                        len(raw_reports))
            llm_results = None
            raise ValueError("LLM batch result mismatch")

        log.info("  LLM batch classification successful!")

    except Exception as e:
        is_fallback = True
        error_str = str(e)
        log.warning("  LLM BATCH FAILED: %s", error_str[:120])
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
            log.info("  Rate limit detected — switching LLM provider...")
            reset_provider()
        log.info("  Falling back to keyword-based classifier for all reports...")

    for idx, raw in enumerate(raw_reports):
        similar_pattern = similar_patterns.get(raw.title)

        if llm_results:
            result = llm_results[idx]
            raw_signal = str(result.get("signal", "NOISE")).upper()
            if raw_signal in ("SIGNAL", "NOISE"):
                signal = SignalType(raw_signal)
            elif raw_signal in ("PHISHING", "SCAM", "BREACH", "PHYSICAL"):
                signal = SignalType.SIGNAL
            else:
                signal = SignalType.NOISE

            raw_category = str(result.get("category", "NOISE")).upper()
            try:
                category = Category(raw_category)
            except ValueError:
                category = Category.NOISE if signal == SignalType.NOISE else Category.SCAM

            try:
                severity = Severity(str(result.get("severity", "LOW")).upper())
            except ValueError:
                severity = Severity.LOW
            confidence = float(result.get("confidence", 0.8))

            log.info("  [%d] \"%s\"", idx + 1, raw.title[:55])
            log.info("       LLM → %s | %s | %s | conf=%.2f | %s",
                     signal.value, category.value, severity.value,
                     confidence, result.get("reasoning", "")[:60])
            classified.append(ClassifiedReport(
                source=raw.source,
                title=raw.title,
                content=raw.content,
                url=raw.url,
                published_at=raw.published_at,
                city=raw.city or "Unknown",
                signal=signal,
                category=category,
                severity=severity,
                confidence=confidence,
                similar_pattern=similar_pattern,
                metadata=raw.metadata,
            ))
        else:
            signal, category, severity, confidence = classify_by_keywords(raw.title, raw.content)
            log.info("  [%d] \"%s\"", idx + 1, raw.title[:55])
            log.info("       FALLBACK → %s | %s | %s | conf=%.2f",
                     signal.value, category.value, severity.value, confidence)
            classified.append(ClassifiedReport(
                source=raw.source,
                title=raw.title,
                content=raw.content,
                url=raw.url,
                published_at=raw.published_at,
                city=raw.city or "Unknown",
                signal=signal,
                category=category,
                severity=severity,
                confidence=confidence,
                similar_pattern=similar_pattern,
                metadata=raw.metadata,
            ))

    signal_count = sum(1 for c in classified if c.signal == SignalType.SIGNAL)
    noise_count = len(classified) - signal_count
    log.info("-" * 60)
    log.info("  Classification complete: %d SIGNAL, %d NOISE (fallback=%s)",
             signal_count, noise_count, is_fallback)

    return {"classified_reports": classified, "is_fallback": is_fallback}



def respond_node(state: DigestState) -> dict:
    classified = state.get("classified_reports", [])
    is_fallback = state.get("is_fallback", False)
    actionable = []

    signal_reports = [r for r in classified if r.signal == SignalType.SIGNAL]

    log.info("=" * 60)
    log.info("NODE: respond  |  Agent 2 (Responder)  |  %d SIGNAL reports to process", len(signal_reports))
    log.info("  Mode: %s", "FALLBACK (template checklists)" if is_fallback else "LLM (generating checklists)")
    log.info("=" * 60)

    if is_fallback or not signal_reports:
        for idx, report in enumerate(signal_reports):
            fb = get_fallback_checklist(report.category)
            log.info("  [%d] \"%s\" → template checklist (%s)", idx + 1, report.title[:50], report.category.value)
            actionable.append(ActionableReport(
                report=report,
                checklist=fb["checklist"],
                simple_checklist=fb["simple_checklist"],
                helpline=fb["helpline"],
            ))
        log.info("  Generated %d actionable reports (fallback templates)", len(actionable))
        return {"actionable_reports": actionable}

    try:
        report_lines = []
        for idx, report in enumerate(signal_reports):
            pattern_ctx = f" [Matches: {report.similar_pattern}]" if report.similar_pattern else ""
            report_lines.append(
                f"Report {idx + 1}:{pattern_ctx}\n"
                f"  Title: {report.title}\n"
                f"  Content: {report.content[:200]}\n"
                f"  Category: {report.category.value}\n"
                f"  Severity: {report.severity.value}\n"
                f"  City: {report.city}"
            )
        reports_block = "\n\n".join(report_lines)

        log.info("  Sending SINGLE batched LLM call for %d SIGNAL reports...", len(signal_reports))
        llm = _get_llm(temperature=0.4)
        if llm is None:
            raise ValueError("No LLM available")
        prompt = ChatPromptTemplate.from_template(BATCH_RESPONDER_PROMPT)
        chain = prompt | llm | JsonOutputParser()
        llm_results = chain.invoke({"reports_block": reports_block})

        if not isinstance(llm_results, list) or len(llm_results) != len(signal_reports):
            raise ValueError(f"Expected {len(signal_reports)} results, got {len(llm_results) if isinstance(llm_results, list) else 'non-list'}")

        log.info("  LLM batch response successful!")

        for idx, report in enumerate(signal_reports):
            result = llm_results[idx]
            log.info("  [%d] \"%s\"", idx + 1, report.title[:50])
            log.info("       Checklist: %s", result.get("checklist"))
            log.info("       Helpline: %s", result.get("helpline"))
            actionable.append(ActionableReport(
                report=report,
                checklist=result.get("checklist", []),
                simple_checklist=result.get("simple_checklist"),
                helpline=result.get("helpline"),
            ))

    except Exception as e:
        error_str = str(e)
        log.warning("  LLM BATCH FAILED: %s — using template fallback for all", error_str[:120])
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
            log.info("  Rate limit detected — switching LLM provider...")
            reset_provider()
        for report in signal_reports:
            fb = get_fallback_checklist(report.category)
            actionable.append(ActionableReport(
                report=report,
                checklist=fb["checklist"],
                simple_checklist=fb["simple_checklist"],
                helpline=fb["helpline"],
            ))

    log.info("  Generated %d actionable reports", len(actionable))
    return {"actionable_reports": actionable}




def generate_tip_node(state: DigestState) -> dict:
    city = state["city"]
    today = datetime.now().strftime("%Y-%m-%d")

    log.info("=" * 60)
    log.info("NODE: generate_tip  |  city=%s  |  date=%s", city, today)
    log.info("=" * 60)

    cached = get_daily_tip(city, today)
    if cached:
        log.info("  Using CACHED daily tip (already generated today)")
        log.info("  Tip: \"%s\"", cached[:80])
        return {"daily_tip": cached}

    classified = state.get("classified_reports", [])
    signal_reports = [r for r in classified if r.signal == SignalType.SIGNAL]

    if not signal_reports or state.get("is_fallback", False):
        tip = get_fallback_daily_tip()
        log.info("  Using FALLBACK daily tip (no signal reports or fallback mode)")
        log.info("  Tip: \"%s\"", tip[:80])
        save_daily_tip(city, tip, today)
        return {"daily_tip": tip}

    threat_summaries = "\n".join(
        f"- [{r.category.value}/{r.severity.value}] {r.title}"
        for r in signal_reports[:10]
    )

    try:
        log.info("  Generating LLM daily tip from %d threat trends...", len(signal_reports))
        llm = _get_llm()
        if llm is None:
            raise ValueError("No LLM available")
        prompt = ChatPromptTemplate.from_template(DAILY_TIP_PROMPT)
        chain = prompt | llm
        result = chain.invoke({"city": city, "threat_summaries": threat_summaries})
        tip = _sanitize_text(result.content.strip())
        log.info("  LLM Tip: \"%s\"", tip[:80])
    except Exception as e:
        error_str = str(e)
        log.warning("  LLM FAILED: %s — using fallback tip", error_str[:100])
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
            reset_provider()
        tip = get_fallback_daily_tip()

    save_daily_tip(city, tip, today)
    return {"daily_tip": tip}




def save_results_node(state: DigestState) -> dict:
    actionable = state.get("actionable_reports", [])

    log.info("=" * 60)
    log.info("NODE: save_results  |  Persisting %d reports to SQLite", len(actionable))
    log.info("=" * 60)

    for ar in actionable:
        report_dict = {
            "source": ar.report.source,
            "title": ar.report.title,
            "content": ar.report.content,
            "url": ar.report.url,
            "published_at": ar.report.published_at,
            "city": ar.report.city,
            "signal": ar.report.signal.value,
            "category": ar.report.category.value,
            "severity": ar.report.severity.value,
            "confidence": ar.report.confidence,
            "similar_pattern": ar.report.similar_pattern,
            "checklist": json.dumps(ar.checklist),
            "simple_checklist": ar.simple_checklist,
            "helpline": ar.helpline,
        }
        report_id = save_report(report_dict)
        ar.report.id = report_id

        article_id = hashlib.md5(ar.report.title.encode()).hexdigest()[:16]
        was_new = store_news_article(
            article_id=article_id,
            title=ar.report.title,
            content=ar.report.content[:500],
            metadata={
                "title": ar.report.title,
                "city": ar.report.city or "",
                "source": ar.report.source,
                "published_at": ar.report.published_at or "",
                "url": ar.report.url or "",
                "category": ar.report.category.value,
                "severity": ar.report.severity.value,
                "confidence": ar.report.confidence,
                "similar_pattern": ar.report.similar_pattern or "",
                "origin": "digest_pipeline",
            },
        )

        log.info("  Saved report id=%d: \"%s\" (%s/%s)%s",
                 report_id, ar.report.title[:50], ar.report.category.value,
                 ar.report.severity.value, " [+ChromaDB]" if was_new else "")

    return {}



def has_signal_reports(state: DigestState) -> bool:
    classified = state.get("classified_reports", [])
    has_signal = any(r.signal == SignalType.SIGNAL for r in classified)
    log.info("-" * 60)
    log.info("EDGE: has_signal_reports → %s", has_signal)
    if has_signal:
        log.info("  Routing to: respond (Agent 2)")
    else:
        log.info("  Routing to: generate_tip (skipping Agent 2 — all NOISE)")
    return has_signal
