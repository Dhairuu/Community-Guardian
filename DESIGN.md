# Design Document — Community Guardian

## Problem Analysis

### Core Problem
Indian communities face information overload when it comes to safety, real cyber threats (UPI scams, phishing, data breaches) are buried under clickbait, rumors, social media drama, and generic fear-mongering. This creates two failure modes:
1. **Panic** — people react to noise as if it were signal
2. **Complacency** — people tune out everything, missing real threats

### Target Audiences
1. **Neighborhood Groups** — Want local trends without social media toxicity
2. **Remote Workers** — Need breach/phishing alerts relevant to their digital footprint
3. **Elderly Users** — Need plain language, single actions, helpline numbers

### Design Philosophy
- **Calm over alarmist** — Empowering language, neutral black-and-white palette, focus on "here's what you CAN do"
- **Signal over noise** — The core feature IS the filtering; if everything is an alert, nothing is
- **Graceful degradation** — Safety tools must work even when dependencies fail
- **Privacy by default** — City-level only, no PII collection, no GPS tracking

---

## AI Pipeline Architecture

### Digest Pipeline — LangGraph StateGraph

A deterministic pipeline that processes news articles through classification and response generation.

**Why a Dual-Agent Pipeline?**

A single classifier would either be too broad (missing nuances) or too narrow (over-classifying). By splitting into two specialized agents:

- **Agent 1 (Classifier)** focuses on the decision — is this a real safety concern or noise? — plus categorization and severity scoring. Tuned for precision (temperature: 0.1).
- **Agent 2 (Responder)** focuses on generating helpful, calm, actionable responses. Tuned for helpfulness (temperature: 0.4).

**Pipeline Flow:**

```
START → fetch_data → pattern_lookup → classify
                                         ↓
                               ┌── SIGNAL? ──┐
                               ↓             ↓
                           respond        (skip)
                               ↓             ↓
                           generate_tip ←────┘
                               ↓
                           save_results → END
```

Each node:
- `fetch_data`: Calls news_fetcher (newsdata.io or synthetic JSON), returns raw_reports
- `pattern_lookup`: Queries ChromaDB for similar known threats per report
- `classify`: Runs LLM classification (try/except → keyword fallback). Sets is_fallback=True on failure
- `respond`: For SIGNAL reports, generates 3-step checklist via LLM (or template fallback)
- `generate_tip`: Daily security tip from classified threat trends
- `save_results`: Persists to SQLite with deduplication (title + city)

**Why LangGraph?**
- **Conditional routing**: NOISE reports skip Agent 2 → saves ~50% of LLM calls
- **Typed state**: DigestState TypedDict flows through each node
- **Debuggability**: Each node's state transition is inspectable
- **Extensibility**: Adding new nodes (e.g., sentiment analysis) is trivial

### Chat Agent — LangGraph ReAct (Prebuilt)

A separate tool-calling agent for interactive Q&A. Uses `langgraph.prebuilt.create_react_agent` with 6 tools:

| Tool | Purpose |
|---|---|
| `search_news` | Fetch live news from newsdata.io |
| `search_threat_db` | Query ChromaDB for known threat patterns |
| `get_trending_threats` | Get recent classified threats from SQLite |
| `verify_credibility` | Check if a news source is credible |
| `extract_keywords` | Extract safety keywords from natural language |
| `get_safety_checklist` | Generate action checklist for a threat category |

The agent autonomously decides which tools to call based on the user's question. It supports multi-turn conversation via LangChain message history (HumanMessage/AIMessage).

**Guardrails**: The chat agent only answers community safety questions. Off-topic queries (jokes, coding, general knowledge) are politely redirected.

**Fallback chain**: ReAct agent → direct LLM call (no tools) → static safety response with helpline numbers.

---

## 3-Tier LLM Provider

```
Gemini 2.5 Flash (Google AI Studio, free tier)
        ↓ (if unavailable or 429 rate limit)
Ollama (local model, e.g. qwen2.5:7b)
        ↓ (if unavailable)
Keyword fallback (no LLM needed)
```

