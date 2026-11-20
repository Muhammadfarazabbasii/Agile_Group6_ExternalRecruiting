"""Fills fixed data. Seniority levels are a fixed list: JUNIOR, SENIOR, EXPERT."""
from sqlalchemy import select

from .database import SessionLocal
from .models import SeniorityLevel

LEVELS = [("JUNIOR", "Junior", 1), ("SENIOR", "Senior", 2), ("EXPERT", "Expert", 3)]


def seed() -> None:
    with SessionLocal() as db:
        for code, label, order in LEVELS:
            if db.scalar(select(SeniorityLevel).where(SeniorityLevel.code == code)) is None:
                db.add(SeniorityLevel(code=code, label=label, sort_order=order))
        db.commit()
