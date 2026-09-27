"""
Seed script — populates the database with realistic diagnostic centres and tests.

IDEMPOTENT: Safe to run multiple times. Uses get-or-create pattern
to prevent duplicate records.

Usage:
  python -m scripts.seed_data
"""

import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models import (
    DiagnosticCentre,
    DiagnosticTest,
    CentreTest,
    Booking,
    Payment,
    User,
)


# ---------- Seed Data ----------

CENTRES = [
    {"name": "Apollo Diagnostics", "location": "Delhi"},
    {"name": "Dr. Lal PathLabs", "location": "Mumbai"},
    {"name": "Thyrocare", "location": "Bangalore"},
    {"name": "SRL Diagnostics", "location": "Chennai"},
    {"name": "Metropolis Healthcare", "location": "Hyderabad"},
]

TESTS = [
    {"name": "Complete Blood Count (CBC)", "description": "Measures various components of blood including RBCs, WBCs, hemoglobin, and platelets."},
    {"name": "Blood Sugar (Fasting)", "description": "Measures blood glucose levels after an overnight fast."},
    {"name": "Thyroid Profile (T3, T4, TSH)", "description": "Evaluates thyroid gland function by measuring thyroid hormones."},
    {"name": "Lipid Profile", "description": "Measures cholesterol, triglycerides, HDL, LDL, and VLDL levels."},
    {"name": "Vitamin D (25-OH)", "description": "Measures Vitamin D levels in the blood."},
    {"name": "HbA1c (Glycated Hemoglobin)", "description": "Measures average blood sugar over the past 2-3 months."},
    {"name": "Liver Function Test (LFT)", "description": "Evaluates liver health by measuring enzymes, proteins, and bilirubin."},
    {"name": "Kidney Function Test (KFT)", "description": "Assesses kidney health by measuring creatinine, urea, and electrolytes."},
]

# Centre-specific pricing (same test, different prices at different centres)
# Format: (centre_index, test_index, price)
CENTRE_TEST_PRICES = [
    # Apollo Diagnostics
    (0, 0, "500.00"),  (0, 1, "150.00"),  (0, 2, "900.00"),
    (0, 3, "600.00"),  (0, 4, "1200.00"), (0, 5, "550.00"),
    (0, 6, "700.00"),  (0, 7, "650.00"),
    # Dr. Lal PathLabs
    (1, 0, "400.00"),  (1, 1, "120.00"),  (1, 2, "850.00"),
    (1, 3, "550.00"),  (1, 4, "1100.00"), (1, 5, "500.00"),
    (1, 6, "650.00"),  (1, 7, "600.00"),
    # Thyrocare
    (2, 0, "350.00"),  (2, 1, "100.00"),  (2, 2, "700.00"),
    (2, 3, "450.00"),  (2, 4, "999.00"),  (2, 5, "450.00"),
    # SRL Diagnostics
    (3, 0, "450.00"),  (3, 1, "130.00"),  (3, 2, "800.00"),
    (3, 3, "500.00"),  (3, 4, "1150.00"), (3, 5, "520.00"),
    (3, 6, "680.00"),
    # Metropolis Healthcare
    (4, 0, "480.00"),  (4, 1, "140.00"),  (4, 2, "950.00"),
    (4, 3, "580.00"),  (4, 4, "1250.00"), (4, 5, "560.00"),
    (4, 6, "720.00"),  (4, 7, "670.00"),
]


def seed(db: Session) -> None:
    """Run the seed operation idempotently."""
    print("🌱 Seeding database...")

    # Seed centres (get-or-create)
    centres = []
    for c_data in CENTRES:
        existing = db.query(DiagnosticCentre).filter_by(name=c_data["name"]).first()
        if existing:
            centres.append(existing)
            print(f"  ✓ Centre exists: {c_data['name']}")
        else:
            centre = DiagnosticCentre(**c_data)
            db.add(centre)
            db.flush()
            centres.append(centre)
            print(f"  + Created centre: {c_data['name']}")

    # Seed tests (get-or-create)
    tests = []
    for t_data in TESTS:
        existing = db.query(DiagnosticTest).filter_by(name=t_data["name"]).first()
        if existing:
            tests.append(existing)
            print(f"  ✓ Test exists: {t_data['name']}")
        else:
            test = DiagnosticTest(**t_data)
            db.add(test)
            db.flush()
            tests.append(test)
            print(f"  + Created test: {t_data['name']}")

    # Seed centre-test pricing (get-or-create)
    for c_idx, t_idx, price in CENTRE_TEST_PRICES:
        centre = centres[c_idx]
        test = tests[t_idx]
        existing = db.query(CentreTest).filter_by(
            centre_id=centre.id, test_id=test.id
        ).first()
        if existing:
            continue
        ct = CentreTest(
            centre_id=centre.id,
            test_id=test.id,
            price=Decimal(price),
        )
        db.add(ct)

    db.commit()
    print(f"\n✅ Seed complete: {len(centres)} centres, {len(tests)} tests, {len(CENTRE_TEST_PRICES)} price entries")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed(db)
    except Exception as e:
        print(f"❌ Seed failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()
