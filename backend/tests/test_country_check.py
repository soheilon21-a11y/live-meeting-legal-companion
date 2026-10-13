from app.services import country_check


def test_de_returns_entry():
    entry = country_check.get_country("DE")
    assert entry["source"] == "§ 201 StGB (Germany)"
    assert "summary_en" in entry
    assert "summary_de" in entry
    assert entry["confidence"] in {"high", "medium", "low"}


def test_known_countries_return_entries():
    for code in ["DE", "AT", "CH", "US", "UK"]:
        entry = country_check.get_country(code)
        assert entry["confidence"] in {"high", "medium", "low"}
        assert entry["summary_en"]
        assert entry["summary_de"]


def test_unknown_country_returns_fallback():
    entry = country_check.get_country("XX")
    assert entry["source"] == "unverified"
    assert entry["confidence"] == "low"
    assert "consult a local legal professional" in entry["summary_en"].lower()


def test_lowercase_code_normalized():
    assert country_check.get_country("de")["source"] == "§ 201 StGB (Germany)"
