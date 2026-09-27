"""Tests router — diagnostic test listing with Redis caching."""

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.services.test_service import TestService
from app.schemas.diagnostic_test import (
    TestListResponse,
    DiagnosticTestDetailResponse,
)
from app.cache.centre_cache import (
    get_cached,
    set_cached,
    tests_list_key,
    test_detail_key,
)
from app.utils.pagination import MAX_PAGE_SIZE

router = APIRouter(prefix="/api/v1/tests", tags=["Diagnostic Tests"])


@router.get(
    "",
    response_model=TestListResponse,
    summary="List diagnostic tests",
    description="Returns a paginated list of diagnostic tests. Optionally filter by centre_id.",
)
def list_tests(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    centre_id: Optional[uuid.UUID] = Query(default=None, description="Filter by centre"),
    db: Session = Depends(get_db),
):
    cache_key = tests_list_key(page, page_size, str(centre_id) if centre_id else None)
    cached = get_cached(cache_key)
    if cached:
        return json.loads(cached)

    service = TestService(db)
    result = service.list_tests(page=page, page_size=page_size, centre_id=centre_id)

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
    "/{test_id}",
    response_model=DiagnosticTestDetailResponse,
    summary="Get test details with offering centres",
    description="Returns test info including all centres that offer it and their prices.",
)
def get_test(test_id: uuid.UUID, db: Session = Depends(get_db)):
    cache_key = test_detail_key(str(test_id))
    cached = get_cached(cache_key)
    if cached:
        return json.loads(cached)

    service = TestService(db)
    result = service.get_test(test_id)
    cache_data = result.model_dump(mode="json")
    set_cached(cache_key, json.dumps(cache_data))
    return cache_data
