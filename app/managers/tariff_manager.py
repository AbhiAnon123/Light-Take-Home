import csv
from datetime import datetime
from typing import Any, Dict, List

from app.configs.tariffs import HourlyConfig, select_config, TARIFFS

def calculate_from_csv(file_obj, consider_generation: bool, allow_switch: bool) -> Dict[str, Any]:
    """Process uploaded CSV stream month by month without loading entire file."""
    reader = csv.DictReader(line.decode() if isinstance(line, bytes) else line for line in file_obj)

    configs_by_plan = {p["name"]: [HourlyConfig(c) for c in p.get("hourlyConfigs", [])] for p in TARIFFS}
    base_fees = {p["name"]: p.get("baseFee", 0.0) for p in TARIFFS}
    metrics: Dict[str, Any] = {p["name"]: {"months": {}, "total_cost": 0.0} for p in TARIFFS}

    month_usage = {p["name"]: 0.0 for p in TARIFFS}
    month_cost = {p["name"]: 0.0 for p in TARIFFS}
    month_detail: Dict[str, Dict[str, Dict[str, float]]] = {p["name"]: {} for p in TARIFFS}

    current_month: str | None = None
    months_order: List[str] = []

    def finalize_month(month: str) -> None:
        for plan_name in configs_by_plan:
            month_cost[plan_name] += base_fees[plan_name]
            metrics[plan_name]["months"][month] = {
                "cost": month_cost[plan_name],
                "usage": month_usage[plan_name],
                "breakdown": month_detail[plan_name],
            }
            metrics[plan_name]["total_cost"] += month_cost[plan_name]
            month_usage[plan_name] = 0.0
            month_cost[plan_name] = 0.0
            month_detail[plan_name] = {}
        months_order.append(month)

    for row in reader:
        dt = datetime.fromisoformat(row["datetime"])
        unit = row["unit"].lower()
        cons = float(row["consumption"])
        gen = float(row.get("generation", 0))
        if consider_generation:
            cons -= gen
            if cons < 0:
                cons = 0.0
        if unit == "wh":
            cons /= 1000.0
        elif unit != "kwh":
            raise ValueError(f"Unsupported unit {unit}")

        month = dt.strftime("%Y-%m")
        if current_month is None:
            current_month = month
        elif month != current_month:
            finalize_month(current_month)
            current_month = month

        hour = dt.hour
        for plan_name, configs in configs_by_plan.items():
            usage_so_far = month_usage[plan_name]
            remaining = cons
            while remaining > 0:
                config = select_config(configs, hour, usage_so_far)
                higher = [c.threshold for c in configs if c.matches_hour(hour) and c.threshold > usage_so_far]
                next_threshold = min(higher) if higher else float("inf")
                portion = min(remaining, next_threshold - usage_so_far)
                cost = portion * config.cost
                month_usage[plan_name] = usage_so_far + portion
                usage_so_far = month_usage[plan_name]
                month_cost[plan_name] += cost
                key = f"h{config.start}_{config.end}_t{config.threshold}"
                detail = month_detail[plan_name].setdefault(key, {"usage": 0.0, "cost": 0.0})
                detail["usage"] += portion
                detail["cost"] += cost
                remaining -= portion

    if current_month is not None:
        finalize_month(current_month)

    result: Dict[str, Any] = {}
    if allow_switch:
        result["months"] = {}
        for m in months_order:
            best_plan, best_cost = None, float("inf")
            for plan_name, data in metrics.items():
                cost = data["months"][m]["cost"]
                if cost < best_cost:
                    best_cost = cost
                    best_plan = plan_name
            result["months"][m] = {"plan": best_plan, "cost": best_cost}
    else:
        best_plan = min(metrics.items(), key=lambda kv: kv[1]["total_cost"])[0]
        result["plan"] = best_plan
        result["cost"] = metrics[best_plan]["total_cost"]

    # include metrics for further analysis or explanation
    result["metrics"] = metrics
    return result
