
import hashlib
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from app.core.config import settings
from app.db.mongodb import get_database
from app.schemas.document import DocumentResponse, UploadResponse
from app.services.document_service import ingest_document
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def public_record(record: dict) -> dict:
    record.pop("_id", None)
    record.pop("content_hash", None)
    record.pop("file_path", None)
    return record


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
):
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()

    if not filename or extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Supported formats: PDF, DOCX, TXT, MD.",
        )

    content = await file.read(settings.max_upload_size_mb * 1024 * 1024 + 1)

    if not content:
        raise HTTPException(status_code=400, detail="The file is empty.")

    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Maximum upload size is {settings.max_upload_size_mb} MB.",
        )

    content_hash = hashlib.sha256(content).hexdigest()

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = settings.upload_dir / f"{uuid4().hex}{extension}"
    file_path.write_bytes(content)

    database = get_database(request.app.state.mongo_client)
    vector_collection = request.app.state.chroma_collection

    try:
        record, duplicate = await run_in_threadpool(
            ingest_document,
            file_path,
            filename,
            content_hash,
            database,
            vector_collection,
        )

        if duplicate:
            file_path.unlink(missing_ok=True)

        return {
            "document": public_record(record),
            "duplicate": duplicate,
        }

    except ValueError as exc:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    except Exception as exc:
        logger.exception("Document ingestion failed for %s", filename)
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail="Document ingestion failed. Check server logs.",
        ) from exc


@router.get("", response_model=list[DocumentResponse])
def list_documents(request: Request):
    database = get_database(request.app.state.mongo_client)

    records = database["documents"].find().sort("created_at", -1)

    return [public_record(record) for record in records]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, request: Request):
    database = get_database(request.app.state.mongo_client)

    record = database["documents"].find_one({
        "document_id": document_id
    })

    if not record:
        raise HTTPException(status_code=404, detail="Document not found.")

    return public_record(record)


@router.delete("/{document_id}")
def delete_document(document_id: str, request: Request):
    database = get_database(request.app.state.mongo_client)
    documents = database["documents"]

    record = documents.find_one({"document_id": document_id})

    if not record:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        request.app.state.chroma_collection.delete(
            where={"document_id": document_id}
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not remove indexed chunks. Try again.",
        ) from exc

    file_path = record.get("file_path")
    if file_path:
        Path(file_path).unlink(missing_ok=True)

    documents.delete_one({"document_id": document_id})

    return {
        "message": "Document deleted.",
        "document_id": document_id,
    }
