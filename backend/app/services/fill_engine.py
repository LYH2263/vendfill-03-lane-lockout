"""Vending refill: gap = capacity - stock - in_transit; fills capped by gap; no negative fills.

Blocked lanes (检修封锁): fill is always 0 and status is "blocked". Blocked is
mutually exclusive with full/overbooked — a blocked lane is never reported as
full even when stock + in_transit already equals capacity.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

@dataclass
class FillLine:
    lane_id: int
    slot_no: str
    sku_name: str
    capacity: int
    stock: int
    in_transit: int
    gap: int
    fill_qty: int
    status: str  # need_fill | full | overbooked | blocked
    blocked: bool = False

def compute_gap(capacity: int, stock: int, in_transit: int) -> int:
    return capacity - stock - in_transit

def build_fill_lines(lanes: list[dict], requested: dict[int, int] | None = None) -> list[FillLine]:
    """requested optional desired fill per lane_id; capped by gap; never negative.
    A lane with blocked=True is forced to fill 0 with status "blocked",
    regardless of its gap."""
    lines: list[FillLine] = []
    for lane in lanes:
        gap = compute_gap(int(lane["capacity"]), int(lane["stock"]), int(lane["in_transit"]))
        blocked = bool(lane.get("blocked", False))
        if blocked:
            status = "blocked"
            fill = 0
        elif gap < 0:
            status = "overbooked"
            fill = 0
        elif gap == 0:
            status = "full"
            fill = 0
        else:
            status = "need_fill"
            desire = gap if requested is None else int(requested.get(lane["id"], gap))
            fill = max(0, min(desire, gap))
        lines.append(FillLine(
            lane_id=lane["id"], slot_no=lane["slot_no"], sku_name=lane["sku_name"],
            capacity=lane["capacity"], stock=lane["stock"], in_transit=lane["in_transit"],
            gap=gap, fill_qty=fill, status=status, blocked=blocked,
        ))
    return lines

def summarize(lines: list[FillLine]) -> dict:
    return {
        "total_fill": sum(l.fill_qty for l in lines),
        "need_fill_count": sum(1 for l in lines if l.status == "need_fill"),
        "full_count": sum(1 for l in lines if l.status == "full"),
        "overbooked_count": sum(1 for l in lines if l.status == "overbooked"),
        "blocked_count": sum(1 for l in lines if l.status == "blocked"),
        "lines": [asdict(l) for l in lines],
    }
