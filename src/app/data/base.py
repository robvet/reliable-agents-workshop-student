"""SQLAlchemy declarative base shared by the data-generator's ORM models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
