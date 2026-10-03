"""Shared refill-order helpers: one rule set for lanes / refills / full / summary.

A location's current effective refill order is its latest RefillOrder row.
Block-flag saves and refill runs both rebuild summaries through compute_summary
so the block rule (blocked -> fill 0, never full) is applied identically
everywhere.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Lane, RefillOrder
from app.services.fill_engine import build_fill_lines, summarize


def lane_payloads(db: Session, location_id: int) -> list[dict]:
    lanes = db.scalars(
        select(Lane).where(Lane.location_id == location_id).order_by(Lane.slot_no)
    ).all()
    return [
        {
            "id": l.id,
            "slot_no": l.slot_no,
            "sku_name": l.sku_name,
            "capacity": l.capacity,
            "stock": l.stock,
            "in_transit": l.in_transit,
            "blocked": l.blocked,
        }
        for l in lanes
    ]


def compute_summary(db: Session, location_id: int) -> dict:
    return summarize(build_fill_lines(lane_payloads(db, location_id)))


def latest_order(db: Session, location_id: int) -> RefillOrder | None:
    return db.scalars(
        select(RefillOrder)
        .where(RefillOrder.location_id == location_id)
        .order_by(RefillOrder.id.desc())
    ).first()
