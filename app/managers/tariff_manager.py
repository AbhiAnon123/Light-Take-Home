import csv
from datetime import datetime
from typing import Any, Dict, List, Tuple, Iterable

from app.configs.tariffs import HourlyConfig, select_config, TARIFFS


def describe_config(cfg: HourlyConfig) -> str:
    """Return a human friendly description of a config."""
    if cfg.start is None and cfg.end is None:
        hour_desc = "All hours of the day"
    else:
        start = cfg.start if cfg.start is not None else 0
        end = cfg.end if cfg.end is not None else 24
        hour_desc = f"Hours {start}-{end}"

    if cfg.threshold:
        thr_desc = f"applied after {cfg.threshold} kWh"
    else:
        thr_desc = "applied from the first kWh"
    return f"{hour_desc}, {thr_desc}"


def iterate_rows(file_obj: Iterable[str]) -> Iterable[Dict[str, str]]:
    """Yield raw rows from the CSV stream."""
    reader = csv.DictReader(
        line.decode() if isinstance(line, bytes) else line for line in file_obj
    )
    for row in reader:
        yield row


def prepare_consumption(row: Dict[str, str], consider_generation: bool) -> Tuple[datetime, float]:
    """Parse a CSV row and return (datetime, consumption_kwh)."""
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

    return dt, cons


def charge_usage(
    consumption: float,
    hour: int,
    configs: List[HourlyConfig],
    usage_so_far: float,
    detail: Dict[str, Dict[str, Any]],
) -> Tuple[float, float]:
    """Apply consumption to a tariff plan returning new usage and added cost."""
    remaining = consumption
    added_cost = 0.0
    while remaining > 0:
        config = select_config(configs, hour, usage_so_far)
        higher = [c.threshold for c in configs if c.matches_hour(hour) and c.threshold > usage_so_far]
        next_threshold = min(higher) if higher else float("inf")
        portion = min(remaining, next_threshold - usage_so_far)
        cost = portion * config.cost
        usage_so_far += portion
        added_cost += cost
        key = f"h{config.start}_{config.end}_t{config.threshold}"
        entry = detail.setdefault(
            key,
            {"usage": 0.0, "cost": 0.0, "description": describe_config(config)},
        )
        entry["usage"] += portion
        entry["cost"] += cost
        remaining -= portion

    return usage_so_far, added_cost


def finalize_month(
    month: str,
    plan_names: Iterable[str],
    base_fees: Dict[str, float],
    metrics: Dict[str, Any],
    month_usage: Dict[str, float],
    month_cost: Dict[str, float],
    month_detail: Dict[str, Dict[str, Dict[str, Any]]],
    months_order: List[str],
) -> None:
    """Finalize metrics for a month and reset temp counters."""
    for plan_name in plan_names:
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


def calculate_usage_metrics(
    file_obj, consider_generation: bool
) -> Tuple[Dict[str, Any], List[str]]:
    """Return raw monthly metrics for each plan without selecting a winner."""
    configs_by_plan = {
        p["name"]: [HourlyConfig(c) for c in p.get("hourlyConfigs", [])] for p in TARIFFS
    }
    base_fees = {p["name"]: p.get("baseFee", 0.0) for p in TARIFFS}
    metrics: Dict[str, Any] = {p["name"]: {"months": {}, "total_cost": 0.0} for p in TARIFFS}
    month_usage = {p["name"]: 0.0 for p in TARIFFS}
    month_cost = {p["name"]: 0.0 for p in TARIFFS}
    month_detail: Dict[str, Dict[str, Dict[str, Any]]] = {p["name"]: {} for p in TARIFFS}

    current_month: str | None = None
    months_order: List[str] = []

    for raw_row in iterate_rows(file_obj):
        dt, cons = prepare_consumption(raw_row, consider_generation)
        month = dt.strftime("%Y-%m")
        if current_month is None:
            current_month = month
        elif month != current_month:
            finalize_month(
                current_month,
                configs_by_plan.keys(),
                base_fees,
                metrics,
                month_usage,
                month_cost,
                month_detail,
                months_order,
            )
            current_month = month

        hour = dt.hour
        for plan_name, configs in configs_by_plan.items():
            usage_so_far = month_usage[plan_name]
            new_usage, added_cost = charge_usage(
                cons, hour, configs, usage_so_far, month_detail[plan_name]
            )
            month_usage[plan_name] = new_usage
            month_cost[plan_name] += added_cost

    if current_month is not None:
        finalize_month(
            current_month,
            configs_by_plan.keys(),
            base_fees,
            metrics,
            month_usage,
            month_cost,
            month_detail,
            months_order,
        )

    return metrics, months_order


def recommend_from_metrics(
    metrics: Dict[str, Any],
    months_order: List[str],
    allow_switch: bool,
) -> Dict[str, Any]:
    """Return recommendation result given metrics."""
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

    result["metrics"] = metrics
    return result


def average_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Average monthly metrics across years for forecasting."""
    averaged: Dict[str, Any] = {}
    for plan, data in metrics.items():
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for month, values in data["months"].items():
            mm = month[5:]
            grouped.setdefault(mm, []).append(values)

        averaged[plan] = {"months": {}, "total_cost": 0.0}
        for mm, vals in grouped.items():
            count = len(vals)
            cost = sum(v["cost"] for v in vals) / count
            usage = sum(v["usage"] for v in vals) / count
            breakdown: Dict[str, Dict[str, Any]] = {}
            for v in vals:
                for k, d in v["breakdown"].items():
                    bd = breakdown.setdefault(k, {
                        "usage": 0.0,
                        "cost": 0.0,
                        "description": d.get("description"),
                    })
                    bd["usage"] += d["usage"]
                    bd["cost"] += d["cost"]
            for d in breakdown.values():
                d["usage"] /= count
                d["cost"] /= count

            averaged[plan]["months"][mm] = {
                "cost": cost,
                "usage": usage,
                "breakdown": breakdown,
            }
            averaged[plan]["total_cost"] += cost
    return averaged



def calculate_from_csv(file_obj, consider_generation: bool, allow_switch: bool) -> Dict[str, Any]:
    """Process uploaded CSV stream month by month without loading entire file."""
    metrics, months_order = calculate_usage_metrics(file_obj, consider_generation)
    return recommend_from_metrics(metrics, months_order, allow_switch)
