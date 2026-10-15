from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict


DocumentStatus = Literal["processing", "completed", "failed"]


class DocumentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_id: str
    filename: str
    file_type: str
    status: DocumentStatus
    chunk_count: int = 0
    created_at: datetime
    error: str | None = None


class UploadResponse(BaseModel):
    document: DocumentResponse
    duplicate: bool = False
