from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
from datetime import datetime


class Category(str, Enum):
    PHISHING = "PHISHING"
    SCAM = "SCAM"
    BREACH = "BREACH"
    PHYSICAL = "PHYSICAL"
    NOISE = "NOISE"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SignalType(str, Enum):
    SIGNAL = "SIGNAL"
    NOISE = "NOISE"


class RawReport(BaseModel):
    source: str
    title: str
    content: str
    url: Optional[str] = None
    published_at: Optional[str] = None
    city: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class ClassifiedReport(BaseModel):
    id: Optional[int] = None
    source: str
    title: str
    content: str
    url: Optional[str] = None
    published_at: Optional[str] = None
    city: str
    signal: SignalType
    category: Category
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    similar_pattern: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class ActionableReport(BaseModel):
    report: ClassifiedReport
    checklist: list[str]
    simple_checklist: Optional[str] = None
    helpline: Optional[str] = None


class DigestRequest(BaseModel):
    city: str = Field(min_length=1, max_length=100)
    simple_mode: bool = False


class DigestResponse(BaseModel):
    city: str
    generated_at: str
    reports: list[ActionableReport]
    daily_tip: str
    simple_mode: bool
    is_fallback: bool = False


class ChatHistoryMessage(BaseModel):
    role: str  # "user" or "bot"
    text: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    city: str = "Bengaluru"
    simple_mode: bool = False
    chat_history: list[ChatHistoryMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] = Field(default_factory=list)


class ReportStatusUpdate(BaseModel):
    status: str
