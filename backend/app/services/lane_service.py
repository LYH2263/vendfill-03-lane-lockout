"""Lane maintenance blocking (检修封锁).

The lane flag, the location's current (latest) refill order and the full-lane
list share one blocking rule and one transaction: flipping the flag recomputes
the latest order's lines in the same commit; any failure rolls both back.
Earlier orders are historical text and are never rewritten.
"""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Lane, RefillOrder
from app.services.fill_engine import build_fill_lines, summarize


class LaneNotFoundError(Exception):
    """Raised when the target lane does not exist."""


def lane_payload(lane: Lane) -> dict:
    return {"id": lane.id, "slot_no": lane.slot_no, "sku_name": lane.sku_name,
            "capacity": lane.capacity, "stock": lane.stock, "in_transit": lane.in_transit,
            "blocked": lane.blocked}


def latest_order(db: Session, location_id: int) -> RefillOrder | None:
    return db.scalars(select(RefillOrder).where(RefillOrder.location_id == location_id)
                      .order_by(RefillOrder.id.desc())).first()


def set_lane_blocked(db: Session, lane_id: int, blocked: bool) -> Lane:
    """Set the lane's block flag and, if the location already has a current
    refill order, recompute that order's lines under the block rule (blocked
    lane fills 0). Flag and order commit together; on failure both roll back
    to their previous state."""
    lane = db.get(Lane, lane_id)
    if lane is None:
        raise LaneNotFoundError(lane_id)
    try:
        lane.blocked = blocked
        order = latest_order(db, lane.location_id)
        if order is not None:
            lanes = db.scalars(select(Lane).where(Lane.location_id == lane.location_id)
                               .order_by(Lane.slot_no)).all()
            summary = summarize(build_fill_lines([lane_payload(l) for l in lanes]))
            order.lines_json = json.dumps(summary, ensure_ascii=False)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(lane)
    return lane
