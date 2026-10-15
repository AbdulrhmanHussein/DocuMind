import chromadb
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from app.core.config import settings
from app.db.mongodb import get_database

router = APIRouter(prefix="/api/v1/health", tags=["Health"])


@router.get("/live")
def liveness():
    return {
        "status": "alive",
        "application": settings.app_name,
    }


@router.get("/ready")
def readiness(request: Request):
    checks = {
        "mongodb": "unavailable",
        "chroma": "unavailable",
    }

    try:
        client = request.app.state.mongo_client
        client.admin.command("ping")
        get_database(client).command("ping")
        checks["mongodb"] = "connected"
    except PyMongoError:
        pass

    try:
        chroma_client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
        chroma_client.heartbeat()
        checks["chroma"] = "connected"
    except Exception:
        pass

    ready = all(value == "connected" for value in checks.values())

    result = {
        "status": "ready" if ready else "not_ready",
        "checks": checks,
    }

    return JSONResponse(
        status_code=200 if ready else 503,
        content=result,
    )