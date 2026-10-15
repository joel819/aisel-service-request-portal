"""Create the first user from SEED_USER_EMAIL / SEED_USER_PASSWORD. Idempotent."""
import os
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Role, User
from app.security import hash_password


def main() -> int:
    email = os.environ.get("SEED_USER_EMAIL", "").strip().lower()
    password = os.environ.get("SEED_USER_PASSWORD", "")
    if not email or not password:
        print("SEED_USER_EMAIL and SEED_USER_PASSWORD must be set", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None and existing.role == Role.admin:
            print("Seed user already exists; nothing to do")
            return 0
        if existing is not None:
            existing.role = Role.admin
            db.commit()
            print("Seed user promoted to admin")
            return 0
        db.add(
            User(
                email=email,
                hashed_password=hash_password(password),
                full_name="Seed User",
                role=Role.admin,
            )
        )
        db.commit()
    print("Seed user created")
    return 0


if __name__ == "__main__":
    sys.exit(main())
