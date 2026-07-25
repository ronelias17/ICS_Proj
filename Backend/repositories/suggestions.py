from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase


class SuggestionsRepository:
    """Mongo access for suggested questions."""

    def __init__(self, database: AsyncIOMotorDatabase, collection_name: str):
        self.collection = database[collection_name]

    async def list_active(self) -> list[dict]:
        """Return active suggestion questions."""
        cursor = self.collection.find({"active": {"$ne": False}}, {"_id": 0}).sort("order", 1)
        rows = await cursor.to_list(length=50)
        return [
            {
                "id": str(row.get("id") or ""),
                "question": str(row.get("question") or ""),
            }
            for row in rows
            if row.get("question")
        ]
