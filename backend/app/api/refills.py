import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Location, RefillOrder
from app.services.refill_service import compute_summary, latest_order
router = APIRouter(prefix="/refills", tags=["refills"])

@router.post("/run")
def run_refill(location_id: int = 1, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if not loc: raise HTTPException(404, "点位不存在")
    summary = compute_summary(db, location_id)
    order = RefillOrder(location_id=location_id, created_at=datetime.utcnow(),
                        lines_json=json.dumps(summary, ensure_ascii=False))
    db.add(order); db.commit(); db.refresh(order)
    return {"id": order.id, "location_id": location_id, **summary}

@router.get("/latest")
def latest(location_id: int = 1, db: Session = Depends(get_db)):
    order = latest_order(db, location_id)
    if not order:
        return run_refill(location_id=location_id, db=db)
    data = json.loads(order.lines_json)
    return {"id": order.id, "location_id": location_id, **data}

@router.get("/full")
def full_lanes(location_id: int = 1, db: Session = Depends(get_db)):
    data = latest(location_id=location_id, db=db)
    # 封锁与满仓互斥：blocked 行状态永不为 full，此处天然被排除
    return {"location_id": location_id, "lanes": [l for l in data["lines"] if l["status"] == "full"]}

@router.get("/summary")
def refill_summary(location_id: int = 1, db: Session = Depends(get_db)):
    data = latest(location_id=location_id, db=db)
    return {
        "location_id": location_id,
        "total_fill": data["total_fill"],
        "need_fill_count": data["need_fill_count"],
        "full_count": data["full_count"],
        "overbooked_count": data["overbooked_count"],
        "blocked_count": data.get("blocked_count", 0),
    }
