import io
from app.managers.tariff_manager import calculate_from_csv

CSV_HEADER = "datetime,duration,unit,consumption,generation\n"


def make_file(rows: str):
    return io.StringIO(CSV_HEADER + rows)


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
