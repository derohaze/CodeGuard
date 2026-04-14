import asyncio
import logging

from pymongo import AsyncMongoClient

from app.core.config import get_settings


_mongo_client: AsyncMongoClient | None = None
_mongo_database = None
_mongo_lock = asyncio.Lock()
_mongo_uri_in_use: str | None = None
logger = logging.getLogger(__name__)
LEGACY_DATABASE_NAMES = ("CodeGuard",)


def _build_client(uri: str | None = None) -> AsyncMongoClient:
    settings = get_settings()
    return AsyncMongoClient(
        uri or settings.mongodb_uri,
        maxPoolSize=settings.mongodb_max_pool_size,
        minPoolSize=settings.mongodb_min_pool_size,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
        uuidRepresentation="standard",
    )


def _candidate_uris() -> list[str]:
    settings = get_settings()
    uris: list[str] = [settings.mongodb_uri]
    fallback_uri = settings.mongodb_fallback_uri
    if fallback_uri and fallback_uri not in uris:
        uris.append(fallback_uri)
    return uris


async def initialize_mongo():
    global _mongo_client, _mongo_database, _mongo_uri_in_use
    if _mongo_database is not None:
        return _mongo_database

    async with _mongo_lock:
        if _mongo_database is not None:
            return _mongo_database
        settings = get_settings()
        errors: list[tuple[str, Exception]] = []
        for uri in _candidate_uris():
            client = _build_client(uri)
            database = client[settings.mongodb_database]
            try:
                await database.command("ping")
                _mongo_client = client
                _mongo_database = database
                _mongo_uri_in_use = uri
                return _mongo_database
            except Exception as exc:
                errors.append((uri, exc))
                await client.close()

        failure_details = "; ".join(f"{uri}: {type(exc).__name__}" for uri, exc in errors)
        logger.error("Failed to initialize MongoDB for all configured URIs: %s", failure_details)
        raise RuntimeError("Failed to initialize MongoDB connection.") from errors[-1][1]


def get_database(database_name: str | None = None):
    global _mongo_client, _mongo_database, _mongo_uri_in_use
    settings = get_settings()
    if _mongo_database is None:
        last_error: Exception | None = None
        for uri in _candidate_uris():
            try:
                _mongo_client = _build_client(uri)
                _mongo_database = _mongo_client[settings.mongodb_database]
                _mongo_uri_in_use = uri
                break
            except Exception as exc:
                last_error = exc
        if _mongo_database is None and last_error is not None:
            raise RuntimeError("MongoDB client is not available for the configured URIs.") from last_error
    if database_name and database_name != settings.mongodb_database:
        return _mongo_client[database_name]
    return _mongo_database


def get_legacy_database_names() -> list[str]:
    current_name = get_settings().mongodb_database
    return [name for name in LEGACY_DATABASE_NAMES if name and name != current_name]


def get_legacy_databases() -> list:
    return [get_database(database_name) for database_name in get_legacy_database_names()]


async def ping_mongo() -> bool:
    try:
        database = await initialize_mongo()
        await database.command("ping")
        return True
    except Exception:
        return False


async def close_mongo() -> None:
    global _mongo_client, _mongo_database, _mongo_uri_in_use
    if _mongo_client is not None:
        await _mongo_client.close()
    _mongo_client = None
    _mongo_database = None
    _mongo_uri_in_use = None
