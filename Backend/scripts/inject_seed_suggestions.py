from __future__ import annotations

import sys
from pathlib import Path

from pymongo import MongoClient, UpdateOne

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.settings import AppSettings


SEED_SUGGESTIONS = [
    ("suggestion_01", "איזה התמחויות לומדים אצלכם במדעי המחשב"),
    ("suggestion_02", "כמה זמן לומדים מדעי המחשב וכמה נקודות זכות יש בתואר"),
    ("suggestion_03", "כמה זמן נמשך תואר במדעי האחיות"),
    ("suggestion_04", "מה הטלפון של מרכז ייעוץ והרשמה"),
    ("suggestion_05", "איפה נמצאת החניה"),
    ("suggestion_06", "האם דמי הרשמה מוחזרים במקרה של ביטול הרשמה"),
    ("suggestion_07", "איך יוצרים קשר עם מחלקת שכר לימוד"),
    ("suggestion_08", "האם יש הנחה על תשלום יתרת שכר לימוד בתשלום אחד"),
    ("suggestion_09", "איפה נמצאים המעונות"),
    ("suggestion_10", "איזה פקולטות יש אצלכם ברופין"),
    ("suggestion_11", "מה סכום המקדמה לתואר שני בפסיכולוגיה קלינית"),
    ("suggestion_12", "איפה מתקיימים לימודי מדעי הים"),
    ("suggestion_13", "האם אפשר לשלם שכר לימוד במזומן"),
    ("suggestion_14", "מה תנאי הקבלה לתואר ראשון בהנדסת מחשבים"),
    ("suggestion_15", "האם יש מסלול מכינה להנדסה ומדעים"),
]


def main() -> int:
    """Inject default suggestion questions into Mongo."""
    settings = AppSettings.from_env()
    client = MongoClient(settings.mongo_uri)
    collection = client[settings.mongo_db][settings.suggestions_collection]
    operations = [
        UpdateOne(
            {"id": suggestion_id},
            {
                "$set": {
                    "id": suggestion_id,
                    "question": question,
                    "active": True,
                    "order": index,
                }
            },
            upsert=True,
        )
        for index, (suggestion_id, question) in enumerate(SEED_SUGGESTIONS, start=1)
    ]
    result = collection.bulk_write(operations, ordered=True)
    print(
        "Seeded suggestions: "
        f"matched={result.matched_count}, modified={result.modified_count}, upserted={len(result.upserted_ids)}"
    )
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
