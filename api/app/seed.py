"""Idempotentno punjenje setova i malih kontroliranih rječnika."""
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import Attribute, CardSet, Color, Keyword


def initial_sets() -> list[tuple[str, str]]:
    return (
        [(f"OP{i:02d}", f"OP{i:02d}") for i in range(1, 19)]
        + [(f"EB{i:02d}", f"EB{i:02d}") for i in range(1, 6)]
        + [(f"ST{i:02d}", f"ST{i:02d}") for i in range(1, 37)]
        + [(f"PRB{i:02d}", f"PRB{i:02d}") for i in range(1, 3)]
        + [("P", "Promotional Cards"), ("OSTALO", "Ostalo")]
        + [("DON", "DON!! Cards")]
    )

COLORS = ("Red", "Yellow", "Green", "Blue", "Purple", "Black")
ATTRIBUTES = ("Slash", "Strike", "Special", "Ranged", "Wisdom", "?")
KEYWORDS = (
    "Blocker", "Rush", "Rush: Character", "Double Attack", "Banish",
    "Trigger", "Unblockable", "On Play", "When Attacking", "On K.O.",
    "On Block", "On Your Opponent's Attack", "Activate: Main", "Main",
    "Counter", "Once Per Turn", "Your Turn", "Opponent's Turn",
    "End of Your Turn", "End of Your Opponent's Turn", "DON!! xN",
    "DON!! -N", "K.O.", "Trash",
)


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        existing_sets = set((await session.scalars(select(CardSet.code))).all())
        for order, (code, name) in enumerate(initial_sets(), start=1):
            if code not in existing_sets:
                session.add(CardSet(code=code, name=name, sort_order=order))

        for model, values in (
            (Color, COLORS), (Attribute, ATTRIBUTES), (Keyword, KEYWORDS)
        ):
            existing = set((await session.scalars(select(model.name))).all())
            for name in values:
                if name not in existing:
                    session.add(model(name=name))

        # Archetypes se ne pune rucno: citat cemo ih iz kataloga pri importu.
        # DON!! izdanja takoder ne dodajemo bez potvrdenih ID-jeva.
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
