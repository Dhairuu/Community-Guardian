import os
from dotenv import load_dotenv

load_dotenv()


SAFETY_KEYWORDS = [
    "scam", "fraud", "cyber", "phishing", "theft", "robbery",
    "breach", "hack", "safety", "crime", "ransomware", "skimming",
    "identity theft", "malware", "kidnapping", "murder", "attack",
]


class Settings:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")

    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    NEWSDATA_API_KEY: str = os.getenv("NEWSDATA_API_KEY", os.getenv("NEWSAPI_KEY", ""))
    NEWSDATA_BASE_URL: str = "https://newsdata.io/api/1/latest"

    REDDIT_CLIENT_ID: str = os.getenv("REDDIT_CLIENT_ID", "")
    REDDIT_CLIENT_SECRET: str = os.getenv("REDDIT_CLIENT_SECRET", "")

    DATA_MODE: str = os.getenv("DATA_MODE", "synthetic")

    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    DATABASE_URL: str = "sqlite:///./community_guardian.db"
    CHROMA_PERSIST_DIR: str = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
    DATA_DIR: str = os.path.join(os.path.dirname(__file__), "..", "data")


settings = Settings()
