# Community Guardian

**Community Safety & Digital Wellness Platform**

| | |
|---|---|
| **Candidate** | Dhairya Sharma |
| **Scenario** | 3 — Community Safety & Digital Wellness |
| **Time Spent** | ~6 hours |
| **Video Demo** | (https://www.youtube.com/watch?v=2k0BRu21JY4) |

---

## Problem Statement

Indian communities face information overload when it comes to safety — real cyber threats (UPI scams, phishing, data breaches) are buried under clickbait, rumors, and social media drama. This creates two failure modes:
1. **Panic** — people react to noise as if it were signal
2. **Complacency** — people tune out everything, missing real threats

Community Guardian acts as an **intelligent safety filter**: it aggregates local safety data from credible sources, uses a dual-agent AI pipeline to separate signal from noise, and delivers calm, actionable safety digests tailored to Indian cities.

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- (Optional) [Ollama](https://ollama.com) for local LLM fallback

### 1. Clone and set up backend

```bash
cd community-guardian
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env:
#   GOOGLE_API_KEY  — free tier from aistudio.google.com (optional)
#   NEWSDATA_API_KEY — free tier from newsdata.io (optional)
#   DATA_MODE=synthetic  — works out of the box with no API keys
```

### 3. Start backend

```bash
uvicorn backend.main:app --reload --port 8000
```

### 4. Start frontend

```bash
cd frontend
npm install
npm run dev
```

### 5. Open in browser

Navigate to `http://localhost:5173`

### 6. Run tests

```bash
pytest tests/ -v
```

All 17 tests pass (8 keyword classifier + 9 API endpoint tests). Tests use synthetic data and require no API keys.

---

## Features

| Feature | Description |
|---|---|
| **City-based Safety Digest** | Auto-generated digest filtered by city (Bengaluru, Delhi, Mumbai, Hyderabad, Chennai) |
| **AI Noise Filtering** | Dual-agent pipeline classifies each item as SIGNAL vs NOISE (SIGNAL here referes to anything related to crime, scams, etc and NOISE is like the sales or celebrity news)|
| **Threat Classification** | Category (Phishing/Scam/Breach/Physical) + Severity (Low–Critical) with confidence scores |
| **Threat Pattern Memory** | ChromaDB vector store with 25 known Indian threat patterns for similarity matching |
| **Action Checklists** | 3-step calm, specific action plan per threat |
| **Daily Security Tip** | AI-generated tip based on current threat trends in a city |
| **ReAct Chat Agent** | Ask questions like "Any UPI scams in Bengaluru?", the agent autonomously searches news and threat DB |
| **Simple Mode** | Elderly-friendly: plain language, single action, large text, helpline numbers |
| **Category Filters** | Filter by Phishing, Scam, Breach, Physical |
| **Report Status** | Mark threats as resolved or dismissed (CRUD Update + deduplication), this is currently just a global change, the idea is the application will know user wise what threats/situation the user is concerned about or has no relevance to the user |
| **3-Tier LLM Fallback** | Gemini → Ollama → keyword classifier — app works even with no LLM |
| **Live + Synthetic Data** | One env var (`DATA_MODE`) switches between newsdata.io live API and demo JSON |

---

## Architecture

```
User selects city (e.g. Bengaluru)
        ↓
┌──────────────────────────────────────────────────┐
│  DATA INGESTION                                  │
│  newsdata.io (live + synthetic)                  │
│  [Synthetic JSON for demo / live via env switch] │
└──────────────────┬───────────────────────────────┘
                   ↓
┌──────────────────────────────────────────────────┐
│  LangGraph StateGraph Pipeline                   │
│                                                  │
│  fetch_data → pattern_lookup → classify          │
│                                   ↓              │
│                         ┌── SIGNAL? ──┐          │
│                         ↓             ↓          │
│                     respond        (skip)        │
│                         ↓             ↓          │
│                     generate_tip ←────┘          │
│                         ↓                        │
│                     save_results → END           │
│                                                  │
│  ChromaDB: Threat pattern similarity matching    │
│  Agent 1: Classifier (signal/noise + category)   │
│  Agent 2: Responder (3-step checklist)           │
│  Fallback: Keyword rules + template checklists   │
└──────────────────┬───────────────────────────────┘
                   ↓
┌──────────────────────────────────────────────────┐
│  ReAct Chat Agent (langgraph prebuilt)           │
│  6 tools: search_news, search_threat_db,         │
│  get_trending_threats, verify_credibility,        │
│  extract_keywords, get_safety_checklist          │
│  Conversation history + guardrails               │
└──────────────────┬───────────────────────────────┘
                   ↓
┌──────────────────────────────────────────────────┐
│  React + Tailwind Frontend                       │
│  Dashboard | Chat | Simple Mode | Filters        │
└──────────────────────────────────────────────────┘
```

### Key Differentiator: Threat Pattern Memory

This is not a simple RAG (Retrieval-Augmented Generation) system that just fetches documents for an LLM. ChromaDB serves as a **learning threat intelligence layer** with two collections:

1. **`threat_patterns`** — 25 static, abstract threat definitions (UPI scams, fake KYC, SIM swap, etc.) that act as the initial knowledge base.
2. **`news_intelligence`** — a growing collection of real-world SIGNAL articles classified by the digest pipeline. Every time the system processes news and identifies a genuine threat, it stores the article as a vector embedding with classification metadata (category, severity, city, source).

Over time, this creates **organic clusters** in the vector space — similar UPI scam articles naturally group together, phishing variants cluster near each other. The system doesn't just retrieve documents; it recognizes patterns across accumulated data. With enough data, the application can surface insights like: *"This matches a UPI collect request scam pattern — similar incidents were reported across 3 cities in the past month."*

This mirrors how enterprise threat intelligence platforms (like Palo Alto's Cortex XDR) correlate indicators of compromise — the difference is that our system builds its intelligence from classified news rather than network telemetry.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Backend | Python + FastAPI | Async, lightweight, fast prototyping |
| AI Orchestration | LangGraph + LangChain | Structured state graph with conditional routing for digest; prebuilt ReAct agent for chat |
| LLM (Primary) | Google Gemini 2.5 Flash | Free tier via AI Studio, fast, good at structured classification |
| LLM (Fallback) | Ollama (local) | Works offline, no API dependency, auto-switches on Gemini 429 |
| Vector DB | ChromaDB | Semantic similarity search for threat pattern matching |
| Database | SQLite | Zero-setup, file-based, sufficient for prototype |
| Frontend | React + Tailwind CSS (Vite) | Component-based UI with utility-first styling |
| Testing | pytest + FastAPI TestClient | 17 tests covering classifier logic + all API endpoints |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check with AI status and data mode |
| POST | `/api/digest` | Generate city safety digest (main pipeline) |
| POST | `/api/chat` | Chat with Community Guardian (ReAct agent) |
| GET | `/api/reports` | List reports (filterable by city, category, severity) |
| PUT | `/api/reports/{id}/status` | Update report status (resolved/dismissed) |
| GET | `/api/daily-tip` | Get today's security tip for a city |

---

## Design Decisions & Tradeoffs

### Why LangGraph over raw LangChain chains?
LangGraph provides an explicit state graph with conditional edges. NOISE reports skip Agent 2 entirely (saving ~50% of LLM calls). Each node's input/output is inspectable for debugging. This mirrors production-grade agent architectures.

### Why source-controlled data ingestion (newsdata.io) over generic web search?
A community safety app using uncontrolled web search risks surfacing the same misinformation it's trying to filter. By pulling from specific credible news outlets, we control input quality. A web search is biased with various ranking algorithms, economic interests.

### Why a 3-tier LLM fallback (Gemini → Ollama → Keywords)?
AI availability shouldn't be a single point of failure for a safety tool. The keyword-based classifier and pre-built checklist templates ensure the app remains useful at all times. The system auto-detects available providers at startup and switches mid-session on rate-limit errors (429 detection with provider reset).

In a production setting, the architecture would likely be 2-tier: a robust cloud LLM endpoint (with proper rate limits and SLAs) plus a well-developed offline classifier built over time with labeled training data. For this prototype, I've shown a 3-tier approach — the local Ollama model serves as the middle tier to demonstrate that the full pipeline works with an actual LLM even when the cloud API is unavailable, while the keyword classifier provides a minimal baseline that required no training data to build within the timebox.

### Why city-level only (no GPS/coordinates)?
Privacy by design. A community safety tool shouldn't require precise location data. City-level filtering provides useful context without invasive tracking.

### What I cut to stay within the timebox
- **Gmail Scam Scanner** — UI mockup is included (Gmail Scanner page) but the read-only Gmail API integration was scoped out. The page shows how it would work as a future feature.
- **Reddit integration** — Initially planned as a second data source, but removed to keep the pipeline focused. newsdata.io alone provides sufficient coverage.
- **Pincode/region filtering** — newsdata.io's `region` parameter requires a Corporate plan. The UI shows a disabled pincode input to indicate future scope.
- **User authentication** — No login system in the prototype. With auth, users could pin/bookmark threats, track their resolution journey, and the system could analyze aggregate behavior — which threat categories cause the most anxiety, how quickly people act on alerts, and which news sources consistently trigger fear vs informed action. This data could generate **media accountability reports**: *"Source X's coverage of UPI scams caused 3x more panic reactions than Source Y's coverage of the same incidents"* — holding news outlets accountable for sensationalism vs responsible reporting.

### What I'd build next with more time
- **Gmail Scam Scanner** — Read-only Gmail API integration to flag potential phishing/scam emails in the user's inbox, with on-device analysis (no email content stored server-side)
- **Real-time push notifications** for critical threats
- **Safe Circles** — encrypted status sharing within trusted groups
- **Reddit/community forum integration** — Second data source for hyperlocal community reports
- **Multi-language support** — Hindi, Kannada, Tamil, Telugu translations
- **Community voting** on report accuracy to improve signal quality

### Known limitations
- **Free API rate limits** — Gemini free tier has 15 RPM / 1M TPM limits. The app auto-switches to Ollama on 429 errors. The keyword fallback always works.
- **newsdata.io free tier** — 200 credits/day, results limited to recent articles. Some cities may return fewer results than others depending on news coverage.
- **Synthetic data for demo** — The default `DATA_MODE=synthetic` uses static JSON files. Live mode requires API keys but demonstrates the same pipeline with real data.
- **No persistent user sessions** — No user accounts by design (privacy-first). Report dismiss/resolve actions persist in SQLite but are shared across all users. With authentication, per-user preferences and behavioral analytics (as described above) would be possible.
- **Single-language** — Currently English only. Indian language support would require multilingual LLM prompts and UI translations.

---

## Responsible AI Practices

1. **Confidence transparency** — Every classified report shows a confidence score (0.0–1.0)
2. **Fallback indicator** — UI clearly shows when keyword-based classification is used instead of AI
3. **No PII** — No user accounts, no personal data collection, city-level only
4. **Honest limitations** — AI classifications are labeled as such, not presented as verified facts
5. **Calm tone** — AI prompts explicitly instruct "calm, factual, empowering — never alarmist"
6. **Helpline visibility** — Indian emergency numbers (112, 1930) always accessible
7. **Guardrails** — Chat agent rejects off-topic queries and redirects to safety topics
8. **Output sanitization** — Non-Latin character filtering to prevent multilingual model leakage

---

## AI Disclosure

**Did you use an AI assistant?** Yes, Claude was used as a development assistant for debuggin and testing.

**How did you verify the suggestions?** Every generated component was tested manually in the browser and via `pytest`. LLM integration code was verified by running the full pipeline with both Gemini and Ollama, inspecting structured JSON outputs, and confirming fallback behavior by disabling API keys. All 17 tests pass in fallback mode (no LLM required).

**Example of a suggestion rejected or changed:**
- Claude suggested to use Tavily to extract news information, but it was a llm structured web search which was not great, so I switched to a news API.
- I rejected a suggestion to use `react-router` for page navigation `useState` with conditional rendering was simpler and avoided an unnecessary dependency for 3 pages.

**AI used in the application itself:**
- Google Gemini 2.5 Flash (primary) and Ollama local models (fallback) for:
  - Classifying safety reports (signal vs noise, category, severity)
  - Generating action checklists for identified threats
  - Generating daily security tips from threat trends
  - Answering user questions via ReAct chat agent with tool-calling
- All AI-classified content is labeled with confidence scores. A banner appears when the keyword fallback classifier is used instead. The system never presents AI-generated classifications as verified facts.

---

## Project Structure

```
community-guardian/
├── backend/
│   ├── config.py              # Settings from .env
│   ├── models.py              # Pydantic models + enums
│   ├── database.py            # SQLite CRUD with deduplication
│   ├── main.py                # FastAPI endpoints
│   ├── llm_provider.py        # 3-tier LLM factory (Gemini → Ollama → None)
│   ├── agents/
│   │   ├── state.py           # LangGraph DigestState
│   │   ├── nodes.py           # Graph nodes (fetch, classify, respond, tip)
│   │   ├── graph.py           # LangGraph StateGraph definition
│   │   ├── tools.py           # 6 ReAct agent tools
│   │   └── chat_agent.py      # ReAct chat agent (langgraph prebuilt)
│   ├── fallback/
│   │   ├── keyword_rules.py   # Rule-based classifier
│   │   └── templates.py       # Pre-built checklists + daily tips
│   └── services/
│       ├── news_fetcher.py    # newsdata.io (live + synthetic)
│       └── vector_store.py    # ChromaDB init, seed, search
├── frontend/src/
│   ├── App.jsx                # Root component
│   ├── api.js                 # API client
│   └── components/            # Sidebar, TopBar, Digest, ReportCard, ChatPanel, etc.
├── data/
│   ├── news_feed.json         # 18 synthetic articles (5 cities)
│   └── threat_patterns.json   # 25 known Indian threat patterns
├── tests/
│   ├── test_classifier.py     # 8 keyword classifier tests
│   └── test_api.py            # 9 API endpoint tests
├── .env.example
├── requirements.txt
├── DESIGN.md                  # Architecture deep-dive
└── README.md
```

---

## Time Spent

~6 hours total:
- Planning & architecture: 2 hr
- Backend (models, DB, services, LLM provider, agents, fallback): 2 hr
- Frontend (React + Tailwind components): 1.5 hr
- Testing & documentation: 0.5 hr
