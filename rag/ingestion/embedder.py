from app.providers.factory import get_provider


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    return get_provider().embed_documents(texts)


def embedding_dimension() -> int:
    return get_provider().get_embedding_dimension()
