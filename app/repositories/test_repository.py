"""Test repository — data access for diagnostic tests."""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.diagnostic_test import DiagnosticTest
from app.models.centre_test import CentreTest


class TestRepository:
    __test__ = False

    def __init__(self, db: Session):
        self.db = db

    def get_all_query(self, centre_id: Optional[uuid.UUID] = None):
        """Return a select query for pagination, optionally filtered by centre."""
        query = select(DiagnosticTest).order_by(DiagnosticTest.name)
        if centre_id:
            query = query.join(CentreTest).filter(CentreTest.centre_id == centre_id)
        return query

    def get_by_id(self, test_id: uuid.UUID) -> Optional[DiagnosticTest]:
        return self.db.query(DiagnosticTest).filter(
            DiagnosticTest.id == test_id
        ).first()

    def get_by_id_with_centres(self, test_id: uuid.UUID) -> Optional[DiagnosticTest]:
        """Eager-load centres offering this test."""
        return (
            self.db.query(DiagnosticTest)
            .options(joinedload(DiagnosticTest.centre_tests).joinedload(CentreTest.centre))
            .filter(DiagnosticTest.id == test_id)
            .first()
        )

    def get_centre_test(
        self, centre_id: uuid.UUID, test_id: uuid.UUID
    ) -> Optional[CentreTest]:
        """Find the price for a specific centre-test combination."""
        return (
            self.db.query(CentreTest)
            .filter(CentreTest.centre_id == centre_id, CentreTest.test_id == test_id)
            .first()
        )
