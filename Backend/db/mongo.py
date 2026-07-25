from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from core.settings import AppSettings


class MongoClientProvider:
    """Own the backend Mongo client lifecycle."""

    def __init__(self, settings: AppSettings):
        self.client = AsyncIOMotorClient(settings.mongo_uri)
        self.database: AsyncIOMotorDatabase = self.client[settings.mongo_db]

    async def ping(self) -> None:
        """Verify Mongo connectivity."""
        await self.database.command("ping")

    def close(self) -> None:
        """Close the Mongo client."""
        self.client.close()
