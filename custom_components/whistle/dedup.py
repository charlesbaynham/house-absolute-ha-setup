"""Groups one whistle heard by several nodes and picks the node that heard it loudest. No HA imports."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Detection:
    node: str
    event_type: str
    id: str
    t: float  # Unix time of the whistle per the node's SNTP clock; 0 if unsynced
    received: float  # monotonic arrival time
    level: float
    payload: dict


@dataclass
class Group:
    event_type: str
    detections: list[Detection] = field(default_factory=list)

    @property
    def nodes(self) -> set[str]:
        return {d.node for d in self.detections}

    def matches(self, d: Detection, match_s: float, collect_s: float) -> bool:
        first = self.detections[0]
        if d.event_type != self.event_type or d.node in self.nodes:
            return False
        if d.t and first.t:
            return abs(d.t - first.t) <= match_s
        return d.received - first.received <= collect_s


@dataclass(frozen=True)
class Verdict:
    event_type: str
    ranked: list[Detection]  # loudest first
    confident: bool

    @property
    def winner(self) -> Detection:
        return self.ranked[0]


class Grouper:
    def __init__(self, match_s: float, collect_s: float, confident_db: float):
        self.match_s, self.collect_s, self.confident_db = match_s, collect_s, confident_db
        self.open: list[Group] = []

    def add(self, d: Detection) -> tuple[Group, bool]:
        """Returns the group the detection joined and whether it is new."""
        for g in self.open:
            if g.matches(d, self.match_s, self.collect_s):
                g.detections.append(d)
                return g, False
        g = Group(d.event_type, [d])
        self.open.append(g)
        return g, True

    def close(self, g: Group) -> Verdict | None:
        """None if the group was already closed (early close, then its timer fires)."""
        if g not in self.open:
            return None
        self.open.remove(g)
        ranked = sorted(g.detections, key=lambda d: d.level, reverse=True)
        margin = ranked[0].level - ranked[1].level if len(ranked) > 1 else float("inf")
        return Verdict(g.event_type, ranked, margin >= self.confident_db)
