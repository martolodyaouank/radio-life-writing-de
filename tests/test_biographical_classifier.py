from lives_on_air.classification.biographical import biographical_label, biographical_score


def test_english_life_signal_is_possible():
    text = "A radio portrait of Dylan Thomas based on letters and memoirs."
    assert biographical_score(text) >= 2
    assert biographical_label(text) == "high_confidence_biographical"


def test_german_life_signal_is_possible():
    text = "Ein Hoerspiel ueber das Leben und die Briefe einer Schriftstellerin."
    assert biographical_score(text) >= 2
    assert biographical_label(text) == "high_confidence_biographical"


def test_unrelated_text_is_not_biographical():
    assert biographical_label("A science fiction radio play about a distant planet.") == "not_biographical"
