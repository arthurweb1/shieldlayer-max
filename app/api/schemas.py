from typing import Optional
from pydantic import BaseModel


class Message(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    stream: bool = False


class ComplianceInfo(BaseModel):
    compliant: bool
    article: Optional[str] = None
    retries: int = 0


class ChatResponse(BaseModel):
    id: str
    content: str
    compliance: ComplianceInfo
    cached: bool = False


class AuditExportParams(BaseModel):
    from_ts: Optional[str] = None  # ISO datetime
    to_ts: Optional[str] = None
    limit: int = 1000
    format: str = "pdf"
