from app.services.fill_engine import build_fill_lines, compute_gap, summarize

def test_gap_basic():
    assert compute_gap(20, 5, 0) == 15
    assert compute_gap(20, 10, 5) == 5

def test_no_negative_fill():
    lanes = [{"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 10, "stock": 12, "in_transit": 0}]
    lines = build_fill_lines(lanes)
    assert lines[0].fill_qty == 0
    assert lines[0].status == "overbooked"

def test_cap_by_gap():
    lanes = [{"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 20, "stock": 5, "in_transit": 0}]
    lines = build_fill_lines(lanes, requested={1: 100})
    assert lines[0].fill_qty == 15
    assert lines[0].gap == 15

def test_full_zero_fill():
    lanes = [{"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 10, "stock": 8, "in_transit": 2}]
    s = summarize(build_fill_lines(lanes))
    assert s["full_count"] == 1
    assert s["total_fill"] == 0

def test_blocked_fill_zero_with_gap():
    lanes = [{"id": 1, "slot_no": "C1", "sku_name": "棒", "capacity": 10, "stock": 0, "in_transit": 0, "blocked": True}]
    lines = build_fill_lines(lanes)
    assert lines[0].fill_qty == 0
    assert lines[0].status == "blocked"
    assert lines[0].blocked is True
    assert lines[0].reason == "货道封锁"

def test_blocked_reason_not_combined():
    # 封锁补 0 的原因只写货道封锁，不与已满仓、超占并句
    lanes = [
        {"id": 1, "slot_no": "C1", "sku_name": "棒", "capacity": 10, "stock": 10, "in_transit": 0, "blocked": True},
        {"id": 2, "slot_no": "C2", "sku_name": "糖", "capacity": 10, "stock": 12, "in_transit": 0, "blocked": True},
    ]
    lines = build_fill_lines(lanes)
    for l in lines:
        assert l.reason == "货道封锁"
        assert "满仓" not in l.reason and "超占" not in l.reason

def test_blocked_full_mutually_exclusive():
    # 库存+在途=容量 的封锁道不得计入满仓
    lanes = [
        {"id": 1, "slot_no": "A2", "sku_name": "可乐", "capacity": 18, "stock": 18, "in_transit": 0, "blocked": True},
        {"id": 2, "slot_no": "B2", "sku_name": "巧", "capacity": 15, "stock": 10, "in_transit": 5},
    ]
    s = summarize(build_fill_lines(lanes))
    assert s["full_count"] == 1
    assert s["blocked_count"] == 1
    full_ids = [l["lane_id"] for l in s["lines"] if l["status"] == "full"]
    assert full_ids == [2]

def test_unblocked_keeps_gap_logic():
    lanes = [{"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 20, "stock": 5, "in_transit": 0, "blocked": False}]
    lines = build_fill_lines(lanes)
    assert lines[0].status == "need_fill"
    assert lines[0].fill_qty == 15
    assert lines[0].reason == "待补"
