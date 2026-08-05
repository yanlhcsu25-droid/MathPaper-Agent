from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


@lru_cache
def build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


@lru_cache
def build_session_factory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=build_engine(database_url), expire_on_commit=False)


@lru_cache
def create_schema(database_url: str) -> None:
    from calculus_agent import models  # noqa: F401

    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    columns = {item["name"] for item in inspect(engine).get_columns("paper")}
    with engine.begin() as connection:
        if "root_paper_id" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE paper ADD COLUMN root_paper_id VARCHAR(36) REFERENCES paper(id)"
            )
        if "parent_version_id" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE paper ADD COLUMN parent_version_id VARCHAR(36) REFERENCES paper(id)"
            )


@contextmanager
def session_scope(database_url: str) -> Iterator[Session]:
    factory = build_session_factory(database_url)
    with factory.begin() as session:
        yield session
