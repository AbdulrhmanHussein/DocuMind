from contextlib import asynccontextmanager
import chromadb
from fastapi import FastAPI
from app.api.routes.data import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.chat import router as chat_router
from app.core.config import settings
from app.db.mongodb import create_mongo_client, get_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo_client = create_mongo_client()
    app.state.mongo_client = mongo_client

    chroma_client = None

    try:
        # Fail startup if MongoDB is unavailable.
        mongo_client.admin.command("ping")

        database = get_database(mongo_client)
        database["documents"].create_index(
            "document_id", unique=True
        )
        database["documents"].create_index("content_hash")
        database["documents"].create_index("created_at")

        chroma_client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
        chroma_client.heartbeat()

        app.state.chroma_client = chroma_client
        app.state.chroma_collection = (
            chroma_client.get_or_create_collection(
                name=settings.chroma_collection,
                metadata={"hnsw:space": "cosine"},
            )
        )

        yield

    finally:
        mongo_client.close()


app = FastAPI(
    title=settings.app_name,
    description="Document intelligence and RAG platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(documents_router)
app.include_router(chat_router)

@app.get("/")
def root():
    return {
        "application": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/health/ready",
    }
