"""
ReAct chat agent with tool-calling loop (langgraph prebuilt).

The agent has access to 6 tools and autonomously decides which to call
based on the user's question. Supports conversation history via LangChain
HumanMessage/AIMessage. Falls back to a direct LLM call (no tools)
if tool-calling fails, and to a static response if LLM is unavailable.
"""

import asyncio
import json
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

from backend.llm_provider import get_llm, get_provider_name, reset_provider
from backend.agents.tools import ALL_TOOLS
from backend.services.vector_store import search_similar_threats, search_news_intelligence
from backend.services.news_fetcher import fetch_news
from backend.database import get_reports

log = logging.getLogger("pipeline.chat")


def _extract_text(content) -> str:
    """Safely extract text from LLM message content.
    Gemini sometimes returns a list of content parts instead of a plain string."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(part["text"])
        return " ".join(parts).strip()
    return str(content).strip()


def _build_langchain_history(chat_history: list[dict]) -> list[HumanMessage | AIMessage]:
    """Convert frontend chat history to LangChain message objects."""
    messages = []
    for msg in chat_history:
        text = msg.get("text", "")
        if msg.get("role") == "user":
            messages.append(HumanMessage(content=text))
        else:
            messages.append(AIMessage(content=text))
    return messages


SYSTEM_PROMPT = """You are Community Guardian, a calm and helpful safety advisor for Indian communities.

You have access to tools that let you:
- Search for latest news about safety threats (search_news)
- Check the threat intelligence database for known patterns (search_threat_db)
- See what threats are trending right now (get_trending_threats)
- Verify if a news source is credible (verify_credibility)
- Extract safety keywords from text (extract_keywords)
- Get actionable safety checklists with helpline numbers (get_safety_checklist)

CRITICAL RULES:
- You ONLY answer questions related to community safety, crime, scams, digital security, and public welfare in India.
- If the user asks something unrelated (e.g. jokes, coding, general knowledge, personal advice), politely redirect: "I'm Community Guardian, focused on community safety. I can help with safety concerns, scam alerts, or crime information in your city. How can I help you stay safe?"
- ALWAYS use search_news or search_threat_db before answering questions about threats or incidents.
- READ your tool results carefully. If a tool returned articles matching the user's query, cite them specifically by title and source.
- Do NOT say "no results found" if your tools returned relevant articles — summarize what was found.
- If the user asks a follow-up like "yes" or "tell me more", look at the conversation history to understand what they're referring to, then use tools to get more details.
- Always include Indian helpline numbers when discussing safety threats (1930 for cybercrime, 112 for emergency).
- Be calm, factual, and empowering. Never alarmist.
- Keep responses concise: 3-5 sentences for normal mode, 2-3 for simple mode.
- If simple_mode is True, use very plain language, short sentences, no jargon.

