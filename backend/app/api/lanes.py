from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Lane
from app.services.fill_engine import compute_gap
from app.services.lane_service import LaneNotFoundError, set_lane_blocked
router = APIRouter(prefix="/lanes", tags=["lanes"])

def lane_dict(r: Lane) -> dict:
    gap = compute_gap(r.capacity, r.stock, r.in_transit)
    return {"id": r.id, "location_id": r.location_id, "slot_no": r.slot_no, "sku_name": r.sku_name,
            "capacity": r.capacity, "stock": r.stock, "in_transit": r.in_transit, "gap": gap,
            "blocked": r.blocked,
            "fill_pct": round(r.stock / r.capacity * 100, 1) if r.capacity else 0}

@router.get("")
def list_lanes(location_id: int | None = None, db: Session = Depends(get_db)):
    q = select(Lane).order_by(Lane.slot_no)
    if location_id is not None: q = q.where(Lane.location_id == location_id)
    return [lane_dict(r) for r in db.scalars(q).all()]

class LaneBlockIn(BaseModel):
    blocked: bool

@router.patch("/{lane_id}/blocked")
def update_lane_blocked(lane_id: int, body: LaneBlockIn, db: Session = Depends(get_db)):
    """打开/关闭货道封锁并保存：旗标与该点位当前有效补货单在同一事务内更新，
    任一失败则两者一起回滚。"""
    try:
        lane = set_lane_blocked(db, lane_id, body.blocked)
    except LaneNotFoundError:
        raise HTTPException(404, "货道不存在")
    except Exception:
        raise HTTPException(500, "封锁保存失败，旗标与补货单已一并回滚")
    return lane_dict(lane)
