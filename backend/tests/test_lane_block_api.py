"""Lane block (检修封锁) end-to-end rules:

- toggling the flag rewrites the current effective refill order in one commit;
- flag, effective order and full-lane list succeed/fail together (rollback on error);
- blocked lanes fill 0, never appear on the full page, never count as pending fill;
- older orders keep the text they were generated with.
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models.models import Lane, Location, RefillOrder, Sale
from app.services.seed import seed_if_empty


@pytest.fixture()
def client():
    with TestClient(app) as c:
        db = SessionLocal()
        try:
            for model in (Sale, RefillOrder, Lane, Location):
                db.query(model).delete()
            db.commit()
        finally:
            db.close()
        yield c


def _make_location(lanes_spec):
    """lanes_spec: list of (slot, sku, capacity, stock, in_transit, blocked)."""
    db = SessionLocal()
    try:
        loc = Location(code="T-01", name="测试点位", address="")
        db.add(loc)
        db.flush()
        lanes = []
        for slot, sku, cap, stock, transit, blocked in lanes_spec:
            lane = Lane(location_id=loc.id, slot_no=slot, sku_name=sku, capacity=cap,
                        stock=stock, in_transit=transit, blocked=blocked)
            db.add(lane)
            lanes.append(lane)
        db.commit()
        return loc.id, {l.slot_no: l.id for l in lanes}
    finally:
        db.close()


def _line(order_data, slot):
    return next(l for l in order_data["lines"] if l["slot_no"] == slot)


def test_block_save_rewrites_latest_order_in_one_commit(client):
    loc_id, ids = _make_location([
        ("A1", "矿泉水", 10, 5, 0, False),
        ("C1", "能量棒", 10, 0, 0, False),
    ])
    first = client.post(f"/api/refills/run?location_id={loc_id}").json()
    assert _line(first, "C1")["fill_qty"] == 10

    res = client.put(f"/api/lanes/{ids['C1']}", json={"blocked": True})
    assert res.status_code == 200
    body = res.json()
    assert body["blocked"] is True
    assert _line(body["order"], "C1")["fill_qty"] == 0
    assert _line(body["order"], "C1")["status"] == "blocked"
    assert _line(body["order"], "A1")["fill_qty"] == 5  # 未封锁道保持缺口逻辑

    latest = client.get(f"/api/refills/latest?location_id={loc_id}").json()
    assert latest["id"] == first["id"]  # 同一有效单被改写，而非另起新单
    assert _line(latest, "C1")["fill_qty"] == 0
    assert _line(latest, "C1")["status"] == "blocked"

    full = client.get(f"/api/refills/full?location_id={loc_id}").json()
    assert all(l["slot_no"] != "C1" for l in full["lanes"])

    summary = client.get(f"/api/refills/summary?location_id={loc_id}").json()
    assert summary["need_fill_count"] == 1  # 汇总待补不含 C1
    assert summary["blocked_count"] == 1
    assert summary["total_fill"] == 5

    lanes = {l["slot_no"]: l for l in client.get("/api/lanes").json()}
    assert lanes["C1"]["blocked"] is True


def test_blocked_lane_never_listed_as_full(client):
    # 即便库存+在途已等于容量，封锁道也不进满仓页
    loc_id, ids = _make_location([
        ("A2", "可乐", 10, 10, 0, False),
        ("C1", "能量棒", 10, 10, 0, False),
    ])
    client.post(f"/api/refills/run?location_id={loc_id}")
    res = client.put(f"/api/lanes/{ids['C1']}", json={"blocked": True})
    assert res.status_code == 200

    full = client.get(f"/api/refills/full?location_id={loc_id}").json()
    slots = [l["slot_no"] for l in full["lanes"]]
    assert "A2" in slots
    assert "C1" not in slots

    latest = client.get(f"/api/refills/latest?location_id={loc_id}").json()
    assert _line(latest, "C1")["status"] == "blocked"
    assert _line(latest, "C1")["fill_qty"] == 0


def test_failed_save_rolls_back_flag_and_order(client, monkeypatch):
    loc_id, ids = _make_location([("A1", "矿泉水", 10, 5, 0, False)])
    before = client.post(f"/api/refills/run?location_id={loc_id}").json()
    assert _line(before, "A1")["fill_qty"] == 5

    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated recompute failure")

    monkeypatch.setattr("app.api.lanes.compute_summary", boom)
    res = client.put(f"/api/lanes/{ids['A1']}", json={"blocked": True})
    assert res.status_code == 500

    lanes = client.get("/api/lanes").json()
    assert lanes[0]["blocked"] is False  # 旗标回滚

    latest = client.get(f"/api/refills/latest?location_id={loc_id}").json()
    assert latest["id"] == before["id"]
    assert _line(latest, "A1")["fill_qty"] == 5  # 有效单一起回滚
    assert _line(latest, "A1")["status"] == "need_fill"


def test_older_orders_keep_their_original_text(client):
    loc_id, ids = _make_location([("A1", "矿泉水", 10, 5, 0, False)])
    first = client.post(f"/api/refills/run?location_id={loc_id}").json()
    second = client.post(f"/api/refills/run?location_id={loc_id}").json()
    assert second["id"] != first["id"]

    db = SessionLocal()
    try:
        original_text = db.get(RefillOrder, first["id"]).lines_json
    finally:
        db.close()

    res = client.put(f"/api/lanes/{ids['A1']}", json={"blocked": True})
    assert res.status_code == 200

    db = SessionLocal()
    try:
        old = db.get(RefillOrder, first["id"])
        assert old.lines_json == original_text  # 旧单文本保持生成当时样子，一字不改
        old_line = next(l for l in json.loads(old.lines_json)["lines"] if l["slot_no"] == "A1")
        assert old_line["fill_qty"] == 5
        assert old_line["status"] == "need_fill"

        current = db.get(RefillOrder, second["id"])
        cur_line = next(l for l in json.loads(current.lines_json)["lines"] if l["slot_no"] == "A1")
        assert cur_line["fill_qty"] == 0
        assert cur_line["status"] == "blocked"
    finally:
        db.close()


def test_unblock_restores_gap_fill(client):
    loc_id, ids = _make_location([("C1", "能量棒", 10, 0, 0, True)])
    client.post(f"/api/refills/run?location_id={loc_id}")
    res = client.put(f"/api/lanes/{ids['C1']}", json={"blocked": False})
    assert res.status_code == 200
    line = _line(res.json()["order"], "C1")
    assert line["fill_qty"] == 10
    assert line["status"] == "need_fill"

    summary = client.get(f"/api/refills/summary?location_id={loc_id}").json()
    assert summary["blocked_count"] == 0
    assert summary["total_fill"] == 10


def test_seed_marks_c1_blocked_and_latest_order_fill_zero(client):
    db = SessionLocal()
    try:
        seed_if_empty(db)
        c1 = db.scalars(select(Lane).where(Lane.slot_no == "C1")).one()
        loc_id = c1.location_id
        assert c1.blocked is True
    finally:
        db.close()

    latest = client.get(f"/api/refills/latest?location_id={loc_id}").json()
    c1_line = _line(latest, "C1")
    assert c1_line["fill_qty"] == 0
    assert c1_line["status"] == "blocked"

    full = client.get(f"/api/refills/full?location_id={loc_id}").json()
    assert all(l["slot_no"] != "C1" for l in full["lanes"])

    summary = client.get(f"/api/refills/summary?location_id={loc_id}").json()
    # 种子口径：A1 缺 15、B1 缺 7；C1 封锁不计入待补
    assert summary["total_fill"] == 22
    assert summary["need_fill_count"] == 2
    assert summary["blocked_count"] == 1
