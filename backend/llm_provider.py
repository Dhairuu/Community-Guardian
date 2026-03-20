"""
Centralized 3-tier LLM factory: Gemini → Ollama → None (keyword fallback).
Every module that needs an LLM calls get_llm() from here.
"""

import logging
from langchain_core.language_models.chat_models import BaseChatModel

from backend.config import settings

log = logging.getLogger("pipeline.llm")

_current_provider: str | None = None  # "gemini", "ollama", or None
_gemini_available: bool | None = None
_ollama_available: bool | None = None


def _test_gemini() -> bool:
    global _gemini_available
    if not settings.GOOGLE_API_KEY:
        _gemini_available = False
        return False
    try:
        # Use the google-genai SDK directly for a fast probe with no retries.
        # The LangChain wrapper triggers the SDK's internal retry loop (6 retries,
        # exponential backoff) which wastes ~40s when the quota is exhausted.
        from google import genai
        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        client.models.generate_content(
            model=settings.LLM_MODEL,
            contents="test",
            config={"http_options": {"timeout": 10000}},  # 10s hard timeout
        )
        _gemini_available = True
        return True
    except Exception as e:
        log.warning("Gemini unavailable: %s", str(e)[:80])
        _gemini_available = False
        return False


def _test_ollama() -> bool:
    global _ollama_available
    try:
        from langchain_ollama import ChatOllama
        llm = ChatOllama(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0,
            timeout=30,
        )
        llm.invoke("test")
        _ollama_available = True
        return True
    except Exception as e:
        log.warning("Ollama unavailable: %s", str(e)[:80])
        _ollama_available = False
        return False


def detect_provider() -> str:
    """Test available providers and cache the result. Called once at startup."""
    global _current_provider

    log.info("Detecting LLM provider...")

    if _test_gemini():
        _current_provider = "gemini"
        log.info("  → Using Gemini (%s)", settings.LLM_MODEL)
        return _current_provider

    if _test_ollama():
        _current_provider = "ollama"
        log.info("  → Using Ollama (%s)", settings.OLLAMA_MODEL)
        return _current_provider

    _current_provider = None
    log.warning("  → No LLM available — keyword fallback mode")
    return "fallback"


def get_provider_name() -> str:
    if _current_provider is None and _gemini_available is None:
        detect_provider()
    return _current_provider or "fallback"


def get_llm(temperature: float = 0.1) -> BaseChatModel | None:
    """
    Returns the best available LLM. Falls through:
      Gemini → Ollama → None
    If Gemini was working but starts failing (rate limit), auto-switches to Ollama.
    """
    global _current_provider, _gemini_available

    if _current_provider is None and _gemini_available is None:
        detect_provider()

    if _current_provider == "gemini" or (_gemini_available is not False):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=settings.LLM_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=temperature,
                max_retries=2,  # Limit retries to fail fast on 429
            )
        except Exception:
            log.warning("Gemini failed at runtime, switching to Ollama...")
            _gemini_available = False
            _current_provider = "ollama" if _ollama_available else None

    if _current_provider == "ollama" or (_ollama_available is not False):
        try:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=settings.OLLAMA_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
                temperature=temperature,
                timeout=60,
            )
        except Exception:
            log.warning("Ollama failed at runtime")
            _ollama_available = False
            _current_provider = None

    return None


def reset_provider():
    """Force re-detection. Useful after rate limits expire."""
    global _current_provider, _gemini_available, _ollama_available
    _current_provider = None
    _gemini_available = None
    _ollama_available = None
