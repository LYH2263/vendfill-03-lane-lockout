import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Lane
from app.services.fill_engine import compute_gap
from app.services.refill_service import compute_summary, latest_order

router = APIRouter(prefix="/lanes", tags=["lanes"])


def _lane_out(r: Lane) -> dict:
    return {
        "id": r.id, "location_id": r.location_id, "slot_no": r.slot_no, "sku_name": r.sku_name,
        "capacity": r.capacity, "stock": r.stock, "in_transit": r.in_transit,
        "gap": compute_gap(r.capacity, r.stock, r.in_transit),
        "blocked": r.blocked,
        "fill_pct": round(r.stock / r.capacity * 100, 1) if r.capacity else 0,
    }


@router.get("")
def list_lanes(location_id: int | None = None, db: Session = Depends(get_db)):
    q = select(Lane).order_by(Lane.slot_no)
    if location_id is not None:
        q = q.where(Lane.location_id == location_id)
    return [_lane_out(r) for r in db.scalars(q).all()]


class LaneBlockUpdate(BaseModel):
    blocked: bool


@router.put("/{lane_id}")
def set_lane_blocked(lane_id: int, body: LaneBlockUpdate, db: Session = Depends(get_db)):
    """Toggle the maintenance block on a lane.

    One commit covers the flag AND the location's current effective refill
    order (rebuilt in place under the block rules, so the blocked line's fill
    becomes 0). If anything fails, both roll back: flag, effective order and
    the full-lane list never diverge. Older orders are left untouched.
    """
    lane = db.get(Lane, lane_id)
    if not lane:
        raise HTTPException(404, "货道不存在")
    lane.blocked = body.blocked
    order = latest_order(db, lane.location_id)
    summary = None
    try:
        if order is not None:
            summary = compute_summary(db, lane.location_id)
            order.lines_json = json.dumps(summary, ensure_ascii=False)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(500, "保存封锁失败，货道旗标与当前补货单已一并回滚")
    db.refresh(lane)
    out = _lane_out(lane)
    out["order"] = {"id": order.id, "location_id": lane.location_id, **summary} if order else None
    return out
