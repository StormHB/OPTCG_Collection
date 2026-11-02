"""Ponovljivo stvaranje popisa setova. Bez demo lozinki i korisničkih količina."""

import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import CardSet


def initial_sets() -> list[tuple[str, str]]:
    return (
        [(f"OP{i:02d}", f"OP{i:02d}") for i in range(1, 19)]
        + [(f"EB{i:02d}", f"EB{i:02d}") for i in range(1, 6)]
        + [(f"ST{i:02d}", f"ST{i:02d}") for i in range(1, 37)]
        + [(f"PRB{i:02d}", f"PRB{i:02d}") for i in range(1, 3)]
        + [("P", "Promotional Cards"), ("OSTALO", "Ostalo")]
    )


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        existing = set(
            (await session.scalars(select(CardSet.code))).all()
        )
        for order, (code, name) in enumerate(initial_sets(), start=1):
            if code not in existing:
                session.add(CardSet(code=code, name=name, sort_order=order))
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
