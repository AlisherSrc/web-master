"""Celestial Classifier — FastAPI application.

Endpoints
---------
GET    /api/health                       liveness + DB + classifier info
GET    /api/categories                   READ  categories table
POST   /api/classify                     WRITE new classification (image -> AI -> DB)
GET    /api/classifications              READ  paginated, filterable history
GET    /api/classifications/{id}         READ  single classification
GET    /api/classifications/{id}/image   READ  stored image bytes
DELETE /api/classifications/{id}         WRITE delete a classification
GET    /api/stats                        READ  aggregate statistics
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .classifier import ClassifierError, build_classifier
from .config import settings
from .db import engine, get_session, ping_db, wait_for_db
from .models import Category, Classification
from .schemas import (
    CategoryOut,
    CategoryStat,
    ClassificationOut,
    ClassificationPage,
    HealthOut,
    StatsOut,
)

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("celestial")

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    wait_for_db()
    app.state.classifier = build_classifier(settings)
    log.info(
        "%s ready — classifier=%s model=%s",
        settings.app_name,
        app.state.classifier.mode,
        app.state.classifier.model_name,
    )
    yield
    engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="Upload a space image and let Gemini tell you what celestial object it is.",
    version="1.0.0",
    lifespan=lifespan,
)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def sniff_image_type(data: bytes) -> str | None:
    """Detect the real image type from magic bytes (don't trust the client)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def to_out(c: Classification) -> ClassificationOut:
    return ClassificationOut(
        id=c.id,
        original_name=c.original_name,
        mime_type=c.mime_type,
        image_size=c.image_size,
        image_url=f"/api/classifications/{c.id}/image",
        category=c.category,
        category_label=c.category_ref.label,
        is_celestial=c.category_ref.is_celestial,
        confidence=float(c.confidence),
        object_name=c.object_name,
        description=c.description,
        visual_features=list(c.visual_features or []),
        fun_fact=c.fun_fact,
        model_used=c.model_used,
        created_at=c.created_at,
    )


def get_or_404(db: Session, classification_id: int) -> Classification:
    record = db.get(Classification, classification_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Classification not found")
    return record


# -----------------------------------------------------------------------------
# API
# -----------------------------------------------------------------------------
@app.get("/api/health", response_model=HealthOut, tags=["system"])
def health(request: Request, response: Response) -> HealthOut:
    db_ok = ping_db()
    if not db_ok:
        response.status_code = 503
    clf = request.app.state.classifier
    return HealthOut(
        status="ok" if db_ok else "degraded",
        database="up" if db_ok else "down",
        classifier_mode=clf.mode,
        model=clf.model_name,
        max_upload_mb=settings.max_upload_mb,
    )


@app.get("/api/categories", response_model=list[CategoryOut], tags=["categories"])
def list_categories(db: Session = Depends(get_session)) -> list[CategoryOut]:
    rows = db.scalars(select(Category).order_by(Category.sort_order)).all()
    return [CategoryOut.model_validate(r, from_attributes=True) for r in rows]


@app.post("/api/classify", response_model=ClassificationOut, status_code=201, tags=["classifications"])
def classify(
    request: Request,
    file: UploadFile = File(..., description="JPEG, PNG or WEBP image"),
    db: Session = Depends(get_session),
) -> ClassificationOut:
    max_bytes = settings.max_upload_bytes
    data = file.file.read(max_bytes + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Image is too large (max {settings.max_upload_mb} MB).")

    mime_type = sniff_image_type(data)
    if mime_type is None:
        raise HTTPException(status_code=415, detail="Unsupported file type. Please upload a JPEG, PNG or WEBP image.")

    categories = db.scalars(select(Category).order_by(Category.sort_order)).all()
    if not categories:
        raise HTTPException(status_code=500, detail="No categories configured in the database.")

    try:
        result = request.app.state.classifier.classify(data, mime_type, categories)
    except ClassifierError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    record = Classification(
        original_name=(file.filename or "upload")[:255],
        mime_type=mime_type,
        image_size=len(data),
        image_data=data,
        **result,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    log.info("Saved classification #%d: %s (%.0f%%)", record.id, record.category, float(record.confidence) * 100)
    return to_out(record)


@app.get("/api/classifications", response_model=ClassificationPage, tags=["classifications"])
def list_classifications(
    category: str | None = Query(default=None, description="Filter by category slug"),
    limit: int = Query(default=12, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_session),
) -> ClassificationPage:
    query = select(Classification)
    count_query = select(func.count(Classification.id))
    if category:
        query = query.where(Classification.category == category)
        count_query = count_query.where(Classification.category == category)

    total = db.scalar(count_query) or 0
    rows = db.scalars(
        query.order_by(Classification.created_at.desc(), Classification.id.desc()).limit(limit).offset(offset)
    ).all()
    return ClassificationPage(items=[to_out(r) for r in rows], total=total, limit=limit, offset=offset)


@app.get("/api/classifications/{classification_id}", response_model=ClassificationOut, tags=["classifications"])
def get_classification(classification_id: int, db: Session = Depends(get_session)) -> ClassificationOut:
    return to_out(get_or_404(db, classification_id))


@app.get("/api/classifications/{classification_id}/image", tags=["classifications"])
def get_classification_image(classification_id: int, db: Session = Depends(get_session)) -> Response:
    record = get_or_404(db, classification_id)
    return Response(
        content=record.image_data,
        media_type=record.mime_type,
        headers={"Cache-Control": "public, max-age=86400, immutable"},
    )


@app.delete("/api/classifications/{classification_id}", status_code=204, tags=["classifications"])
def delete_classification(classification_id: int, db: Session = Depends(get_session)) -> Response:
    record = get_or_404(db, classification_id)
    db.delete(record)
    db.commit()
    log.info("Deleted classification #%d", classification_id)
    return Response(status_code=204)


@app.get("/api/stats", response_model=StatsOut, tags=["stats"])
def stats(db: Session = Depends(get_session)) -> StatsOut:
    rows = db.execute(
        select(
            Category.slug,
            Category.label,
            Category.is_celestial,
            func.count(Classification.id),
            func.avg(Classification.confidence),
        )
        .outerjoin(Classification, Classification.category == Category.slug)
        .group_by(Category.slug, Category.label, Category.is_celestial, Category.sort_order)
        .order_by(Category.sort_order)
    ).all()

    totals = db.execute(
        select(
            func.count(Classification.id),
            func.coalesce(func.sum(case((Category.is_celestial.is_(True), 1), else_=0)), 0),
            func.avg(Classification.confidence),
            func.max(Classification.created_at),
        ).join(Category, Classification.category == Category.slug)
    ).one()

    total, celestial, avg_conf, last_at = totals
    return StatsOut(
        total=total,
        celestial=int(celestial),
        not_celestial=total - int(celestial),
        avg_confidence=float(avg_conf) if avg_conf is not None else None,
        last_classified_at=last_at,
        by_category=[
            CategoryStat(
                slug=slug,
                label=label,
                is_celestial=is_cel,
                count=count,
                avg_confidence=float(avg) if avg is not None else None,
            )
            for slug, label, is_cel, count, avg in rows
        ],
    )


# -----------------------------------------------------------------------------
# Web UI
# -----------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
