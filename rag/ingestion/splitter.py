
def split_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")

    if not 0 <= chunk_overlap < chunk_size:
        raise ValueError(
            "chunk_overlap must be >= 0 and smaller than chunk_size."
        )

    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    length = len(text)
    step = chunk_size - chunk_overlap

    while start < length:
        end = min(start + chunk_size, length)

        if end < length:
            minimum_end = start + int(chunk_size * 0.7)

            for separator in ("\n\n", "\n", " "):
                boundary = text.rfind(separator, minimum_end, end)
                if boundary != -1:
                    end = boundary
                    break

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= length:
            break

        # Guarantee forward progress even if a boundary is too early.
        start = max(start + 1, end - chunk_overlap)

    return chunks
