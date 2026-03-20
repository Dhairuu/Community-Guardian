import logging
import time
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
import asyncio

from backend.config import settings
from backend.models import (
    DigestRequest, DigestResponse, ChatRequest, ChatResponse,
    ReportStatusUpdate, Category, Severity, SignalType,
)
from backend.database import init_db, get_reports, update_report_status
from backend.services.vector_store import get_collection, get_news_intelligence_stats
from backend.llm_provider import detect_provider, get_provider_name
from backend.agents.graph import digest_pipeline
from backend.agents.chat_agent import chat as chat_agent

logging.basicConfig(
    level=logging.INFO,
    format="\033[36m%(asctime)s\033[0m | \033[33m%(name)-18s\033[0m | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=" * 60)
    log.info("Community Guardian starting up...")
    log.info("  DATA_MODE: %s", settings.DATA_MODE)
    log.info("  NEWSDATA_API_KEY: %s", "configured" if settings.NEWSDATA_API_KEY else "NOT SET")
    log.info("=" * 60)

    init_db()
    log.info("SQLite database initialized")
    get_collection()
    log.info("ChromaDB threat patterns loaded")

    log.info("Detecting LLM provider...")
    provider = detect_provider()
    log.info("LLM provider: %s", provider)

    log.info("=" * 60)
    log.info("Community Guardian ready!")
    log.info("=" * 60)
    yield


app = FastAPI(
    title="Community Guardian",
    description="Community Safety & Digital Wellness Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    news_stats = get_news_intelligence_stats()
    return {
        "status": "healthy",
        "data_mode": settings.DATA_MODE,
        "llm_provider": get_provider_name(),
        "news_intelligence_count": news_stats["total_articles"],
        "timestamp": datetime.now().isoformat(),
    }

@app.post("/api/digest", response_model=DigestResponse)
async def generate_digest(request: DigestRequest):
    try:
        log.info("")
        log.info("*" * 60)
        log.info("DIGEST REQUEST  |  city=%s  |  simple_mode=%s", request.city, request.simple_mode)
        log.info("*" * 60)
        start = time.time()

        initial_state = {
            "city": request.city,
            "simple_mode": request.simple_mode,
            "raw_reports": [],
            "pattern_matches": {},
            "classified_reports": [],
            "actionable_reports": [],
            "daily_tip": "",
            "is_fallback": False,
        }

        log.info("Invoking LangGraph digest pipeline...")
        log.info("  Graph: START → fetch_data → pattern_lookup → classify → [respond] → generate_tip → save_results → END")

        result = await asyncio.to_thread(digest_pipeline.invoke, initial_state)

        elapsed = time.time() - start
        actionable = result.get("actionable_reports", [])

        # Filter for simple mode
        if request.simple_mode:
            before = len(actionable)
            actionable = [
                a for a in actionable
                if a.report.severity in (Severity.HIGH, Severity.CRITICAL)
            ]
            log.info("Simple mode filter: %d → %d reports (HIGH + CRITICAL only)", before, len(actionable))

        log.info("*" * 60)
        log.info("DIGEST COMPLETE  |  %.2fs  |  %d reports  |  fallback=%s",
                 elapsed, len(actionable), result.get("is_fallback", False))
        log.info("*" * 60)
        log.info("")

        return DigestResponse(
            city=request.city,
            generated_at=datetime.now().isoformat(),
            reports=actionable,
            daily_tip=result.get("daily_tip", "Stay alert and stay safe."),
            simple_mode=request.simple_mode,
            is_fallback=result.get("is_fallback", False),
        )

    except Exception as e:
        log.error("DIGEST FAILED: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Digest generation failed: {str(e)}")


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    log.info("")
    log.info("*" * 60)
    log.info("CHAT REQUEST  |  city=%s  |  history=%d msgs  |  message=\"%s\"",
             request.city, len(request.chat_history), request.message[:80])
    log.info("*" * 60)
    start = time.time()

    history = [{"role": m.role, "text": m.text} for m in request.chat_history]

    result = await asyncio.to_thread(
        chat_agent, request.message, request.city, request.simple_mode, history
    )

    elapsed = time.time() - start
    log.info("CHAT COMPLETE  |  %.2fs  |  sources=%s", elapsed, result.get("sources", []))
    log.info("")

    return ChatResponse(reply=result["reply"], sources=result.get("sources", []))


@app.get("/api/reports")
async def list_reports(
    city: str = Query(None),
    category: str = Query(None),
    severity: str = Query(None),
):
    reports = get_reports(city=city, category=category, severity=severity)
    return {"reports": reports, "count": len(reports)}


@app.put("/api/reports/{report_id}/status")
async def update_status(report_id: int, update: ReportStatusUpdate):
    valid_statuses = ["active", "resolved", "dismissed"]
    if update.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Status must be one of: {valid_statuses}",
        )
    success = update_report_status(report_id, update.status)
    if not success:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"message": f"Report {report_id} updated to {update.status}"}


@app.get("/api/daily-tip")
async def daily_tip(city: str = Query("Bengaluru")):
    from backend.database import get_daily_tip as db_get_tip
    from backend.fallback.templates import get_fallback_daily_tip

    today = datetime.now().strftime("%Y-%m-%d")
    tip = db_get_tip(city, today)
    if not tip:
        tip = get_fallback_daily_tip()
    return {"tip": tip, "date": today, "city": city}
