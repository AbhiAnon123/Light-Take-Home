import json
import os
from typing import Any, Dict, List

class HourlyConfig:
    def __init__(self, data: Dict[str, Any]):
        self.start = data.get("startHour")
        self.end = data.get("endHour")
        self.threshold = data.get("billedAfterUsage") or 0.0
        self.cost = data["cost"]

    def matches_hour(self, hour: int) -> bool:
        if self.start is None and self.end is None:
            return True
        start = self.start or 0
        end = self.end or 24
        return start <= hour < end


def select_config(configs: List[HourlyConfig], hour: int, usage: float) -> HourlyConfig:
    """Select the config that applies for the given hour and cumulative usage."""
    applicable = [c for c in configs if c.matches_hour(hour) and usage >= c.threshold]
    if not applicable:
        applicable = [c for c in configs if c.matches_hour(hour)]
    if not applicable:
        raise ValueError("No tariff config applies to hour")
    return max(applicable, key=lambda c: c.threshold)


def load_tariffs(path: str = "tariffs.json") -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Tariff config {path} not found")
    with open(path, "r") as f:
        return json.load(f)


TARIFFS: List[Dict[str, Any]] = load_tariffs()
