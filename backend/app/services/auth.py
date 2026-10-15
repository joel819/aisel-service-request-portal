from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.security import hash_password, verify_password

# Verified against when the email is unknown so both failure paths take similar time.
_DUMMY_HASH = hash_password("not-a-real-password")


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    hashed = user.hashed_password if user else _DUMMY_HASH
    password_ok = verify_password(password, hashed)
    if user is None or not password_ok or not user.is_active:
        return None
    return user
