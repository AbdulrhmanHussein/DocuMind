import cohere
from app.providers.base import LLMProvider

class CohereProvider(LLMProvider):
    EMBEDDING_DIMENSIONS = {
        "embed-multilingual-v3.0": 1024,
        "embed-multilingual-light-v3.0": 384,
    }

    MAX_TEXTS_PER_REQUEST = 96

    def __init__(
        self,
        api_key: str,
        embedding_model: str,
        generation_model: str,
    ):
        if not api_key or not api_key.strip():
            raise RuntimeError(
                "COHERE_API_KEY is missing. Configure it in .env."
            )

        if embedding_model not in self.EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Unsupported embedding model: {embedding_model}"
            )

        self.embedding_model = embedding_model
        self.generation_model = generation_model
        self.client = cohere.ClientV2(api_key=api_key)

    def _embed(
        self,
        texts: list[str],
        input_type: str,
    ) -> list[list[float]]:
        if not texts:
            return []

        embeddings = []

        for start in range(0, len(texts), self.MAX_TEXTS_PER_REQUEST):
            batch = texts[
                start : start + self.MAX_TEXTS_PER_REQUEST
            ]

            response = self.client.embed(
                model=self.embedding_model,
                texts=batch,
                input_type=input_type,
                embedding_types=["float"],
                truncate="NONE",
            )

            batch_embeddings = response.embeddings.float

            if len(batch_embeddings) != len(batch):
                raise RuntimeError(
                    "Cohere returned an unexpected number of embeddings."
                )

            embeddings.extend(
                [list(vector) for vector in batch_embeddings]
            )

        return embeddings

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        return self._embed(
            texts=texts,
            input_type="search_document",
        )

    def embed_query(self, text: str) -> list[float]:
        text = text.strip()

        if not text:
            raise ValueError("Query text cannot be blank.")

        embeddings = self._embed(
            texts=[text],
            input_type="search_query",
        )

        return embeddings[0]

    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_output_tokens: int = 800,
        temperature: float = 0.1,
    ) -> str:
        messages = []

        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt,
            })

        messages.append({
            "role": "user",
            "content": prompt,
        })

        response = self.client.chat(
            model=self.generation_model,
            messages=messages,
            max_tokens=max_output_tokens,
            temperature=temperature,
        )

        content = response.message.content or []
        text_parts = [
            part.text
            for part in content
            if getattr(part, "text", None)
        ]

        answer = "\n".join(text_parts).strip()

        if not answer:
            raise RuntimeError(
                "Cohere returned an empty generation response."
            )

        return answer

    def get_embedding_dimension(self) -> int:
        return self.EMBEDDING_DIMENSIONS[self.embedding_model]
