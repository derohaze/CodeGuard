import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.database import mongo as mongo_module


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        mongodb_uri="mongodb://primary-uri",
        mongodb_fallback_uri="mongodb://fallback-uri",
        mongodb_database="Khwarizm",
        mongodb_max_pool_size=30,
        mongodb_min_pool_size=5,
        mongodb_server_selection_timeout_ms=3000,
    )


def _make_client(command_mock: AsyncMock) -> MagicMock:
    database = MagicMock()
    database.command = command_mock
    client = MagicMock()
    client.__getitem__.return_value = database
    client.close = AsyncMock()
    return client


class MongoFallbackTests(unittest.TestCase):
    def tearDown(self) -> None:
        mongo_module._mongo_client = None
        mongo_module._mongo_database = None
        mongo_module._mongo_uri_in_use = None

    def test_initialize_mongo_falls_back_when_primary_fails(self):
        primary_client = _make_client(AsyncMock(side_effect=TimeoutError("dns timeout")))
        fallback_client = _make_client(AsyncMock(return_value={"ok": 1}))

        def build_client(uri: str | None = None):
            if uri == "mongodb://primary-uri":
                return primary_client
            if uri == "mongodb://fallback-uri":
                return fallback_client
            raise AssertionError(f"Unexpected URI {uri}")

        with patch("app.infrastructure.database.mongo.get_settings", return_value=_settings()), patch(
            "app.infrastructure.database.mongo._build_client",
            side_effect=build_client,
        ):
            database = asyncio.run(mongo_module.initialize_mongo())

        self.assertIs(database, fallback_client.__getitem__.return_value)
        primary_client.close.assert_awaited_once()
        fallback_client.close.assert_not_awaited()

    def test_get_database_uses_fallback_when_primary_client_creation_fails(self):
        fallback_client = _make_client(AsyncMock(return_value={"ok": 1}))

        def build_client(uri: str | None = None):
            if uri == "mongodb://primary-uri":
                raise ValueError("invalid primary uri")
            if uri == "mongodb://fallback-uri":
                return fallback_client
            raise AssertionError(f"Unexpected URI {uri}")

        with patch("app.infrastructure.database.mongo.get_settings", return_value=_settings()), patch(
            "app.infrastructure.database.mongo._build_client",
            side_effect=build_client,
        ):
            database = mongo_module.get_database()

        self.assertIs(database, fallback_client.__getitem__.return_value)


if __name__ == "__main__":
    unittest.main()
