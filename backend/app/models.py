"""SQLAlchemy ORM models — mirror the schema in db/init.sql."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, LargeBinary, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    slug: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str]
    description: Mapped[str]
    is_celestial: Mapped[bool]
    sort_order: Mapped[int]


class Classification(Base):
    __tablename__ = "classifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_name: Mapped[str]
    mime_type: Mapped[str]
    image_size: Mapped[int]
    # Deferred: list/stat queries never load the (large) image bytes.
    image_data: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    category: Mapped[str] = mapped_column(ForeignKey("categories.slug"))
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    object_name: Mapped[str | None]
    description: Mapped[str | None]
    visual_features: Mapped[list[str]] = mapped_column(JSONB, default=list)
    fun_fact: Mapped[str | None]
    model_used: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    category_ref: Mapped[Category] = relationship(lazy="joined")
