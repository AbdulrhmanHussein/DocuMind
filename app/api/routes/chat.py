import logging
from fastapi import APIRouter, HTTPException, Request
from app.schemas.chat import ChatRequest, ChatResponse, SourceResponse
from rag.generation.generator import generate_answer
from rag.retrieval.retriever import retrieve_context


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["Chat"],
)


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, request: Request):
    question = payload.question.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="Question cannot be blank.",
        )

    document_id = payload.document_id

    if document_id is not None:
        document_id = document_id.strip()

        if not document_id:
            raise HTTPException(
                status_code=422,
                detail="document_id cannot be blank.",
            )

    try:
        collection = request.app.state.chroma_collection

        chunks = retrieve_context(
            question=question,
            vector_collection=collection,
            top_k=payload.top_k,
            document_id=document_id,
        )

        if not chunks:
            answer = generate_answer(question, [])
            return ChatResponse(
                answer=answer,
                question=question,
                sources=[],
            )

        answer = generate_answer(question, chunks)

        sources = []

        for index, chunk in enumerate(chunks, start=1):
            metadata = chunk.get("metadata", {})

            sources.append(
                SourceResponse(
                    source_id=f"S{index}",
                    document_id=metadata.get("document_id"),
                    filename=metadata.get("filename", "Unknown document"),
                    page=metadata.get("page"),
                    chunk_index=metadata.get("chunk_index"),
                    distance=chunk.get("distance"),
                )
            )

        return ChatResponse(
            answer=answer,
            question=question,
            sources=sources,
        )

    except Exception as exc:
        logger.exception("Chat request failed.")

        status_code = getattr(exc, "status_code", None)

        if status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="Cohere's API rate limit was reached. Try again later.",
            ) from exc

        if status_code in (401, 403):
            raise HTTPException(
                status_code=502,
                detail="The cloud provider rejected the API credentials or access.",
            ) from exc

        raise HTTPException(
            status_code=502,
            detail="The RAG request failed. Check the server logs.",
        ) from exc
