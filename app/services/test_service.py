"""Test service — business logic for diagnostic tests."""

import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.repositories.test_repository import TestRepository
from app.utils.exceptions import NotFoundError
from app.utils.pagination import paginate, build_paginated_response
from app.schemas.diagnostic_test import (
    DiagnosticTestResponse,
    DiagnosticTestDetailResponse,
    CentreForTest,
)


class TestService:
    __test__ = False

    def __init__(self, db: Session):
        self.repo = TestRepository(db)
        self.db = db

    def list_tests(self, page: int, page_size: int, centre_id: Optional[uuid.UUID] = None) -> dict:
        query = self.repo.get_all_query(centre_id=centre_id)
        items, total = paginate(self.db, query, page, page_size)
        serialized = [DiagnosticTestResponse.model_validate(t) for t in items]
        return build_paginated_response(serialized, page, page_size, total)

    def get_test(self, test_id: uuid.UUID) -> DiagnosticTestDetailResponse:
        test = self.repo.get_by_id_with_centres(test_id)
        if not test:
            raise NotFoundError(detail="Diagnostic test not found")

        centres = [
            CentreForTest(
                centre_id=ct.centre.id,
                centre_name=ct.centre.name,
                price=ct.price,
            )
            for ct in test.centre_tests
        ]
        return DiagnosticTestDetailResponse(
            id=test.id,
            name=test.name,
            description=test.description,
            centres=centres,
            created_at=test.created_at,
            updated_at=test.updated_at,
        )