**Auto-switching**: The system detects provider availability at startup. If Gemini hits a 429 rate limit mid-session, `reset_provider()` is called and the system auto-switches to Ollama without user intervention. Gemini retries are capped at 2 to fail fast.

**Why this approach?** A free-tier API has hard rate limits (200 requests/day for newsdata.io, quota limits for Gemini). A local Ollama fallback ensures the demo always works. The keyword fallback ensures the app works even without any LLM.

---

## Threat Pattern Memory (ChromaDB)

This is the key differentiator. Before classification, every report is compared against a vector database of 25 known Indian threat patterns using cosine similarity. This provides:

1. **Pattern recognition**: "This matches a known UPI collect request scam"
2. **Context for LLM**: The classifier receives pattern match data, improving accuracy
3. **Trend detection**: Multiple reports matching the same pattern indicates an active campaign
4. **Enterprise relevance**: This mirrors how Palo Alto's Cortex XDR correlates threat indicators

**Dual collections**:
- `threat_patterns`: 25 static patterns seeded from `data/threat_patterns.json` — UPI scams, phishing, impersonation, breaches, physical threats
- `news_intelligence`: Dynamic collection that grows over time — stores SIGNAL articles from the digest pipeline and keyword-relevant articles from chat searches, building a learning threat knowledge base

The patterns cover:
- UPI scams (collect request, QR code, money doubling)
- Phishing (fake KYC, bank SMS, IT refund)
- Impersonation (CBI/police, tech support, delivery)
- Data breaches (corporate, healthcare, government)
- Physical safety (chain snatching, ATM tampering)

---

## Fallback System

### Why fallback matters
An AI-powered safety tool that goes dark when the LLM API is unreachable defeats its purpose. The fallback system ensures the app remains useful at all times.

### Keyword-Based Classifier
- Scores text against category-specific keyword dictionaries
- Detects noise indicators (cricket, Bollywood, food, weather terms)
- Confidence deliberately capped at 0.3–0.6 (honest about lower certainty)
- UI shows a "Fallback Mode" banner so users know AI classification is unavailable

### Template Checklists
- Pre-built 3-step action plans for each category (Phishing, Scam, Breach, Physical)
- Simplified single-sentence versions for Simple Mode
- Indian helpline numbers: 1930 (Cybercrime), 112 (Emergency), 181 (Women)

### Daily Tip Rotation
- 31 pre-written security tips (one per day of month)
- Covers practical topics: UPI safety, password hygiene, WhatsApp forwarding, ATM awareness

---

## Data Ingestion Strategy

### Source-Controlled vs Generic Search
I deliberately chose newsdata.io (Indian crime news) over generic web search because:

1. **Source quality**: A safety app using uncontrolled web search risks surfacing the same misinformation it's trying to filter. Web search is biased with various ranking algorithms and economic interests.
2. **Reproducibility**: Synthetic JSON files mirror exact API response formats, so switching to live is a single env variable change
3. **City targeting**: newsdata.io `category=crime` + `country=in` provides focused Indian safety news

### newsdata.io Integration
- Free tier: 200 credits/day, no `region` param — city names injected into `q` parameter as keywords
- Multi-strategy query: user keywords + city → keywords only → city + generic safety → generic fallback
- Safety relevance filter: articles checked against safety keyword dictionary
- City detection: text-based matching against city aliases (e.g., "Bengaluru" / "Bangalore" / "Karnataka")
- Content handling: free tier returns "ONLY AVAILABLE IN PAID PLANS" for full content — system falls back to description field

### Synthetic Data
The demo ships with:
- `news_feed.json`: 18 synthetic articles across 5 cities — mix of real threats + noise
- `threat_patterns.json`: 25 known Indian threat patterns for ChromaDB seeding

All synthetic data is structured to match the exact format of live API responses.

---

## Frontend Design

