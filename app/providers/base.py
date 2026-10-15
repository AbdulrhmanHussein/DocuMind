from abc import ABC, abstractmethod


class LLMProvider(ABC):

    @abstractmethod
    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Create embeddings for document chunks."""
        raise NotImplementedError

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Create an embedding for a search query."""
        raise NotImplementedError

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_output_tokens: int = 800,
        temperature: float = 0.1,
    ) -> str:
        """Generate text using the configured language model."""
        raise NotImplementedError

    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """Return the dimension of the configured embedding model."""
        raise NotImplementedError
