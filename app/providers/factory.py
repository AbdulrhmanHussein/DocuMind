from functools import lru_cache

from app.core.config import settings
from app.providers.base import LLMProvider
from app.providers.cohere_provider import CohereProvider


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    provider_name = settings.llm_provider.strip().lower()

    if provider_name == "cohere":
        return CohereProvider(
            api_key=settings.cohere_api_key,
            embedding_model=settings.cohere_embedding_model,
            generation_model=settings.cohere_generation_model,
        )

    raise ValueError(
        f"Unsupported LLM provider: {provider_name}"
    )
