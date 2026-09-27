"""
Centres router — diagnostic centre listing with Redis caching.

Cached responses are served from Redis (fast path).
On cache miss, data is fetched from PostgreSQL and cached for TTL seconds.
If Redis is unavailable, PostgreSQL is queried directly.
"""

import json
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.services.centre_service import CentreService
from app.schemas.diagnostic_centre import (
    CentreListResponse,
    DiagnosticCentreDetailResponse,
    CentreTestItem,
)
from app.cache.centre_cache import (
    get_cached,
    set_cached,
    centres_list_key,
    centre_detail_key,
    centre_tests_key,
)
from app.utils.pagination import MAX_PAGE_SIZE

router = APIRouter(prefix="/api/v1/centres", tags=["Diagnostic Centres"])


@router.get(
    "",
    response_model=CentreListResponse,
    summary="List diagnostic centres",
    description="Returns a paginated list of diagnostic centres. Cached in Redis.",
)
def list_centres(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
):
    # Check cache
    cache_key = centres_list_key(page, page_size)
    cached = get_cached(cache_key)
    if cached:
        return json.loads(cached)

    # Cache miss — query DB
    service = CentreService(db)
    result = service.list_centres(page=page, page_size=page_size)

    # Serialize for cache (Pydantic models → dicts → JSON)
    cache_data = {
        "items": [item.model_dump(mode="json") for item in result["items"]],
        "page": result["page"],
        "page_size": result["page_size"],
        "total": result["total"],
        "total_pages": result["total_pages"],
    }
    set_cached(cache_key, json.dumps(cache_data))
    return cache_data


@router.get(
    "/{centre_id}",
    response_model=DiagnosticCentreDetailResponse,
    summary="Get centre details with available tests",
    description="Returns centre info including all offered tests and their prices.",
)
def get_centre(centre_id: uuid.UUID, db: Session = Depends(get_db)):
    cache_key = centre_detail_key(str(centre_id))
    cached = get_cached(cache_key)
    if cached:
        return json.loads(cached)

    service = CentreService(db)
    result = service.get_centre(centre_id)
    cache_data = result.model_dump(mode="json")
    set_cached(cache_key, json.dumps(cache_data))
    return cache_data


@router.get(
    "/{centre_id}/tests",
    response_model=list[CentreTestItem],
    summary="List tests offered by a centre",
    description="Returns all diagnostic tests available at this centre with prices.",
)
def get_centre_tests(centre_id: uuid.UUID, db: Session = Depends(get_db)):
    cache_key = centre_tests_key(str(centre_id))
    cached = get_cached(cache_key)
    if cached:
        return json.loads(cached)

    service = CentreService(db)
    result = service.get_centre_tests(centre_id)
    cache_data = [item.model_dump(mode="json") for item in result]
    set_cached(cache_key, json.dumps(cache_data))
    return cache_data
