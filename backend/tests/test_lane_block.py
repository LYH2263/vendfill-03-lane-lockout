"""API-level tests for lane maintenance blocking (货道检修封锁).

Uses an in-memory SQLite database via dependency override; the app lifespan
(which would touch Postgres) does not run under a plain TestClient.
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Lane, RefillOrder
from app.services.seed import seed_if_empty

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield


def lane_id_by_slot(slot: str) -> int:
    db = TestingSessionLocal()
    try:
        return next(l.id for l in db.query(Lane).all() if l.slot_no == slot)
    finally:
        db.close()


def latest_lines() -> dict:
    data = client.get("/api/refills/latest?location_id=1").json()
    return {l["slot_no"]: l for l in data["lines"]}


def test_seed_marks_c1_blocked():
    rows = {r["slot_no"]: r for r in client.get("/api/lanes").json()}
    assert rows["C1"]["blocked"] is True
    assert all(not r["blocked"] for s, r in rows.items() if s != "C1")


def test_seed_flow_latest_order_full_and_summary():
    # 种子把 C1 标封锁后：最新单 C1 补量为 0
    run = client.post("/api/refills/run?location_id=1").json()
    c1 = next(l for l in run["lines"] if l["slot_no"] == "C1")
    assert c1["fill_qty"] == 0
    assert c1["status"] == "blocked"
    assert c1["reason"] == "货道封锁"
    # 满仓页无 C1（即便它库存+在途等于容量也不得列入——此处验证互斥口径）
    full = client.get("/api/refills/full?location_id=1").json()["lanes"]
    full_slots = [l["slot_no"] for l in full]
    assert "C1" not in full_slots
    assert set(full_slots) == {"A2", "B2"}
    # 汇总待补不含 C1
    s = client.get("/api/refills/summary?location_id=1").json()
    assert s["need_fill_count"] == 2  # A1、B1
    assert s["blocked_count"] == 1
    assert s["total_fill"] == 22  # 15 + 7


def test_block_save_updates_flag_and_latest_order_together():
    order = client.post("/api/refills/run?location_id=1").json()
    a1 = lane_id_by_slot("A1")
    resp = client.patch(f"/api/lanes/{a1}/blocked", json={"blocked": True})
    assert resp.status_code == 200
    assert resp.json()["blocked"] is True
    # 同一次提交里当前有效单被整单重算：A1 补量改 0，其余行不变
    latest = client.get("/api/refills/latest?location_id=1").json()
    assert latest["id"] == order["id"]
    lines = {l["slot_no"]: l for l in latest["lines"]}
    assert lines["A1"]["fill_qty"] == 0
    assert lines["A1"]["status"] == "blocked"
    assert lines["A1"]["reason"] == "货道封锁"
    assert lines["B1"]["fill_qty"] == 7
    assert latest["blocked_count"] == 2  # A1 + C1
    # 满仓列表同步：A1 不在其中（它本非满仓），口径一致
    full_slots = [l["slot_no"] for l in client.get("/api/refills/full?location_id=1").json()["lanes"]]
    assert "A1" not in full_slots


def test_unblock_restores_gap_logic():
    client.post("/api/refills/run?location_id=1")
    c1 = lane_id_by_slot("C1")
    resp = client.patch(f"/api/lanes/{c1}/blocked", json={"blocked": False})
    assert resp.status_code == 200
    lines = latest_lines()
    assert lines["C1"]["status"] == "need_fill"
    assert lines["C1"]["fill_qty"] == 10
    assert lines["C1"]["reason"] == "待补"


def test_earlier_orders_keep_original_text():
    first = client.post("/api/refills/run?location_id=1").json()
    second = client.post("/api/refills/run?location_id=1").json()
    db = TestingSessionLocal()
    try:
        before = db.get(RefillOrder, first["id"]).lines_json
    finally:
        db.close()
    a1 = lane_id_by_slot("A1")
    client.patch(f"/api/lanes/{a1}/blocked", json={"blocked": True})
    db = TestingSessionLocal()
    try:
        # 更早的单一字不改；最新单已按封锁规则重算
        assert db.get(RefillOrder, first["id"]).lines_json == before
        latest = json.loads(db.get(RefillOrder, second["id"]).lines_json)
    finally:
        db.close()
    a1_line = next(l for l in latest["lines"] if l["slot_no"] == "A1")
    assert a1_line["status"] == "blocked"
    assert a1_line["fill_qty"] == 0


def test_save_failure_rolls_back_flag_and_order(monkeypatch):
    order = client.post("/api/refills/run?location_id=1").json()
    a1 = lane_id_by_slot("A1")

    def boom(_lanes):
        raise RuntimeError("recompute exploded")

    monkeypatch.setattr("app.services.lane_service.build_fill_lines", boom)
    resp = client.patch(f"/api/lanes/{a1}/blocked", json={"blocked": True})
    assert resp.status_code == 500
    # 旗标回滚
    rows = {r["slot_no"]: r for r in client.get("/api/lanes").json()}
    assert rows["A1"]["blocked"] is False
    # 有效单回滚（整单文本与改前一致）
    latest = client.get("/api/refills/latest?location_id=1").json()
    assert latest["id"] == order["id"]
    assert latest["lines"] == order["lines"]
    db = TestingSessionLocal()
    try:
        assert db.get(Lane, a1).blocked is False
        assert json.loads(db.get(RefillOrder, order["id"]).lines_json)["lines"] == order["lines"]
    finally:
        db.close()


def test_block_unknown_lane_404():
    resp = client.patch("/api/lanes/9999/blocked", json={"blocked": True})
    assert resp.status_code == 404