User's city: {city}
Simple mode: {simple_mode}"""


def chat(message: str, city: str = "Bengaluru", simple_mode: bool = False,
         chat_history: list[dict] = None) -> dict:
    if chat_history is None:
        chat_history = []

    log.info("=" * 60)
    log.info("CHAT AGENT (ReAct)  |  city=%s  |  simple_mode=%s  |  provider=%s  |  history=%d",
             city, simple_mode, get_provider_name(), len(chat_history))
    log.info("  User message: \"%s\"", message[:100])
    log.info("=" * 60)

    llm = get_llm(temperature=0.3)

    if llm is None:
        log.warning("  No LLM available — returning static fallback")
        return _static_fallback(message, city)

  
    lc_history = _build_langchain_history(chat_history)

   
    rate_limited = False
    try:
        log.info("  Attempting ReAct agent with %d tools...", len(ALL_TOOLS))
        result = _run_react_agent(llm, message, city, simple_mode, lc_history)
        if result:
            return result
    except Exception as e:
        error_str = str(e)
        log.warning("  ReAct agent failed: %s", error_str[:120])
        
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
            rate_limited = True
            log.info("  Rate limit detected — resetting provider to try Ollama...")
            reset_provider()
            llm = get_llm(temperature=0.3)
            if llm is None:
                log.warning("  No fallback LLM available after rate limit")
                return _static_fallback(message, city)

   
    try:
        log.info("  Falling back to direct LLM call with context%s...",
                 " (switched to Ollama)" if rate_limited else "")
        return _direct_llm_chat(llm, message, city, simple_mode, lc_history)
    except Exception as e:
        log.warning("  Direct LLM also failed: %s", str(e)[:120])

    return _static_fallback(message, city)


def _run_react_agent(llm, message: str, city: str, simple_mode: bool,
                     lc_history: list) -> dict | None:
    """Run the ReAct agent using langgraph prebuilt create_react_agent."""
    from langgraph.prebuilt import create_react_agent

    system_msg = SYSTEM_PROMPT.format(city=city, simple_mode=simple_mode)

    agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=system_msg,
    )

    
    input_messages = lc_history + [HumanMessage(content=message)]

    log.info("  Invoking langgraph ReAct agent (%d history + 1 new message)...", len(lc_history))
    result = agent.invoke({"messages": input_messages})

   
    messages = result.get("messages", [])
    sources = []
    reply = ""

    for msg in messages:
        msg_type = type(msg).__name__
        if msg_type == "AIMessage" and getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                tool_name = tc.get("name", "unknown")
                sources.append(f"tool:{tool_name}")
                log.info("    Tool called: %s(%s)", tool_name,
                         str(tc.get("args", {}))[:80])
        if msg_type == "ToolMessage":
            log.info("    Tool result (%s): %s...",
                     getattr(msg, "name", "?"), str(msg.content)[:100])

   
    for msg in reversed(messages):
        if type(msg).__name__ == "AIMessage" and not getattr(msg, "tool_calls", None):
            reply = _extract_text(msg.content)
            break

    if not reply:
        for msg in reversed(messages):
            if type(msg).__name__ == "AIMessage" and msg.content:
                reply = _extract_text(msg.content)
                break

    if not reply:
        log.warning("  ReAct agent returned no reply")
        return None

    log.info("  Agent reply: \"%s\"", reply[:120])
    log.info("  Tools used: %s", sources)
    return {"reply": reply, "sources": sources}


def _run_async(coro):
    """Run an async function from sync context."""
    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


def _direct_llm_chat(llm, message: str, city: str, simple_mode: bool,
                     lc_history: list) -> dict:
    """Fallback: gather ALL context manually (news + patterns + DB) and call LLM.
    This runs the same searches the ReAct tools would, just without tool calling."""
    sources = []

    log.info("  [Direct] Step 1: Searching newsdata.io for '%s' in %s...", message[:40], city)
    news_context = ""
    try:
        articles = _run_async(fetch_news(city, query=message))
        if articles:
            news_context = "Recent news articles:\n" + "\n".join(
                f"- [{a.metadata.get('news_source', a.source)}] {a.title}: {a.content[:150]}"
                for a in articles[:5]
            )
            sources.extend(f"news:{a.metadata.get('news_source', a.source)}" for a in articles[:3])
            log.info("  [Direct] Found %d news articles", len(articles))
        else:
            log.info("  [Direct] No news articles found")
    except Exception as e:
        log.warning("  [Direct] News search failed: %s", str(e)[:80])

    log.info("  [Direct] Step 2: Searching threat intelligence DB...")
    pattern_matches = search_similar_threats(message, city)
    pattern_context = ""
    if pattern_matches:
        pattern_context = "Known threat patterns:\n" + "\n".join(
            f"- {m['metadata']['pattern_name']} ({m['similarity']*100:.0f}% match): {m['pattern']}"
            for m in pattern_matches
        )
        sources.extend(m["metadata"]["pattern_name"] for m in pattern_matches)

    news_intel = search_news_intelligence(message, city=city, n_results=3)
    if news_intel:
        pattern_context += "\n\nPast news intelligence:\n" + "\n".join(
            f"- {m['metadata'].get('title', m['document'][:80])} (similarity: {m['similarity']*100:.0f}%)"
            for m in news_intel
        )

    log.info("  [Direct] Step 3: Checking recent classified reports...")
    db_reports = get_reports(city=city)
    report_context = ""
    if db_reports:
        report_context = "Recent classified reports in this city:\n" + "\n".join(
            f"- [{r['category']}/{r['severity']}] {r['title']}" for r in db_reports[:5]
        )

    history_context = ""
    if lc_history:
        history_lines = []
        for msg in lc_history[-6:]:  # Last 3 exchanges max
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            history_lines.append(f"{role}: {_extract_text(msg.content)[:200]}")
        history_context = "Conversation so far:\n" + "\n".join(history_lines)

    log.info("  [Direct] Step 4: Calling LLM with all context...")
    direct_prompt = ChatPromptTemplate.from_template(
        """You are Community Guardian, a calm and helpful safety advisor for Indian communities.

User's city: {city}
Simple mode: {simple_mode}

{history_context}

{news_context}

{pattern_context}

{report_context}

User question: {message}

Guidelines:
- Be calm, factual, and empowering. Never alarmist.
- Cite specific news articles or threat patterns from the context above when relevant.
- If simple_mode is True, use very plain language, short sentences, no jargon.
- Include relevant Indian helpline numbers when appropriate (1930 for cybercrime, 112 for emergency).
- Keep response concise — 3-5 sentences for normal mode, 2-3 for simple mode.
- If no relevant information was found, say so honestly and provide general safety advice.

Respond helpfully:"""
    )

    chain = direct_prompt | llm
    result = chain.invoke({
        "city": city,
        "simple_mode": simple_mode,
        "history_context": history_context or "",
        "news_context": news_context or "No recent news articles found for this query.",
        "pattern_context": pattern_context or "No matching threat patterns found.",
        "report_context": report_context or "No recent classified reports available.",
        "message": message,
    })

    reply = _extract_text(result.content)
    log.info("  Direct LLM reply: \"%s\"", reply[:120])
    log.info("  Sources: %s", sources)
    return {"reply": reply, "sources": sources}


def _static_fallback(message: str, city: str) -> dict:
    """Last resort: static response with helpline numbers."""
    return {
        "reply": (
            f"I'm having trouble connecting right now. "
            f"For immediate safety concerns in {city}, please call "
            f"112 (Emergency) or 1930 (Cyber Crime Helpline)."
        ),
        "sources": [],
    }
