from lives_on_air.analysis.export_spreadsheet_semantic_map import duration_minutes_from_row


def test_duration_minutes_prefers_existing_minutes():
    assert duration_minutes_from_row({"duration_minutes": "46.4", "duration_seconds": "2644"}) == 46.4


def test_duration_minutes_converts_seconds_when_minutes_missing():
    assert duration_minutes_from_row({"duration_minutes": "", "duration_seconds": "2644"}) == 2644 / 60


def test_duration_minutes_parses_legacy_minute_second_value():
    assert duration_minutes_from_row({"duration": "46'24"}) == 46.4


def test_duration_minutes_treats_large_numeric_duration_as_seconds():
    assert duration_minutes_from_row({"duration": "2644.0"}) == 2644 / 60
