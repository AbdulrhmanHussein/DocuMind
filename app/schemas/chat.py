from pydantic import BaseModel, Field
from app.core.config import settings


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    document_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    top_k: int = Field(
        default=settings.retrieval_top_k,
        ge=1,
        le=10,
    )


class SourceResponse(BaseModel):
    source_id: str
    document_id: str | None = None
    filename: str
    page: int | None = None
    chunk_index: int | None = None
    distance: float | None = None


class ChatResponse(BaseModel):
    answer: str
    question: str
    sources: list[SourceResponse]
