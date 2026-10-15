from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "DocuMind"
    app_env: str = "development"

    mongodb_uri: str
    mongodb_database: str = "documind"

    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = "documind_chunks"

    llm_provider: str = "cohere"
    cohere_api_key: str = ""
    cohere_embedding_model: str = "embed-multilingual-v3.0"
    cohere_generation_model: str = "command-a-plus-05-2026"

    chunk_size: int = 800
    chunk_overlap: int = 120
    max_upload_size_mb: int = 20

    retrieval_top_k: int = 5
    retrieval_max_distance: float = 0.65
    generation_max_output_tokens: int = 800
    generation_temperature: float = 0.1

    upload_dir: Path = PROJECT_ROOT / "data" / "uploads"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()