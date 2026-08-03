from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def build_session_factory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=build_engine(database_url), expire_on_commit=False)


def create_schema(database_url: str) -> None:
    from calculus_agent import models  # noqa: F401

    Base.metadata.create_all(build_engine(database_url))


@contextmanager
def session_scope(database_url: str) -> Iterator[Session]:
    factory = build_session_factory(database_url)
    with factory.begin() as session:
        yield session
