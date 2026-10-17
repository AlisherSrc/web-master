"""Pydantic response schemas."""

from datetime import datetime

from pydantic import BaseModel


class CategoryOut(BaseModel):
    slug: str
    label: str
    description: str
    is_celestial: bool


class ClassificationOut(BaseModel):
    id: int
    original_name: str
    mime_type: str
    image_size: int
    image_url: str
    category: str
    category_label: str
    is_celestial: bool
    confidence: float
    object_name: str | None
    description: str | None
    visual_features: list[str]
    fun_fact: str | None
    model_used: str
    created_at: datetime


class ClassificationPage(BaseModel):
    items: list[ClassificationOut]
    total: int
    limit: int
    offset: int


class CategoryStat(BaseModel):
    slug: str
    label: str
    is_celestial: bool
    count: int
    avg_confidence: float | None


class StatsOut(BaseModel):
    total: int
    celestial: int
    not_celestial: int
    avg_confidence: float | None
    last_classified_at: datetime | None
    by_category: list[CategoryStat]


class HealthOut(BaseModel):
    status: str
    database: str
    classifier_mode: str
    model: str
    max_upload_mb: int
