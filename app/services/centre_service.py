"""Centre service — business logic for diagnostic centres."""

import uuid
from sqlalchemy.orm import Session

from app.repositories.centre_repository import CentreRepository
from app.utils.exceptions import NotFoundError
from app.utils.pagination import paginate, build_paginated_response
from app.schemas.diagnostic_centre import (
    DiagnosticCentreResponse,
    DiagnosticCentreDetailResponse,
    CentreTestItem,
)


class CentreService:
    def __init__(self, db: Session):
        self.repo = CentreRepository(db)
        self.db = db

    def list_centres(self, page: int, page_size: int) -> dict:
        query = self.repo.get_all_query()
        items, total = paginate(self.db, query, page, page_size)
        serialized = [DiagnosticCentreResponse.model_validate(c) for c in items]
        return build_paginated_response(serialized, page, page_size, total)

    def get_centre(self, centre_id: uuid.UUID) -> DiagnosticCentreDetailResponse:
        centre = self.repo.get_by_id_with_tests(centre_id)
        if not centre:
            raise NotFoundError(detail="Diagnostic centre not found")

        tests = [
            CentreTestItem(id=ct.test.id, name=ct.test.name, price=ct.price)
            for ct in centre.centre_tests
        ]
        return DiagnosticCentreDetailResponse(
            id=centre.id,
            name=centre.name,
            location=centre.location,
            tests=tests,
            created_at=centre.created_at,
            updated_at=centre.updated_at,
        )

    def get_centre_tests(self, centre_id: uuid.UUID) -> list[CentreTestItem]:
        """Get tests offered by a specific centre."""
        centre = self.repo.get_by_id(centre_id)
        if not centre:
            raise NotFoundError(detail="Diagnostic centre not found")

        centre_tests = self.repo.get_centre_tests(centre_id)
        return [
            CentreTestItem(id=ct.test.id, name=ct.test.name, price=ct.price)
            for ct in centre_tests
        ]
