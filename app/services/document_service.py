from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from pymongo.database import Database
from app.core.config import settings
from rag.ingestion.embedder import embed_texts
from rag.ingestion.loader import load_document
from rag.ingestion.splitter import split_text


def ingest_document(
    file_path: Path,
    filename: str,
    content_hash: str,
    database: Database,
    vector_collection,
) -> tuple[dict, bool]:
    documents = database["documents"]

    existing = documents.find_one({
        "content_hash": content_hash,
        "status": "completed",
    })

    if existing:
        existing.pop("_id", None)
        return existing, True

    document_id = str(uuid4())
    now = datetime.now(timezone.utc)

    record = {
        "document_id": document_id,
        "filename": filename,
        "file_type": file_path.suffix.lower().lstrip("."),
        "file_path": str(file_path.resolve()),
        "content_hash": content_hash,
        "status": "processing",
        "chunk_count": 0,
        "created_at": now,
        "updated_at": now,
        "error": None,
    }

    documents.insert_one(record)
    vector_ids = []

    try:
        pages = load_document(file_path)
        chunks = []

        for page in pages:
            for text in split_text(
                page["text"],
                settings.chunk_size,
                settings.chunk_overlap,
            ):
                chunks.append({
                    "text": text,
                    "page": page["page"],
                })

        if not chunks:
            raise ValueError("No text chunks were produced.")

        embeddings = embed_texts([chunk["text"] for chunk in chunks])

        metadatas = []
        ids = []

        for index, chunk in enumerate(chunks):
            ids.append(f"{document_id}_{index}")
            metadata = {
                "document_id": document_id,
                "filename": filename,
                "chunk_index": index,
                "content_hash": content_hash,
            }

            if chunk["page"] is not None:
                metadata["page"] = chunk["page"]

            metadatas.append(metadata)

        vector_ids = ids

        vector_collection.add(
            ids=ids,
            documents=[chunk["text"] for chunk in chunks],
            embeddings=embeddings,
            metadatas=metadatas,
        )

        documents.update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "status": "completed",
                    "chunk_count": len(chunks),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        record.update({
            "status": "completed",
            "chunk_count": len(chunks),
            "updated_at": datetime.now(timezone.utc),
        })

        return record, False

    except Exception as exc:
        if vector_ids:
            try:
                vector_collection.delete(ids=vector_ids)
            except Exception:
                pass

        documents.update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "status": "failed",
                    "error": str(exc)[:1000],
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        raise
