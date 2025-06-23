import io
import json
from app.managers.tariff_manager import (
    calculate_from_csv,
    calculate_usage_metrics,
    average_metrics,
    recommend_from_metrics,
)
import types

CSV_HEADER = "datetime,duration,unit,consumption,generation\n"


def make_file(rows: str):
    return io.StringIO(CSV_HEADER + rows)


def run_recommend_v2(rows: str, allow_switch: bool):
    """Helper that mimics the /v2/recommend endpoint."""
    csv_file = io.StringIO(CSV_HEADER + rows)
    metrics, _ = calculate_usage_metrics(csv_file, True)
    avg_metrics = average_metrics(metrics)
    months_order = (
        sorted(next(iter(avg_metrics.values()))["months"].keys())
        if avg_metrics
        else []
    )
    return recommend_from_metrics(avg_metrics, months_order, allow_switch)


def run_explain(rows: str, allow_switch: bool):
    """Helper that mimics the /explain endpoint."""
    csv_file = io.StringIO(CSV_HEADER + rows)
    metrics, _ = calculate_usage_metrics(csv_file, True)
    avg_metrics = average_metrics(metrics)
    months_order = (
        sorted(next(iter(avg_metrics.values()))["months"].keys()) if avg_metrics else []
    )
    result = recommend_from_metrics(avg_metrics, months_order, allow_switch)

    class DummyCC:
        @staticmethod
        def create(*args, **kwargs):
            return {"choices": [{"message": {"content": "Explanation"}}]}

    openai = types.SimpleNamespace(ChatCompletion=DummyCC)

    system_prompt = "prompt"
    user_message = json.dumps(result, indent=2)
    completion = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
    )
    explanation = completion["choices"][0]["message"]["content"]
    email = (
        "Dear Customer,\n\n"
        "Thank you for being a valued customer with us! Here is your tariff plan recommendations for the next year, split by month (if allowPlanSwitching):\n\n"
        f"{explanation}\n\n"
        "Thank you again!\n"
        "Sincerely, Light"
    )

    return email, result


def test_basic_no_switch():
    csv_file = make_file(
        "2023-01-01T01:00:00,3600,kWh,1,0\n"
        "2023-01-01T07:00:00,3600,kWh,1,0\n"
    )
    result = calculate_from_csv(csv_file, True, False)
    assert result["plan"] == "Tiered"
    assert result["cost"] == 20


def test_high_usage_tiered_more_expensive():
    csv_file = make_file("2023-01-01T01:00:00,3600,kWh,120,0\n")
    result = calculate_from_csv(csv_file, True, False)
    assert result["plan"] == "NightSaver"
    assert result["cost"] == 605


def test_switching_between_months():
    csv_file = make_file(
        "2023-01-01T01:00:00,3600,kWh,1,0\n"
        "2023-02-01T12:00:00,3600,kWh,1,0\n"
    )
    result = calculate_from_csv(csv_file, True, True)
    assert result["months"]["2023-01"]["plan"] == "NightSaver"
    assert result["months"]["2023-01"]["cost"] == 10
    assert result["months"]["2023-02"]["plan"] == "Tiered"
    assert result["months"]["2023-02"]["cost"] == 10


def test_generation_affects_cost():
    csv_file = make_file(
        "2023-01-01T01:00:00,3600,kWh,1,0\n"
        "2023-01-01T07:00:00,3600,kWh,1,1\n"
    )
    result_with_gen = calculate_from_csv(csv_file, True, False)
    assert result_with_gen["plan"] == "NightSaver"
    assert result_with_gen["cost"] == 10

    csv_file.seek(0)
    result_no_gen = calculate_from_csv(csv_file, False, False)
    assert result_no_gen["plan"] == "Tiered"
    assert result_no_gen["cost"] == 20

def test_generation_zero_usage_costs():
    csv_file = make_file(
        "2023-01-01T01:00:00,3600,kWh,1,2\n"
    )
    result = calculate_from_csv(csv_file, True, False)
    assert result["plan"] == "FlatRate"
    assert result["cost"] == 0


def test_wh_unit_conversion():
    csv_file = make_file(
        "2023-01-01T02:00:00,3600,Wh,1000,0\n"
    )
    result = calculate_from_csv(csv_file, True, False)
    assert result["plan"] == "NightSaver"
    assert result["cost"] == 10


def test_tiered_exact_threshold():
    csv_file = make_file(
        "2023-01-01T12:00:00,3600,kWh,100,0\n"
    )
    result = calculate_from_csv(csv_file, True, False)
    assert result["plan"] == "Tiered"
    assert result["cost"] == 1000


def test_invalid_unit():
    csv_file = make_file(
        "2023-01-01T12:00:00,3600,MWh,1,0\n"
    )
    try:
        calculate_from_csv(csv_file, True, False)
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_v2_endpoint_no_switch():
    rows = (
        "2023-01-01T01:00:00,3600,kWh,1,0\n"
        "2023-01-01T07:00:00,3600,kWh,1,0\n"
    )
    data = run_recommend_v2(rows, False)
    assert data["plan"] == "Tiered"
    assert data["cost"] == 20
    # breakdown entries should include descriptions
    flat_breakdown = data["metrics"]["FlatRate"]["months"]["01"]["breakdown"]
    assert all("description" in d for d in flat_breakdown.values())


def test_v2_average_usage():
    rows = (
        "2022-01-01T01:00:00,3600,kWh,1,0\n"
        "2023-01-01T01:00:00,3600,kWh,3,0\n"
    )
    data = run_recommend_v2(rows, False)
    assert data["plan"] == "NightSaver"
    assert data["cost"] == 15


def test_v2_switching_between_months():
    rows = (
        "2023-01-01T01:00:00,3600,kWh,1,0\n"
        "2023-02-01T12:00:00,3600,kWh,1,0\n"
    )
    data = run_recommend_v2(rows, True)
    assert data["months"]["01"]["plan"] == "NightSaver"
    assert data["months"]["01"]["cost"] == 10
    assert data["months"]["02"]["plan"] == "Tiered"
    assert data["months"]["02"]["cost"] == 10


def test_explain_email():
    rows = (
        "2023-01-01T01:00:00,3600,kWh,1,0\n"
    )
    email, analysis = run_explain(rows, False)
    assert "Dear Customer" in email
    assert "Explanation" in email
    assert analysis["plan"] == "NightSaver" or analysis["plan"] == "Tiered" or analysis["plan"] == "FlatRate"


def test_explain_average():
    rows = (
        "2022-01-01T01:00:00,3600,kWh,1,0\n"
        "2023-01-01T01:00:00,3600,kWh,3,0\n"
    )
    _, analysis = run_explain(rows, False)
    assert analysis["plan"] == "NightSaver"


