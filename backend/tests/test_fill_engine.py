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

def test_blocked_lane_fill_zero_and_status():
    lanes = [{"id": 1, "slot_no": "C1", "sku_name": "能量棒", "capacity": 10, "stock": 0, "in_transit": 0, "blocked": True}]
    lines = build_fill_lines(lanes)
    assert lines[0].fill_qty == 0
    assert lines[0].status == "blocked"
    assert lines[0].blocked is True

def test_blocked_excludes_full_even_at_capacity():
    # 封锁与满仓互斥：库存+在途=容量也不得记为满仓
    lanes = [{"id": 1, "slot_no": "C1", "sku_name": "能量棒", "capacity": 10, "stock": 10, "in_transit": 0, "blocked": True}]
    lines = build_fill_lines(lanes)
    assert lines[0].status == "blocked"
    s = summarize(lines)
    assert s["full_count"] == 0
    assert s["blocked_count"] == 1

def test_blocked_excludes_overbooked():
    lanes = [{"id": 1, "slot_no": "C1", "sku_name": "能量棒", "capacity": 10, "stock": 12, "in_transit": 0, "blocked": True}]
    lines = build_fill_lines(lanes)
    assert lines[0].status == "blocked"
    s = summarize(lines)
    assert s["overbooked_count"] == 0
    assert s["blocked_count"] == 1

def test_blocked_not_counted_as_need_fill():
    lanes = [
        {"id": 1, "slot_no": "A1", "sku_name": "水", "capacity": 10, "stock": 5, "in_transit": 0, "blocked": False},
        {"id": 2, "slot_no": "C1", "sku_name": "能量棒", "capacity": 10, "stock": 0, "in_transit": 0, "blocked": True},
    ]
    s = summarize(build_fill_lines(lanes))
    assert s["need_fill_count"] == 1
    assert s["total_fill"] == 5
    assert s["blocked_count"] == 1

def test_requested_ignored_for_blocked_lane():
    lanes = [{"id": 1, "slot_no": "C1", "sku_name": "能量棒", "capacity": 10, "stock": 0, "in_transit": 0, "blocked": True}]
    lines = build_fill_lines(lanes, requested={1: 7})
    assert lines[0].fill_qty == 0
    assert lines[0].status == "blocked"
