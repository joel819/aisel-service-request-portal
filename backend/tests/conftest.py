import os
from collections.abc import Iterator

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.database import Base, get_db
from app.main import app
from app.models import Role, User
from app.security import create_access_token, hash_password
from app.services.rate_limit import assistant_limiter, login_limiter

TEST_EMAIL = "tester@example.com"
TEST_PASSWORD = "test-password-123"


def _create_database_if_missing(url: str) -> None:
    parsed = make_url(url)
    admin = create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": parsed.database}
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{parsed.database}"'))
    admin.dispose()


def _reset_schema_and_migrate(engine: Engine, url: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = os.environ["TEST_DATABASE_URL"]
    if not (make_url(url).database or "").endswith("_test"):
        pytest.exit("TEST_DATABASE_URL must point at a database whose name ends in _test", returncode=2)
    _create_database_if_missing(url)
    test_engine = create_engine(url)
    _reset_schema_and_migrate(test_engine, url)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture(autouse=True)
def reset_limiters() -> None:
    login_limiter.reset()
    assistant_limiter.reset()


@pytest.fixture
def user(db: Session) -> User:
    """The seeded test user; an admin, like the real seed user."""
    seeded = User(
        email=TEST_EMAIL,
        hashed_password=hash_password(TEST_PASSWORD),
        full_name="Test",
        role=Role.admin,
    )
    db.add(seeded)
    db.commit()
    return seeded


@pytest.fixture
def member(db: Session) -> User:
    other = User(
        email="member@example.com", hashed_password=hash_password(TEST_PASSWORD), role=Role.user
    )
    db.add(other)
    db.commit()
    return other


@pytest.fixture
def member_headers(member: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(member.id)}"}


@pytest.fixture
def client(db: Session, user: User) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}
