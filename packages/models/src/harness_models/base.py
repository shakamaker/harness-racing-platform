"""SQLAlchemy 2.x declarative base for harness racing ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, mapped_column

# Conventional naming improves Alembic autogenerate diffs and makes migration
# scripts deterministic across environments.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Project-wide declarative base. All ORM models inherit from this."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Reusable typed column aliases keep the model files terse and consistent.
created_at_col = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now()),
]
updated_at_col = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    ),
]
