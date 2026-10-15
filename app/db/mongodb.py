from pymongo import MongoClient
from pymongo.database import Database
from app.core.config import settings


def create_mongo_client() -> MongoClient:
    return MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=3000,
        connectTimeoutMS=3000,
    )


def get_database(client: MongoClient) -> Database:
    return client[settings.mongodb_database]