### Theme: Black & White Newspaper
The UI uses a **monochrome newspaper theme** (Playfair Display + Source Serif 4 serif fonts) with a deliberate absence of color. This is a conscious design choice:
- **Neutral presentation** — Safety information should be presented factually, not emotionally. Bright colors (red alerts, orange warnings) trigger anxiety. A calm, newspaper-like layout lets users process information rationally.
- **Severity via grayscale** — CRITICAL threats use a black top-border accent, HIGH uses dark gray, MEDIUM uses medium gray, LOW uses light gray. Text labels always present alongside visual indicators.
- **Monochrome badges** — Active filter: `bg-black text-white`. Inactive: `border border-gray-300`. No color-based information encoding that could be missed by colorblind users.

### Layout: Sidebar + 3 Pages
- **Sidebar** (fixed left, 240px) — App title, 3 navigation items (Home, AI Chat, Gmail Scanner), status indicators, emergency numbers
- **TopBar** — Page title, city selector, disabled pincode input (future scope), Simple Mode toggle, user icon
- **Pages** managed by `useState("home" | "chat" | "gmail")` — no react-router dependency
- **ChatPanel** always mounted (hidden via `display: none` when inactive) to preserve conversation state

### Accessibility Decisions
- **Simple Mode**: Large text (1.25rem base), single action instead of 3-step checklist, helpline numbers prominent
- **Chat interface**: Natural language queries lower the barrier for non-technical users
- **Chat reset on city change**: Conversation clears when switching cities to avoid confusion

### State Management
Pure React state (useState/useEffect) — no Redux or external state management. For a prototype of this scope, component-level state is simpler to reason about and sufficient.

### Status Indicators
- **AI provider badge**: Shows active LLM (e.g., "AI: gemini" or "AI: ollama")
- **Data mode badge**: Shows "synthetic" or "live"
- **Fallback banner**: Appears on individual digests when keyword classification was used

---

## Responsible AI Practices

1. **Confidence transparency**: Every classified report shows a confidence score (0.0–1.0)
2. **Fallback indicator**: UI clearly shows when keyword-based classification is used instead of AI
3. **No PII**: No user accounts, no personal data collection, city-level only
4. **Honest limitations**: AI classifications are labeled as such, not presented as verified facts
5. **Calm tone**: AI prompts explicitly instruct "calm, factual, empowering — never alarmist"
6. **Helpline visibility**: Indian emergency numbers (112, 1930) always accessible
7. **Chat guardrails**: Agent rejects off-topic queries (jokes, coding, general knowledge)
8. **Output sanitization**: Regex filter strips non-Latin characters to prevent multilingual model leakage (e.g., Chinese from qwen2.5)
9. **Deduplication**: Same article won't appear multiple times across refreshes (title + city uniqueness)

---

## Testing Strategy

### Unit Tests (test_classifier.py — 8 tests)
- Happy path: UPI scam correctly classified as SIGNAL/SCAM
- Category accuracy: Phishing, Breach, Physical correctly identified
- Noise detection: Entertainment (cricket) and food articles classified as NOISE
- Edge cases: Empty content handled gracefully
- Confidence bounds: Always 0.3–0.6 for fallback classifier

### Integration Tests (test_api.py — 9 tests)
- Health endpoint returns correct schema
- Digest pipeline runs end-to-end (synthetic mode + fallback)
- Validation: Missing city → 422, empty chat → 422, invalid status → 400
- Reports CRUD: List, filter, status update
- Daily tip: Returns tip for given city

### What I'd test with more time
- Load testing the LangGraph pipeline with 100+ reports
- LLM response parsing edge cases (malformed JSON from model)
- ChromaDB similarity threshold tuning
- Frontend component tests (React Testing Library)

---

## Success Metrics Coverage

| Metric | How We Address It |
|---|---|
| **Anxiety Reduction** | Calm language in AI prompts, empowering tone ("here's what to do"), neutral black-and-white newspaper theme avoids color-triggered anxiety, severity communicated via grayscale accents + text labels |
| **Contextual Relevance** | City-based filtering, daily tip from local threat trends, ChromaDB pattern matching, newsdata.io `category=crime` + `country=in` |
| **Trust & Privacy** | City-level only (no coordinates), explicit "AI classified" labels, footer disclaimer, confidence scores |
| **AI Application** | LangGraph dual-agent digest + ReAct chat agent with 6 tools, 3-tier LLM fallback, ChromaDB vector similarity |
