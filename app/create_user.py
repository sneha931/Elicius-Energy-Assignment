import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.database import AsyncSessionLocal
from app.db.models import User


async def create_user():
    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(User).where(
                User.username == "admin"
            )
        )

        existing_user = result.scalar_one_or_none()

        if existing_user:
            print("User already exists")
            return

        user = User(
            username="admin",
            password_hash=hash_password("admin123"),
            role="admin",
        )

        db.add(user)

        await db.commit()

        print("Admin user created")


if __name__ == "__main__":
    asyncio.run(create_user())