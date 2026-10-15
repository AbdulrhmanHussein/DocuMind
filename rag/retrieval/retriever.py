from app.core.config import settings
from app.providers.factory import get_provider


def retrieve_context(
    question: str,
    vector_collection,
    top_k: int | None = None,
    document_id: str | None = None,
) -> list[dict]:
    """Retrieve relevant document chunks from Chroma."""

    question = question.strip()

    if not question:
        return []

    # Avoid querying Chroma when no documents are indexed.
    collection_count = vector_collection.count()

    if collection_count == 0:
        return []

    requested_top_k = (
        top_k if top_k is not None else settings.retrieval_top_k
    )
    requested_top_k = max(1, min(requested_top_k, 10))
    requested_top_k = min(requested_top_k, collection_count)

    # Embed the query using the same provider as document ingestion.
    query_embedding = get_provider().embed_query(question)

    query_args = {
        "query_embeddings": [query_embedding],
        "n_results": requested_top_k,
        "include": ["documents", "metadatas", "distances"],
    }

    if document_id:
        query_args["where"] = {"document_id": document_id}

    results = vector_collection.query(**query_args)

    result_documents = results.get("documents")
    result_metadatas = results.get("metadatas")
    result_distances = results.get("distances")

    if not result_documents or not result_documents[0]:
        return []

    documents = result_documents[0]

    metadatas = (
        result_metadatas[0]
        if result_metadatas and result_metadatas[0]
        else []
    )

    distances = (
        result_distances[0]
        if result_distances and result_distances[0]
        else []
    )

    chunks = []

    for index, text in enumerate(documents):
        if not text or not text.strip():
            continue

        metadata = (
            metadatas[index]
            if index < len(metadatas) and metadatas[index]
            else {}
        )

        distance = (
            float(distances[index])
            if index < len(distances)
            else None
        )

        # Filter chunks that are too distant from the query.
        if (
            distance is not None
            and distance > settings.retrieval_max_distance
        ):
            continue

        chunks.append({
            "text": text,
            "metadata": metadata,
            "distance": distance,
        })

    return chunks
