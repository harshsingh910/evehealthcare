"""Centre repository — data access for diagnostic centres."""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.diagnostic_centre import DiagnosticCentre
from app.models.centre_test import CentreTest


class CentreRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> list[DiagnosticCentre]:
        return self.db.query(DiagnosticCentre).all()

    def get_all_query(self):
        """Return a select query for pagination."""
        return select(DiagnosticCentre).order_by(DiagnosticCentre.name)

    def get_by_id(self, centre_id: uuid.UUID) -> Optional[DiagnosticCentre]:
        return self.db.query(DiagnosticCentre).filter(
            DiagnosticCentre.id == centre_id
        ).first()

    def get_by_id_with_tests(self, centre_id: uuid.UUID) -> Optional[DiagnosticCentre]:
        """Eager-load centre_tests and test details for the centre detail endpoint."""
        return (
            self.db.query(DiagnosticCentre)
            .options(joinedload(DiagnosticCentre.centre_tests).joinedload(CentreTest.test))
            .filter(DiagnosticCentre.id == centre_id)
            .first()
        )

    def get_centre_tests(self, centre_id: uuid.UUID) -> list[CentreTest]:
        """Get all test offerings for a specific centre."""
        return (
            self.db.query(CentreTest)
            .options(joinedload(CentreTest.test))
            .filter(CentreTest.centre_id == centre_id)
            .all()
        )
